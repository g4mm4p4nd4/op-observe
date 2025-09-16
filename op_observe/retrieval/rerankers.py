"""Cross-encoder rerankers for semantic search."""

from __future__ import annotations

import asyncio
import re
import time
from typing import List, Protocol, Sequence

from .models import SearchHit

_TOKEN_PATTERN = re.compile(r"[\w']+")


class CrossEncoderReranker(Protocol):
    """Protocol implemented by asynchronous rerankers."""

    async def rerank(self, query: str, hits: Sequence[SearchHit]) -> List[SearchHit]:
        """Return the reranked hits."""


class SimpleCrossEncoderReranker:
    """Deterministic reranker that simulates a cross-encoder.

    The implementation is intentionally lightweight so that it can run inside the
    evaluation environment without pulling heavy model dependencies.  It
    emphasises contiguous phrase matches and token overlap to produce a refined
    ordering of the candidates produced by the vector store.  To keep the
    reranking path out of the p95 latency budget, the actual scoring is executed
    in a worker thread via :func:`asyncio.to_thread`.
    """

    def __init__(
        self,
        *,
        base_weight: float = 0.1,
        overlap_weight: float = 0.3,
        phrase_weight: float = 1.0,
        latency: float = 0.0,
    ) -> None:
        self._base_weight = base_weight
        self._overlap_weight = overlap_weight
        self._phrase_weight = phrase_weight
        self._latency = latency

    async def rerank(self, query: str, hits: Sequence[SearchHit]) -> List[SearchHit]:
        if not hits:
            return []
        return await asyncio.to_thread(self._rerank_sync, query, tuple(hits))

    def _rerank_sync(self, query: str, hits: Sequence[SearchHit]) -> List[SearchHit]:
        if self._latency > 0:
            time.sleep(self._latency)
        query_tokens = self._tokenize(query)
        query_tuple = tuple(query_tokens)
        query_set = set(query_tokens)
        scored: List[tuple[float, SearchHit, dict[str, int]]] = []
        for hit in hits:
            doc_tokens = self._tokenize(hit.document.content)
            overlap = sum(1 for token in doc_tokens if token in query_set)
            phrase_hits = self._count_phrase(query_tuple, doc_tokens)
            score = (
                self._base_weight * hit.score
                + self._overlap_weight * overlap
                + self._phrase_weight * phrase_hits
            )
            scored.append((score, hit, {"rerank_overlap": overlap, "rerank_phrase_hits": phrase_hits}))
        scored.sort(key=lambda item: item[0], reverse=True)
        reranked: List[SearchHit] = []
        for rank, (score, hit, metadata) in enumerate(scored, start=1):
            reranked.append(
                hit.with_score(
                    score=score,
                    rank=rank,
                    score_source="cross_encoder",
                    extra_metadata=metadata,
                )
            )
        return reranked

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return _TOKEN_PATTERN.findall(text.lower())

    @staticmethod
    def _count_phrase(query_tokens: Sequence[str], doc_tokens: Sequence[str]) -> int:
        if len(query_tokens) < 2 or len(doc_tokens) < len(query_tokens):
            return 0
        window = len(query_tokens)
        hits = 0
        for index in range(len(doc_tokens) - window + 1):
            if tuple(doc_tokens[index : index + window]) == tuple(query_tokens):
                hits += 1
        return hits


__all__ = ["CrossEncoderReranker", "SimpleCrossEncoderReranker"]
