"""Sampling configuration stubs."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TraceIdRatioBased:
    ratio: float
