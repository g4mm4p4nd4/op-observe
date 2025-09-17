"""Detection of tools defined in agentic applications."""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .base import Finding, SourceWalker, format_location


_TOOL_DECORATOR_KEYWORDS = ("tool", "register_tool", "langchain.tool", "lc_tool")
_TOOL_CLASS_SUFFIXES = ("Tool", "BaseTool")
_TOOL_CALL_KEYWORDS = ("Tool", "StructuredTool", "PythonREPLTool", "BaseTool")


@dataclass
class ToolFinding(Finding):
    """Finding representing a tool definition."""

    definition_type: str = "tool"
    metadata: Dict[str, object] = field(default_factory=dict)


class ToolDetector(SourceWalker):
    """Detector that discovers tool definitions in Python source files."""

    def __init__(self) -> None:
        super().__init__(extensions=(".py",))

    def scan_paths(self, paths: Iterable[Path | str]) -> List[ToolFinding]:
        findings: List[ToolFinding] = []
        for path in self.iter_files(paths):
            findings.extend(self._scan_file(path))
        return findings

    def _scan_file(self, path: Path) -> List[ToolFinding]:
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            return []

        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return []

        visitor = _ToolAstVisitor(path)
        visitor.visit(tree)
        return visitor.findings


class _ToolAstVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self._path = path
        self.findings: List[ToolFinding] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # pragma: no cover - alias handled below
        self._maybe_add_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._maybe_add_function(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        bases = [_name_from_node(base) for base in node.bases]
        matches = [base for base in bases if _is_tool_class(base)]
        if matches:
            metadata = {
                "bases": bases,
            }
            finding = ToolFinding(
                detector="tool",
                name=node.name,
                location=format_location(self._path, getattr(node, "lineno", None)),
                definition_type="class",
                metadata=metadata,
            )
            self.findings.append(finding)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        self._maybe_add_assignment(node)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._maybe_add_assignment(node)
        self.generic_visit(node)

    def _maybe_add_function(self, node: ast.AST) -> None:
        decorator_names = [_name_from_node(dec) for dec in getattr(node, "decorator_list", [])]
        matches = [name for name in decorator_names if _is_tool_decorator(name)]
        if matches:
            metadata = {
                "decorators": decorator_names,
                "docstring": ast.get_docstring(node),
            }
            finding = ToolFinding(
                detector="tool",
                name=getattr(node, "name", "<anonymous>"),
                location=format_location(self._path, getattr(node, "lineno", None)),
                definition_type="function",
                metadata=metadata,
            )
            self.findings.append(finding)

    def _maybe_add_assignment(self, node: ast.Assign | ast.AnnAssign) -> None:
        value = getattr(node, "value", None)
        if not isinstance(value, ast.Call):
            return

        call_name = _name_from_node(value.func)
        if not _is_tool_call(call_name):
            return

        targets: List[str] = []
        raw_targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in raw_targets:
            if isinstance(target, ast.Name):
                targets.append(target.id)
            else:
                try:
                    targets.append(ast.unparse(target))  # type: ignore[attr-defined]
                except Exception:  # pragma: no cover - best effort for Python <3.9
                    continue

        metadata = {
            "call": call_name,
            "keywords": {kw.arg: _literal_from_node(kw.value) for kw in value.keywords if kw.arg},
        }
        finding = ToolFinding(
            detector="tool",
            name=", ".join(targets) if targets else call_name or "<unknown>",
            location=format_location(self._path, getattr(node, "lineno", None)),
            definition_type="assignment",
            metadata=metadata,
        )
        self.findings.append(finding)


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
    if isinstance(node, ast.Call):  # pragma: no cover - defensive path
        return _name_from_node(node.func)
    if hasattr(ast, "unparse"):
        try:
            return ast.unparse(node)  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - best effort
            return None
    return None


def _literal_from_node(node: ast.AST) -> object:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_literal_from_node(elt) for elt in node.elts]
    if isinstance(node, ast.Dict):
        return {
            _literal_from_node(key): _literal_from_node(value)
            for key, value in zip(node.keys, node.values)
        }
    return _name_from_node(node)


def _is_tool_decorator(name: Optional[str]) -> bool:
    if not name:
        return False
    lower = name.lower()
    return any(lower.endswith(keyword) or keyword in lower for keyword in _TOOL_DECORATOR_KEYWORDS)


def _is_tool_class(name: Optional[str]) -> bool:
    if not name:
        return False
    return any(name.endswith(suffix) for suffix in _TOOL_CLASS_SUFFIXES)


def _is_tool_call(name: Optional[str]) -> bool:
    if not name:
        return False
    base = name.split(".")[-1]
    if base in _TOOL_CALL_KEYWORDS:
        return True
    return base.lower().endswith("tool")
