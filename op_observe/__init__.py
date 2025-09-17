"""Baseline namespace exports for the :mod:`op_observe` package.

This module exists to provide a consistent import surface across branches so
that feature work does not fight over the package initializer. Do **not**
modify this file in feature branches; propose changes through the baseline
update process instead.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Iterable

__all__ = [
    "observability",
    "security",
    "retrieval",
    "telemetry",
    "enablement",
    "core",
]


def _iter_public_names() -> Iterable[str]:
    """Return the public attribute names for :func:`__dir__`."""

    return set(globals()) | set(__all__)


def __getattr__(name: str) -> ModuleType:
    """Lazily import reserved submodules when they are first accessed."""

    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    try:
        return importlib.import_module(f".{name}", __name__)
    except ModuleNotFoundError as exc:  # pragma: no cover - defensive guard
        if exc.name == f"{__name__}.{name}":
            raise AttributeError(
                f"Baseline namespace {name!r} is reserved but not yet implemented."
            ) from exc
        raise


def __dir__() -> list[str]:
    """Expose the baseline namespace for better auto-completion support."""

    return sorted(_iter_public_names())
