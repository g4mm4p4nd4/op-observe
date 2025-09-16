import asyncio
import time
from typing import Sequence

from op_observe.retrieval import (
    Document,
    InMemoryVectorStore,
    SearchHit,
    SemanticSearchPipeline,
    SimpleCrossEncoderReranker,
)


def test_cross_encoder_reranks_for_phrase_matches() -> None:
    async def _run() -> None:
        documents = [
            Document(
                doc_id="dense-security",
                content="Security security security practices with a nod to agentic systems",
            ),
            Document(
                doc_id="agentic-security",
                content="Agentic security posture management playbook",
            ),
            Document(doc_id="observability", content="Observability metrics and tracing deep dive"),
        ]
        store = InMemoryVectorStore(documents)
        pipeline = SemanticSearchPipeline(
            store,
            reranker=SimpleCrossEncoderReranker(base_weight=0.1, overlap_weight=0.3, phrase_weight=1.4),
        )

        response = await pipeline.search("agentic security", top_k=3, rerank=True)
        initial_ids = [hit.document.doc_id for hit in response.initial_hits]
        assert initial_ids[0] == "dense-security"

        reranked_results = await response.get_results()
        reranked_ids = [hit.document.doc_id for hit in reranked_results]
        assert reranked_ids[0] == "agentic-security"
        assert reranked_results[0].metadata["score_source"] == "cross_encoder"
        assert "baseline_score" in reranked_results[0].metadata

    asyncio.run(_run())


def test_async_rerank_does_not_block_initial_results() -> None:
    async def _run() -> None:
        documents = [
            Document(doc_id="a", content="Security security agentic"),
            Document(doc_id="b", content="Agentic security posture"),
        ]
        store = InMemoryVectorStore(documents)
        latency = 0.1
        reranker = SimpleCrossEncoderReranker(latency=latency)
        pipeline = SemanticSearchPipeline(store, reranker=reranker)

        start = time.perf_counter()
        response = await pipeline.search("agentic security", top_k=2, rerank=True)
        elapsed = time.perf_counter() - start

        # The heavy reranker sleeps for ``latency`` seconds; returning faster shows the
        # operation was launched asynchronously.
        assert elapsed < latency
        assert response.has_async_rerank

        initial_now = response.results_nowait()
        assert list(initial_now) == list(response.initial_hits)

        final_results = await response.get_results()
        assert len(final_results) == 2

    asyncio.run(_run())


def test_pipeline_respects_rerank_disabled_flag() -> None:
    async def _run() -> None:
        documents = [
            Document(doc_id="a", content="Security security agentic"),
            Document(doc_id="b", content="Agentic security posture"),
        ]
        store = InMemoryVectorStore(documents)
        pipeline = SemanticSearchPipeline(store, reranker=SimpleCrossEncoderReranker())

        response = await pipeline.search("agentic security", top_k=2, rerank=False)
        assert not response.has_async_rerank

        results = await response.get_results()
        assert list(results) == list(response.initial_hits)

    asyncio.run(_run())


class FailingReranker(SimpleCrossEncoderReranker):
    async def rerank(self, query: str, hits: Sequence[SearchHit]) -> Sequence[SearchHit]:
        raise RuntimeError("boom")


def test_rerank_failure_falls_back_to_ann() -> None:
    async def _run() -> None:
        documents = [
            Document(doc_id="a", content="Security security agentic"),
            Document(doc_id="b", content="Agentic security posture"),
        ]
        store = InMemoryVectorStore(documents)
        pipeline = SemanticSearchPipeline(store, reranker=FailingReranker())

        response = await pipeline.search("agentic security", top_k=2, rerank=True)
        results = await response.get_results()

        assert list(results) == list(response.initial_hits)
        assert response.rerank_failed
        assert isinstance(response.rerank_exception, RuntimeError)

    asyncio.run(_run())
