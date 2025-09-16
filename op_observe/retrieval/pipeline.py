"""Retrieval pipeline with optional cross-encoder reranking."""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional, Sequence

from .models import SearchHit
from .rerankers import CrossEncoderReranker
from .vector_store import VectorStore

LOGGER = logging.getLogger(__name__)


class SearchResponse:
    """Container returned by :class:`SemanticSearchPipeline`.

    The response exposes both the initial ANN ranking and the asynchronously
    computed reranked results (if enabled).  Consumers can read the initial hits
    immediately via :meth:`results_nowait` without waiting for the cross-encoder
    to finish.
    """

    def __init__(self, query: str, initial_hits: Sequence[SearchHit]) -> None:
        self.query = query
        self.initial_hits = tuple(initial_hits)
        self._rerank_task: Optional[asyncio.Task[List[SearchHit]]] = None
        self._reranked_hits: Optional[List[SearchHit]] = None
        self._rerank_failed = False
        self._rerank_exception: Optional[BaseException] = None

    def attach_rerank_task(self, task: asyncio.Task[List[SearchHit]]) -> None:
        if self._rerank_task is not None:
            raise RuntimeError("Rerank task already attached")
        self._rerank_task = task
        task.add_done_callback(self._store_rerank_result)

    def _store_rerank_result(self, task: asyncio.Task[List[SearchHit]]) -> None:
        try:
            self._reranked_hits = task.result()
            self._rerank_failed = False
            self._rerank_exception = None
        except Exception as exc:  # noqa: BLE001 - surface the failure downstream
            LOGGER.warning("Cross-encoder rerank failed; using ANN order", exc_info=exc)
            self._reranked_hits = list(self.initial_hits)
            self._rerank_failed = True
            self._rerank_exception = exc

    def results_nowait(self) -> Sequence[SearchHit]:
        """Return whichever set of results is currently available."""

        if self._reranked_hits is not None:
            return tuple(self._reranked_hits)
        return self.initial_hits

    async def get_results(self) -> Sequence[SearchHit]:
        """Await the reranker if present and return the best available results."""

        if self._rerank_task and not self._rerank_task.done():
            try:
                await asyncio.shield(self._rerank_task)
            except Exception:  # rerank failure already logged in callback
                return self.initial_hits
        return self.results_nowait()

    def rerank_ready(self) -> bool:
        """Whether the reranked results are ready to be consumed."""

        if not self._rerank_task:
            return True
        return self._rerank_task.done()

    @property
    def rerank_failed(self) -> bool:
        return self._rerank_failed

    @property
    def rerank_exception(self) -> Optional[BaseException]:
        return self._rerank_exception

    @property
    def has_async_rerank(self) -> bool:
        return self._rerank_task is not None


class SemanticSearchPipeline:
    """Composes vector search with an optional asynchronous reranker."""

    def __init__(self, vector_store: VectorStore, reranker: Optional[CrossEncoderReranker] = None) -> None:
        self._vector_store = vector_store
        self._reranker = reranker

    async def search(self, query: str, *, top_k: int = 5, rerank: bool = True) -> SearchResponse:
        """Retrieve the top results for ``query``.

        When reranking is enabled and a reranker is configured, the heavy scoring
        runs in the background.  Callers can inspect the immediate results to stay
        within tight latency budgets and optionally await :meth:`SearchResponse.get_results`
        to obtain the refined ordering.
        """

        initial_hits = self._vector_store.search(query, top_k)
        response = SearchResponse(query, initial_hits)
        if rerank and self._reranker and initial_hits:
            task = asyncio.create_task(self._run_rerank(query, initial_hits))
            response.attach_rerank_task(task)
        return response

    async def _run_rerank(self, query: str, hits: Sequence[SearchHit]) -> List[SearchHit]:
        if not self._reranker:
            return list(hits)
        reranked = await self._reranker.rerank(query, hits)
        if not reranked:
            return list(hits)
        return reranked


__all__ = ["SearchResponse", "SemanticSearchPipeline"]
