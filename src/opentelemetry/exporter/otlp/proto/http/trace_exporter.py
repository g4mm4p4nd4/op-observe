"""Minimal OTLP/HTTP span exporter used for tests."""

from __future__ import annotations

import json
from typing import Mapping, Optional, Sequence
from urllib import error, request

from opentelemetry.sdk.trace.export import SpanExportResult, SpanExporter
from opentelemetry.trace import Span


class OTLPSpanExporter(SpanExporter):
    def __init__(
        self,
        *,
        endpoint: str,
        insecure: bool = True,
        headers: Optional[Mapping[str, str]] = None,
        timeout: float = 10.0,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        if not self._endpoint.endswith("/v1/traces"):
            self._endpoint = f"{self._endpoint}/v1/traces"
        self._headers = {"Content-Type": "application/json"}
        if headers:
            self._headers.update(headers)
        self._timeout = timeout
        self._opener = request.build_opener()
        self._insecure = insecure

    def export(self, spans: Sequence[Span]) -> SpanExportResult:
        payload = {"spans": [self._serialize_span(span) for span in spans]}
        data = json.dumps(payload, separators=(",", ":")).encode()
        req = request.Request(self._endpoint, data=data, headers=self._headers, method="POST")
        try:
            with self._opener.open(req, timeout=self._timeout) as resp:
                status = resp.getcode()
                _ = resp.read() if status < 400 else resp.read()
        except error.URLError:  # pragma: no cover - network failure path
            return SpanExportResult.FAILURE
        return SpanExportResult.SUCCESS if status < 400 else SpanExportResult.FAILURE

    def shutdown(self) -> None:
        return

    def force_flush(self) -> None:
        return

    def _serialize_span(self, span: Span) -> Mapping[str, object]:
        context = span.get_span_context()
        return {
            "name": span.name,
            "trace_id": format(context.trace_id, "032x"),
            "span_id": format(context.span_id, "016x"),
            "start_time": span.start_time,
            "end_time": span.end_time,
            "attributes": dict(span.attributes),
            "resource": getattr(span.resource, "attributes", {}),
        }


__all__ = ["OTLPSpanExporter"]
