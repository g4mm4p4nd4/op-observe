"""Metrics instrumentation helpers for guardrail verdicts and critic scores.

The helpers in this module provide a thin wrapper around OpenTelemetry meters
and Prometheus-compatible collectors. The implementation prefers the real
OpenTelemetry and :mod:`prometheus_client` packages when they are available at
runtime but gracefully falls back to in-memory collectors so unit tests can run
without optional dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Dict, Iterable, Mapping, MutableMapping, Optional, Tuple

try:  # pragma: no cover - optional dependency
    from opentelemetry import metrics as otel_metrics
    from opentelemetry.sdk.metrics import MeterProvider as OtelMeterProvider
    try:  # pragma: no cover - optional exporter
        from opentelemetry.exporter.prometheus import PrometheusMetricReader
    except Exception:  # pragma: no cover - best-effort importer
        PrometheusMetricReader = None
except Exception:  # pragma: no cover - optional dependency
    otel_metrics = None
    OtelMeterProvider = None
    PrometheusMetricReader = None

try:  # pragma: no cover - optional dependency
    from prometheus_client import (
        CollectorRegistry as PromCollectorRegistry,
        Counter as PromCounter,
        Histogram as PromHistogram,
        REGISTRY as PROMETHEUS_DEFAULT_REGISTRY,
    )
except Exception:  # pragma: no cover - optional dependency
    PromCollectorRegistry = None
    PromCounter = None
    PromHistogram = None
    PROMETHEUS_DEFAULT_REGISTRY = None

GuardFailureKey = Tuple["GuardrailDirection", "GuardrailSeverity"]


class GuardrailDirection(str, Enum):
    """Direction of the guardrail check."""

    INPUT = "input"
    OUTPUT = "output"


class GuardrailSeverity(str, Enum):
    """Severity level emitted by guardrail verdicts."""

    S0 = "S0"
    S1 = "S1"


@dataclass(frozen=True)
class CriticScoreSnapshot:
    """Snapshot of histogram statistics for critic score observations."""

    count: int
    total: float
    buckets: Mapping[float, int]


class _FallbackCounterInstrument:
    """In-memory OpenTelemetry counter fallback used in tests."""

    def __init__(self) -> None:
        self._records: list[Tuple[float, Mapping[str, str]]] = []
        self._lock = Lock()

    def add(self, amount: float, attributes: Optional[Mapping[str, str]] = None) -> None:
        with self._lock:
            self._records.append((amount, dict(attributes or {})))

    def iter_records(self) -> Iterable[Tuple[float, Mapping[str, str]]]:
        with self._lock:
            yield from list(self._records)


class _FallbackHistogramInstrument:
    """In-memory OpenTelemetry histogram fallback used in tests."""

    def __init__(self) -> None:
        self._records: list[Tuple[float, Mapping[str, str]]] = []
        self._lock = Lock()

    def record(self, value: float, attributes: Optional[Mapping[str, str]] = None) -> None:
        with self._lock:
            self._records.append((value, dict(attributes or {})))

    def iter_records(self) -> Iterable[Tuple[float, Mapping[str, str]]]:
        with self._lock:
            yield from list(self._records)


class _FallbackMeter:
    """Minimal meter that mimics the subset of the OpenTelemetry API we need."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: Dict[str, _FallbackCounterInstrument] = {}
        self._histograms: Dict[str, _FallbackHistogramInstrument] = {}

    def create_counter(self, name: str, **_: object) -> _FallbackCounterInstrument:
        with self._lock:
            counter = self._counters.get(name)
            if counter is None:
                counter = _FallbackCounterInstrument()
                self._counters[name] = counter
            return counter

    def create_histogram(self, name: str, **_: object) -> _FallbackHistogramInstrument:
        with self._lock:
            histogram = self._histograms.get(name)
            if histogram is None:
                histogram = _FallbackHistogramInstrument()
                self._histograms[name] = histogram
            return histogram


