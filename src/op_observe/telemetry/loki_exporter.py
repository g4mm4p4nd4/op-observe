"""OpenTelemetry log exporter that pushes records to Grafana Loki."""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, Iterable, Mapping, MutableMapping, Optional, Sequence, Tuple
from urllib import error, request
from urllib.parse import urljoin

from opentelemetry.sdk._logs import LogData
from opentelemetry.sdk._logs.export import ExportResult, LogExporter
from opentelemetry.sdk.resources import Resource


def _sanitize_label_key(key: str) -> str:
    """Return a Loki-compatible label key."""
    sanitized = key.replace(".", "_").replace("-", "_")
    if not sanitized:
        return "_"
    if sanitized[0].isdigit():
        sanitized = f"_{sanitized}"
    allowed = []
    for char in sanitized:
        if char.isalnum() or char in {"_", ":"}:
            allowed.append(char)
        else:
            allowed.append("_")
    result = "".join(allowed)
    if result[0] == ":":
        result = f"_{result}"
    return result


def _stringify(value: object) -> str:
    if isinstance(value, (str, bytes)):
        return value.decode() if isinstance(value, bytes) else value
    return json.dumps(value, sort_keys=True) if isinstance(value, (dict, list, tuple)) else str(value)


@dataclass
class LokiExporterConfig:
    """Runtime configuration for :class:`LokiLogExporter`."""

    endpoint: str
    tenant_id: Optional[str] = None
    push_path: str = "/loki/api/v1/push"
    timeout: float = 10.0
    default_labels: Mapping[str, str] = field(default_factory=dict)


class LokiLogExporter(LogExporter):
    """Export OpenTelemetry log batches to Loki using the HTTP push API."""

    def __init__(
        self,
        config: LokiExporterConfig,
        opener: Optional[request.OpenerDirector] = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._opener = opener or request.build_opener()
        self._push_url = urljoin(config.endpoint.rstrip("/") + "/", config.push_path.lstrip("/"))
        self._lock = threading.Lock()
        self._log = logging.getLogger(__name__)

    def export(self, batch: Sequence[LogData]) -> ExportResult:
        if not batch:
            return ExportResult.SUCCESS

        streams: Dict[Tuple[Tuple[str, str], ...], MutableMapping[str, object]] = {}

        for log_data in batch:
            labels = self._labels_from_log(log_data)
            label_key = tuple(sorted(labels.items()))
            stream = streams.get(label_key)
            if stream is None:
                stream = {"stream": labels, "values": []}
                streams[label_key] = stream
            stream_values = stream["values"]
            assert isinstance(stream_values, list)
            stream_values.append(self._serialize_value(log_data))

        payload = {"streams": list(streams.values())}

        headers = {"Content-Type": "application/json"}
        if self._config.tenant_id:
            headers["X-Scope-OrgID"] = self._config.tenant_id

        data = json.dumps(payload, separators=(",", ":")).encode()
        req = request.Request(self._push_url, data=data, headers=headers, method="POST")

        try:
            with self._lock:
                with self._opener.open(req, timeout=self._config.timeout) as resp:
                    status_code = resp.getcode()
                    body = resp.read().decode() if status_code >= 400 else ""
        except error.URLError as exc:  # pragma: no cover - network failure path
            self._log.warning("Failed to export logs to Loki", exc_info=exc)
            return ExportResult.FAILURE

        if status_code >= 400:
            self._log.warning(
                "Loki push request failed", extra={"status": status_code, "body": body}
            )
            return ExportResult.FAILURE

        return ExportResult.SUCCESS

    def shutdown(self) -> None:
        super().shutdown()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _labels_from_log(self, log_data: LogData) -> Dict[str, str]:
        record = log_data.log_record
        resource = log_data.resource or Resource.get_empty()
        labels: Dict[str, str] = {"level": record.severity_text or record.severity_number or "UNKNOWN"}
        labels.update({
            _sanitize_label_key(k): _stringify(v)
            for k, v in self._config.default_labels.items()
        })

        for key, value in resource.attributes.items():
            labels[_sanitize_label_key(key)] = _stringify(value)

        if log_data.instrumentation_scope:
            scope = log_data.instrumentation_scope
            if scope.name:
                labels.setdefault("instrumentation_scope", scope.name)
            if scope.version:
                labels.setdefault("instrumentation_version", scope.version)

        for key, value in (record.attributes or {}).items():
            labels[_sanitize_label_key(key)] = _stringify(value)

        if record.trace_id:
            labels.setdefault("trace_id", format(record.trace_id, "032x"))
        if record.span_id:
            labels.setdefault("span_id", format(record.span_id, "016x"))

        if record.trace_flags is not None:
            labels.setdefault("trace_flags", format(int(record.trace_flags), "02x"))

        if record.trace_state:
            labels.setdefault("trace_state", str(record.trace_state))

        return labels

    def _serialize_value(self, log_data: LogData) -> Iterable[str]:
        record = log_data.log_record
        timestamp = str(int(record.timestamp)) if record.timestamp else "0"
        body = _stringify(record.body)
        trace_id = ""
        span_id = ""
        if record.attributes:
            trace_id = record.attributes.get("trace_id", trace_id)
            span_id = record.attributes.get("span_id", span_id)
        if record.trace_id and not trace_id:
            trace_id = format(record.trace_id, "032x")
        if record.span_id and not span_id:
            span_id = format(record.span_id, "016x")

        extras = {}
        for key, value in (record.attributes or {}).items():
            if key in {"trace_id", "span_id"}:
                continue
            extras[key] = value

        parts = [body]
        if trace_id:
            parts.append(f"trace_id={trace_id}")
        if span_id:
            parts.append(f"span_id={span_id}")
        if extras:
            parts.append(f"attrs={json.dumps(extras, sort_keys=True)}")
        line = " | ".join(parts)
        return [timestamp, line]


__all__ = ["LokiLogExporter", "LokiExporterConfig"]
