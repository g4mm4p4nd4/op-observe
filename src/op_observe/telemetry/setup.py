"""Telemetry wiring helpers for OP-Observe services."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Mapping, Optional

from opentelemetry import trace
from opentelemetry._logs import get_logger_provider, set_logger_provider
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, LogExporter
from opentelemetry.sdk._logs.handler import LoggingHandler
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

from .loki_exporter import LokiExporterConfig, LokiLogExporter

_DEFAULT_SAMPLE_RATIO = 1.0


@dataclass
class TelemetryHandles:
    """Runtime handles returned by :func:`configure_telemetry`."""

    logger_provider: LoggerProvider
    log_processor: BatchLogRecordProcessor
    log_handler: LoggingHandler
    instrumentor: LoggingInstrumentor
    tracer_provider: Optional[TracerProvider]
    span_processor: Optional[BatchSpanProcessor]
    log_exporter: LogExporter
    span_exporter: Optional[SpanExporter]
    previous_logger_provider: Optional[LoggerProvider]
    previous_tracer_provider: Optional[TracerProvider]

    def force_flush(self) -> None:
        self.log_processor.force_flush()
        self.logger_provider.force_flush()
        if self.tracer_provider:
            if self.span_processor:
                self.span_processor.force_flush()
            self.tracer_provider.force_flush()

    def shutdown(self) -> None:
        root_logger = logging.getLogger()
        if self.log_handler in root_logger.handlers:
            root_logger.removeHandler(self.log_handler)
        self.log_handler.close()
        self.instrumentor.uninstrument()
        self.log_processor.shutdown()
        self.logger_provider.shutdown()
        if self.previous_logger_provider is not None:
            set_logger_provider(self.previous_logger_provider)
        if self.tracer_provider:
            if self.span_processor:
                self.span_processor.shutdown()
            self.tracer_provider.shutdown()
        if self.previous_tracer_provider is not None:
            trace.set_tracer_provider(self.previous_tracer_provider)


def _default_log_hook(log_data, record) -> None:
    span = trace.get_current_span()
    span_context = span.get_span_context() if span else None
    if span_context and span_context.trace_id:
        trace_id = format(span_context.trace_id, "032x")
        span_id = format(span_context.span_id, "016x")
        log_data.log_record.trace_id = span_context.trace_id
        log_data.log_record.span_id = span_context.span_id
        log_data.log_record.trace_flags = span_context.trace_flags
        log_data.log_record.trace_state = span_context.trace_state
        log_data.log_record.attributes["trace_id"] = trace_id
        log_data.log_record.attributes["span_id"] = span_id
        record.trace_id = trace_id
        record.span_id = span_id
        record.trace_flags = span_context.trace_flags
        record.trace_state = span_context.trace_state


def configure_telemetry(
    *,
    service_name: str,
    loki_endpoint: str,
    loki_tenant_id: Optional[str] = None,
    default_labels: Optional[Mapping[str, str]] = None,
    resource_attributes: Optional[Mapping[str, object]] = None,
    log_level: int = logging.INFO,
    log_exporter: Optional[LogExporter] = None,
    span_exporter: Optional[SpanExporter] = None,
    tempo_endpoint: Optional[str] = None,
    tempo_insecure: bool = True,
    tempo_headers: Optional[Mapping[str, str]] = None,
    sample_ratio: float = _DEFAULT_SAMPLE_RATIO,
    log_hook: Optional[Callable] = None,
) -> TelemetryHandles:
    """Configure OpenTelemetry logging and tracing for Loki + Tempo."""

    resource_attributes = dict(resource_attributes or {})
    resource_attributes.setdefault("service.name", service_name)
    resource = Resource.create(resource_attributes)

    previous_logger_provider = get_logger_provider()
    logger_provider = LoggerProvider(resource=resource)
    set_logger_provider(logger_provider)

    exporter = log_exporter or LokiLogExporter(
        LokiExporterConfig(
            endpoint=loki_endpoint,
            tenant_id=loki_tenant_id,
            default_labels=default_labels or {},
        )
    )
    log_processor = BatchLogRecordProcessor(exporter)
    logger_provider.add_log_record_processor(log_processor)

    instrumentor = LoggingInstrumentor()
    instrumentor.uninstrument()
    instrumentor.instrument(set_logging_format=True, log_hook=log_hook or _default_log_hook)

    handler = LoggingHandler(level=log_level, logger_provider=logger_provider)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)

    tracer_provider: Optional[TracerProvider] = None
    span_processor: Optional[BatchSpanProcessor] = None
    previous_tracer_provider: Optional[TracerProvider] = None

    if span_exporter is None and tempo_endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        span_exporter = OTLPSpanExporter(
            endpoint=tempo_endpoint,
            insecure=tempo_insecure,
            headers=dict(tempo_headers or {}),
        )

    if span_exporter is not None:
        previous_tracer_provider = trace.get_tracer_provider()
        tracer_provider = TracerProvider(resource=resource, sampler=TraceIdRatioBased(sample_ratio))
        span_processor = BatchSpanProcessor(span_exporter)
        tracer_provider.add_span_processor(span_processor)
        trace.set_tracer_provider(tracer_provider)

    return TelemetryHandles(
        logger_provider=logger_provider,
        log_processor=log_processor,
        log_handler=handler,
        instrumentor=instrumentor,
        tracer_provider=tracer_provider,
        span_processor=span_processor,
        log_exporter=exporter,
        span_exporter=span_exporter,
        previous_logger_provider=previous_logger_provider,
        previous_tracer_provider=previous_tracer_provider,
    )


__all__ = ["TelemetryHandles", "configure_telemetry"]
