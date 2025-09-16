"""Lightweight retrieval agent for orchestrated RAG flows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Sequence


@dataclass(slots=True)
class Document:
    """Simple document container used for RAG responses."""

    id: str
    content: str
    metadata: dict[str, object] = field(default_factory=dict)


class RetrievalAgent:
    """A trivial lexical retrieval agent suitable for tests and demos."""

    def __init__(self, documents: Iterable[Document] | None = None) -> None:
        self._documents: List[Document] = list(documents or [])
        self._initialized = False

    def initialize(self) -> None:
        """Prepare in-memory indices for lexical search."""

        self._normalized_docs: List[tuple[Document, set[str]]] = [
            (doc, set(doc.content.lower().split())) for doc in self._documents
        ]
        self._initialized = True

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def add_documents(self, documents: Sequence[Document]) -> None:
        self._documents.extend(documents)
        if self._initialized:
            self.initialize()

    def search(self, query: str, *, top_k: int = 3) -> List[Document]:
        """Perform a naive lexical search over the documents."""

        if not self._initialized:
            raise RuntimeError("RetrievalAgent must be initialized before search")

        tokens = set(query.lower().split())
        scored: List[tuple[int, Document]] = []
        for doc, normalized in self._normalized_docs:
            score = sum(1 for token in tokens if token in normalized)
            if score:
                scored.append((score, doc))

        if not scored:
            return []

        scored.sort(key=lambda pair: pair[0], reverse=True)
        top_docs = [doc for _, doc in scored[:top_k]]
        return top_docs
