"""Telemetry aggregation utilities."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List


@dataclass(slots=True)
class TelemetryEvent:
    """Represents a single telemetry event."""

    event_type: str
    timestamp: float
    metadata: Dict[str, object]


class TelemetryAgent:
    """Stores runtime telemetry for later evidence packaging."""

    def __init__(self) -> None:
        self._events: List[TelemetryEvent] = []
        self._initialized = False

    def initialize(self) -> None:
        self._initialized = True

    def record_event(self, event_type: str, metadata: Dict[str, object] | None = None) -> None:
        if not self._initialized:
            raise RuntimeError("TelemetryAgent must be initialized before recording events")

        event = TelemetryEvent(event_type=event_type, timestamp=time.time(), metadata=metadata or {})
        self._events.append(event)

    def snapshot(self) -> Dict[str, object]:
        """Return a serializable snapshot of telemetry state."""

        return {
            "total_events": len(self._events),
            "events": [
                {
                    "event_type": event.event_type,
                    "timestamp": event.timestamp,
                    "metadata": event.metadata,
                }
                for event in self._events
            ],
        }
