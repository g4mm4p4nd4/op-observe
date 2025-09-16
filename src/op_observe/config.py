"""Configuration helpers for OP-Observe telemetry exporters."""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Mapping


_truthy = {"1", "true", "yes", "on"}


def _bool_env(var_name: str, default: bool) -> bool:
    value = os.getenv(var_name)
    if value is None:
        return default
    return value.strip().lower() in _truthy


@dataclass(frozen=True)
class TelemetryConfig:
    """Runtime configuration for the OpenTelemetry exporters.

    The configuration uses environment variables so that deployments can be
    tailored without modifying code. Defaults are designed for the local
    docker-compose environment that accompanies this repository.
    """

    service_name: str = field(default_factory=lambda: os.getenv("OTEL_SERVICE_NAME", "op-observe-service"))
    otlp_endpoint: str = field(default_factory=lambda: os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318"))
    otlp_headers: Mapping[str, str] | None = None
    insecure: bool = field(default_factory=lambda: _bool_env("OTEL_EXPORTER_OTLP_INSECURE", True))
    metric_export_interval: float = field(default_factory=lambda: float(os.getenv("OTEL_METRIC_EXPORT_INTERVAL", "5")))

    @staticmethod
    def from_env() -> "TelemetryConfig":
        """Instantiate :class:`TelemetryConfig` from environment variables."""

        headers_string = os.getenv("OTEL_EXPORTER_OTLP_HEADERS")
        headers: Mapping[str, str] | None = None
        if headers_string:
            parsed_headers: dict[str, str] = {}
            for pair in headers_string.split(","):
                if not pair:
                    continue
                key, _, value = pair.partition("=")
                parsed_headers[key.strip()] = value.strip()
            headers = parsed_headers
        return TelemetryConfig(otlp_headers=headers)

    def to_traces_endpoint(self) -> str:
        endpoint = self.otlp_endpoint.rstrip("/")
        return f"{endpoint}/v1/traces"

    def to_metrics_endpoint(self) -> str:
        endpoint = self.otlp_endpoint.rstrip("/")
        return f"{endpoint}/v1/metrics"
