"""Telemetry utilities for OP-Observe.

This module exposes convenience imports for configuring OpenTelemetry
collectors and exporting runtime metrics to Prometheus and ClickHouse.
"""

from .collector import build_collector_config
from .exporters import ClickHouseExporterConfig, PrometheusExporterConfig
from .grafana import build_guardrail_dashboard
from .metrics import MetricsRegistry

__all__ = [
    "build_collector_config",
    "ClickHouseExporterConfig",
    "PrometheusExporterConfig",
    "MetricsRegistry",
    "build_guardrail_dashboard",
]
