"""In-memory metrics registry for Prometheus and ClickHouse exports."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Mapping, MutableMapping, Tuple


LabelValues = Tuple[str, ...]
LabelDict = Dict[str, str]


class MetricError(ValueError):
    """Raised when metric labels are misconfigured."""


@dataclass
class _MetricBase:
    name: str
    description: str
    label_names: Tuple[str, ...] = ()

    def _key(self, labels: Mapping[str, str]) -> LabelValues:
        if set(labels) != set(self.label_names):
            missing = set(self.label_names) - set(labels)
            extra = set(labels) - set(self.label_names)
            problems: List[str] = []
            if missing:
                problems.append(f"missing labels: {sorted(missing)}")
            if extra:
                problems.append(f"unexpected labels: {sorted(extra)}")
            raise MetricError(
                f"labels for metric '{self.name}' invalid ({', '.join(problems)})"
            )
        return tuple(labels[name] for name in self.label_names)


@dataclass
class CounterMetric(_MetricBase):
    values: MutableMapping[LabelValues, float] = field(default_factory=dict)
    label_cache: MutableMapping[LabelValues, LabelDict] = field(default_factory=dict)

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        key = self._key(labels)
        self.values[key] = self.values.get(key, 0.0) + amount
        if key not in self.label_cache:
            self.label_cache[key] = dict(labels)


@dataclass
class GaugeMetric(_MetricBase):
    values: MutableMapping[LabelValues, float] = field(default_factory=dict)
    label_cache: MutableMapping[LabelValues, LabelDict] = field(default_factory=dict)

    def set(self, value: float, **labels: str) -> None:
        key = self._key(labels)
        self.values[key] = value
        self.label_cache[key] = dict(labels)


@dataclass
class HistogramMetric(_MetricBase):
    buckets: Tuple[float, ...] = (50, 100, 200, 500, 1000)
    samples: MutableMapping[LabelValues, List[float]] = field(default_factory=dict)
    label_cache: MutableMapping[LabelValues, LabelDict] = field(default_factory=dict)

    def observe(self, value: float, **labels: str) -> None:
        key = self._key(labels)
        self.samples.setdefault(key, []).append(value)
        if key not in self.label_cache:
            self.label_cache[key] = dict(labels)

    def iter_statistics(self) -> Iterable[Tuple[LabelDict, List[float]]]:
        for key, values in self.samples.items():
            labels = self.label_cache.get(key, {})
            yield labels, values


class MetricsRegistry:
    """Collect guardrail, critic and latency metrics in-memory."""

    def __init__(self, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(timezone.utc))
        self.guardrail_verdicts = CounterMetric(
            name="guardrail_verdict_total",
            description="Count of guardrail verdict outcomes",
            label_names=("verdict",),
        )
        self.llm_critic_score = GaugeMetric(
            name="llm_critic_score",
            description="Latest LLM-Critic score by scenario",
            label_names=("scenario",),
        )
        self.system_latency_ms = HistogramMetric(
            name="system_latency_ms",
            description="Distribution of end-to-end latency in milliseconds",
            label_names=("stage",),
        )

    # Recording helpers -------------------------------------------------
    def record_guardrail_verdict(self, verdict: str, weight: float = 1.0) -> None:
        self.guardrail_verdicts.inc(weight, verdict=verdict)

    def record_llm_critic_score(self, scenario: str, score: float) -> None:
        self.llm_critic_score.set(score, scenario=scenario)

    def observe_latency(self, latency_ms: float, stage: str = "overall") -> None:
        self.system_latency_ms.observe(latency_ms, stage=stage)

    # Export helpers ----------------------------------------------------
    def as_prometheus(self) -> str:
        lines: List[str] = []
        # Counters
        lines.extend(self._prometheus_counter(self.guardrail_verdicts))
        # Gauges
        lines.extend(self._prometheus_gauge(self.llm_critic_score))
        # Histograms
        lines.extend(self._prometheus_histogram(self.system_latency_ms))
        return "\n".join(lines) + "\n"

    def as_clickhouse_rows(self) -> List[Dict[str, object]]:
        timestamp = self._now().isoformat()
        rows: List[Dict[str, object]] = []

        for key, value in self.guardrail_verdicts.values.items():
            labels = self.guardrail_verdicts.label_cache[key]
            rows.append(
                {
                    "metric": self.guardrail_verdicts.name,
                    "value": value,
                    "type": "counter",
                    "labels": dict(labels),
                    "timestamp": timestamp,
                }
            )

        for key, value in self.llm_critic_score.values.items():
            labels = self.llm_critic_score.label_cache[key]
            rows.append(
                {
                    "metric": self.llm_critic_score.name,
                    "value": value,
                    "type": "gauge",
                    "labels": dict(labels),
                    "timestamp": timestamp,
                }
            )

        for labels, values in self.system_latency_ms.iter_statistics():
            total = sum(values)
            count = len(values)
            buckets = self._histogram_bucket_counts(values, self.system_latency_ms.buckets)
            for bound, bucket_count in buckets.items():
                bucket_labels = dict(labels)
                bucket_labels["le"] = bound
                rows.append(
                    {
                        "metric": f"{self.system_latency_ms.name}_bucket",
                        "value": bucket_count,
                        "type": "histogram_bucket",
                        "labels": bucket_labels,
                        "timestamp": timestamp,
                    }
                )
            rows.append(
                {
                    "metric": f"{self.system_latency_ms.name}_sum",
                    "value": total,
                    "type": "histogram_sum",
                    "labels": dict(labels),
                    "timestamp": timestamp,
                }
            )
            rows.append(
                {
                    "metric": f"{self.system_latency_ms.name}_count",
                    "value": count,
                    "type": "histogram_count",
                    "labels": dict(labels),
                    "timestamp": timestamp,
                }
            )
        return rows

    # Internal helpers --------------------------------------------------
    def _prometheus_counter(self, metric: CounterMetric) -> List[str]:
        lines = [f"# HELP {metric.name} {metric.description}", f"# TYPE {metric.name} counter"]
        for key, value in sorted(metric.values.items()):
            labels = metric.label_cache[key]
            label_str = self._format_labels(labels)
            lines.append(f"{metric.name}{label_str} {value}")
        return lines

    def _prometheus_gauge(self, metric: GaugeMetric) -> List[str]:
        lines = [f"# HELP {metric.name} {metric.description}", f"# TYPE {metric.name} gauge"]
        for key, value in sorted(metric.values.items()):
            labels = metric.label_cache[key]
            label_str = self._format_labels(labels)
            lines.append(f"{metric.name}{label_str} {value}")
        return lines

    def _prometheus_histogram(self, metric: HistogramMetric) -> List[str]:
        lines = [f"# HELP {metric.name} {metric.description}", f"# TYPE {metric.name} histogram"]
        for labels, values in metric.iter_statistics():
            buckets = metric.buckets
            counts = self._histogram_bucket_counts(values, buckets)
            base_label = self._format_labels(labels)
            cumulative = 0
            for bound in buckets:
                cumulative += counts[str(bound)]
                label_map = dict(labels)
                label_map["le"] = str(bound)
                label_str = self._format_labels(label_map)
                lines.append(f"{metric.name}_bucket{label_str} {cumulative}")
            cumulative += counts["+Inf"]
            inf_labels = dict(labels)
            inf_labels["le"] = "+Inf"
            lines.append(
                f"{metric.name}_bucket{self._format_labels(inf_labels)} {cumulative}"
            )
            lines.append(f"{metric.name}_sum{base_label} {sum(values)}")
            lines.append(f"{metric.name}_count{base_label} {len(values)}")
        return lines

    @staticmethod
    def _histogram_bucket_counts(values: Iterable[float], buckets: Tuple[float, ...]) -> Dict[str, int]:
        counts = {str(bound): 0 for bound in buckets}
        counts["+Inf"] = 0
        for value in values:
            placed = False
            for bound in buckets:
                if value <= bound:
                    counts[str(bound)] += 1
                    placed = True
                    break
            if not placed:
                counts["+Inf"] += 1
        return counts

    @staticmethod
    def _format_labels(labels: Mapping[str, str]) -> str:
        if not labels:
            return ""
        formatted = ",".join(
            f"{key}=\"{value}\"" for key, value in sorted(labels.items())
        )
        return f"{{{formatted}}}"
