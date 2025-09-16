"""Lightweight tracing primitives inspired by OpenTelemetry."""

from __future__ import annotations

import contextlib
import contextvars
import random
import time
from dataclasses import dataclass
from typing import Callable, Optional

from ..sdk.util import InstrumentationScope


__all__ = [
    "Span",
    "SpanContext",
    "Tracer",
    "TracerProvider",
    "get_current_span",
    "get_tracer",
    "get_tracer_provider",
    "set_tracer_provider",
]


_CURRENT_SPAN: contextvars.ContextVar[Optional["Span"]] = contextvars.ContextVar(
    "opentelemetry_current_span", default=None
)
_TRACER_PROVIDER: Optional["TracerProvider"] = None


def _generate_trace_id() -> int:
    trace_id = 0
    while trace_id == 0:
        trace_id = random.getrandbits(128)
    return trace_id


def _generate_span_id() -> int:
    span_id = 0
    while span_id == 0:
        span_id = random.getrandbits(64)
    return span_id


@dataclass
class SpanContext:
    trace_id: int
    span_id: int
    trace_flags: int = 1
    trace_state: str = ""
    is_remote: bool = False


class Span:
    def __init__(
        self,
        name: str,
        instrumentation_scope: InstrumentationScope,
        resource: "Resource",
        parent: Optional["Span"],
    ) -> None:
        self.name = name
        self.instrumentation_scope = instrumentation_scope
        self.resource = resource
        parent_context = parent.get_span_context() if parent else None
        if parent_context:
            trace_id = parent_context.trace_id
        else:
            trace_id = _generate_trace_id()
        self._context = SpanContext(trace_id=trace_id, span_id=_generate_span_id())
        self.parent = parent
        self.start_time = time.time_ns()
        self.end_time: Optional[int] = None
        self.attributes = {}

    def get_span_context(self) -> SpanContext:
        return self._context

    def end(self) -> None:
        if self.end_time is None:
            self.end_time = time.time_ns()

    @property
    def context(self) -> SpanContext:
        return self._context


class _SpanContextManager(contextlib.AbstractContextManager[Span]):
    def __init__(
        self,
        provider: "TracerProvider",
        name: str,
        instrumentation_scope: InstrumentationScope,
    ) -> None:
        self._provider = provider
        self._name = name
        self._instrumentation_scope = instrumentation_scope
        self._token: Optional[contextvars.Token[Optional[Span]]] = None
        self._span: Optional[Span] = None

    def __enter__(self) -> Span:
        parent = get_current_span()
        span = Span(self._name, self._instrumentation_scope, self._provider.resource, parent)
        self._span = span
        self._token = _CURRENT_SPAN.set(span)
        for processor in self._provider._span_processors:
            processor.on_start(span)
        return span

    def __exit__(self, exc_type, exc_val, exc_tb) -> Optional[bool]:
        assert self._span is not None
        self._span.end()
        for processor in self._provider._span_processors:
            processor.on_end(self._span)
        if self._token is not None:
            _CURRENT_SPAN.reset(self._token)
        return None


class Tracer:
    def __init__(self, provider: "TracerProvider", instrumentation_scope: InstrumentationScope) -> None:
        self._provider = provider
        self._scope = instrumentation_scope

    def start_as_current_span(self, name: str) -> _SpanContextManager:
        return _SpanContextManager(self._provider, name, self._scope)


class TracerProvider:
    def __init__(self, resource: "Resource", sampler: Optional[object] = None) -> None:
        self.resource = resource
        self.sampler = sampler
        self._span_processors: list["SpanProcessor"] = []

    def add_span_processor(self, processor: "SpanProcessor") -> None:
        self._span_processors.append(processor)

    def get_tracer(self, name: str, version: Optional[str] = None) -> Tracer:
        return Tracer(self, InstrumentationScope(name=name, version=version))

    def force_flush(self) -> None:
        for processor in self._span_processors:
            processor.force_flush()

    def shutdown(self) -> None:
        for processor in self._span_processors:
            processor.shutdown()


class SpanProcessor:
    def on_start(self, span: Span) -> None:  # pragma: no cover - interface hook
        pass

    def on_end(self, span: Span) -> None:  # pragma: no cover - interface hook
        pass

    def force_flush(self) -> None:  # pragma: no cover - interface hook
        pass

    def shutdown(self) -> None:  # pragma: no cover - interface hook
        pass


def get_tracer(name: str, version: Optional[str] = None) -> Tracer:
    return get_tracer_provider().get_tracer(name, version)


def set_tracer_provider(provider: TracerProvider) -> None:
    global _TRACER_PROVIDER
    _TRACER_PROVIDER = provider


def get_tracer_provider() -> TracerProvider:
    global _TRACER_PROVIDER
    if _TRACER_PROVIDER is None:
        from ..sdk.resources import Resource

        _TRACER_PROVIDER = TracerProvider(Resource.get_empty())
    return _TRACER_PROVIDER


def get_current_span() -> Optional[Span]:
    return _CURRENT_SPAN.get()
