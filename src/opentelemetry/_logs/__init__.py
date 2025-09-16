"""Global logger provider registry."""

from __future__ import annotations

from typing import Optional

from ..sdk._logs import LoggerProvider
from ..sdk.resources import Resource


_LOGGER_PROVIDER: Optional[LoggerProvider] = None


def get_logger_provider() -> LoggerProvider:
    global _LOGGER_PROVIDER
    if _LOGGER_PROVIDER is None:
        _LOGGER_PROVIDER = LoggerProvider(Resource.get_empty())
    return _LOGGER_PROVIDER


def set_logger_provider(provider: LoggerProvider) -> None:
    global _LOGGER_PROVIDER
    _LOGGER_PROVIDER = provider
