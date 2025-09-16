"""Minimal logging SDK compatible with the subset used in tests."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..resources import Resource
from ..util import InstrumentationScope


@dataclass
class LogRecord:
    body: object
    severity_text: Optional[str] = None
    severity_number: Optional[int] = None
    attributes: Dict[str, object] = field(default_factory=dict)
    timestamp: int = field(default_factory=lambda: time.time_ns())
    observed_timestamp: int = field(default_factory=lambda: time.time_ns())
    trace_id: Optional[int] = None
    span_id: Optional[int] = None
    trace_flags: Optional[int] = None
    trace_state: Optional[str] = None


@dataclass
class LogData:
    log_record: LogRecord
    resource: Resource
    instrumentation_scope: Optional[InstrumentationScope] = None


class LoggerProvider:
    def __init__(self, resource: Resource) -> None:
        self.resource = resource
        self._processors: List["LogRecordProcessor"] = []

    def add_log_record_processor(self, processor: "LogRecordProcessor") -> None:
        self._processors.append(processor)

    def emit(self, log_data: LogData) -> None:
        for processor in list(self._processors):
            processor.emit(log_data)

    def force_flush(self) -> None:
        for processor in self._processors:
            processor.force_flush()

    def shutdown(self) -> None:
        for processor in self._processors:
            processor.shutdown()


class LogRecordProcessor:
    def emit(self, log_data: LogData) -> None:  # pragma: no cover - hook
        pass

    def force_flush(self) -> None:  # pragma: no cover - hook
        pass

    def shutdown(self) -> None:  # pragma: no cover - hook
        pass
