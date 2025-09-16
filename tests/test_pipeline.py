from __future__ import annotations

from op_observe.models import Document
from .conftest import build_pipeline


def test_ingest_and_search_returns_best_match():
    fixture = build_pipeline()
    docs = [
        Document("a", "The quick brown fox"),
        Document("b", "Jumps over the lazy dog"),
        Document("c", "Retrieval augmented generation"),
    ]
    fixture.pipeline.ingest_documents(docs)

    response = fixture.pipeline.search("quick fox", top_k=2)

    assert response.results, "Expected at least one result"
    best = response.results[0]
    assert best.doc_id == "a"
    assert "quick" in best.text
    assert response.latency_ms < 200
    assert not response.cached


def test_search_uses_cache_and_avoids_recomputing_embeddings():
    fixture = build_pipeline()
    fixture.pipeline.ingest_texts(["alpha", "beta", "gamma"])

    first = fixture.pipeline.search("alpha")
    embed_calls_after_first = fixture.embedder.calls
    second = fixture.pipeline.search("alpha")

    assert second.cached is True
    assert fixture.embedder.calls == embed_calls_after_first
    assert first.results[0].doc_id == second.results[0].doc_id


def test_cache_is_invalidated_on_new_ingest():
    fixture = build_pipeline()
    fixture.pipeline.ingest_texts(["alpha", "beta"])
    fixture.pipeline.search("alpha")

    fixture.pipeline.ingest_documents([Document("2", "alpha beta gamma")])
    response = fixture.pipeline.search("alpha")

    assert response.cached is False


def test_optional_reranking_is_respected():
    fixture = build_pipeline(use_reranker=True)
    fixture.pipeline.ingest_texts(["zero", "one", "two"])

    response = fixture.pipeline.search("two")

    assert response.used_reranker is True
    assert response.latency_ms < 200
