"""Detection of Model Context Protocol (MCP) servers."""
from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .base import Finding, SourceWalker, format_location


_ENDPOINT_KEYS = {"uri", "url", "endpoint", "server", "server_url", "base_url", "address"}
_CAPABILITY_KEYS = {"capabilities", "tools", "permissions"}


@dataclass
class MCPServerFinding(Finding):
    """Finding capturing metadata about an MCP server or client."""

    endpoint: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class MCPServerDetector(SourceWalker):
    """Detector for discovering MCP servers in source code and configuration."""

    def __init__(self) -> None:
        super().__init__(extensions=(".py", ".json", ".yaml", ".yml"))

    def scan_paths(self, paths: Iterable[Path | str]) -> List[MCPServerFinding]:
        findings: List[MCPServerFinding] = []
        for path in self.iter_files(paths):
            findings.extend(self._scan_file(path))
        return findings

    def _scan_file(self, path: Path) -> List[MCPServerFinding]:
        suffix = path.suffix.lower()
        if suffix == ".py":
            return self._scan_python(path)
        if suffix in {".json", ".yaml", ".yml"}:
            return self._scan_config(path)
        return []

    def _scan_python(self, path: Path) -> List[MCPServerFinding]:
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            return []
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return []
        visitor = _McpAstVisitor(path)
        visitor.visit(tree)
        return visitor.findings

    def _scan_config(self, path: Path) -> List[MCPServerFinding]:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return []

        suffix = path.suffix.lower()
        data: Any
        if suffix == ".json":
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = None
        else:
            data = _safe_load_yaml(text)

        findings: List[MCPServerFinding] = []
        if data is not None:
            for entry in _find_mcp_in_mapping(data):
                findings.append(
                    MCPServerFinding(
                        detector="mcp",
                        name=entry.get("name") or entry.get("id") or "mcp_server",
                        endpoint=entry.get("endpoint"),
                        location=str(path),
                        metadata={k: v for k, v in entry.items() if k not in {"name", "endpoint"}},
                    )
                )
        else:
            findings.extend(_scan_text_for_mcp(text, path))
        return findings


class _McpAstVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self._path = path
        self.findings: List[MCPServerFinding] = []

    def visit_Call(self, node: ast.Call) -> Any:  # type: ignore[override]
        call_name = _name_from_node(node.func)
        if call_name and _looks_like_mcp(call_name):
            endpoint = _extract_endpoint(node)
            capabilities = _extract_capabilities(node)
            finding = MCPServerFinding(
                detector="mcp",
                name=call_name.split(".")[-1],
                endpoint=endpoint,
                location=format_location(self._path, getattr(node, "lineno", None)),
                metadata={
                    "call": call_name,
                    "capabilities": capabilities,
                },
            )
            self.findings.append(finding)
        self.generic_visit(node)


def _name_from_node(node: Optional[ast.AST]) -> Optional[str]:
    if node is None:
        return None
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _name_from_node(node.value)
        if parent:
            return f"{parent}.{node.attr}"
        return node.attr
    if hasattr(ast, "unparse"):
        try:
            return ast.unparse(node)  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - fallback
            return None
    return None


def _extract_endpoint(node: ast.Call) -> Optional[str]:
    for keyword in node.keywords:
        if keyword.arg and keyword.arg.lower() in _ENDPOINT_KEYS:
            value = keyword.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                return value.value
    if node.args:
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
    return None


def _extract_capabilities(node: ast.Call) -> List[str]:
    for keyword in node.keywords:
        if keyword.arg and keyword.arg.lower() in _CAPABILITY_KEYS:
            value = keyword.value
            if isinstance(value, (ast.List, ast.Tuple)):
                items = []
                for elt in value.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        items.append(elt.value)
                return items
    return []


def _looks_like_mcp(call_name: str) -> bool:
    lower = call_name.lower()
    return "mcp" in lower or "modelcontext" in lower or "model_context" in lower


def _safe_load_yaml(text: str) -> Any:
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except Exception:
        return None


def _find_mcp_in_mapping(node: Any, *, trail: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    trail = trail or []
    findings: List[Dict[str, Any]] = []

    if isinstance(node, dict):
        is_mcp = any("mcp" in str(key).lower() for key in node.keys())
        endpoint_key = next((key for key in node.keys() if str(key).lower() in _ENDPOINT_KEYS), None)
        endpoint = node.get(endpoint_key) if endpoint_key else None
        if is_mcp or endpoint:
            entry: Dict[str, Any] = {
                "name": node.get("name") or node.get("id") or ".".join(trail) if trail else "mcp",
                "endpoint": endpoint if isinstance(endpoint, str) else None,
            }
            for key in node.keys():
                value = node[key]
                if str(key).lower() in _CAPABILITY_KEYS and isinstance(value, list):
                    entry[str(key)] = value
            findings.append(entry)
        for key, value in node.items():
            findings.extend(_find_mcp_in_mapping(value, trail=trail + [str(key)]))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            findings.extend(_find_mcp_in_mapping(value, trail=trail + [str(index)]))
    return findings


def _scan_text_for_mcp(text: str, path: Path) -> List[MCPServerFinding]:
    findings: List[MCPServerFinding] = []
    pattern = re.compile(r"(?P<endpoint>(?:mcp|https?)://[^\s'\"]+)")
    for match in pattern.finditer(text):
        endpoint = match.group("endpoint")
        findings.append(
            MCPServerFinding(
                detector="mcp",
                name="mcp_endpoint",
                endpoint=endpoint,
                location=f"{path}:?",
                metadata={"extracted_from": "text"},
            )
        )
    return findings
