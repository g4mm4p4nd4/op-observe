"""Telemetry models used to structure trace and evaluation data."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional


def _ensure_utc(value: datetime) -> datetime:
    """Normalise a datetime to UTC with tzinfo."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(slots=True)
class Dataset:
    """Metadata describing a Phoenix dataset."""

    name: str
    schema: Mapping[str, str]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("dataset name must be provided")
        if not isinstance(self.schema, Mapping) or not self.schema:
            raise ValueError("dataset schema must be a non-empty mapping")

    def to_payload(self) -> Dict[str, Any]:
        """Return a serialisable payload for Phoenix dataset registration."""
        return {
            "name": self.name,
            "schema": dict(self.schema),
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class TraceSpan:
    """Representation of a single OpenInference span."""

    trace_id: str
    span_id: str
    name: str
    start_time: datetime
    end_time: datetime
    parent_span_id: Optional[str] = None
    kind: Optional[str] = None
    status_code: Optional[str] = None
    status_message: Optional[str] = None
    attributes: MutableMapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.trace_id:
            raise ValueError("trace_id must be provided")
        if not self.span_id:
            raise ValueError("span_id must be provided")
        if self.end_time < self.start_time:
            raise ValueError("span end_time cannot be earlier than start_time")
        self.start_time = _ensure_utc(self.start_time)
        self.end_time = _ensure_utc(self.end_time)

    @property
    def duration_ms(self) -> float:
        """Return the span duration in milliseconds."""
        delta = self.end_time - self.start_time
        return delta.total_seconds() * 1000


@dataclass(slots=True)
class EvaluationMetric:
    """A single evaluation metric tied to a trace or span."""

    evaluation_name: str
    metric_name: str
    value: float
    trace_id: str
    timestamp: datetime
    span_id: Optional[str] = None
    metadata: MutableMapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.evaluation_name:
            raise ValueError("evaluation_name must be provided")
        if not self.metric_name:
            raise ValueError("metric_name must be provided")
        if not isinstance(self.value, (int, float)):
            raise TypeError("value must be numeric")
        if not self.trace_id:
            raise ValueError("trace_id must be provided")
        self.timestamp = _ensure_utc(self.timestamp)


@dataclass(slots=True)
class TelemetryBatch:
    """Bundle of telemetry destined for Phoenix."""

    dataset: Dataset
    traces: List[TraceSpan] = field(default_factory=list)
    evaluations: List[EvaluationMetric] = field(default_factory=list)

    def iter_spans(self) -> Iterable[TraceSpan]:
        return iter(self.traces)

    def iter_evaluations(self) -> Iterable[EvaluationMetric]:
        return iter(self.evaluations)
