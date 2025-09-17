"""Lightweight OpenTelemetry-compatible primitives used for testing.

The real project would depend on ``opentelemetry`` as well as
OpenLLMetry/OpenInference integrations. Since those libraries are not
available in the execution environment we provide a very small shim that
exposes the subset of behaviour required by the unit tests. The API is
inspired by ``opentelemetry.trace`` and only implements the minimal
surface necessary for the decorators provided in
:mod:`op_observe.instrumentation`.
"""

from __future__ import annotations

import copy
import os
import threading
import time
from contextlib import AbstractContextManager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

__all__ = [
    "SpanContext",
    "SpanRecord",
    "StatusCode",
    "Span",
    "Tracer",
    "TracerProvider",
    "SimpleSpanProcessor",
    "InMemoryOTLPSpanExporter",
    "InMemoryOTLPCollector",
    "get_tracer",
    "set_tracer_provider",
    "reset_tracer_provider",
]


class StatusCode(str, Enum):
    """Enumeration that mirrors the OpenTelemetry ``StatusCode`` type."""

    UNSET = "UNSET"
    OK = "OK"
    ERROR = "ERROR"


@dataclass(frozen=True)
class SpanContext:
    """Simple immutable span context holding trace and span identifiers."""

    trace_id: str
    span_id: str


@dataclass
class SpanRecord:
    """Record exported by the in-memory collector."""

    name: str
    context: SpanContext
    parent_id: Optional[str]
    attributes: Dict[str, Any]
    start_time: float
    end_time: Optional[float]
    status: StatusCode
    instrumentation_scope: str
    events: List[Dict[str, Any]] = field(default_factory=list)


_current_span: ContextVar[Optional["Span"]] = ContextVar("current_span", default=None)


def _generate_trace_id() -> str:
    return os.urandom(16).hex()


def _generate_span_id() -> str:
    return os.urandom(8).hex()


class Span:
    """Minimal representation of an OpenTelemetry span."""

    def __init__(
        self,
        tracer: "Tracer",
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        parent: Optional["Span"] = None,
    ) -> None:
        self._tracer = tracer
        self._name = name
        parent_context = parent.context if parent is not None else None
        trace_id = parent_context.trace_id if parent_context else _generate_trace_id()
        self._context = SpanContext(trace_id=trace_id, span_id=_generate_span_id())
        self._record = SpanRecord(
            name=name,
            context=self._context,
            parent_id=parent_context.span_id if parent_context else None,
            attributes=dict(attributes or {}),
            start_time=time.time(),
            end_time=None,
            status=StatusCode.UNSET,
            instrumentation_scope=tracer.instrumentation_scope,
        )
        self._ended = False

    # ------------------------------------------------------------------
    # OpenTelemetry-like surface
    # ------------------------------------------------------------------
    @property
    def name(self) -> str:
        return self._name

    @property
    def context(self) -> SpanContext:
        return self._context

    @property
    def attributes(self) -> Dict[str, Any]:
        return self._record.attributes

    @property
    def status(self) -> StatusCode:
        return self._record.status

    def set_attribute(self, key: str, value: Any) -> None:
        self._record.attributes[key] = value

    def record_exception(self, exc: BaseException) -> None:
        self._record.events.append(
            {
                "name": "exception",
                "attributes": {
                    "exception.type": exc.__class__.__name__,
                    "exception.message": str(exc),
                },
            }
        )

    def set_status(self, status: StatusCode) -> None:
        self._record.status = status

    def end(self) -> None:
        if self._ended:
            return
        self._record.end_time = time.time()
        self._tracer.provider._on_end(self._record)
        self._ended = True


class _SpanContextManager(AbstractContextManager):
    """Context manager returned by :meth:`Tracer.start_as_current_span`."""

    def __init__(self, span: Span) -> None:
        self._span = span
        self._token = None

    def __enter__(self) -> Span:
        self._token = _current_span.set(self._span)
        return self._span

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is None:
            if self._span.status == StatusCode.UNSET:
                self._span.set_status(StatusCode.OK)
        else:
            self._span.record_exception(exc)  # type: ignore[arg-type]
            self._span.set_status(StatusCode.ERROR)
        try:
            self._span.end()
        finally:
            if self._token is not None:
                _current_span.reset(self._token)
        return False


class Tracer:
    """Very small tracer implementation."""

    def __init__(self, provider: "TracerProvider", instrumentation_scope: str) -> None:
        self.provider = provider
        self.instrumentation_scope = instrumentation_scope

    def start_span(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> Span:
        parent = _current_span.get()
        return Span(self, name, attributes, parent)

    def start_as_current_span(
        self, name: str, attributes: Optional[Dict[str, Any]] = None
    ) -> _SpanContextManager:
        span = self.start_span(name, attributes)
        return _SpanContextManager(span)


class TracerProvider:
    """Simplified tracer provider that keeps a list of processors."""

    def __init__(self) -> None:
        self._processors: List[SimpleSpanProcessor] = []

    def get_tracer(self, instrumentation_scope: str) -> Tracer:
        return Tracer(self, instrumentation_scope)

    def add_span_processor(self, processor: "SimpleSpanProcessor") -> None:
        self._processors.append(processor)

    # Internal hook
    def _on_end(self, record: SpanRecord) -> None:
        for processor in self._processors:
            processor.on_end(record)


class SimpleSpanProcessor:
    """Processor that immediately exports spans synchronously."""

    def __init__(self, exporter: "InMemoryOTLPSpanExporter") -> None:
        self._exporter = exporter

    def on_end(self, record: SpanRecord) -> None:
        # Export a defensive copy so later mutations do not leak.
        self._exporter.export([copy.deepcopy(record)])


class InMemoryOTLPSpanExporter:
    """Small OTLP-like exporter that keeps spans in memory."""

    def __init__(self) -> None:
        self._spans: List[SpanRecord] = []
        self._lock = threading.Lock()

    def export(self, spans: Iterable[SpanRecord]) -> None:
        with self._lock:
            for span in spans:
                self._spans.append(copy.deepcopy(span))

    def get_finished_spans(self) -> List[SpanRecord]:
        with self._lock:
            return [copy.deepcopy(span) for span in self._spans]

    def clear(self) -> None:
        with self._lock:
            self._spans.clear()


class InMemoryOTLPCollector:
    """Convenience helper used by the tests to capture exported spans."""

    def __init__(self) -> None:
        self.exporter = InMemoryOTLPSpanExporter()
        self.processor = SimpleSpanProcessor(self.exporter)
        self.tracer_provider = TracerProvider()
        self.tracer_provider.add_span_processor(self.processor)

    def get_finished_spans(self) -> List[SpanRecord]:
        return self.exporter.get_finished_spans()

    def clear(self) -> None:
        self.exporter.clear()


_global_tracer_provider = TracerProvider()


def get_tracer(instrumentation_scope: str) -> Tracer:
    """Return a tracer for the requested instrumentation scope."""

    return _global_tracer_provider.get_tracer(instrumentation_scope)


def set_tracer_provider(provider: TracerProvider) -> None:
    """Replace the global tracer provider."""

    global _global_tracer_provider
    _global_tracer_provider = provider


def reset_tracer_provider() -> None:
    """Restore the global provider to a clean instance."""

    set_tracer_provider(TracerProvider())
