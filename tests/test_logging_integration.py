import logging

from opentelemetry import baggage, trace
from opentelemetry.sdk._logs.export import InMemoryLogExporter
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from op_observe.logging_integration import (
    configure_otel_logging,
    correlation_context,
    create_otlp_log_exporter,
    create_otlp_span_exporter,
)


def _configure_logger(setup: configure_otel_logging.__annotations__["return"], name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.handlers = []
    setup.configure_logger(logger)
    return logger


def test_structured_logs_include_trace_and_span_ids():
    log_exporter = InMemoryLogExporter()
    span_exporter = InMemorySpanExporter()
    setup = configure_otel_logging(
        service_name="integration-test",
        loki_endpoint="http://loki:4318/v1/logs",
        tempo_endpoint="http://tempo:4318/v1/traces",
        log_exporter=log_exporter,
        span_exporter=span_exporter,
        attach_to_root=False,
    )

    logger = _configure_logger(setup, "otel-logger")
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span("span-ctx") as span:
        with correlation_context(request_id="req-123"):
            logger.info("structured log", extra={"tenant": "acme"})

    setup.force_flush()

    exported = log_exporter.get_finished_logs()
    assert len(exported) == 1
    log_record = exported[0].log_record

    span_context = span.get_span_context()
    assert trace.format_trace_id(log_record.trace_id) == trace.format_trace_id(
        span_context.trace_id
    )
    assert trace.format_span_id(log_record.span_id) == trace.format_span_id(
        span_context.span_id
    )

    body = log_record.body
    assert isinstance(body, dict)
    assert body["message"] == "structured log"
    assert body["resource"]["service.name"] == "integration-test"

    attributes = dict(log_record.attributes)
    assert attributes["tenant"] == "acme"
    assert attributes["baggage.request_id"] == "req-123"

    spans = span_exporter.get_finished_spans()
    assert [finished_span.name for finished_span in spans] == ["span-ctx"]

    setup.shutdown()


def test_correlation_context_clears_baggage_after_exit():
    assert baggage.get_all() == {}
    with correlation_context(user="alice"):
        assert baggage.get_baggage("user") == "alice"
    assert baggage.get_baggage("user") is None


def test_exporter_factories_configure_endpoints():
    log_exporter = create_otlp_log_exporter("http://loki")
    span_exporter = create_otlp_span_exporter("http://tempo")

    assert getattr(log_exporter, "_endpoint") == "http://loki"
    assert getattr(span_exporter, "_endpoint") == "http://tempo"
