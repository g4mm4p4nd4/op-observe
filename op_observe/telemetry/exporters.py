"""Exporter configuration helpers.

The test-suite does not rely on real network connectivity.  Instead of
instantiating the OpenTelemetry collector, we construct configuration
snippets that mirror what the collector expects.  These snippets can be
serialised to YAML by downstream tooling.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional


@dataclass(frozen=True)
class PrometheusExporterConfig:
    """Configuration for the OpenTelemetry Prometheus exporter."""

    endpoint: str = "0.0.0.0"
    port: int = 9464
    metric_namespace: str = "op_observe"
    collectors: Mapping[str, str] = field(
        default_factory=lambda: {
            "scrape_interval": "15s",
            "scrape_timeout": "10s",
        }
    )

    def otel_exporter(self) -> Dict[str, object]:
        """Return a collector configuration fragment for Prometheus."""

        return {
            "prometheus": {
                "endpoint": f"{self.endpoint}:{self.port}",
                "namespace": self.metric_namespace,
                "controller": dict(self.collectors),
            }
        }


@dataclass(frozen=True)
class ClickHouseExporterConfig:
    """Configuration for exporting metrics to ClickHouse."""

    endpoint: str = "http://localhost:8123"
    database: str = "otel"
    table: str = "metrics"
    username: Optional[str] = None
    password: Optional[str] = None
    timeout: str = "10s"

    def otel_exporter(self) -> Dict[str, object]:
        """Return a collector configuration fragment for ClickHouse."""

        exporter = {
            "endpoint": self.endpoint,
            "database": self.database,
            "table": self.table,
            "timeout": self.timeout,
        }
        if self.username:
            exporter["username"] = self.username
        if self.password:
            exporter["password"] = self.password
        return {"clickhouse": exporter}
