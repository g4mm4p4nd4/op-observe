"""Minimal in-memory implementation of the Qdrant client APIs used in the demos."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence

from .http.models import Distance, PointStruct, ScoredPoint, VectorParams


class QdrantClient:
    """In-memory implementation suitable for unit tests."""

    def __init__(self, location: str | None = None) -> None:
        self.location = location or ":memory:"
        self._collections: Dict[str, Dict[str, Any]] = {}

    def recreate_collection(self, collection_name: str, vectors_config: VectorParams) -> None:
        self._collections[collection_name] = {
            "config": vectors_config,
            "points": [],
        }

    def upsert(self, collection_name: str, points: Iterable[PointStruct]) -> None:
        collection = self._collections.setdefault(collection_name, {"points": []})
        existing: Dict[int, PointStruct] = {point.id: point for point in collection["points"]}
        for point in points:
            existing[int(point.id)] = point
        collection["points"] = list(existing.values())

    def search(
        self,
        collection_name: str,
        query_vector: Sequence[float],
        limit: int = 10,
    ) -> List[ScoredPoint]:
        collection = self._collections.get(collection_name)
        if not collection:
            return []
        results: List[ScoredPoint] = []
        for point in collection["points"]:
            score = _cosine_similarity(query_vector, point.vector)
            results.append(ScoredPoint(id=point.id, score=score, payload=point.payload))
        results.sort(key=lambda item: item.score, reverse=True)
        return results[:limit]


def _cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    length = min(len(vec_a), len(vec_b))
    dot = sum(float(vec_a[i]) * float(vec_b[i]) for i in range(length))
    norm_a = sum(float(vec_a[i]) ** 2 for i in range(length)) ** 0.5 or 1.0
    norm_b = sum(float(vec_b[i]) ** 2 for i in range(length)) ** 0.5 or 1.0
    return round(dot / (norm_a * norm_b), 6)


__all__ = [
    "QdrantClient",
    "Distance",
    "VectorParams",
    "PointStruct",
    "ScoredPoint",
]
