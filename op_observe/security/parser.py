"""Static parser that extracts agent graphs from code and configs.

This module focuses on the *agentic-security* use case where we must
understand which agents, tools, and retrievers are wired together inside a
repository.  The parser relies on lightweight static analysis so that it can
operate inside CI systems without importing project code.

The parser currently supports the following frameworks:

* LangGraph – detects ``StateGraph`` builders, nodes, edges, and ``ToolNode``
  registrations.
* OpenAI Agents – inspects ``client.beta.agents/assistants.create`` calls and
  their tool declarations.
* CrewAI – captures ``Agent`` declarations, registered tools, and crew/task
  relationships.
* AutoGen – observes ``AssistantAgent``/``UserProxyAgent`` instances and
  ``@tool`` decorated callables.
* n8n – parses workflow JSON/YAML to produce graph nodes and data-flow edges.

The parser also scans for MCP (Model Context Protocol) endpoints inside code
and configurations.  The resulting :class:`AgentGraph` instance provides a
normalized set of nodes (agents, tools, retrievers) and edges (call/data
flows) that can be rendered in security reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import ast
import json
import re

try:  # pragma: no cover - optional dependency at runtime
    import yaml  # type: ignore
except Exception:  # pragma: no cover - we fall back to JSON parsing only
    yaml = None

MCP_PATTERN = re.compile(r"mcp[\w+\-:/.]*", re.IGNORECASE)


@dataclass
class AgentNode:
    """Represents an element inside an agent workflow graph."""

    id: str
    type: str  # ``agent``, ``tool``, or ``retriever``
    framework: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def update(self, framework: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Merge framework/metadata information for an existing node."""

        if framework and framework != self.framework:
            # Preserve the original framework but add provenance information.
            frameworks: Set[str] = set(self.metadata.get("frameworks", []))
            if self.framework:
                frameworks.add(self.framework)
            frameworks.add(framework)
            self.metadata["frameworks"] = sorted(frameworks)
        if metadata:
            for key, value in metadata.items():
                # Metadata values may not be hashable; store stringified fallbacks
                # to guarantee deterministic serialization.
                if value is None:
                    continue
                if isinstance(value, (str, int, float, bool)):
                    self.metadata[key] = value
                else:
                    self.metadata[key] = repr(value)


@dataclass(frozen=True)
class AgentEdge:
    """Directed relationship between two nodes."""

    source: str
    target: str
    kind: str  # ``call`` or ``data_flow``
    metadata: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)

    @classmethod
    def create(
        cls,
        source: str,
        target: str,
        kind: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "AgentEdge":
        serialized: Tuple[Tuple[str, str], ...] = tuple()
        if metadata:
            serialized = tuple(sorted((k, str(v)) for k, v in metadata.items()))
        return cls(source=source, target=target, kind=kind, metadata=serialized)


class AgentGraph:
    """Container for nodes, edges, and MCP endpoints."""

    def __init__(self) -> None:
        self.nodes: Dict[str, AgentNode] = {}
        self.edges: Set[AgentEdge] = set()
        self.mcp_endpoints: Dict[str, Set[str]] = {}

    # ------------------------------------------------------------------
    # Node/edge registration helpers
    # ------------------------------------------------------------------
    def add_node(
        self,
        node_id: str,
        node_type: str,
        *,
        framework: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentNode:
        if not node_id:
            raise ValueError("node_id must be non-empty")
        if node_id not in self.nodes:
            self.nodes[node_id] = AgentNode(id=node_id, type=node_type, framework=framework)
        node = self.nodes[node_id]
        if framework and not node.framework:
            node.framework = framework
        node.update(framework=framework, metadata=metadata)
        return node

    def add_edge(
        self,
        source: str,
        target: str,
        kind: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not source or not target:
            return
        edge = AgentEdge.create(source, target, kind, metadata)
        self.edges.add(edge)

    def add_mcp_endpoint(self, endpoint: str, *, source: str) -> None:
        endpoint = endpoint.strip()
        if not endpoint:
            return
        record = self.mcp_endpoints.setdefault(endpoint, set())
        record.add(source)

    # ------------------------------------------------------------------
    def as_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [
                {
                    "id": node.id,
                    "type": node.type,
                    "framework": node.framework,
                    "metadata": dict(sorted(node.metadata.items())),
                }
                for node in sorted(self.nodes.values(), key=lambda n: n.id)
            ],
            "edges": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "kind": edge.kind,
                    "metadata": dict(edge.metadata),
                }
                for edge in sorted(self.edges, key=lambda e: (e.source, e.target, e.kind))
            ],
            "mcp_endpoints": [
                {"endpoint": endpoint, "sources": sorted(list(sources))}
                for endpoint, sources in sorted(self.mcp_endpoints.items())
            ],
        }


