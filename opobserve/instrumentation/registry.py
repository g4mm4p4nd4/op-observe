"""Registry utilities for module specific instrumentation.

The :class:`InstrumentationRegistry` keeps track of wrappers, metric
registrations and module configurations.  The registry is intentionally
lightweight; it does not attempt to configure exporters or providers.  A
higher level orchestration layer can iterate over the registered modules
and wire the OpenTelemetry SDK accordingly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, MutableMapping, Optional, Sequence

from .config import UnifiedTelemetryConfig

Wrapper = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class MetricDefinition:
    """Describe a metric instrument to be created during initialisation."""

    name: str
    description: str
    instrument_type: str = "counter"
    unit: str = "1"
    value_type: type = float


@dataclass
class ModuleInstrumentation:
    """Container for instrumentation artefacts associated with a module."""

    config: UnifiedTelemetryConfig
    wrappers: List[Wrapper] = field(default_factory=list)
    metrics: List[MetricDefinition] = field(default_factory=list)


class InstrumentationRegistry:
    """Hold instrumentation artefacts for multiple modules.

    The registry is purposely minimal: it keeps track of the wrappers and
    metric definitions so that a later bootstrap phase can configure the
    OpenTelemetry SDK.  The class also stores a copy of the configuration
    used by each module which makes the final pipeline reproducible.

    Examples
    --------
    >>> from opobserve.instrumentation.config import UnifiedTelemetryConfig
    >>> config = UnifiedTelemetryConfig(service_name="demo")
    >>> registry = InstrumentationRegistry()
    >>> registry.register_module("observability", config)
    >>> sorted(registry.modules)
    ['observability']
    """

    def __init__(self) -> None:
        self._modules: Dict[str, ModuleInstrumentation] = {}

    @property
    def modules(self) -> MutableMapping[str, ModuleInstrumentation]:
        """Return a mutable view of the registered modules."""

        return self._modules

    def register_module(
        self,
        module: str,
        config: UnifiedTelemetryConfig,
        wrappers: Optional[Sequence[Wrapper]] = None,
        metrics: Optional[Sequence[MetricDefinition]] = None,
    ) -> None:
        """Register instrumentation metadata for ``module``.

        Existing entries are overwritten which allows reconfiguration of a
        module if required by the runtime environment.  Wrappers and
        metrics are stored in insertion order which simplifies testing and
        traceability.
        """

        entry = ModuleInstrumentation(config=config)
        if wrappers:
            entry.wrappers.extend(wrappers)
        if metrics:
            entry.metrics.extend(metrics)
        self._modules[module] = entry

    def extend_wrappers(self, module: str, wrappers: Iterable[Wrapper]) -> None:
        """Append wrappers to a registered module.

        Raises
        ------
        KeyError
            If the module is unknown.
        """

        try:
            entry = self._modules[module]
        except KeyError as exc:  # pragma: no cover - defensive
            raise KeyError(f"module '{module}' has not been registered") from exc
        entry.wrappers.extend(wrappers)

    def extend_metrics(self, module: str, metrics: Iterable[MetricDefinition]) -> None:
        """Append metric definitions to a registered module.

        Raises
        ------
        KeyError
            If the module is unknown.
        """

        try:
            entry = self._modules[module]
        except KeyError as exc:  # pragma: no cover - defensive
            raise KeyError(f"module '{module}' has not been registered") from exc
        entry.metrics.extend(metrics)

    def get_module(self, module: str) -> ModuleInstrumentation:
        """Return the :class:`ModuleInstrumentation` for ``module``.

        The returned instance is the live entry stored in the registry.  It
        can therefore be mutated by callers that need to refine
        instrumentation artefacts after the initial bootstrap.
        """

        return self._modules[module]


__all__ = [
    "MetricDefinition",
    "ModuleInstrumentation",
    "InstrumentationRegistry",
]
