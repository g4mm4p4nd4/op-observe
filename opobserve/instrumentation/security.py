"""Security and guardrail instrumentation helpers."""

from __future__ import annotations

from typing import Optional, Sequence

from .config import UnifiedTelemetryConfig
from .registry import InstrumentationRegistry, MetricDefinition, Wrapper
from .utils import unique_metrics, unique_wrappers
from .wrappers import annotate_wrapper, attach_metadata

_MODULE_NAME = "security"

_DEFAULT_WRAPPERS: Sequence[Wrapper] = (
    annotate_wrapper("otel_span", f"{_MODULE_NAME}.guard"),
    attach_metadata(otel_scope=_MODULE_NAME, security_signal="guardrail"),
)

_DEFAULT_METRICS: Sequence[MetricDefinition] = (
    MetricDefinition(
        name="security_guard_failures_total",
        description="Count of guardrail failures detected",
        instrument_type="counter",
        unit="1",
        value_type=int,
    ),
    MetricDefinition(
        name="security_policy_violations_total",
        description="Total policy violations flagged by automated checks",
        instrument_type="counter",
        unit="1",
        value_type=int,
    ),
)


def init_security_instrumentation(
    config: UnifiedTelemetryConfig,
    registry: Optional[InstrumentationRegistry] = None,
    wrappers: Optional[Sequence[Wrapper]] = None,
    metrics: Optional[Sequence[MetricDefinition]] = None,
) -> InstrumentationRegistry:
    """Register security instrumentation metadata.

    Examples
    --------
    >>> from opobserve.instrumentation import UnifiedTelemetryConfig
    >>> config = UnifiedTelemetryConfig(service_name="guardian")
    >>> registry = init_security_instrumentation(config)
    >>> [metric.name for metric in registry.modules['security'].metrics]
    ['security_guard_failures_total', 'security_policy_violations_total']
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


__all__ = ["init_security_instrumentation"]
