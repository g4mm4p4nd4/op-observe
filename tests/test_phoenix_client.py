from __future__ import annotations

from datetime import datetime, timezone

import pytest

from op_observe.phoenix.client import EvaluationResult, PhoenixClient
from op_observe.telemetry.models import Dataset


def test_register_dataset_caches_response() -> None:
    calls = []

    def transport(method: str, path: str, payload: dict) -> dict:
        calls.append((method, path, payload))
        assert method == "POST"
        assert path == "/v1/datasets"
        assert payload["name"] == "test-dataset"
        return {"dataset_id": "ds-123"}

    client = PhoenixClient("http://phoenix", transport=transport)
    dataset = Dataset(name="test-dataset", schema={"input": "text"}, metadata={"env": "dev"})

    assert client.register_dataset(dataset) == "ds-123"
    assert client.register_dataset(dataset) == "ds-123"
    assert len(calls) == 1
    assert client.dataset_registered("test-dataset")


def test_update_evaluation_payload() -> None:
    recorded = []

    def transport(method: str, path: str, payload: dict) -> dict:
        recorded.append((method, path, payload))
        return {"status": "ok"}

    client = PhoenixClient("http://phoenix", transport=transport)

    result = EvaluationResult(
        record_id="trace-1",
        trace_id="trace-1",
        span_id="span-1",
        metrics={"accuracy": 0.9},
        metadata={"label": "A"},
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )

    response = client.update_evaluation("ds-1", "retrieval", [result])
    assert recorded[0][0] == "POST"
    assert recorded[0][1] == "/v1/datasets/ds-1/evaluations/retrieval"
    payload = recorded[0][2]
    assert payload["dataset_id"] == "ds-1"
    assert payload["results"][0]["record_id"] == "trace-1"
    assert payload["results"][0]["metadata"]["label"] == "A"
    assert response == {"status": "ok"}


def test_update_evaluation_skips_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_transport(method: str, path: str, payload: dict) -> dict:  # pragma: no cover - should not be called
        raise AssertionError("transport should not be called for empty results")

    client = PhoenixClient("http://phoenix", transport=failing_transport)
    assert client.update_evaluation("ds-1", "eval", []) == {}


def test_log_spans_skips_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_transport(method: str, path: str, payload: dict) -> dict:  # pragma: no cover - should not be called
        raise AssertionError("transport should not be called for empty spans")

    client = PhoenixClient("http://phoenix", transport=failing_transport)
    assert client.log_spans("ds-1", []) == {}
