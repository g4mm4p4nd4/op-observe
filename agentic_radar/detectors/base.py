"""Common utilities for Agentic Radar detectors."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional, Sequence, Set


@dataclass
class Finding:
    """Base finding returned by detectors."""

    detector: str
    name: str
    location: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


def format_location(path: Path, lineno: Optional[int]) -> str:
    """Return a human-friendly location string."""

    if lineno:
        return f"{path}:{lineno}"
    return str(path)


class SourceWalker:
    """Utility mixin that walks files and directories."""

    def __init__(self, *, extensions: Optional[Sequence[str]] = None) -> None:
        self._extensions: Optional[Set[str]] = set(extensions) if extensions else None

    def iter_files(self, paths: Iterable[Path | str]) -> Iterator[Path]:
        """Yield source files under *paths* respecting configured extensions."""

        for raw_path in paths:
            path = Path(raw_path)
            if path.is_dir():
                yield from self._iter_directory(path)
            elif path.is_file():
                if self._should_include(path):
                    yield path

    def _iter_directory(self, directory: Path) -> Iterator[Path]:
        for path in directory.rglob("*"):
            if path.is_file() and self._should_include(path):
                yield path

    def _should_include(self, path: Path) -> bool:
        if not self._extensions:
            return True
        return path.suffix in self._extensions


def normalise_string(value: Optional[str]) -> Optional[str]:
    """Normalise a string for comparison by lowercasing and stripping."""

    if value is None:
        return None
    return value.strip().lower()
