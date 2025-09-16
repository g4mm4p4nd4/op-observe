"""Instrumentation utilities for OP-Observe."""

from .config import UnifiedTelemetryConfig
from .observability import init_observability_instrumentation
from .registry import InstrumentationRegistry, MetricDefinition, ModuleInstrumentation
from .retrieval import init_retrieval_instrumentation
from .security import init_security_instrumentation
from .telemetry import init_telemetry_instrumentation
from .utils import unique_metrics, unique_wrappers
from .wrappers import annotate_wrapper, attach_metadata

__all__ = [
    "UnifiedTelemetryConfig",
    "InstrumentationRegistry",
    "MetricDefinition",
    "ModuleInstrumentation",
    "init_observability_instrumentation",
    "init_retrieval_instrumentation",
    "init_security_instrumentation",
    "init_telemetry_instrumentation",
    "unique_metrics",
    "unique_wrappers",
    "annotate_wrapper",
    "attach_metadata",
]