class AgentGraphParser:
    """Entry point that walks a repository to construct an :class:`AgentGraph`."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    # ------------------------------------------------------------------
    def parse(self) -> AgentGraph:
        graph = AgentGraph()
        if self.root.is_file():
            self._parse_file(self.root, graph)
            return graph

        for path in sorted(self.root.rglob("*")):
            if path.is_file():
                self._parse_file(path, graph)
        return graph

    # ------------------------------------------------------------------
    def _parse_file(self, path: Path, graph: AgentGraph) -> None:
        suffix = path.suffix.lower()
        try:
            if suffix == ".py":
                analyzer = _PythonAgentAnalyzer(path, graph)
                analyzer.analyze()
            elif suffix in {".json", ".yaml", ".yml"}:
                self._parse_config_file(path, graph)
        except SyntaxError:
            # Ignore files with syntax errors – they are outside of the parser's
            # responsibilities but should not fail the entire scan.
            return

    # ------------------------------------------------------------------
    def _parse_config_file(self, path: Path, graph: AgentGraph) -> None:
        text = path.read_text(encoding="utf-8")
        data: Any
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            if yaml is None:
                return
            data = yaml.safe_load(text)
        if isinstance(data, dict) and {"nodes", "connections"} <= data.keys():
            self._parse_n8n_workflow(path, data, graph)
        # Always look for MCP references.
        self._scan_for_mcp(data, graph, source=str(path))

    # ------------------------------------------------------------------
    def _parse_n8n_workflow(self, path: Path, workflow: Dict[str, Any], graph: AgentGraph) -> None:
        nodes = workflow.get("nodes", [])
        if not isinstance(nodes, list):
            return
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("name") or node.get("id") or "")
            node_type_raw = str(node.get("type") or "")
            node_type = _classify_n8n_node(node_type_raw)
            metadata = {
                "file": str(path),
                "n8n_type": node_type_raw,
            }
            graph.add_node(node_id, node_type, framework="n8n", metadata=metadata)
            self._scan_for_mcp(node, graph, source=str(path))

        connections = workflow.get("connections", {})
        if not isinstance(connections, dict):
            return
        for source, mapping in connections.items():
            if not isinstance(mapping, dict):
                continue
            for conn_type, conn_entries in mapping.items():
                if not isinstance(conn_entries, list):
                    continue
                for entry in conn_entries:
                    if isinstance(entry, list):
                        iterator: Iterable[Any] = entry
                    else:
                        iterator = [entry]
                    for item in iterator:
                        if not isinstance(item, dict):
                            continue
                        target = item.get("node")
                        if target:
                            graph.add_edge(
                                str(source),
                                str(target),
                                "data_flow",
                                metadata={"framework": "n8n", "connection": conn_type},
                            )

    # ------------------------------------------------------------------
    def _scan_for_mcp(self, value: Any, graph: AgentGraph, *, source: str) -> None:
        if isinstance(value, str):
            if MCP_PATTERN.search(value):
                graph.add_mcp_endpoint(value, source=source)
            return
        if isinstance(value, dict):
            for key, inner in value.items():
                if isinstance(key, str) and "mcp" in key.lower():
                    if isinstance(inner, str):
                        graph.add_mcp_endpoint(inner, source=source)
                    else:
                        self._scan_for_mcp(inner, graph, source=source)
                else:
                    self._scan_for_mcp(inner, graph, source=source)
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                self._scan_for_mcp(item, graph, source=source)


# ----------------------------------------------------------------------
# Python analyzer
# ----------------------------------------------------------------------


class _PythonAgentAnalyzer(ast.NodeVisitor):
    """AST visitor that extracts graph information from Python code."""

    def __init__(self, path: Path, graph: AgentGraph) -> None:
        self.path = path
        self.graph = graph
        self.alias_map: Dict[str, str] = {}
        self.langgraph_builders: Set[str] = set()
        self.assign_context: List[str] = []
        self.current_function_defs: List[str] = []
        # Map variable names to the canonical node identifier created for the
        # referenced tool/agent.  This helps resolve patterns such as
        # ``search_tool = Tool(name="search")`` followed by
        # ``Agent(..., tools=[search_tool])``.
        self.object_aliases: Dict[str, str] = {}

    # ------------------------------------------------------------------
    def analyze(self) -> None:
        tree = ast.parse(self.path.read_text(encoding="utf-8"), filename=str(self.path))
        self.visit(tree)

    # ------------------------------------------------------------------
    # Import handling ---------------------------------------------------
    def visit_Import(self, node: ast.Import) -> Any:
        for alias in node.names:
            name = alias.asname or alias.name.split(".")[-1]
            self.alias_map[name] = alias.name
        return self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        module = node.module or ""
        for alias in node.names:
            if alias.name == "*":
                continue
            name = alias.asname or alias.name
            if module:
                self.alias_map[name] = f"{module}.{alias.name}"
            else:
                self.alias_map[name] = alias.name
        return self.generic_visit(node)

    # ------------------------------------------------------------------
    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self.current_function_defs.append(node.name)
        for decorator in node.decorator_list:
            deco_name = self._call_name(decorator)
            if not deco_name:
                continue
            resolved = self._resolve_symbol(deco_name.split(".")[-1])
            if resolved and _looks_like_tool_decorator(deco_name, resolved):
                metadata = {"file": str(self.path)}
                self.graph.add_node(node.name, "tool", framework="autogen", metadata=metadata)
        self.generic_visit(node)
        self.current_function_defs.pop()

    # ------------------------------------------------------------------
    def visit_Assign(self, node: ast.Assign) -> Any:
        targets = [self._target_name(target) for target in node.targets]
        targets = [t for t in targets if t]
        if isinstance(node.value, ast.Call):
            self._handle_call(node.value, targets)
        elif isinstance(node.value, (ast.List, ast.Dict, ast.Tuple)):
            self._scan_literal_for_mcp(node.value)
        elif isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            self._maybe_register_mcp(node.value.value)
        return self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr) -> Any:
        if isinstance(node.value, ast.Call):
            self._handle_call(node.value, [])
        elif isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str):
                self._maybe_register_mcp(node.value.value)
        return self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        # Raw call inside arguments; inspect for string literals (MCP hints)
        for arg in list(node.args) + [kw.value for kw in node.keywords]:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                self._maybe_register_mcp(arg.value)
        return self.generic_visit(node)

    # ------------------------------------------------------------------
    # Helpers -----------------------------------------------------------
    def _handle_call(self, call: ast.Call, assigned_to: Sequence[str]) -> None:
        call_name = self._call_name(call.func)
        if not call_name:
            return
        resolved_symbol = self._resolve_symbol(call_name.split(".")[-1])
        base_name = self._attribute_base_name(call.func)

        if _is_langgraph_builder(call_name, resolved_symbol):
            for target in assigned_to:
                if target:
                    self.langgraph_builders.add(target)
            return

        if base_name and base_name in self.langgraph_builders:
            self._handle_langgraph_call(call, base_name, assigned_to)
            return

        if _is_openai_agent_call(call_name):
            self._handle_openai_call(call, assigned_to)
            return

        if resolved_symbol and resolved_symbol.startswith("crewai") and resolved_symbol.endswith("Agent"):
            self._handle_crewai_agent(call, assigned_to)
            return

        if resolved_symbol and resolved_symbol.startswith("crewai") and resolved_symbol.endswith("Tool"):
            self._handle_crewai_tool(call, assigned_to)
            return

        if resolved_symbol and resolved_symbol.startswith("autogen") and resolved_symbol.endswith("Agent"):
            self._handle_autogen_agent(call, assigned_to)
            return

        if resolved_symbol and resolved_symbol.startswith("autogen") and resolved_symbol.endswith("Tool"):
            self._register_tool_from_call(call, assigned_to, framework="autogen")
            return

        if call_name.endswith("ToolNode") or (resolved_symbol and resolved_symbol.endswith("ToolNode")):
            self._register_tool_from_call(call, assigned_to, framework="langgraph")
            return

        if call_name.lower().endswith("tool") and not assigned_to:
            # Catch inline tool registration such as register_tool(...)
            tool_names = _extract_tool_names_from_args(call)
            for tool_name in tool_names:
                metadata = {"file": str(self.path)}
                self.graph.add_node(tool_name, "tool", framework=None, metadata=metadata)

    # ------------------------------------------------------------------
    def _handle_langgraph_call(self, call: ast.Call, base_name: str, assigned_to: Sequence[str]) -> None:
        attr = call.func.attr if isinstance(call.func, ast.Attribute) else ""
        metadata = {"file": str(self.path), "builder": base_name}
        if attr == "add_node":
            node_id = _extract_first_string(call.args, call.keywords)
            node_type = "agent"
            if call.args:
                first_arg = call.args[0]
                if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                    node_id = first_arg.value
            tool_hint = _detect_tool_from_call_args(call)
            if tool_hint:
                node_type = "tool"
                node_id = node_id or tool_hint
            elif assigned_to:
                node_id = node_id or assigned_to[0]
            if node_id:
                self.graph.add_node(node_id, node_type, framework="langgraph", metadata=metadata)
                if tool_hint and call.args:
                    agent_source = _extract_first_string(call.args[0:1], call.keywords)
                    if agent_source and agent_source != node_id:
                        self.graph.add_edge(agent_source, node_id, "call", metadata={"framework": "langgraph", "file": str(self.path)})
        elif attr in {"add_edge", "add_transition"}:
            args = call.args
            if len(args) >= 2:
                source = _literal_name(args[0])
                target = _literal_name(args[1])
                if source and target:
                    self.graph.add_edge(
                        source,
                        target,
                        "call",
                        metadata={"framework": "langgraph", "file": str(self.path)},
                    )
        elif attr in {"add_tool", "register_tool"}:
            tool_names = _extract_tool_names_from_args(call)
            owner = _extract_first_string(call.args[:1], call.keywords)
            for tool_name in tool_names:
                self.graph.add_node(tool_name, "tool", framework="langgraph", metadata=metadata)
                if owner:
                    self.graph.add_edge(owner, tool_name, "call", metadata={"framework": "langgraph", "file": str(self.path)})

    # ------------------------------------------------------------------
    def _handle_openai_call(self, call: ast.Call, assigned_to: Sequence[str]) -> None:
        metadata = {"file": str(self.path)}
        name = _get_keyword_string(call, "name")
        agent_id = name or (assigned_to[0] if assigned_to else "openai_agent")
        node = self.graph.add_node(agent_id, "agent", framework="openai", metadata=metadata)
        tools_kw = _get_keyword(call, "tools")
        for tool_name, tool_type in _parse_openai_tools(tools_kw):
            t_metadata = {"file": str(self.path), "source": "openai"}
            self.graph.add_node(tool_name, tool_type, framework="openai", metadata=t_metadata)
            self.graph.add_edge(agent_id, tool_name, "call", metadata={"framework": "openai", "file": str(self.path)})
        self._scan_arguments_for_mcp(call)

    def _handle_crewai_agent(self, call: ast.Call, assigned_to: Sequence[str]) -> None:
        metadata = {"file": str(self.path)}
        name = _get_keyword_string(call, "name")
        agent_id = name or (assigned_to[0] if assigned_to else "crewai_agent")
        self.graph.add_node(agent_id, "agent", framework="crewai", metadata=metadata)
        tools_kw = _get_keyword(call, "tools") or _get_keyword(call, "toolkit")
        tool_names = _extract_tool_names(tools_kw)
        for tool_name in tool_names:
            resolved_name = self.object_aliases.get(tool_name, tool_name)
            self.graph.add_edge(
                agent_id,
                resolved_name,
                "call",
                metadata={"framework": "crewai", "file": str(self.path)},
            )

    def _handle_crewai_tool(self, call: ast.Call, assigned_to: Sequence[str]) -> None:
        self._register_tool_from_call(call, assigned_to, framework="crewai")

    def _handle_autogen_agent(self, call: ast.Call, assigned_to: Sequence[str]) -> None:
        metadata = {"file": str(self.path)}
        name = _get_keyword_string(call, "name") or (assigned_to[0] if assigned_to else "autogen_agent")
        self.graph.add_node(name, "agent", framework="autogen", metadata=metadata)
        tools_kw = _get_keyword(call, "tools") or _get_keyword(call, "toolkits")
        for tool_name in _extract_tool_names(tools_kw):
            self.graph.add_edge(name, tool_name, "call", metadata={"framework": "autogen", "file": str(self.path)})
        self._scan_arguments_for_mcp(call)

    # ------------------------------------------------------------------
    def _register_tool_from_call(self, call: ast.Call, assigned_to: Sequence[str], *, framework: Optional[str]) -> None:
        metadata = {"file": str(self.path)}
        tool_name = _extract_first_string(call.args, call.keywords) or (assigned_to[0] if assigned_to else None)
        if tool_name:
            self.graph.add_node(tool_name, "tool", framework=framework, metadata=metadata)
            for target in assigned_to:
                if target:
                    self.object_aliases[target] = tool_name
        self._scan_arguments_for_mcp(call)

    def _scan_arguments_for_mcp(self, call: ast.Call) -> None:
        for arg in list(call.args) + [kw.value for kw in call.keywords]:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                self._maybe_register_mcp(arg.value)
            elif isinstance(arg, (ast.Dict, ast.List, ast.Tuple)):
                self._scan_literal_for_mcp(arg)

    def _scan_literal_for_mcp(self, node: ast.AST) -> None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            self._maybe_register_mcp(node.value)
            return
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            for element in node.elts:
                self._scan_literal_for_mcp(element)
            return
        if isinstance(node, ast.Dict):
            for value in node.values:
                if value is not None:
                    self._scan_literal_for_mcp(value)
            return

    # ------------------------------------------------------------------
    def _maybe_register_mcp(self, value: str) -> None:
        if MCP_PATTERN.search(value):
            self.graph.add_mcp_endpoint(value, source=str(self.path))

    # ------------------------------------------------------------------
    def _resolve_symbol(self, symbol: str) -> Optional[str]:
        return self.alias_map.get(symbol, self.alias_map.get(symbol.split(".")[0], symbol))

    def _call_name(self, node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = self._call_name(node.value)
            if base:
                return f"{base}.{node.attr}"
            return node.attr
        if isinstance(node, ast.Call):
            return self._call_name(node.func)
        return None

    def _attribute_base_name(self, node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            return node.value.id
        if isinstance(node, ast.Attribute):
            return self._attribute_base_name(node.value)
        return None

    def _target_name(self, node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return None


def _extract_tool_names(value: Optional[ast.AST]) -> List[str]:
    names: List[str] = []
    if isinstance(value, ast.List):
        for element in value.elts:
            names.extend(_extract_tool_names(element))
    elif isinstance(value, ast.Tuple):
        for element in value.elts:
            names.extend(_extract_tool_names(element))
    elif isinstance(value, ast.Name):
        names.append(value.id)
    elif isinstance(value, ast.Constant) and isinstance(value.value, str):
        names.append(value.value)
    elif isinstance(value, ast.Dict):
        maybe_name = None
        tool_type = None
        for key, val in zip(value.keys, value.values):
            if isinstance(key, ast.Constant):
                if key.value == "name" and isinstance(val, ast.Constant):
                    maybe_name = str(val.value)
                if key.value == "type" and isinstance(val, ast.Constant):
                    tool_type = str(val.value)
                if key.value == "function" and isinstance(val, ast.Dict):
                    for sub_key, sub_val in zip(val.keys, val.values):
                        if isinstance(sub_key, ast.Constant) and sub_key.value == "name" and isinstance(sub_val, ast.Constant):
                            maybe_name = str(sub_val.value)
        if maybe_name:
            names.append(maybe_name)
        elif tool_type:
            names.append(tool_type)
    return names


def _extract_tool_names_from_args(call: ast.Call) -> List[str]:
    names: List[str] = []
    for arg in call.args[1:]:
        names.extend(_extract_tool_names(arg))
    for kw in call.keywords:
        if kw.arg and kw.arg.lower() in {"tool", "tools", "node", "executor"}:
            names.extend(_extract_tool_names(kw.value))
    return names


def _extract_first_string(args: Sequence[ast.AST], keywords: Sequence[ast.keyword]) -> Optional[str]:
    for arg in args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
    for kw in keywords:
        if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
    return None


def _literal_name(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return node.id
    return None


def _get_keyword(call: ast.Call, name: str) -> Optional[ast.AST]:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _get_keyword_string(call: ast.Call, name: str) -> Optional[str]:
    kw = _get_keyword(call, name)
    if isinstance(kw, ast.Constant) and isinstance(kw.value, str):
        return kw.value
    return None


def _parse_openai_tools(value: Optional[ast.AST]) -> List[Tuple[str, str]]:
    tools: List[Tuple[str, str]] = []
    for tool_name in _extract_tool_names(value):
        tool_type = "tool"
        if tool_name.lower() in {"retrieval", "file_search", "vector_store"}:
            tool_type = "retriever"
        tools.append((tool_name, tool_type))
    return tools


def _is_openai_agent_call(call_name: str) -> bool:
    lowered = call_name.lower()
    return ".agents.create" in lowered or lowered.endswith("assistants.create")


def _is_langgraph_builder(call_name: str, resolved_symbol: Optional[str]) -> bool:
    if "StateGraph" in call_name:
        return True
    if resolved_symbol and "langgraph" in resolved_symbol and "Graph" in resolved_symbol.split(".")[-1]:
        return True
    return False


def _detect_tool_from_call_args(call: ast.Call) -> Optional[str]:
    for arg in call.args[1:]:
        if isinstance(arg, ast.Call):
            call_name = _call_name_static(arg.func)
            if call_name and call_name.endswith("ToolNode"):
                return _extract_first_string(arg.args, arg.keywords) or "tool"
        elif isinstance(arg, ast.Name):
            return arg.id
    for kw in call.keywords:
        if kw.arg and kw.arg.lower() in {"tool", "tools"}:
            extracted = _extract_tool_names(kw.value)
            if extracted:
                return extracted[0]
    return None


def _classify_n8n_node(node_type: str) -> str:
    lowered = node_type.lower()
    if "agent" in lowered or "workflow" in lowered:
        return "agent"
    if "retriever" in lowered or "vector" in lowered:
        return "retriever"
    return "tool"


def _looks_like_tool_decorator(name: str, resolved: str) -> bool:
    lowered = name.lower()
    return "tool" in lowered or "register_for" in lowered or resolved.endswith("tool")


def _call_name_static(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name_static(node.value)
        if base:
            return f"{base}.{node.attr}"
        return node.attr
    return None

