"""Logging instrumentation shim."""

from __future__ import annotations

import logging
from typing import Callable, Optional


_ACTIVE_INSTRUMENTOR: Optional["LoggingInstrumentor"] = None


class LoggingInstrumentor:
    def __init__(self) -> None:
        self._log_hook: Optional[Callable] = None
        self._format_applied = False

    def instrument(self, *, set_logging_format: bool = False, log_hook: Optional[Callable] = None) -> None:
        global _ACTIVE_INSTRUMENTOR
        self._log_hook = log_hook
        _ACTIVE_INSTRUMENTOR = self
        if set_logging_format and not self._format_applied:
            if not logging.getLogger().handlers:
                logging.basicConfig(
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s trace_id=%(trace_id)s span_id=%(span_id)s"
                )
            self._format_applied = True

    def uninstrument(self) -> None:
        global _ACTIVE_INSTRUMENTOR
        if _ACTIVE_INSTRUMENTOR is self:
            _ACTIVE_INSTRUMENTOR = None
        self._log_hook = None
        self._format_applied = False

    @property
    def log_hook(self) -> Optional[Callable]:
        return self._log_hook


def get_active_log_hook() -> Optional[Callable]:
    if _ACTIVE_INSTRUMENTOR is None:
        return None
    return _ACTIVE_INSTRUMENTOR.log_hook
