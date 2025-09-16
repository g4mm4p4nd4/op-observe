"""Simplified resource abstraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping


@dataclass
class Resource:
    attributes: Dict[str, object]

    @classmethod
    def create(cls, attributes: Mapping[str, object]) -> "Resource":
        return cls(dict(attributes))

    @classmethod
    def get_empty(cls) -> "Resource":
        return cls({})

    def merge(self, other: "Resource") -> "Resource":
        merged = dict(self.attributes)
        merged.update(other.attributes)
        return Resource(merged)
