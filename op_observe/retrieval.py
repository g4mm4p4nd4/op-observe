"""Retrieval pipeline built around the Qdrant vector store."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable

from .embeddings.base import BaseEmbedder, CachedEmbedder
from .models import Document, QueryResponse, SearchResult, VectorMatch, VectorRecord
from .rerankers import BaseReranker
from .utils import LRUCache
from .vector_store.qdrant import QdrantVectorStore


@dataclass
class RetrievalConfig:
    collection_name: str = "documents"
    cache_size: int = 128
    latency_budget_ms: float = 200.0
    use_reranker: bool = False
    ef_search: int = 32


class RetrievalPipeline:
    """High-level orchestration of embeddings, ingestion, and search."""

    def __init__(
        self,
        embedder: BaseEmbedder,
        vector_store: QdrantVectorStore,
        reranker: BaseReranker | None = None,
        config: RetrievalConfig | None = None,
        cache_embeddings: bool = True,
    ) -> None:
        self._base_embedder = embedder
        self.embedder = CachedEmbedder(embedder) if cache_embeddings else embedder
        self.vector_store = vector_store
        self.reranker = reranker
        self.config = config or RetrievalConfig(collection_name=vector_store.collection_name)
        self._search_cache: LRUCache[QueryResponse] = LRUCache(self.config.cache_size)

    @property
    def dimension(self) -> int:
        return self.embedder.dimension

    def ingest_documents(self, documents: Iterable[Document]) -> None:
        records = []
        for document in documents:
            vector = self.embedder.embed(document.text)
            payload = document.as_payload()
            records.append(VectorRecord(document.doc_id, vector, payload))
        self.vector_store.upsert_documents(records)
        self._search_cache.clear()

    def ingest_texts(self, texts: Iterable[str]) -> None:
        documents = [Document(str(index), text) for index, text in enumerate(texts)]
        self.ingest_documents(documents)

    def search(self, query: str, top_k: int = 5) -> QueryResponse:
        cached = self._search_cache.get(query)
        if cached is not None:
            return QueryResponse(
                results=[result for result in cached.results],
                latency_ms=cached.latency_ms,
                cached=True,
                used_reranker=cached.used_reranker,
            )
        start = time.perf_counter()
        query_vector = self.embedder.embed(query)
        matches = self.vector_store.search(query_vector, top_k)
        if self.config.use_reranker and self.reranker is not None:
            matches = self.reranker.rerank(query, query_vector, matches)
            used_reranker = True
        else:
            used_reranker = False
        results = [self._to_search_result(match) for match in matches[:top_k]]
        latency_ms = (time.perf_counter() - start) * 1000.0
        response = QueryResponse(results=results, latency_ms=latency_ms, cached=False, used_reranker=used_reranker)
        if latency_ms <= self.config.latency_budget_ms:
            self._search_cache.put(query, response)
        return response

    def _to_search_result(self, match: VectorMatch) -> SearchResult:
        payload = dict(match.payload)
        text = payload.get("text", "")
        metadata = {key: value for key, value in payload.items() if key not in {"text"}}
        metadata.setdefault("doc_id", payload.get("doc_id", match.point_id))
        return SearchResult(doc_id=payload.get("doc_id", match.point_id), score=match.score, text=text, metadata=metadata)

    def clear_cache(self) -> None:
        self._search_cache.clear()
