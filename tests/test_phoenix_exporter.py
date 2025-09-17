from __future__ import annotations

from datetime import datetime, timedelta, timezone

from op_observe.phoenix.client import PhoenixClient
from op_observe.phoenix.exporter import PhoenixExporter
from op_observe.telemetry.models import Dataset, EvaluationMetric, TelemetryBatch, TraceSpan


def test_export_batch_exports_traces_and_evaluations() -> None:
    requests: list[tuple[str, str, dict]] = []

    def transport(method: str, path: str, payload: dict) -> dict:
        requests.append((method, path, payload))
        if path == "/v1/datasets":
            return {"dataset_id": "dataset-xyz"}
        return {"status": "ok"}

    client = PhoenixClient("http://phoenix", transport=transport)
    exporter = PhoenixExporter(client)

    dataset = Dataset(name="observability", schema={"input": "text", "output": "text"})

    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    span = TraceSpan(
        trace_id="trace-1",
        span_id="span-1",
        name="llm.invoke",
        start_time=start,
        end_time=start + timedelta(seconds=1),
        parent_span_id=None,
        kind="LLM",
        status_code="OK",
        attributes={
            "openinference.prompt": "hello",
            "openinference.response": "world",
            "guardrail.verdict": "pass",
            "tenant": "acme",
        },
    )

    metrics = [
        EvaluationMetric(
            evaluation_name="llm_critic",
            metric_name="score",
            value=0.82,
            trace_id="trace-1",
            span_id="span-1",
            timestamp=start + timedelta(seconds=2),
            metadata={"record_id": "trace-1", "label": "good"},
        ),
        EvaluationMetric(
            evaluation_name="llm_critic",
            metric_name="pass",
            value=1.0,
            trace_id="trace-1",
            span_id="span-1",
            timestamp=start + timedelta(seconds=3),
            metadata={"record_id": "trace-1", "threshold": 0.7},
        ),
        EvaluationMetric(
            evaluation_name="retrieval_quality",
            metric_name="hit_rate",
            value=0.9,
            trace_id="trace-2",
            span_id="span-2",
            timestamp=start + timedelta(seconds=4),
            metadata={},
        ),
    ]

    batch = TelemetryBatch(dataset=dataset, traces=[span], evaluations=metrics)

    dataset_id = exporter.export_batch(batch)
    assert dataset_id == "dataset-xyz"

    assert [path for _, path, _ in requests][:1] == ["/v1/datasets"]

    span_request = next(payload for method, path, payload in requests if path.endswith("/spans"))
    spans_payload = span_request["spans"]
    assert spans_payload[0]["trace_id"] == "trace-1"
    assert spans_payload[0]["open_inference"]["prompt"] == "hello"
    assert spans_payload[0]["attributes"]["tenant"] == "acme"

    evaluation_requests = {
        path: payload for method, path, payload in requests if "/evaluations/" in path
    }
    critic_payload = evaluation_requests["/v1/datasets/dataset-xyz/evaluations/llm_critic"]
    critic_results = critic_payload["results"][0]
    assert critic_results["metrics"] == {"score": 0.82, "pass": 1.0}
    assert critic_results["metadata"] == {"label": "good", "threshold": 0.7}
    assert critic_results["span_id"] == "span-1"

    retrieval_payload = evaluation_requests["/v1/datasets/dataset-xyz/evaluations/retrieval_quality"]
    assert retrieval_payload["results"][0]["metrics"]["hit_rate"] == 0.9
