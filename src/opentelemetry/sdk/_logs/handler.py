"""Bridge between Python logging and the lightweight log SDK."""

from __future__ import annotations

import logging
from typing import Any, Dict

from opentelemetry.sdk._logs import LoggerProvider, LogData, LogRecord
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.util import InstrumentationScope
from ...instrumentation.logging import get_active_log_hook


_LOG_RECORD_IGNORED_FIELDS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
}


class LoggingHandler(logging.Handler):
    def __init__(self, level: int = logging.NOTSET, logger_provider: LoggerProvider | None = None) -> None:
        super().__init__(level)
        self._logger_provider = logger_provider or LoggerProvider(Resource.get_empty())

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
            attributes: Dict[str, Any] = {
                key: value
                for key, value in record.__dict__.items()
                if key not in _LOG_RECORD_IGNORED_FIELDS
            }
            log_record = LogRecord(
                body=message,
                severity_text=record.levelname,
                severity_number=record.levelno,
                attributes=attributes,
            )
            log_record.trace_id = getattr(record, "trace_id", None)
            log_record.span_id = getattr(record, "span_id", None)
            if hasattr(record, "trace_flags"):
                log_record.trace_flags = getattr(record, "trace_flags")
            if hasattr(record, "trace_state"):
                log_record.trace_state = getattr(record, "trace_state")

            scope = InstrumentationScope(name=record.name)
            log_data = LogData(
                log_record=log_record,
                resource=self._logger_provider.resource,
                instrumentation_scope=scope,
            )

            hook = get_active_log_hook()
            if hook:
                hook(log_data, record)

            self._logger_provider.emit(log_data)
        except Exception:  # pragma: no cover - defensive
            self.handleError(record)
