"""Interfaces and helpers for embedding providers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, List

from ..models import Vector


class BaseEmbedder(ABC):
    """Common interface implemented by embedding backends."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the dimensionality of vectors produced by the embedder."""

    @abstractmethod
    def embed(self, text: str) -> Vector:
        """Generate an embedding for the provided text."""

    def embed_batch(self, texts: Iterable[str]) -> List[Vector]:
        """Embed a batch of texts."""

        return [self.embed(text) for text in texts]


class CachedEmbedder(BaseEmbedder):
    """Decorator that adds LRU caching to another embedder."""

    def __init__(self, inner: BaseEmbedder, maxsize: int = 256):
        from ..utils import LRUCache

        self._inner = inner
        self._cache = LRUCache[List[float]](maxsize=maxsize)

    @property
    def dimension(self) -> int:
        return self._inner.dimension

    def embed(self, text: str) -> Vector:
        cached = self._cache.get(text)
        if cached is not None:
            return list(cached)
        vector = self._inner.embed(text)
        self._cache.put(text, list(vector))
        return vector

    def embed_batch(self, texts: Iterable[str]) -> List[Vector]:
        return [self.embed(text) for text in texts]
