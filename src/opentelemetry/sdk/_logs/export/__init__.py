"""Log exporting primitives."""

from __future__ import annotations

from enum import Enum
from typing import Iterable, Sequence

from .. import LogData, LogRecordProcessor


class ExportResult(Enum):
    SUCCESS = 0
    FAILURE = 1


class LogExporter:
    def export(self, batch: Sequence[LogData]) -> ExportResult:  # pragma: no cover - interface hook
        return ExportResult.SUCCESS

    def shutdown(self) -> None:  # pragma: no cover - interface hook
        pass

    def force_flush(self) -> None:  # pragma: no cover - interface hook
        pass


class BatchLogRecordProcessor(LogRecordProcessor):
    def __init__(self, exporter: LogExporter) -> None:
        self._exporter = exporter

    def emit(self, log_data: LogData) -> None:
        self._exporter.export([log_data])

    def force_flush(self) -> None:
        self._exporter.force_flush()

    def shutdown(self) -> None:
        self._exporter.shutdown()
