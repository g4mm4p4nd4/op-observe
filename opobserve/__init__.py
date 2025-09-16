"""Top-level package for OP-Observe instrumentation utilities.

This module exposes convenience imports for the instrumentation
initialisation helpers implemented in :mod:`opobserve.instrumentation`.
"""

from .instrumentation.config import UnifiedTelemetryConfig
from .instrumentation.registry import MetricDefinition, InstrumentationRegistry
from .instrumentation.observability import init_observability_instrumentation
from .instrumentation.retrieval import init_retrieval_instrumentation
from .instrumentation.security import init_security_instrumentation
from .instrumentation.telemetry import init_telemetry_instrumentation

__all__ = [
    "UnifiedTelemetryConfig",
    "MetricDefinition",
    "InstrumentationRegistry",
    "init_observability_instrumentation",
    "init_retrieval_instrumentation",
    "init_security_instrumentation",
    "init_telemetry_instrumentation",
]
