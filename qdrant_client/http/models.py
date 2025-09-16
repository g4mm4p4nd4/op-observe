"""Simplified models emulating qdrant-client data structures."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Sequence


class Distance(str, Enum):
    COSINE = "cosine"


@dataclass
class VectorParams:
    size: int
    distance: Distance = Distance.COSINE


@dataclass
class PointStruct:
    id: int
    vector: Sequence[float]
    payload: Dict[str, Any]


@dataclass
class ScoredPoint:
    id: int
    score: float
    payload: Dict[str, Any]


__all__ = ["Distance", "PointStruct", "VectorParams", "ScoredPoint"]
