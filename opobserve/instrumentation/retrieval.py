"""Retrieval subsystem instrumentation helpers."""

from __future__ import annotations

from typing import Optional, Sequence

from .config import UnifiedTelemetryConfig
from .registry import InstrumentationRegistry, MetricDefinition, Wrapper
from .utils import unique_metrics, unique_wrappers
from .wrappers import annotate_wrapper, attach_metadata

_MODULE_NAME = "retrieval"

_DEFAULT_WRAPPERS: Sequence[Wrapper] = (
    annotate_wrapper("otel_span", f"{_MODULE_NAME}.query"),
    attach_metadata(otel_scope=_MODULE_NAME, retrieval_stage="vector-search"),
)

_DEFAULT_METRICS: Sequence[MetricDefinition] = (
    MetricDefinition(
        name="retrieval_queries_total",
        description="Number of retrieval queries executed",
        instrument_type="counter",
        unit="1",
        value_type=int,
    ),
    MetricDefinition(
        name="retrieval_latency_seconds",
        description="Histogram of retrieval latencies",
        instrument_type="histogram",
        unit="s",
        value_type=float,
    ),
)


def init_retrieval_instrumentation(
    config: UnifiedTelemetryConfig,
    registry: Optional[InstrumentationRegistry] = None,
    wrappers: Optional[Sequence[Wrapper]] = None,
    metrics: Optional[Sequence[MetricDefinition]] = None,
) -> InstrumentationRegistry:
    """Register retrieval instrumentation metadata.

    The helper mirrors :func:`init_observability_instrumentation` but uses
    retrieval specific defaults.  Custom wrappers and metrics are merged
    with the defaults using a stable deduplication strategy to avoid
    repeated registrations when the function is invoked multiple times.

    Examples
    --------
    >>> from opobserve.instrumentation import UnifiedTelemetryConfig
    >>> config = UnifiedTelemetryConfig(service_name="retriever")
    >>> registry = init_retrieval_instrumentation(config)
    >>> registry.modules['retrieval'].wrappers[0].__name__
    'decorator'
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


__all__ = ["init_retrieval_instrumentation"]
