"""Configuration primitives for OpenTelemetry instrumentation.

The :class:`UnifiedTelemetryConfig` data class captures the essential
settings required for wiring OpenTelemetry tracing and metrics across the
platform.  The object keeps the configuration serialisable and easy to
share between modules, while providing helpers to derive OpenTelemetry
resource attributes.

Examples
--------
>>> from opobserve.instrumentation.config import UnifiedTelemetryConfig
>>> config = UnifiedTelemetryConfig(service_name="guarded-rag", environment="dev")
>>> sorted(config.resource_attributes_for().items())
[('deployment.environment', 'dev'), ('service.name', 'guarded-rag')]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional


@dataclass(frozen=True)
class UnifiedTelemetryConfig:
    """Common OpenTelemetry settings shared across subsystems.

    Parameters
    ----------
    service_name:
        Logical name of the instrumented service or workload.  This is
        mapped to the standard ``service.name`` resource attribute.
    environment:
        Deployment environment label (``production``, ``staging``,
        ``dev``…).  Defaults to ``"production"`` following common
        OpenTelemetry conventions.
    tracing_endpoint:
        Optional OTLP/HTTP or OTLP/gRPC endpoint used for tracing
        exports.  The value is stored without validation so that callers
        can decide how to interpret it when creating exporters.
    metrics_endpoint:
        Optional endpoint dedicated to metric exports.  When omitted the
        tracing endpoint may be reused.
    log_endpoint:
        Optional endpoint for log shipping when the application enables
        OpenTelemetry logs.
    resource_attributes:
        Extra resource attributes merged with the automatically provided
        service metadata.  Values must be JSON serialisable to ease
        propagation through config stores.
    sampling_ratio:
        Fraction of traces that should be sampled by default.  The value
        is clamped to the ``[0.0, 1.0]`` range on initialisation.
    """

    service_name: str
    environment: str = "production"
    tracing_endpoint: Optional[str] = None
    metrics_endpoint: Optional[str] = None
    log_endpoint: Optional[str] = None
    resource_attributes: Mapping[str, Any] = field(default_factory=dict)
    sampling_ratio: float = 1.0

    def __post_init__(self) -> None:  # pragma: no cover - handled in ``with``
        object.__setattr__(self, "sampling_ratio", _clamp(self.sampling_ratio, 0.0, 1.0))

    def resource_attributes_for(self, module: Optional[str] = None) -> Dict[str, Any]:
        """Compute OpenTelemetry resource attributes for a module.

        Parameters
        ----------
        module:
            Optional module label, stored under the custom attribute
            ``opobserve.module`` for easier filtering in observability
            back-ends.

        Returns
        -------
        dict
            A copy of the resource attributes ready to be consumed by
            OpenTelemetry SDK helpers.
        """

        base: Dict[str, Any] = {
            "service.name": self.service_name,
            "deployment.environment": self.environment,
        }
        if module:
            base["opobserve.module"] = module

        base.update(self.resource_attributes)
        return base

    def into_dict(self) -> Dict[str, Any]:
        """Serialise the configuration to a dictionary.

        The resulting mapping is convenient when passing configuration to
        other services through JSON or when logging the effective setup.
        A copy is returned so callers can mutate it without affecting the
        instance.
        """

        data: Dict[str, Any] = {
            "service_name": self.service_name,
            "environment": self.environment,
            "tracing_endpoint": self.tracing_endpoint,
            "metrics_endpoint": self.metrics_endpoint,
            "log_endpoint": self.log_endpoint,
            "resource_attributes": dict(self.resource_attributes),
            "sampling_ratio": self.sampling_ratio,
        }
        return data

    def merge_resource_attributes(self, overrides: Mapping[str, Any]) -> "UnifiedTelemetryConfig":
        """Return a copy with additional resource attributes.

        The method does not mutate the current instance; instead it
        produces a new :class:`UnifiedTelemetryConfig` with merged
        attributes.  User-provided keys take precedence over the existing
        ones.
        """

        merged: Dict[str, Any] = dict(self.resource_attributes)
        merged.update(overrides)
        return UnifiedTelemetryConfig(
            service_name=self.service_name,
            environment=self.environment,
            tracing_endpoint=self.tracing_endpoint,
            metrics_endpoint=self.metrics_endpoint,
            log_endpoint=self.log_endpoint,
            resource_attributes=merged,
            sampling_ratio=self.sampling_ratio,
        )


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp ``value`` to the inclusive ``[low, high]`` interval."""

    if value < low:
        return low
    if value > high:
        return high
    return value


__all__ = ["UnifiedTelemetryConfig"]
