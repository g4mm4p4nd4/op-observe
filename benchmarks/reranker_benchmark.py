"""Micro-benchmark for the asynchronous cross-encoder reranker."""

from __future__ import annotations

import asyncio
import time

from op_observe.retrieval import (
    Document,
    InMemoryVectorStore,
    SemanticSearchPipeline,
    SimpleCrossEncoderReranker,
)


async def run_benchmark(iterations: int = 200) -> None:
    documents = [
        Document(doc_id=f"doc-{idx}", content=f"Agentic security posture iteration {idx}")
        for idx in range(10)
    ]
    store = InMemoryVectorStore(documents)
    reranker = SimpleCrossEncoderReranker()
    pipeline = SemanticSearchPipeline(store, reranker=reranker)
    query = "agentic security posture"

    start = time.perf_counter()
    for _ in range(iterations):
        response = await pipeline.search(query, top_k=5, rerank=True)
        await response.get_results()
    rerank_total = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(iterations):
        response = await pipeline.search(query, top_k=5, rerank=False)
        await response.get_results()
    baseline_total = time.perf_counter() - start

    print("Iterations:", iterations)
    print(f"With rerank total: {rerank_total:.4f}s (avg {rerank_total / iterations:.6f}s)")
    print(f"Baseline total: {baseline_total:.4f}s (avg {baseline_total / iterations:.6f}s)")
    print(f"Average overhead per query: {(rerank_total - baseline_total) / iterations:.6f}s")


def main() -> None:
    asyncio.run(run_benchmark())


if __name__ == "__main__":
    main()
