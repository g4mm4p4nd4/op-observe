"""Utilities for exporting telemetry batches to Phoenix."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping

from .client import EvaluationResult, PhoenixClient
from ..telemetry.models import EvaluationMetric, TelemetryBatch, TraceSpan


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _clean_dict(data: Mapping[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


@dataclass
class PhoenixExporter:
    """High-level helper that exports telemetry batches to Phoenix."""

    client: PhoenixClient

    def export_batch(self, batch: TelemetryBatch) -> str:
        """Export traces and evaluations to Phoenix.

        The method ensures that the dataset is registered, uploads OpenInference
        spans, and upserts evaluation results grouped by evaluation name.
        """

        dataset_id = self.client.register_dataset(batch.dataset)
        spans_payload = [self._span_to_payload(span) for span in batch.iter_spans()]
        if spans_payload:
            self.client.log_spans(dataset_id, spans_payload)

        grouped_evaluations = self._group_evaluations(batch.iter_evaluations())
        for evaluation_name, results in grouped_evaluations.items():
            self.client.update_evaluation(dataset_id, evaluation_name, results)
        return dataset_id

    def _span_to_payload(self, span: TraceSpan) -> Dict[str, Any]:
        attributes, open_inference = self._split_open_inference(span.attributes)
        payload: Dict[str, Any] = {
            "trace_id": span.trace_id,
            "span_id": span.span_id,
            "name": span.name,
            "start_time": span.start_time.isoformat(),
            "end_time": span.end_time.isoformat(),
            "duration_ms": span.duration_ms,
        }
        if span.parent_span_id:
            payload["parent_span_id"] = span.parent_span_id
        if span.kind:
            payload["kind"] = span.kind
        status = _clean_dict({"code": span.status_code, "message": span.status_message})
        if status:
            payload["status"] = status
        if attributes:
            payload["attributes"] = _clean_dict(attributes)
        if open_inference:
            payload["open_inference"] = open_inference
        return payload

    def _split_open_inference(
        self, attributes: MutableMapping[str, Any]
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        general: Dict[str, Any] = {}
        open_inference: Dict[str, Any] = {}
        for key, value in attributes.items():
            if key.startswith("openinference."):
                open_inference[key.split(".", 1)[1]] = value
            else:
                general[key] = value
        return general, open_inference

    def _group_evaluations(
        self, evaluations: Iterable[EvaluationMetric]
    ) -> Dict[str, List[EvaluationResult]]:
        grouped: Dict[str, Dict[str, EvaluationResult]] = defaultdict(dict)
        for metric in evaluations:
            record_id = str(metric.metadata.get("record_id") or metric.trace_id)
            evaluation_bucket = grouped[metric.evaluation_name]
            if record_id not in evaluation_bucket:
                metadata = dict(metric.metadata)
                metadata.pop("record_id", None)
                evaluation_bucket[record_id] = EvaluationResult(
                    record_id=record_id,
                    trace_id=metric.trace_id,
                    span_id=metric.span_id,
                    metrics={metric.metric_name: float(metric.value)},
                    metadata=metadata,
                    timestamp=metric.timestamp,
                )
            else:
                result = evaluation_bucket[record_id]
                result.metrics[metric.metric_name] = float(metric.value)
                if metric.metadata:
                    metadata = dict(metric.metadata)
                    metadata.pop("record_id", None)
                    result.metadata.update(metadata)
                candidate_ts = _ensure_utc(metric.timestamp)
                if candidate_ts > result.timestamp:
                    result.timestamp = candidate_ts
                if metric.span_id and not result.span_id:
                    result.span_id = metric.span_id
        return {name: list(results.values()) for name, results in grouped.items()}