class _FallbackMeterProvider:
    """Simple provider mirroring :class:`opentelemetry.metrics.MeterProvider`."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._meters: Dict[str, _FallbackMeter] = {}

    def get_meter(
        self, name: str, version: Optional[str] = None, schema_url: Optional[str] = None
    ) -> _FallbackMeter:
        _ = version, schema_url  # Unused but kept for API parity.
        with self._lock:
            meter = self._meters.get(name)
            if meter is None:
                meter = _FallbackMeter()
                self._meters[name] = meter
            return meter


def _create_meter_provider() -> object:
    """Return a meter provider backed by OpenTelemetry when possible."""

    if otel_metrics is None or OtelMeterProvider is None:
        return _FallbackMeterProvider()

    if PrometheusMetricReader is not None and PromCollectorRegistry is not None:
        registry = PROMETHEUS_DEFAULT_REGISTRY or PromCollectorRegistry()
        reader = PrometheusMetricReader(registry=registry)
        provider = OtelMeterProvider(metric_readers=[reader])
    else:  # pragma: no cover - exercised only when OTEL is available without exporter
        provider = OtelMeterProvider()

    otel_metrics.set_meter_provider(provider)
    return otel_metrics.get_meter_provider()


_METER_PROVIDER = _create_meter_provider()


class _PrometheusCollector:
    """Adapter for Prometheus counters and histograms."""

    def __init__(self, registry: Optional[object] = None) -> None:
        self._registry = registry
        self._lock = Lock()
        if PromCollectorRegistry is not None and registry is None:
            self._registry = PROMETHEUS_DEFAULT_REGISTRY
        if self._registry is None:
            self._registry = MemoryCollectorRegistry()
        self._counters: Dict[str, _CounterWrapper] = {}
        self._histograms: Dict[str, _HistogramWrapper] = {}

    @property
    def registry(self) -> object:
        return self._registry

    def counter(
        self, name: str, description: str, label_names: Iterable[str]
    ) -> "_CounterWrapper":
        with self._lock:
            wrapper = self._counters.get(name)
            if wrapper is None:
                wrapper = _CounterWrapper(name, description, tuple(label_names), self._registry)
                self._counters[name] = wrapper
            return wrapper

    def histogram(
        self,
        name: str,
        description: str,
        label_names: Iterable[str],
        buckets: Iterable[float],
    ) -> "_HistogramWrapper":
        with self._lock:
            wrapper = self._histograms.get(name)
            if wrapper is None:
                wrapper = _HistogramWrapper(
                    name, description, tuple(label_names), tuple(buckets), self._registry
                )
                self._histograms[name] = wrapper
            return wrapper


class _CounterWrapper:
    """Wrap a Prometheus counter while offering an inspectable fallback."""

    def __init__(
        self,
        name: str,
        description: str,
        label_names: Tuple[str, ...],
        registry: object,
    ) -> None:
        self._name = name
        self._labels = label_names
        self._lock = Lock()
        self._values: Dict[Tuple[str, ...], float] = {}

        if (
            PromCounter is not None
            and PromCollectorRegistry is not None
            and isinstance(registry, PromCollectorRegistry)
        ):
            try:
                self._metric = PromCounter(
                    name,
                    description,
                    label_names,
                    registry=registry,
                )
            except ValueError:  # pragma: no cover - reused metric name
                self._metric = registry._names_to_collectors[name]
        else:
            if isinstance(registry, MemoryCollectorRegistry):
                try:
                    self._metric = MemoryCounter(name, description, label_names, registry)
                except ValueError:
                    existing = registry.get_counter(name)
                    if existing is None:  # pragma: no cover - defensive fallback
                        self._metric = MemoryCounter(name, description, label_names, registry)
                    else:
                        self._metric = existing
            else:
                memory_registry = MemoryCollectorRegistry()
                self._metric = MemoryCounter(name, description, label_names, memory_registry)

    def inc(self, labels: Mapping[str, str], amount: float = 1.0) -> None:
        ordered = tuple(str(labels[name]) for name in self._labels)
        with self._lock:
            self._values[ordered] = self._values.get(ordered, 0.0) + amount
        if hasattr(self._metric, "labels"):
            self._metric.labels(**{k: str(labels[k]) for k in self._labels}).inc(amount)
        else:  # pragma: no cover - fallback memory implementation
            self._metric.inc(labels, amount)

    def snapshot(self) -> Mapping[Tuple[str, ...], float]:
        with self._lock:
            return dict(self._values)


class _HistogramWrapper:
    """Wrap a Prometheus histogram while keeping an in-memory mirror."""

    def __init__(
        self,
        name: str,
        description: str,
        label_names: Tuple[str, ...],
        buckets: Tuple[float, ...],
        registry: object,
    ) -> None:
        self._name = name
        self._labels = label_names
        self._buckets = buckets
        self._lock = Lock()
        self._values: Dict[Tuple[str, ...], list[float]] = {}

        if (
            PromHistogram is not None
            and PromCollectorRegistry is not None
            and isinstance(registry, PromCollectorRegistry)
        ):
            try:
                self._metric = PromHistogram(
                    name,
                    description,
                    label_names,
                    registry=registry,
                    buckets=list(buckets),
                )
            except ValueError:  # pragma: no cover - reused metric name
                self._metric = registry._names_to_collectors[name]
        else:
            if isinstance(registry, MemoryCollectorRegistry):
                try:
                    self._metric = MemoryHistogram(
                        name,
                        description,
                        label_names,
                        buckets,
                        registry,
                    )
                except ValueError:
                    existing = registry.get_histogram(name)
                    if existing is None:  # pragma: no cover - defensive fallback
                        self._metric = MemoryHistogram(
                            name,
                            description,
                            label_names,
                            buckets,
                            registry,
                        )
                    else:
                        self._metric = existing
            else:
                memory_registry = MemoryCollectorRegistry()
                self._metric = MemoryHistogram(
                    name,
                    description,
                    label_names,
                    buckets,
                    memory_registry,
                )

    def observe(self, labels: Mapping[str, str], value: float) -> None:
        ordered = tuple(str(labels[name]) for name in self._labels)
        with self._lock:
            self._values.setdefault(ordered, []).append(value)
        if hasattr(self._metric, "labels"):
            self._metric.labels(**{k: str(labels[k]) for k in self._labels}).observe(value)
        else:  # pragma: no cover - fallback memory implementation
            self._metric.observe(labels, value)

    def snapshot(self) -> Mapping[Tuple[str, ...], Tuple[int, float, Mapping[float, int]]]:
        with self._lock:
            output: Dict[Tuple[str, ...], Tuple[int, float, Mapping[float, int]]] = {}
            for label_tuple, values in self._values.items():
                count = len(values)
                total = float(sum(values))
                bucket_counts: MutableMapping[float, int] = {b: 0 for b in self._buckets}
                for item in values:
                    for boundary in self._buckets:
                        if item <= boundary:
                            bucket_counts[boundary] += 1
                    # Implicitly skip boundaries that are smaller than the observation
                output[label_tuple] = (count, total, dict(bucket_counts))
            return output


class MemoryCollectorRegistry:
    """Very small in-memory registry used when :mod:`prometheus_client` is absent."""

    def __init__(self) -> None:
        self._counters: Dict[str, MemoryCounter] = {}
        self._histograms: Dict[str, MemoryHistogram] = {}

    def get_counter(self, name: str) -> Optional["MemoryCounter"]:
        return self._counters.get(name)

    def get_histogram(self, name: str) -> Optional["MemoryHistogram"]:
        return self._histograms.get(name)

    def register_counter(self, metric: "MemoryCounter") -> None:
        if metric.name in self._counters:
            raise ValueError(f"Counter {metric.name} already registered")
        self._counters[metric.name] = metric

    def register_histogram(self, metric: "MemoryHistogram") -> None:
        if metric.name in self._histograms:
            raise ValueError(f"Histogram {metric.name} already registered")
        self._histograms[metric.name] = metric


class MemoryCounter:
    """Fallback counter mirroring the :mod:`prometheus_client` API."""

    def __init__(
        self,
        name: str,
        description: str,
        label_names: Tuple[str, ...],
        registry: MemoryCollectorRegistry,
    ) -> None:
        self.name = name
        self.description = description
        self._labels = label_names
        self._lock = Lock()
        self._values: Dict[Tuple[str, ...], float] = {}
        self._registry = registry
        registry.register_counter(self)

    def labels(self, **labels: str) -> "MemoryCounterChild":
        ordered = tuple(str(labels[name]) for name in self._labels)
        return MemoryCounterChild(self, ordered)

    def _inc(self, label_values: Tuple[str, ...], amount: float) -> None:
        with self._lock:
            self._values[label_values] = self._values.get(label_values, 0.0) + amount

    def collect(self) -> Mapping[Tuple[str, ...], float]:
        with self._lock:
            return dict(self._values)

    def inc(self, labels: Mapping[str, str], amount: float) -> None:
        ordered = tuple(str(labels[name]) for name in self._labels)
        self._inc(ordered, amount)


class MemoryCounterChild:
    def __init__(self, parent: MemoryCounter, label_values: Tuple[str, ...]) -> None:
        self._parent = parent
        self._label_values = label_values

    def inc(self, amount: float = 1.0) -> None:
        self._parent._inc(self._label_values, amount)


class MemoryHistogram:
    """Fallback histogram mirroring the :mod:`prometheus_client` API."""

    def __init__(
        self,
        name: str,
        description: str,
        label_names: Tuple[str, ...],
        buckets: Tuple[float, ...],
        registry: MemoryCollectorRegistry,
    ) -> None:
        self.name = name
        self.description = description
        self._labels = label_names
        self._buckets = buckets
        self._lock = Lock()
        self._values: Dict[Tuple[str, ...], list[float]] = {}
        self._registry = registry
        registry.register_histogram(self)

    def labels(self, **labels: str) -> "MemoryHistogramChild":
        ordered = tuple(str(labels[name]) for name in self._labels)
        return MemoryHistogramChild(self, ordered)

    def _observe(self, label_values: Tuple[str, ...], value: float) -> None:
        with self._lock:
            self._values.setdefault(label_values, []).append(value)

    def collect(self) -> Mapping[Tuple[str, ...], Tuple[int, float, Mapping[float, int]]]:
        with self._lock:
            output: Dict[Tuple[str, ...], Tuple[int, float, Mapping[float, int]]] = {}
            for label_values, values in self._values.items():
                count = len(values)
                total = float(sum(values))
                bucket_counts: MutableMapping[float, int] = {b: 0 for b in self._buckets}
                for item in values:
                    for boundary in self._buckets:
                        if item <= boundary:
                            bucket_counts[boundary] += 1
                output[label_values] = (count, total, dict(bucket_counts))
            return output

    def observe(self, labels: Mapping[str, str], value: float) -> None:
        ordered = tuple(str(labels[name]) for name in self._labels)
        self._observe(ordered, value)


class MemoryHistogramChild:
    def __init__(self, parent: MemoryHistogram, label_values: Tuple[str, ...]) -> None:
        self._parent = parent
        self._label_values = label_values

    def observe(self, value: float) -> None:
        self._parent._observe(self._label_values, value)


def create_memory_registry() -> MemoryCollectorRegistry:
    """Return an isolated in-memory Prometheus registry for tests."""

    return MemoryCollectorRegistry()


class GuardrailMetrics:
    """Coordinate OpenTelemetry + Prometheus metrics for guardrails."""

    _DEFAULT_BUCKETS = (0.0, 0.25, 0.5, 0.75, 0.9, 0.95, 1.0, float("inf"))

    def __init__(
        self,
        *,
        registry: Optional[object] = None,
        buckets: Optional[Iterable[float]] = None,
    ) -> None:
        provider = _METER_PROVIDER
        meter = provider.get_meter("op_observe.guardrails") if hasattr(provider, "get_meter") else _FallbackMeter()
        self._guard_counter = meter.create_counter(
            "guardrail_failures_total",
            unit="1",
            description="Number of guardrail failures partitioned by direction and severity",
        )
        self._critic_histogram = meter.create_histogram(
            "llm_critic_score",
            unit="1",
            description="Distribution of LLM-Critic evaluation scores",
        )

        self._prometheus = _PrometheusCollector(registry)
        self._prom_counter = self._prometheus.counter(
            "guardrail_failures_total",
            "Number of guardrail failures partitioned by direction and severity",
            ("direction", "severity"),
        )
        bucket_list = tuple(sorted(set(buckets or self._DEFAULT_BUCKETS)))
        if bucket_list[-1] != float("inf"):
            bucket_list = (*bucket_list, float("inf"))
        self._bucket_boundaries = bucket_list
        self._prom_histogram = self._prometheus.histogram(
            "llm_critic_score",
            "Distribution of LLM-Critic evaluation scores",
            ("verdict",),
            bucket_list,
        )

        self._lock = Lock()
        self._guard_totals: Dict[GuardFailureKey, int] = {}
        self._critic_count = 0
        self._critic_sum = 0.0
        self._critic_buckets: Dict[float, int] = {boundary: 0 for boundary in self._bucket_boundaries}

    @property
    def registry(self) -> object:
        """Return the Prometheus registry backing this metrics instance."""

        return self._prometheus.registry

    def record_guard_failure(
        self,
        direction: GuardrailDirection,
        severity: GuardrailSeverity,
        *,
        attributes: Optional[Mapping[str, str]] = None,
    ) -> None:
        """Record a guardrail failure for the given direction and severity."""

        attrs = {"direction": direction.value, "severity": severity.value}
        attrs.update({k: str(v) for k, v in (attributes or {}).items()})
        self._guard_counter.add(1, attrs)
        self._prom_counter.inc({"direction": attrs["direction"], "severity": attrs["severity"]})
        with self._lock:
            key = (direction, severity)
            self._guard_totals[key] = self._guard_totals.get(key, 0) + 1

    def record_input_guard_failure(
        self, severity: GuardrailSeverity, *, attributes: Optional[Mapping[str, str]] = None
    ) -> None:
        """Shortcut for :meth:`record_guard_failure` scoped to input checks."""

        self.record_guard_failure(GuardrailDirection.INPUT, severity, attributes=attributes)

    def record_output_guard_failure(
        self, severity: GuardrailSeverity, *, attributes: Optional[Mapping[str, str]] = None
    ) -> None:
        """Shortcut for :meth:`record_guard_failure` scoped to output checks."""

        self.record_guard_failure(GuardrailDirection.OUTPUT, severity, attributes=attributes)

    def record_guard_verdict(
        self,
        passed: bool,
        direction: GuardrailDirection,
        severity: GuardrailSeverity,
        *,
        attributes: Optional[Mapping[str, str]] = None,
    ) -> None:
        """Record a full guardrail verdict.

        Successful verdicts update OpenTelemetry spans but do not increment failure
        counters. Failures increment the counter and histogram instrumentation.
        """

        attrs = dict(attributes or {})
        if not passed:
            self.record_guard_failure(direction, severity, attributes=attrs)

    def record_critic_score(
        self,
        score: float,
        *,
        verdict: str = "unknown",
        attributes: Optional[Mapping[str, str]] = None,
    ) -> None:
        """Record an LLM-Critic score into the histogram."""

        attrs = {"verdict": str(verdict)}
        attrs.update({k: str(v) for k, v in (attributes or {}).items()})
        self._critic_histogram.record(score, attrs)
        self._prom_histogram.observe({"verdict": attrs["verdict"]}, score)
        with self._lock:
            self._critic_count += 1
            self._critic_sum += float(score)
            for boundary in self._bucket_boundaries:
                if score <= boundary:
                    self._critic_buckets[boundary] = self._critic_buckets.get(boundary, 0) + 1

    def guard_failure_totals(self) -> Mapping[GuardFailureKey, int]:
        """Return aggregated guard failure counts for inspection."""

        with self._lock:
            return dict(self._guard_totals)

    def critic_score_snapshot(self) -> CriticScoreSnapshot:
        """Return a snapshot of the critic score histogram."""

        with self._lock:
            return CriticScoreSnapshot(
                count=self._critic_count,
                total=self._critic_sum,
                buckets=dict(self._critic_buckets),
            )


_default_metrics = GuardrailMetrics()


def get_guardrail_metrics() -> GuardrailMetrics:
    """Return the shared guardrail metrics instance."""

    return _default_metrics


def record_guard_failure(
    direction: GuardrailDirection,
    severity: GuardrailSeverity,
    *,
    attributes: Optional[Mapping[str, str]] = None,
) -> None:
    """Record a guardrail failure via the shared metrics instance."""

    _default_metrics.record_guard_failure(direction, severity, attributes=attributes)


def record_critic_score(
    score: float,
    *,
    verdict: str = "unknown",
    attributes: Optional[Mapping[str, str]] = None,
) -> None:
    """Record a critic score via the shared metrics instance."""

    _default_metrics.record_critic_score(score, verdict=verdict, attributes=attributes)


# Provide a friendly alias used by :mod:`op_observe.telemetry.__init__`.
default_guardrail_metrics = _default_metrics

