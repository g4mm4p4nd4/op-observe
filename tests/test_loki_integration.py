import logging
from typing import Dict, Iterable, List

from opentelemetry import trace
from opentelemetry.sdk.trace.export import InMemorySpanExporter

from op_observe.telemetry import configure_telemetry


def _collect_streams(requests: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    streams: List[Dict[str, object]] = []
    for request in requests:
        payload = request.get("json")
        if not isinstance(payload, dict):
            continue
        streams.extend(payload.get("streams", []))
    return streams


def test_logs_include_trace_and_span_ids(loki_server) -> None:
    span_exporter = InMemorySpanExporter()
    telemetry = configure_telemetry(
        service_name="test-service",
        loki_endpoint=loki_server.url,
        span_exporter=span_exporter,
        resource_attributes={"deployment.environment": "test"},
        default_labels={"cluster": "local"},
    )

    tracer = trace.get_tracer(__name__)
    logger = logging.getLogger("test.logger.trace")
    logger.propagate = True

    trace_hex = span_hex = None
    try:
        with tracer.start_as_current_span("integration-span") as span:
            context = span.get_span_context()
            trace_hex = format(context.trace_id, "032x")
            span_hex = format(context.span_id, "016x")
            logger.info("hello loki")

        telemetry.force_flush()

        exported_spans = span_exporter.get_finished_spans()
        assert len(exported_spans) == 1
        assert format(exported_spans[0].context.trace_id, "032x") == trace_hex

        streams = _collect_streams(loki_server.requests())
        assert streams, "expected at least one Loki stream"

        matched = [stream for stream in streams if stream["stream"].get("trace_id") == trace_hex]
        assert matched, "Loki payload did not include the trace identifier"

        for stream in matched:
            labels = stream["stream"]
            values = stream["values"]
            assert labels["span_id"] == span_hex
            assert labels["service_name"] == "test-service"
            assert labels["deployment_environment"] == "test"
            assert labels["cluster"] == "local"
            assert any("trace_id=" + trace_hex in entry[1] for entry in values)
            assert any("span_id=" + span_hex in entry[1] for entry in values)
    finally:
        telemetry.shutdown()
        span_exporter.clear()


def test_child_span_logs_have_distinct_span_ids(loki_server) -> None:
    span_exporter = InMemorySpanExporter()
    telemetry = configure_telemetry(
        service_name="multi-span-service",
        loki_endpoint=loki_server.url,
        span_exporter=span_exporter,
    )

    tracer = trace.get_tracer("tests.child")
    logger = logging.getLogger("test.logger.child")
    logger.propagate = True

    try:
        with tracer.start_as_current_span("parent") as parent:
            parent_ctx = parent.get_span_context()
            trace_hex = format(parent_ctx.trace_id, "032x")
            parent_span_hex = format(parent_ctx.span_id, "016x")
            logger.info("parent message")
            with tracer.start_as_current_span("child") as child:
                child_span_hex = format(child.get_span_context().span_id, "016x")
                logger.warning("child message", extra={"user": "alice"})

        telemetry.force_flush()

        exported_spans = span_exporter.get_finished_spans()
        assert len(exported_spans) == 2
        span_ids = {format(span.context.span_id, "016x") for span in exported_spans}
        assert {parent_span_hex, child_span_hex} <= span_ids

        streams = _collect_streams(loki_server.requests())
        parent_streams = [s for s in streams if s["stream"].get("span_id") == parent_span_hex]
        child_streams = [s for s in streams if s["stream"].get("span_id") == child_span_hex]

        assert any(s["stream"].get("trace_id") == trace_hex for s in parent_streams)
        assert any("parent message" in value[1] for s in parent_streams for value in s["values"])

        assert any(s["stream"].get("trace_id") == trace_hex for s in child_streams)
        child_entries = [value[1] for s in child_streams for value in s["values"]]
        assert any("child message" in entry for entry in child_entries)
        assert any("attrs" in entry and "\"user\": \"alice\"" in entry for entry in child_entries)
    finally:
        telemetry.shutdown()
        span_exporter.clear()
