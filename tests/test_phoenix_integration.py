from __future__ import annotations

import json
from typing import Any, Dict, List

import pytest

from op_observe.observability import (
    OpenInferenceSpanKind,
    PhoenixClient,
    PhoenixTraceExporter,
    PhoenixTraceSession,
)
from op_observe.observability.phoenix import TransportResponse


class FakeClock:
    def __init__(self, start: float = 1_000.0, step: float = 0.5) -> None:
        self._value = start
        self._step = step

    def __call__(self) -> float:
        current = self._value
        self._value += self._step
        return current


class RecordingTransport:
    def __init__(self) -> None:
        self.requests: List[Dict[str, Any]] = []

    def post_json(
        self,
        url: str,
        payload: Dict[str, Any],
        headers: Dict[str, str] | None = None,
    ) -> TransportResponse:
        self.requests.append({"url": url, "payload": payload, "headers": headers or {}})
        return TransportResponse(status_code=200, body=json.dumps({"status": "ok"}))


@pytest.fixture()
def phoenix_components() -> tuple[PhoenixTraceSession, RecordingTransport]:
    transport = RecordingTransport()
    client = PhoenixClient("https://phoenix.example", transport=transport)
    exporter = PhoenixTraceExporter(client)
    session = PhoenixTraceSession(exporter, trace_id="trace-123", clock=FakeClock())
    return session, transport


def test_trace_session_exports_openinference_spans(phoenix_components: tuple[PhoenixTraceSession, RecordingTransport]) -> None:
    session, transport = phoenix_components

    with session.chain_span("agent-flow"):
        with session.model_span(
            "gpt-4",
            attributes={"openinference.model.name": "gpt-4", "llm.temperature": 0.0},
        ) as model_span:
            with session.tool_span("bing-search", attributes={"tool.args": {"q": "phoenix"}}):
                pass
        with session.retriever_span("qdrant"):
            pass

    session.record_evaluation(
        "accuracy",
        0.93,
        span=model_span,
        metadata={"dataset": "eval-set", "threshold": 0.9},
    )
    responses = session.submit()

    assert set(responses.keys()) == {"traces", "evaluations", "dashboards"}
    assert len(transport.requests) == 3

    trace_request = transport.requests[0]
    assert trace_request["url"].endswith("/api/v1/traces")
    assert trace_request["payload"]["trace_id"] == "trace-123"
    spans = trace_request["payload"]["spans"]
    kinds = {span["attributes"]["openinference.span.kind"] for span in spans}
    assert {"chain", "llm", "tool", "retriever"} == kinds

    llm_spans = [
        span
        for span in spans
        if span["attributes"].get("openinference.span.kind") == OpenInferenceSpanKind.MODEL.value
    ]
    assert llm_spans, "Expected at least one LLM span"
    llm_span = llm_spans[0]
    assert llm_span["attributes"]["openinference.model.name"] == "gpt-4"
    assert llm_span["attributes"]["llm.temperature"] == 0.0

    tool_spans = [
        span
        for span in spans
        if span["attributes"]["openinference.span.kind"] == OpenInferenceSpanKind.TOOL.value
    ]
    assert tool_spans[0]["attributes"]["openinference.tool.name"] == "bing-search"
    retriever_spans = [
        span
        for span in spans
        if span["attributes"]["openinference.span.kind"] == OpenInferenceSpanKind.RETRIEVER.value
    ]
    assert retriever_spans[0]["attributes"]["openinference.retriever.name"] == "qdrant"

    eval_request = transport.requests[1]
    assert eval_request["url"].endswith("/api/v1/evaluations")
    assert eval_request["payload"]["trace_id"] == "trace-123"
    evaluation_payload = eval_request["payload"]["evaluations"][0]
    assert evaluation_payload["metric_name"] == "accuracy"
    assert pytest.approx(evaluation_payload["value"], rel=1e-6) == 0.93
    assert evaluation_payload["metadata"] == {"dataset": "eval-set", "threshold": 0.9}
    assert evaluation_payload["span_id"] == model_span.span_id

    dashboard_request = transport.requests[2]
    assert dashboard_request["url"].endswith("/api/v1/dashboards/refresh")
    assert dashboard_request["payload"] == {"trace_id": "trace-123"}
