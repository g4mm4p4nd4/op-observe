"""Helper factories to construct lightweight instrumentation wrappers."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from .registry import Wrapper


def annotate_wrapper(attribute: str, value: str) -> Wrapper:
    """Return a wrapper that annotates the wrapped callable.

    The decorator attaches ``attribute`` with the provided ``value`` to the
    wrapper which makes it easy for downstream integrations to inspect the
    instrumentation intent without requiring concrete OpenTelemetry
    dependencies at import time.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        setattr(wrapped, attribute, value)
        return wrapped

    return decorator


def attach_metadata(**metadata: str) -> Wrapper:
    """Attach arbitrary string metadata to the wrapped callable."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        for key, value in metadata.items():
            setattr(wrapped, key, value)
        return wrapped

    return decorator


__all__ = ["annotate_wrapper", "attach_metadata"]
