"""Telemetry bootstrap utilities for OP-Observe services."""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from .config import TelemetryConfig

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.trace import TracerProvider
else:  # pragma: no cover - fallback for runtime without dependencies
    MeterProvider = Any  # type: ignore[assignment]
    TracerProvider = Any  # type: ignore[assignment]

_LOGGER = logging.getLogger(__name__)


def _load_opentelemetry() -> dict[str, Any]:
    try:
        from opentelemetry import metrics, trace
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:  # pragma: no cover - depends on runtime env
        raise RuntimeError(
            "OpenTelemetry packages are required. Install them with "
            "`pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-http`."
        ) from exc

    return {
        "metrics": metrics,
        "trace": trace,
        "MeterProvider": MeterProvider,
        "PeriodicExportingMetricReader": PeriodicExportingMetricReader,
        "OTLPMetricExporter": OTLPMetricExporter,
        "OTLPSpanExporter": OTLPSpanExporter,
        "Resource": Resource,
        "TracerProvider": TracerProvider,
        "BatchSpanProcessor": BatchSpanProcessor,
    }


def configure_telemetry(config: TelemetryConfig | None = None) -> tuple[TracerProvider, MeterProvider]:
    """Configure OpenTelemetry SDKs for traces and metrics."""

    modules = _load_opentelemetry()
    metrics_mod = modules["metrics"]
    trace_mod = modules["trace"]
    MeterProviderCls = modules["MeterProvider"]
    PeriodicExportingMetricReaderCls = modules["PeriodicExportingMetricReader"]
    OTLPMetricExporterCls = modules["OTLPMetricExporter"]
    OTLPSpanExporterCls = modules["OTLPSpanExporter"]
    ResourceCls = modules["Resource"]
    TracerProviderCls = modules["TracerProvider"]
    BatchSpanProcessorCls = modules["BatchSpanProcessor"]

    config = config or TelemetryConfig.from_env()

    resource = ResourceCls.create({"service.name": config.service_name})

    tracer_provider = TracerProviderCls(resource=resource)
    span_exporter = OTLPSpanExporterCls(
        endpoint=config.to_traces_endpoint(),
        headers=config.otlp_headers,
        insecure=config.insecure,
    )
    tracer_provider.add_span_processor(BatchSpanProcessorCls(span_exporter))
    trace_mod.set_tracer_provider(tracer_provider)

    metric_exporter = OTLPMetricExporterCls(
        endpoint=config.to_metrics_endpoint(),
        headers=config.otlp_headers,
        insecure=config.insecure,
    )
    metric_reader = PeriodicExportingMetricReaderCls(
        metric_exporter,
        export_interval_millis=int(config.metric_export_interval * 1000),
    )
    meter_provider = MeterProviderCls(resource=resource, metric_readers=[metric_reader])
    metrics_mod.set_meter_provider(meter_provider)

    _LOGGER.debug(
        "Telemetry configured",
        extra={"service_name": config.service_name, "endpoint": config.otlp_endpoint},
    )
    return tracer_provider, meter_provider


def generate_sample_telemetry(iterations: int = 5, delay: float = 0.05) -> None:
    """Send sample spans and metrics to the configured collector."""

    modules = _load_opentelemetry()
    metrics_mod = modules["metrics"]
    trace_mod = modules["trace"]

    config = TelemetryConfig.from_env()
    tracer_provider, meter_provider = configure_telemetry(config)

    tracer = trace_mod.get_tracer(__name__)
    meter = metrics_mod.get_meter(__name__)

    request_counter = meter.create_counter(
        "op_observe_sample_request_count",
        unit="{request}",
        description="Synthetic requests generated for integration testing.",
    )
    latency_histogram = meter.create_histogram(
        "op_observe_sample_request_latency_ms",
        unit="ms",
        description="Latency distribution for synthetic requests.",
    )

    for iteration in range(iterations):
        with tracer.start_as_current_span("sample-operation") as span:
            span.set_attribute("iteration", iteration)
            span.set_attribute("component", "integration-test")
            request_counter.add(1, attributes={"endpoint": "/metrics"})
            latency_histogram.record(25.0 + iteration, attributes={"endpoint": "/metrics"})
            time.sleep(delay)

    flush_tracer_provider(tracer_provider)
    flush_meter_provider(meter_provider)
    shutdown_providers(tracer_provider, meter_provider)


def flush_tracer_provider(provider: TracerProvider) -> None:
    try:
        provider.force_flush()
    except Exception:  # pragma: no cover - defensive
        _LOGGER.exception("Failed to flush tracer provider")


def flush_meter_provider(provider: MeterProvider) -> None:
    try:
        provider.force_flush()
    except Exception:  # pragma: no cover - defensive
        _LOGGER.exception("Failed to flush meter provider")


def shutdown_providers(tracer_provider: TracerProvider, meter_provider: MeterProvider) -> None:
    errors: list[Exception] = []
    for func, provider in (
        (tracer_provider.shutdown, tracer_provider),
        (meter_provider.shutdown, meter_provider),
    ):
        try:
            func()
        except Exception as exc:  # pragma: no cover - defensive
            _LOGGER.exception("Failed to shutdown provider %s", provider)
            errors.append(exc)
    if errors:  # pragma: no cover - defensive
        raise RuntimeError("Failed to shutdown telemetry providers") from errors[0]
