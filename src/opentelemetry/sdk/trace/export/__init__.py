"""Span exporting primitives."""

from __future__ import annotations

from enum import Enum
from typing import List, Sequence

from opentelemetry.trace import Span, SpanProcessor


class SpanExportResult(Enum):
    SUCCESS = 0
    FAILURE = 1


class SpanExporter:
    def export(self, spans: Sequence[Span]) -> SpanExportResult:  # pragma: no cover
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:  # pragma: no cover
        pass

    def force_flush(self) -> None:  # pragma: no cover
        pass


class BatchSpanProcessor(SpanProcessor):
    def __init__(self, exporter: SpanExporter) -> None:
        self._exporter = exporter

    def on_start(self, span: Span) -> None:
        # no pre-processing required for the lightweight implementation
        return

    def on_end(self, span: Span) -> None:
        self._exporter.export([span])

    def shutdown(self) -> None:
        self._exporter.shutdown()

    def force_flush(self) -> None:
        self._exporter.force_flush()


class InMemorySpanExporter(SpanExporter):
    def __init__(self) -> None:
        self._finished: List[Span] = []
        self._is_shutdown = False

    def export(self, spans: Sequence[Span]) -> SpanExportResult:
        if self._is_shutdown:
            return SpanExportResult.FAILURE
        self._finished.extend(spans)
        return SpanExportResult.SUCCESS

    def get_finished_spans(self) -> List[Span]:
        return list(self._finished)

    def clear(self) -> None:
        self._finished.clear()

    def shutdown(self) -> None:
        self._is_shutdown = True

    def force_flush(self) -> None:
        return
