"""Telemetry utilities for orchestrator integration tests.

Provides a lightweight span/metrics collector we can use to simulate
OpenTelemetry/OpenLLMetry style instrumentation without external
Dependencies.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Span:
    """Represents a captured unit of work for tracing."""

    name: str
    start_time: float
    end_time: float
    attributes: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        """Duration in milliseconds."""
        return (self.end_time - self.start_time) * 1000


class SpanContext:
    """Context manager used to capture spans."""

    def __init__(self, collector: "TelemetryCollector", name: str, attrs: Dict[str, Any]):
        self._collector = collector
        self._name = name
        self._attrs = attrs
        self.span: Optional[Span] = None
        self._start: Optional[float] = None

    def __enter__(self) -> "SpanContext":
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        end_time = time.perf_counter()
        if self._start is None:
            raise RuntimeError("SpanContext exited without being entered")
        self.span = Span(self._name, self._start, end_time, dict(self._attrs))
        # Attach error information if an exception bubbled up.
        if exc_type:
            self.span.attributes["error.type"] = exc_type.__name__
            self.span.attributes["error.message"] = str(exc_val)
        self._collector.spans.append(self.span)


class TelemetryCollector:
    """Collects metrics, logs and spans for a test run."""

    def __init__(self) -> None:
        self.metrics: Dict[str, Any] = {}
        self.logs: List[str] = []
        self.spans: List[Span] = []

    # ---- Tracing -----------------------------------------------------
    def span(self, name: str, **attrs: Any) -> SpanContext:
        return SpanContext(self, name, attrs)

    # ---- Metrics -----------------------------------------------------
    def record_metric(self, name: str, value: Any) -> None:
        self.metrics[name] = value

    def increment(self, name: str, value: int = 1) -> None:
        self.metrics[name] = self.metrics.get(name, 0) + value

    # ---- Logging -----------------------------------------------------
    def record_log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.logs.append(f"{timestamp} {message}")

    # ---- Helpers -----------------------------------------------------
    def latest_span(self, name: str) -> Optional[Span]:
        for span in reversed(self.spans):
            if span.name == name:
                return span
        return None

    def as_summary(self) -> Dict[str, Any]:
        """Provide a consolidated view of captured telemetry."""
        return {
            "metrics": dict(self.metrics),
            "logs": list(self.logs),
            "traces": [
                {
                    "name": span.name,
                    "duration_ms": span.duration_ms,
                    "attributes": dict(span.attributes),
                }
                for span in self.spans
            ],
        }
