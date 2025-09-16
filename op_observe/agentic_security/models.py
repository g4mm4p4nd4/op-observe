"""Data models for OWASP mapping tables and radar findings."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType
from typing import Mapping, Sequence, Tuple


def _normalize_sequence(values: Sequence[str]) -> Tuple[str, ...]:
    """Return a tuple of lower-cased unique values preserving input order."""
    seen = {}
    for value in values:
        normalized = value.strip().lower()
        if normalized and normalized not in seen:
            seen[normalized] = None
    return tuple(seen.keys())


@dataclass(frozen=True)
class CategoryMatcher:
    """Matching rules for assigning findings to OWASP categories."""

    detectors: Tuple[str, ...] = field(default_factory=tuple)
    tags: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "detectors", _normalize_sequence(self.detectors))
        object.__setattr__(self, "tags", _normalize_sequence(self.tags))

    def matches(self, finding: "RadarFinding") -> bool:
        """Return ``True`` when the matcher covers the provided finding."""
        if self.detectors and finding.detector in self.detectors:
            return True
        if self.tags and finding.tags_set.intersection(self.tags):
            return True
        return False


@dataclass(frozen=True)
class Category:
    """A single OWASP category entry."""

    table_scheme: str
    table_version: str
    id: str
    name: str
    description: str
    matchers: CategoryMatcher
    mitigations: Tuple[str, ...]
    references: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "table_scheme", self.table_scheme)
        object.__setattr__(self, "table_version", self.table_version)
        object.__setattr__(self, "id", self.id.strip())
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "description", self.description.strip())
        object.__setattr__(self, "mitigations", tuple(m.strip() for m in self.mitigations if m.strip()))
        object.__setattr__(self, "references", tuple(r.strip() for r in self.references if r.strip()))

    @property
    def reference(self) -> str:
        """Return a stable reference combining scheme and identifier."""
        return f"{self.table_scheme}:{self.id}"


@dataclass(frozen=True)
class MappingTable:
    """A versioned mapping table loaded from JSON resources."""

    scheme: str
    version: str
    published: date
    source: str
    categories: Tuple[Category, ...]
    _category_index: Mapping[str, Category] = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "scheme", self.scheme)
        object.__setattr__(self, "version", self.version)
        object.__setattr__(self, "source", self.source)
        object.__setattr__(self, "categories", tuple(self.categories))
        object.__setattr__(self, "_category_index", MappingProxyType(dict(self._category_index)))

    def category(self, category_id: str) -> Category:
        return self._category_index[category_id]

    def __iter__(self):
        return iter(self.categories)


@dataclass(frozen=True)
class RadarFinding:
    """Security finding emitted by the radar detector framework."""

    id: str
    detector: str
    tags: Sequence[str] = field(default_factory=tuple)
    severity: str = "medium"
    description: str | None = None
    metadata: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", self.id)
        object.__setattr__(self, "detector", self.detector.strip().lower())
        object.__setattr__(self, "severity", self.severity.strip().lower())
        object.__setattr__(self, "tags", _normalize_sequence(self.tags))
        if self.metadata is None:
            metadata: Mapping[str, object] = {}
        else:
            metadata = dict(self.metadata)
        object.__setattr__(self, "metadata", MappingProxyType(metadata))

    @property
    def tags_set(self) -> frozenset[str]:
        return frozenset(self.tags)


@dataclass(frozen=True)
class FindingMapping:
    """Mapping result for a single finding across multiple tables."""

    finding: RadarFinding
    matches: Mapping[str, Tuple[Category, ...]]

    def __post_init__(self) -> None:
        normalized = {scheme: tuple(categories) for scheme, categories in self.matches.items()}
        object.__setattr__(self, "matches", MappingProxyType(normalized))

    def categories_for_scheme(self, scheme: str) -> Tuple[Category, ...]:
        return self.matches.get(scheme, ())

    def all_categories(self) -> Tuple[Category, ...]:
        result: list[Category] = []
        for categories in self.matches.values():
            result.extend(categories)
        return tuple(result)


@dataclass(frozen=True)
class MitigationChecklistEntry:
    """Aggregated mitigation entry for reporting."""

    category: Category
    finding_ids: Tuple[str, ...]
    mitigations: Tuple[str, ...]
