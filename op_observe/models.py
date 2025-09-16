"""Common dataclasses used across the retrieval pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional


Vector = List[float]


@dataclass(slots=True)
class Document:
    """Container for ingested documents."""

    doc_id: str
    text: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_payload(self) -> Dict[str, Any]:
        """Return a mutable payload for storage in the vector index."""

        payload: Dict[str, Any] = dict(self.metadata)
        payload.setdefault("text", self.text)
        payload.setdefault("doc_id", self.doc_id)
        return payload


@dataclass(slots=True)
class VectorRecord:
    """Representation of a stored vector."""

    point_id: str
    vector: Vector
    payload: MutableMapping[str, Any]


@dataclass(slots=True)
class VectorMatch:
    """Result entry produced by vector store searches."""

    point_id: str
    score: float
    payload: Mapping[str, Any]
    vector: Vector


@dataclass(slots=True)
class SearchResult:
    """Pipeline-friendly search result."""

    doc_id: str
    score: float
    text: str
    metadata: Mapping[str, Any]


@dataclass(slots=True)
class QueryResponse:
    """Container for query responses."""

    results: List[SearchResult]
    latency_ms: float
    cached: bool
    used_reranker: bool


def ensure_vector(vector: Iterable[float]) -> Vector:
    """Normalize an iterable of floats to a list."""

    return [float(x) for x in vector]
