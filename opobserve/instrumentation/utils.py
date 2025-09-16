"""Shared utilities for instrumentation bootstrap helpers."""

from __future__ import annotations

from typing import List, Optional, Sequence

from .registry import MetricDefinition, Wrapper


def unique_wrappers(*collections: Optional[Sequence[Wrapper]]) -> List[Wrapper]:
    """Return wrappers with duplicates removed while preserving order."""

    seen: set[Wrapper] = set()
    result: List[Wrapper] = []
    for collection in collections:
        if not collection:
            continue
        for wrapper in collection:
            if wrapper in seen:
                continue
            seen.add(wrapper)
            result.append(wrapper)
    return result


def unique_metrics(*collections: Optional[Sequence[MetricDefinition]]) -> List[MetricDefinition]:
    """Return metric definitions with duplicates removed by name."""

    seen: set[str] = set()
    result: List[MetricDefinition] = []
    for collection in collections:
        if not collection:
            continue
        for metric in collection:
            if metric.name in seen:
                continue
            seen.add(metric.name)
            result.append(metric)
    return result


__all__ = ["unique_wrappers", "unique_metrics"]
