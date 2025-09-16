from __future__ import annotations

from statistics import mean

from .conftest import build_pipeline


def test_search_latency_stays_under_budget():
    fixture = build_pipeline()
    corpus = [f"document {i} body text" for i in range(64)]
    fixture.pipeline.ingest_texts(corpus)

    latencies = []
    for idx in range(10):
        query = f"document {idx}"
        response = fixture.pipeline.search(query)
        latencies.append(response.latency_ms)
        assert response.latency_ms < 200
        assert not response.cached

    assert mean(latencies) < 200
