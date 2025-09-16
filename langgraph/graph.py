"""Lightweight, self-contained graph runner inspired by LangGraph."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Deque, Dict, List, MutableMapping

START = "__start__"
END = "__end__"

StateFn = Callable[[MutableMapping[str, Any]], MutableMapping[str, Any]]


class StateGraph:
    """Simplified stand-in for LangGraph's StateGraph."""

    def __init__(self, state_type: Any) -> None:
        self.state_type = state_type
        self._nodes: Dict[str, StateFn] = {}
        self._edges: Dict[str, List[str]] = {START: []}

    def add_node(self, name: str, func: StateFn) -> None:
        self._nodes[name] = func
        self._edges.setdefault(name, [])

    def add_edge(self, source: str, target: str) -> None:
        if source not in self._edges:
            self._edges[source] = []
        self._edges[source].append(target)
        self._edges.setdefault(target, [])

    def compile(self) -> "CompiledGraph":
        return CompiledGraph(nodes=self._nodes, edges=self._edges)


@dataclass
class CompiledGraph:
    nodes: Dict[str, StateFn]
    edges: Dict[str, List[str]]

    def invoke(self, initial_state: MutableMapping[str, Any]) -> Dict[str, Any]:
        state: Dict[str, Any] = dict(initial_state)
        queue: Deque[str] = deque(self.edges.get(START, []))
        visited: Dict[str, int] = {}
        while queue:
            node_name = queue.popleft()
            if node_name == END:
                continue
            if node_name not in self.nodes:
                raise KeyError(f"Unknown node '{node_name}' in compiled graph")
            visited[node_name] = visited.get(node_name, 0) + 1
            if visited[node_name] > 10:
                raise RuntimeError(f"Node '{node_name}' executed too many times; check for cycles")
            result = self.nodes[node_name](state)
            if result:
                state.update(result)
            for target in self.edges.get(node_name, []):
                queue.append(target)
        return state


__all__ = ["StateGraph", "CompiledGraph", "START", "END"]
