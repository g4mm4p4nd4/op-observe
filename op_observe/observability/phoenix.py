"""Phoenix backend client and exporter utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Protocol
from urllib import request

from .tracing import (
    OpenInferenceEvaluation,
    OpenInferenceSpan,
    PhoenixTracePayload,
)


class Transport(Protocol):
    """Protocol for HTTP transports used by :class:`PhoenixClient`."""

    def post_json(
        self,
        url: str,
        payload: Mapping[str, Any],
        headers: Mapping[str, str] | None = None,
    ) -> "TransportResponse":
        """Send an HTTP POST request with a JSON payload."""


@dataclass
class TransportResponse:
    """Container for transport responses."""

    status_code: int
    body: str

    def json(self) -> Any:
        try:
            return json.loads(self.body)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise ValueError("Transport response did not contain JSON data") from exc


class UrllibTransport:
    """Minimal :mod:`urllib` transport for communicating with Phoenix."""

    def post_json(
        self,
        url: str,
        payload: Mapping[str, Any],
        headers: Mapping[str, str] | None = None,
    ) -> TransportResponse:
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        for key, value in (headers or {}).items():
            req.add_header(key, value)
        with request.urlopen(req) as resp:  # type: ignore[call-arg]
            body = resp.read().decode("utf-8")
            return TransportResponse(resp.status, body)


class PhoenixClient:
    """Thin Phoenix REST client tailored for OpenInference payloads."""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        transport: Transport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._transport = transport or UrllibTransport()

    # REST endpoints -----------------------------------------------------
    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def upload_trace(self, payload: PhoenixTracePayload) -> TransportResponse:
        """Send trace data to Phoenix's ingestion endpoint."""

        url = f"{self._base_url}/api/v1/traces"
        payload_mapping = {"trace_id": payload.trace_id, "spans": payload.spans}
        return self._transport.post_json(url, payload_mapping, headers=self._headers())

    def upload_evaluations(
        self,
        trace_id: str,
        evaluations: Iterable[OpenInferenceEvaluation],
    ) -> TransportResponse:
        """Push evaluation metrics associated with a trace."""

        url = f"{self._base_url}/api/v1/evaluations"
        payload = {
            "trace_id": trace_id,
            "evaluations": [evaluation.to_wire() for evaluation in evaluations],
        }
        return self._transport.post_json(url, payload, headers=self._headers())

    def refresh_dashboards(self, trace_id: str) -> TransportResponse:
        """Request that Phoenix refresh dashboards for the provided trace."""

        url = f"{self._base_url}/api/v1/dashboards/refresh"
        payload = {"trace_id": trace_id}
        return self._transport.post_json(url, payload, headers=self._headers())


class PhoenixTraceExporter:
    """Push :class:`OpenInferenceSpan` batches to Phoenix."""

    def __init__(self, client: PhoenixClient) -> None:
        self._client = client

    def export(
        self,
        trace_id: str,
        spans: Iterable[OpenInferenceSpan],
        evaluations: Iterable[OpenInferenceEvaluation],
    ) -> MutableMapping[str, TransportResponse]:
        """Send a set of spans + evaluations to Phoenix and refresh dashboards."""

        span_payload = PhoenixTracePayload(
            trace_id=trace_id,
            spans=[span.to_wire() for span in spans],
        )
        responses: Dict[str, TransportResponse] = {}
        responses["traces"] = self._client.upload_trace(span_payload)
        evaluations = list(evaluations)
        if evaluations:
            responses["evaluations"] = self._client.upload_evaluations(
                trace_id,
                evaluations,
            )
        responses["dashboards"] = self._client.refresh_dashboards(trace_id)
        return responses
