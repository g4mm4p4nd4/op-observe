"""Reranking utilities."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, List

from .models import VectorMatch
from .utils import cosine_similarity


class BaseReranker(ABC):
    """Base interface for rerankers."""

    @abstractmethod
    def rerank(
        self,
        query: str,
        query_vector: Iterable[float],
        candidates: List[VectorMatch],
    ) -> List[VectorMatch]:
        """Return the reranked candidates."""


class DotProductReranker(BaseReranker):
    """Simple reranker that sorts by cosine similarity to the query vector."""

    def rerank(
        self,
        query: str,
        query_vector: Iterable[float],
        candidates: List[VectorMatch],
    ) -> List[VectorMatch]:
        query_vector_list = list(query_vector)
        scored = [
            (cosine_similarity(query_vector_list, match.vector), match)
            for match in candidates
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [match for _, match in scored]
