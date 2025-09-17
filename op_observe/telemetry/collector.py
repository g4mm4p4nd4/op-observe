"""Helpers for building OpenTelemetry collector configuration."""
from __future__ import annotations

from typing import Dict, Iterable, Mapping, MutableMapping

from .exporters import ClickHouseExporterConfig, PrometheusExporterConfig


DEFAULT_PROCESSORS = {
    "batch": {
        "timeout": "5s",
        "send_batch_size": 512,
    },
}


def _merge_dict(into: MutableMapping[str, object], other: Mapping[str, object]) -> None:
    for key, value in other.items():
        if key not in into:
            into[key] = value
            continue
        current = into[key]
        if isinstance(current, dict) and isinstance(value, Mapping):
            _merge_dict(current, value)
        else:
            into[key] = value


def build_collector_config(
    prometheus: PrometheusExporterConfig,
    clickhouse: ClickHouseExporterConfig,
    receivers: Iterable[str] | None = None,
) -> Dict[str, object]:
    """Return a complete OpenTelemetry collector configuration.

    Parameters
    ----------
    prometheus:
        Settings for the Prometheus exporter.
    clickhouse:
        Settings for the ClickHouse exporter.
    receivers:
        Optional iterable of receiver names to enable.  If omitted the
        default OTLP gRPC/HTTP receivers are configured.
    """

    receiver_block: Dict[str, object]
    if receivers:
        receiver_block = {name: {} for name in receivers}
    else:
        receiver_block = {
            "otlp": {
                "protocols": {
                    "grpc": {},
                    "http": {},
                }
            }
        }

    exporters: Dict[str, object] = {}
    _merge_dict(exporters, prometheus.otel_exporter())
    _merge_dict(exporters, clickhouse.otel_exporter())

    pipelines = {
        "metrics": {
            "receivers": sorted(receiver_block.keys()),
            "processors": sorted(DEFAULT_PROCESSORS.keys()),
            "exporters": sorted(exporters.keys()),
        }
    }

    return {
        "receivers": receiver_block,
        "processors": DEFAULT_PROCESSORS,
        "exporters": exporters,
        "service": {
            "pipelines": pipelines,
        },
    }
