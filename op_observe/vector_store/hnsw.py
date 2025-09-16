"""Lightweight HNSW-inspired index for unit testing."""
from __future__ import annotations

import heapq
from typing import Dict, List, Optional, Set, Tuple

from ..models import Vector
from ..utils import cosine_similarity


class HnswIndex:
    """A minimal HNSW-inspired graph index.

    The implementation focuses on deterministic behaviour suited for tests while
    still mimicking the greedy search behaviour of HNSW graphs.
    """

    def __init__(
        self,
        dim: int,
        m: int = 16,
        ef_search: int = 32,
    ) -> None:
        if dim <= 0:
            raise ValueError("dim must be positive")
        if m <= 0:
            raise ValueError("m must be positive")
        if ef_search <= 0:
            raise ValueError("ef_search must be positive")
        self.dim = dim
        self.m = m
        self.ef_search = max(ef_search, m)
        self._vectors: Dict[str, Vector] = {}
        self._graph: Dict[str, Set[str]] = {}
        self._entrypoint: Optional[str] = None

    def __len__(self) -> int:
        return len(self._vectors)

    def add_point(self, point_id: str, vector: Vector) -> None:
        if len(vector) != self.dim:
            raise ValueError("vector dimensionality mismatch")
        self._vectors[point_id] = list(vector)
        self._graph.setdefault(point_id, set())
        if self._entrypoint is None:
            self._entrypoint = point_id
            return
        neighbors = self._select_neighbors(point_id, vector)
        for neighbor_id in neighbors:
            self._graph[point_id].add(neighbor_id)
            self._graph.setdefault(neighbor_id, set()).add(point_id)
            self._trim(neighbor_id)
        self._trim(point_id)

    def update_point(self, point_id: str, vector: Vector) -> None:
        if point_id not in self._vectors:
            raise KeyError(point_id)
        if len(vector) != self.dim:
            raise ValueError("vector dimensionality mismatch")
        self._vectors[point_id] = list(vector)

    def _select_neighbors(self, point_id: str, vector: Vector) -> List[str]:
        scored: List[Tuple[float, str]] = []
        for other_id, other_vector in self._vectors.items():
            if other_id == point_id:
                continue
            score = cosine_similarity(vector, other_vector)
            scored.append((score, other_id))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [point for _, point in scored[: self.m]]

    def _trim(self, point_id: str) -> None:
        neighbors = self._graph.get(point_id)
        if not neighbors:
            return
        if len(neighbors) <= self.m:
            return
        vector = self._vectors[point_id]
        scored = [
            (cosine_similarity(vector, self._vectors[neighbor]), neighbor)
            for neighbor in neighbors
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        keep = {neighbor for _, neighbor in scored[: self.m]}
        self._graph[point_id] = keep

    def search(self, query: Vector, top_k: int) -> List[Tuple[str, float]]:
        if len(query) != self.dim:
            raise ValueError("vector dimensionality mismatch")
        if not self._vectors:
            return []
        entrypoint = self._entrypoint
        assert entrypoint is not None
        visited: Set[str] = set()
        candidate_heap: List[Tuple[float, str]] = []
        best_heap: List[Tuple[float, str]] = []
        entry_score = cosine_similarity(query, self._vectors[entrypoint])
        heapq.heappush(candidate_heap, (-entry_score, entrypoint))
        self._push(best_heap, (entry_score, entrypoint), self.ef_search)
        while candidate_heap and len(visited) < self.ef_search:
            score_neg, current = heapq.heappop(candidate_heap)
            score = -score_neg
            if current in visited:
                continue
            visited.add(current)
            current_vector = self._vectors[current]
            for neighbor in self._graph.get(current, set()) | {current}:
                if neighbor in visited:
                    continue
                neighbor_vector = self._vectors[neighbor]
                neighbor_score = cosine_similarity(query, neighbor_vector)
                heapq.heappush(candidate_heap, (-neighbor_score, neighbor))
                self._push(best_heap, (neighbor_score, neighbor), self.ef_search)
        best_heap.sort(key=lambda item: item[0], reverse=True)
        ordered = best_heap[:top_k]
        return [(point_id, score) for score, point_id in ordered]

    @staticmethod
    def _push(heap: List[Tuple[float, str]], item: Tuple[float, str], maxsize: int) -> None:
        if len(heap) < maxsize:
            heap.append(item)
            return
        heap.sort(key=lambda entry: entry[0])
        if item[0] > heap[0][0]:
            heap[0] = item
