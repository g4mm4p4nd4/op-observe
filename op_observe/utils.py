"""Utility helpers for vector operations and caches."""
from __future__ import annotations

import math
from collections import OrderedDict
from typing import Generic, Iterable, Tuple, TypeVar

from .models import Vector

T = TypeVar("T")


def dot_product(a: Vector, b: Vector) -> float:
    if len(a) != len(b):
        raise ValueError("Vectors must share the same dimensionality")
    return sum(x * y for x, y in zip(a, b))


def l2_norm(vector: Vector) -> float:
    return math.sqrt(sum(x * x for x in vector))


def cosine_similarity(a: Vector, b: Vector) -> float:
    denom = l2_norm(a) * l2_norm(b)
    if denom == 0:
        return 0.0
    return dot_product(a, b) / denom


def l2_distance(a: Vector, b: Vector) -> float:
    if len(a) != len(b):
        raise ValueError("Vectors must share the same dimensionality")
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


class LRUCache(OrderedDict[str, T], Generic[T]):
    """Minimal LRU cache for predictable behaviour in tests."""

    def __init__(self, maxsize: int):
        super().__init__()
        if maxsize <= 0:
            raise ValueError("maxsize must be positive")
        self.maxsize = maxsize

    def get(self, key: str) -> T | None:  # type: ignore[override]
        if key not in self:
            return None
        value = super().pop(key)
        super().__setitem__(key, value)
        return value

    def put(self, key: str, value: T) -> None:
        if key in self:
            super().pop(key)
        elif len(self) >= self.maxsize:
            self.popitem(last=False)
        super().__setitem__(key, value)


class TimedCache(LRUCache[Tuple[T, float]]):
    """LRU cache storing (value, latency) tuples."""

    pass
