"""Lightweight in-memory vector store used for tests and demos."""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, List, Protocol, Tuple

from .models import Document, SearchHit

_TOKEN_PATTERN = re.compile(r"[\w']+")


class VectorStore(Protocol):
    """Protocol describing the retrieval operations expected by the pipeline."""

    def search(self, query: str, top_k: int) -> List[SearchHit]:
        """Return the top-k hits for the query."""


class InMemoryVectorStore:
    """Tiny vector store backed by pre-computed token frequency vectors.

    The goal is to provide a deterministic, dependency-free store that exercises
    the retrieval pipeline.  The implementation intentionally keeps the scoring
    simple (raw dot product without normalization) to create scenarios where the
    reranker can produce a different ordering.
    """

    def __init__(self, documents: Iterable[Document] | None = None) -> None:
        self._entries: List[Tuple[Document, Counter[str]]] = []
        if documents is not None:
            for doc in documents:
                self.add_document(doc)

    def add_document(self, document: Document) -> None:
        """Store the document and cache its token counts."""

        self._entries.append((document, self._vectorize(document.content)))

    def search(self, query: str, top_k: int) -> List[SearchHit]:
        vector = self._vectorize(query)
        scored: List[Tuple[float, Document]] = []
        for document, doc_vector in self._entries:
            score = self._dot(vector, doc_vector)
            scored.append((score, document))
        scored.sort(key=lambda item: item[0], reverse=True)
        hits: List[SearchHit] = []
        for rank, (score, document) in enumerate(scored[:top_k], start=1):
            hits.append(
                SearchHit(
                    document=document,
                    score=score,
                    rank=rank,
                    metadata={"score_source": "vector_store"},
                )
            )
        return hits

    @staticmethod
    def _vectorize(text: str) -> Counter[str]:
        tokens = _TOKEN_PATTERN.findall(text.lower())
        return Counter(tokens)

    @staticmethod
    def _dot(query: Counter[str], document: Counter[str]) -> float:
        if not query or not document:
            return 0.0
        return float(sum(query[token] * document[token] for token in query))


__all__ = ["VectorStore", "InMemoryVectorStore"]
