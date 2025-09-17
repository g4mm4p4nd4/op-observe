"""Phoenix API client utilities."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, Mapping, MutableMapping, Optional

from ..telemetry.models import Dataset

Transport = Callable[[str, str, Mapping[str, Any]], Mapping[str, Any]]


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(slots=True)
class EvaluationResult:
    """Structured evaluation payload sent to Phoenix."""

    record_id: str
    trace_id: str
    metrics: MutableMapping[str, float]
    timestamp: datetime
    span_id: Optional[str] = None
    metadata: MutableMapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.record_id:
            raise ValueError("record_id must be provided")
        if not self.trace_id:
            raise ValueError("trace_id must be provided")
        if not self.metrics:
            raise ValueError("metrics must not be empty")
        self.timestamp = _ensure_utc(self.timestamp)

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "record_id": self.record_id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp.isoformat(),
            "metrics": dict(self.metrics),
        }
        if self.span_id:
            payload["span_id"] = self.span_id
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


class PhoenixClient:
    """Minimal Phoenix API client.

    The client keeps a cache of dataset identifiers to avoid duplicate
    registrations and exposes helpers for trace and evaluation ingestion.
    """

    def __init__(
        self,
        base_url: str,
        transport: Optional[Transport] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._transport = transport or self._default_transport
        self._dataset_cache: Dict[str, str] = {}

    def _default_transport(self, method: str, path: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        raise RuntimeError(
            "PhoenixClient transport not configured; provide a callable via the transport argument."
        )

    def register_dataset(self, dataset: Dataset) -> str:
        """Register a dataset if necessary and return its Phoenix identifier."""

        if dataset.name in self._dataset_cache:
            return self._dataset_cache[dataset.name]

        response = self._transport("POST", "/v1/datasets", dataset.to_payload())
        dataset_id = response.get("dataset_id") or response.get("id")
        if not dataset_id:
            raise ValueError("Phoenix response missing dataset identifier")
        self._dataset_cache[dataset.name] = str(dataset_id)
        return str(dataset_id)

    def log_spans(self, dataset_id: str, spans: Iterable[Mapping[str, Any]]) -> Mapping[str, Any]:
        spans_list = [dict(span) for span in spans if span]
        if not spans_list:
            return {}
        return self._transport(
            "POST",
            f"/v1/datasets/{dataset_id}/spans",
            {"spans": spans_list},
        )

    def update_evaluation(
        self,
        dataset_id: str,
        evaluation_name: str,
        results: Iterable[EvaluationResult],
    ) -> Mapping[str, Any]:
        payload_results = [result.to_payload() for result in results]
        if not payload_results:
            return {}
        return self._transport(
            "POST",
            f"/v1/datasets/{dataset_id}/evaluations/{evaluation_name}",
            {
                "dataset_id": dataset_id,
                "evaluation_name": evaluation_name,
                "results": payload_results,
            },
        )

    def dataset_registered(self, dataset_name: str) -> bool:
        return dataset_name in self._dataset_cache
