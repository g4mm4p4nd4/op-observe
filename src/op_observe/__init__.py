"""OP-Observe package entry point.

This module exposes high-level integration helpers for exporting telemetry
into the Phoenix UI.
"""

from .phoenix.client import EvaluationResult, PhoenixClient
from .phoenix.exporter import PhoenixExporter
from .telemetry.models import Dataset, EvaluationMetric, TelemetryBatch, TraceSpan

__all__ = [
    "Dataset",
    "EvaluationMetric",
    "EvaluationResult",
    "PhoenixClient",
    "PhoenixExporter",
    "TelemetryBatch",
    "TraceSpan",
]

__version__ = "0.1.0"
