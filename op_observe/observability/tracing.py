"""OpenInference span abstractions and Phoenix session helpers."""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterator, List, Mapping, MutableMapping

if TYPE_CHECKING:
    from .phoenix import PhoenixTraceExporter, TransportResponse


class OpenInferenceSpanKind(str, Enum):
    """Semantic span categories supported by OpenInference."""

    MODEL = "llm"
    RETRIEVER = "retriever"
    TOOL = "tool"
    CHAIN = "chain"

    def attribute_name(self) -> str:
        """Return the canonical attribute storing the semantic identifier."""

        return {
            OpenInferenceSpanKind.MODEL: "openinference.model.name",
            OpenInferenceSpanKind.RETRIEVER: "openinference.retriever.name",
            OpenInferenceSpanKind.TOOL: "openinference.tool.name",
            OpenInferenceSpanKind.CHAIN: "openinference.chain.name",
        }[self]


@dataclass
class OpenInferenceSpan:
    """Structured representation of an OpenInference span."""

    name: str
    kind: OpenInferenceSpanKind
    start_time: float
    end_time: float
    attributes: MutableMapping[str, Any] = field(default_factory=dict)
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    parent_id: str | None = None
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_wire(self) -> Dict[str, Any]:
        """Serialise span data into the structure expected by Phoenix."""

        payload: Dict[str, Any] = {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "attributes": {
                "openinference.span.kind": self.kind.value,
                **self.attributes,
            },
        }
        return payload


@dataclass
class OpenInferenceEvaluation:
    """Evaluation record tied to a specific span or trace."""

    metric_name: str
    value: float
    span_id: str | None = None
    metadata: Mapping[str, Any] | None = None

    def to_wire(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "metric_name": self.metric_name,
            "value": self.value,
        }
        if self.span_id:
            payload["span_id"] = self.span_id
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


@dataclass
class PhoenixTracePayload:
    """Wire representation of a Phoenix trace payload."""

    trace_id: str
    spans: List[Mapping[str, Any]]


class PhoenixTraceSession:
    """High-level helper to build and submit traces to Phoenix."""

    def __init__(
        self,
        exporter: "PhoenixTraceExporter",
        *,
        trace_id: str | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        from .phoenix import PhoenixTraceExporter  # circular import guard

        if not isinstance(exporter, PhoenixTraceExporter):  # pragma: no cover - defensive
            raise TypeError("exporter must be a PhoenixTraceExporter instance")

        self._exporter = exporter
        self._trace_id = trace_id or uuid.uuid4().hex
        self._clock = clock or time.time
        self._spans: List[OpenInferenceSpan] = []
        self._evaluations: List[OpenInferenceEvaluation] = []
        self._span_stack: List[OpenInferenceSpan] = []

    @property
    def trace_id(self) -> str:
        return self._trace_id

    def record_evaluation(
        self,
        metric_name: str,
        value: float,
        *,
        span: OpenInferenceSpan | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> OpenInferenceEvaluation:
        """Attach an evaluation metric to the trace (optionally to a span)."""

        evaluation = OpenInferenceEvaluation(
            metric_name=metric_name,
            value=value,
            span_id=span.span_id if span else None,
            metadata=metadata,
        )
        self._evaluations.append(evaluation)
        return evaluation

    @contextmanager
    def span(
        self,
        name: str,
        *,
        kind: OpenInferenceSpanKind,
        attributes: Mapping[str, Any] | None = None,
    ) -> Iterator[OpenInferenceSpan]:
        """Context manager for building nested OpenInference spans."""

        start_time = float(self._clock())
        parent = self._span_stack[-1] if self._span_stack else None
        span = OpenInferenceSpan(
            name=name,
            kind=kind,
            start_time=start_time,
            end_time=start_time,  # placeholder; updated on exit
            trace_id=self._trace_id,
            parent_id=parent.span_id if parent else None,
            attributes=dict(attributes or {}),
        )
        semantic_key = kind.attribute_name()
        if semantic_key not in span.attributes:
            span.attributes[semantic_key] = name
        self._span_stack.append(span)
        try:
            yield span
        finally:
            span.end_time = float(self._clock())
            self._spans.append(span)
            self._span_stack.pop()

    def submit(self) -> MutableMapping[str, "TransportResponse"]:
        """Export the captured spans and evaluations via the bound exporter."""

        return self._exporter.export(
            self._trace_id,
            list(self._spans),
            list(self._evaluations),
        )

    # Convenience methods -------------------------------------------------
    def model_span(
        self,
        name: str,
        *,
        attributes: Mapping[str, Any] | None = None,
    ) -> Iterator[OpenInferenceSpan]:
        return self.span(name, kind=OpenInferenceSpanKind.MODEL, attributes=attributes)

    def tool_span(
        self,
        name: str,
        *,
        attributes: Mapping[str, Any] | None = None,
    ) -> Iterator[OpenInferenceSpan]:
        return self.span(name, kind=OpenInferenceSpanKind.TOOL, attributes=attributes)

    def retriever_span(
        self,
        name: str,
        *,
        attributes: Mapping[str, Any] | None = None,
    ) -> Iterator[OpenInferenceSpan]:
        return self.span(
            name,
            kind=OpenInferenceSpanKind.RETRIEVER,
            attributes=attributes,
        )

    def chain_span(
        self,
        name: str,
        *,
        attributes: Mapping[str, Any] | None = None,
    ) -> Iterator[OpenInferenceSpan]:
        return self.span(name, kind=OpenInferenceSpanKind.CHAIN, attributes=attributes)
