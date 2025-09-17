"""Structured logging utilities that correlate OpenTelemetry spans and logs."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterator, Mapping, Optional

from opentelemetry import baggage, context as otel_context, trace
from opentelemetry.exporter.otlp.proto.http import Compression
from opentelemetry.exporter.otlp.proto.http._log_exporter import (
    OTLPLogExporter as HTTPOtLPLogExporter,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as HTTPOtLPSpanExporter,
)
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler, LogRecordProcessor
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, LogExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter

# Type-checkers do not know about logging.LogRecord attributes, so we keep a
# canonical list of the attributes the stdlib attaches to each record. The
# OpenTelemetry logging handler will treat everything else as structured
# metadata.
_STANDARD_RECORD_FIELDS = {
    "args",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


class _StructuredLogFilter(logging.Filter):
    """Convert log records into structured bodies and attach context metadata."""

    def __init__(self, resource: Resource) -> None:
        super().__init__()
        self._resource_attributes: Dict[str, object] = dict(resource.attributes)

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        # Capture the formatted message before mutating the record.
        formatted_message = record.getMessage()

        extra_attributes: Dict[str, object] = {
            key: value
            for key, value in vars(record).items()
            if key not in _STANDARD_RECORD_FIELDS
        }

        baggage_context = baggage.get_all(context=otel_context.get_current())
        if baggage_context:
            extra_attributes.update(
                {f"baggage.{key}": value for key, value in baggage_context.items()}
            )

        structured_body: Dict[str, object] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "severity_text": record.levelname,
            "logger_name": record.name,
            "message": formatted_message,
        }
        if self._resource_attributes:
            structured_body["resource"] = dict(self._resource_attributes)
        if extra_attributes:
            structured_body["attributes"] = dict(extra_attributes)

        # Replace the record body with the structured form so that the
        # OpenTelemetry handler serialises the dictionary instead of a plain
        # string.
        record.msg = structured_body
        record.args = None
        record.message = formatted_message

        # Expose resource metadata and correlation data as attributes so that the
        # OTLP exporter forwards them to Loki.
        service_name = self._resource_attributes.get(SERVICE_NAME)
        if service_name is not None:
            record.__dict__["service.name"] = service_name
        for key, value in extra_attributes.items():
            record.__dict__[key] = value

        return True


@dataclass
class LoggingSetup:
    """Container holding OpenTelemetry logging infrastructure."""

    logger_provider: LoggerProvider
    tracer_provider: TracerProvider
    handler: LoggingHandler
    log_processor: LogRecordProcessor
    span_processor: Optional[BatchSpanProcessor]
    resource: Resource
    attached_to_root: bool

    def configure_logger(self, logger: logging.Logger) -> logging.Logger:
        """Attach the OpenTelemetry handler to *logger* and disable propagation."""

        if self.handler not in logger.handlers:
            logger.addHandler(self.handler)
        logger.setLevel(self.handler.level)
        logger.propagate = False
        return logger

    def force_flush(self) -> None:
        self.logger_provider.force_flush()
        self.tracer_provider.force_flush()

    def shutdown(self) -> None:
        self.logger_provider.shutdown()
        self.tracer_provider.shutdown()
        if self.attached_to_root:
            root_logger = logging.getLogger()
            if self.handler in root_logger.handlers:
                root_logger.removeHandler(self.handler)


def _coerce_compression(
    compression: Optional[object],
) -> Optional[Compression]:
    if compression is None or isinstance(compression, Compression):
        return compression  # type: ignore[return-value]
    if isinstance(compression, str):
        normalized = compression.strip().lower()
        for option in Compression:
            if option.name.lower() == normalized or option.value == normalized:
                return option
        raise ValueError(f"Unsupported compression setting: {compression!r}")
    raise TypeError(
        "compression must be a Compression enum value, its name, or None"
    )


def create_otlp_log_exporter(
    endpoint: str,
    *,
    headers: Optional[Mapping[str, str]] = None,
    compression: Optional[str] = "gzip",
    timeout: Optional[int] = None,
) -> LogExporter:
    """Factory for an OTLP log exporter suitable for Loki."""

    return HTTPOtLPLogExporter(
        endpoint=endpoint,
        headers=dict(headers) if headers else None,
        compression=_coerce_compression(compression),
        timeout=timeout,
    )


def create_otlp_span_exporter(
    endpoint: str,
    *,
    headers: Optional[Mapping[str, str]] = None,
    compression: Optional[str] = "gzip",
    timeout: Optional[int] = None,
) -> SpanExporter:
    """Factory for an OTLP span exporter that can feed Tempo."""

    return HTTPOtLPSpanExporter(
        endpoint=endpoint,
        headers=dict(headers) if headers else None,
        compression=_coerce_compression(compression),
        timeout=timeout,
    )


def configure_otel_logging(
    *,
    service_name: str,
    loki_endpoint: str,
    tempo_endpoint: Optional[str] = None,
    resource_attributes: Optional[Mapping[str, object]] = None,
    log_exporter: Optional[LogExporter] = None,
    span_exporter: Optional[SpanExporter] = None,
    log_processor: Optional[LogRecordProcessor] = None,
    span_processor: Optional[BatchSpanProcessor] = None,
    log_level: int = logging.INFO,
    attach_to_root: bool = True,
) -> LoggingSetup:
    """Configure OpenTelemetry logging and tracing for Loki and Tempo."""

    attributes: Dict[str, object] = {SERVICE_NAME: service_name}
    if resource_attributes:
        attributes.update(resource_attributes)

    resource = Resource.create(attributes)

    logger_provider = LoggerProvider(resource=resource)

    exporter = log_exporter or create_otlp_log_exporter(loki_endpoint)
    processor = log_processor or BatchLogRecordProcessor(exporter)
    logger_provider.add_log_record_processor(processor)

    handler = LoggingHandler(level=log_level, logger_provider=logger_provider)
    handler.addFilter(_StructuredLogFilter(resource))

    current_provider = trace.get_tracer_provider()
    if isinstance(current_provider, TracerProvider):
        tracer_provider = current_provider
    else:
        tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(tracer_provider)

    active_span_processor = span_processor
    if tempo_endpoint or span_exporter or span_processor:
        exporter_span = span_exporter or (
            create_otlp_span_exporter(tempo_endpoint) if tempo_endpoint else None
        )
        if exporter_span:
            active_span_processor = span_processor or BatchSpanProcessor(exporter_span)
            tracer_provider.add_span_processor(active_span_processor)

    if attach_to_root:
        root_logger = logging.getLogger()
        if handler not in root_logger.handlers:
            root_logger.addHandler(handler)
        if root_logger.level > log_level:
            root_logger.setLevel(log_level)

    return LoggingSetup(
        logger_provider=logger_provider,
        tracer_provider=tracer_provider,
        handler=handler,
        log_processor=processor,
        span_processor=active_span_processor,
        resource=resource,
        attached_to_root=attach_to_root,
    )


@contextmanager
def correlation_context(**attributes: object) -> Iterator[None]:
    """Inject baggage attributes so logs correlate with the active span."""

    context = otel_context.get_current()
    for key, value in attributes.items():
        context = baggage.set_baggage(key, value, context=context)
    token = otel_context.attach(context)
    try:
        yield
    finally:
        otel_context.detach(token)


__all__ = [
    "LoggingSetup",
    "configure_otel_logging",
    "create_otlp_log_exporter",
    "create_otlp_span_exporter",
    "correlation_context",
]
