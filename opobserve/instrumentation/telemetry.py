"""Telemetry pipeline instrumentation helpers."""

from __future__ import annotations

from typing import Optional, Sequence

from .config import UnifiedTelemetryConfig
from .registry import InstrumentationRegistry, MetricDefinition, Wrapper
from .utils import unique_metrics, unique_wrappers
from .wrappers import annotate_wrapper, attach_metadata

_MODULE_NAME = "telemetry"

_DEFAULT_WRAPPERS: Sequence[Wrapper] = (
    annotate_wrapper("otel_span", f"{_MODULE_NAME}.export"),
    attach_metadata(otel_scope=_MODULE_NAME, otel_signal="metrics"),
)

_DEFAULT_METRICS: Sequence[MetricDefinition] = (
    MetricDefinition(
        name="telemetry_export_failures_total",
        description="Number of failed telemetry export attempts",
        instrument_type="counter",
        unit="1",
        value_type=int,
    ),
    MetricDefinition(
        name="telemetry_export_latency_seconds",
        description="Histogram of telemetry export latencies",
        instrument_type="histogram",
        unit="s",
        value_type=float,
    ),
)


def init_telemetry_instrumentation(
    config: UnifiedTelemetryConfig,
    registry: Optional[InstrumentationRegistry] = None,
    wrappers: Optional[Sequence[Wrapper]] = None,
    metrics: Optional[Sequence[MetricDefinition]] = None,
) -> InstrumentationRegistry:
    """Register telemetry instrumentation metadata.

    The function is the final piece of the high level initialisation API
    that provides a unified OpenTelemetry configuration surface across the
    code base.

    Examples
    --------
    >>> from opobserve.instrumentation import UnifiedTelemetryConfig
    >>> config = UnifiedTelemetryConfig(service_name="collector")
    >>> registry = init_telemetry_instrumentation(config)
    >>> registry.modules['telemetry'].config.service_name
    'collector'
    """

    target = registry or InstrumentationRegistry()
    combined_wrappers = unique_wrappers(_DEFAULT_WRAPPERS, wrappers)
    combined_metrics = unique_metrics(_DEFAULT_METRICS, metrics)
    target.register_module(
        _MODULE_NAME,
        config,
        wrappers=combined_wrappers,
        metrics=combined_metrics,
    )
    return target


__all__ = ["init_telemetry_instrumentation"]
