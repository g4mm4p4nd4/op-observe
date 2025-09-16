"""Observability module instrumentation bootstrap."""

from __future__ import annotations

from typing import Optional, Sequence

from .config import UnifiedTelemetryConfig
from .registry import InstrumentationRegistry, MetricDefinition, Wrapper
from .utils import unique_metrics, unique_wrappers
from .wrappers import annotate_wrapper, attach_metadata

_MODULE_NAME = "observability"

_DEFAULT_WRAPPERS: Sequence[Wrapper] = (
    annotate_wrapper("otel_span", f"{_MODULE_NAME}.request"),
    attach_metadata(otel_signal="traces", otel_scope=_MODULE_NAME),
)

_DEFAULT_METRICS: Sequence[MetricDefinition] = (
    MetricDefinition(
        name="observability_requests_total",
        description="Total number of guardrail validated requests",
        instrument_type="counter",
        unit="1",
        value_type=int,
    ),
    MetricDefinition(
        name="observability_request_latency_seconds",
        description="Latency histogram for validated requests",
        instrument_type="histogram",
        unit="s",
        value_type=float,
    ),
)


def init_observability_instrumentation(
    config: UnifiedTelemetryConfig,
    registry: Optional[InstrumentationRegistry] = None,
    wrappers: Optional[Sequence[Wrapper]] = None,
    metrics: Optional[Sequence[MetricDefinition]] = None,
) -> InstrumentationRegistry:
    """Register observability instrumentation assets.

    The function merges custom wrappers and metric definitions with the
    module defaults and stores the resulting configuration in the provided
    :class:`InstrumentationRegistry`.  When *registry* is ``None`` a new
    instance is created and returned to the caller.

    Examples
    --------
    >>> from opobserve.instrumentation import (
    ...     UnifiedTelemetryConfig,
    ...     InstrumentationRegistry,
    ... )
    >>> config = UnifiedTelemetryConfig(service_name="observability-service")
    >>> registry = init_observability_instrumentation(config)
    >>> registry.modules['observability'].metrics[0].name
    'observability_requests_total'
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


__all__ = ["init_observability_instrumentation"]
