"""Shared utility structures for the lightweight SDK."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class InstrumentationScope:
    name: str
    version: Optional[str] = None
