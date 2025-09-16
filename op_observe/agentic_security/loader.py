"""Loading helpers for versioned OWASP mapping tables."""

from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from importlib import resources
from typing import Dict, Iterable, Tuple

from .models import Category, CategoryMatcher, MappingTable

_DATA_PACKAGE = "op_observe.agentic_security.data"
_LLM_NAMESPACE = "owasp_llm_top10"
_AGENTIC_NAMESPACE = "owasp_agentic_ai"


def _version_sort_key(version: str) -> Tuple[int, ...]:
    parts: list[int] = []
    for element in version.replace("-", ".").split("."):
        if element.isdigit():
            parts.append(int(element))
        else:
            # Fallback for alphanumeric segments; use their ordinal values.
            parts.extend(ord(ch) for ch in element)
    return tuple(parts)


def _iter_version_files(namespace: str) -> Iterable[resources.abc.Traversable]:
    package = f"{_DATA_PACKAGE}.{namespace}"
    data_path = resources.files(package)
    for resource in data_path.iterdir():
        if resource.name.endswith(".json"):
            yield resource


@lru_cache(maxsize=None)
def _available_versions(namespace: str) -> Dict[str, str]:
    versions: Dict[str, str] = {}
    for resource in _iter_version_files(namespace):
        with resource.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        version = str(payload["version"])
        versions[version] = resource.name
    return versions


def list_llm_top10_versions() -> Tuple[str, ...]:
    """Return the available versions for the OWASP LLM Top-10 table."""
    versions = sorted(_available_versions(_LLM_NAMESPACE), key=_version_sort_key)
    return tuple(versions)


def list_agentic_ai_versions() -> Tuple[str, ...]:
    """Return the available versions for the OWASP Agentic-AI table."""
    versions = sorted(_available_versions(_AGENTIC_NAMESPACE), key=_version_sort_key)
    return tuple(versions)


def _resolve_version(namespace: str, requested: str | None) -> Tuple[str, str]:
    available = _available_versions(namespace)
    if not available:
        raise ValueError(f"No mapping tables available for namespace '{namespace}'")
    if requested is None:
        version = sorted(available, key=_version_sort_key)[-1]
    else:
        version = requested
    try:
        filename = available[version]
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise ValueError(
            f"Unknown version '{version}' for namespace '{namespace}'."
        ) from exc
    return version, filename


@lru_cache(maxsize=None)
def _load_mapping(namespace: str, version: str) -> MappingTable:
    _, filename = _resolve_version(namespace, version)
    package = f"{_DATA_PACKAGE}.{namespace}"
    resource = resources.files(package).joinpath(filename)
    with resource.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    published = date.fromisoformat(payload["published"])
    scheme = payload["scheme"]
    resolved_version = payload["version"]

    categories = []
    index: Dict[str, Category] = {}
    for raw in payload["categories"]:
        matchers = CategoryMatcher(
            detectors=tuple(raw.get("matchers", {}).get("detectors", ())),
            tags=tuple(raw.get("matchers", {}).get("tags", ())),
        )
        category = Category(
            table_scheme=scheme,
            table_version=resolved_version,
            id=raw["id"],
            name=raw["name"],
            description=raw["description"],
            matchers=matchers,
            mitigations=tuple(raw.get("mitigations", ())),
            references=tuple(raw.get("references", ())),
        )
        categories.append(category)
        index[category.id] = category

    return MappingTable(
        scheme=scheme,
        version=resolved_version,
        published=published,
        source=payload["source"],
        categories=tuple(categories),
        _category_index=index,
    )


def get_llm_top10_mapping(version: str | None = None) -> MappingTable:
    """Load the OWASP LLM Top-10 mapping table."""
    resolved, _ = _resolve_version(_LLM_NAMESPACE, version)
    return _load_mapping(_LLM_NAMESPACE, resolved)


def get_agentic_ai_mapping(version: str | None = None) -> MappingTable:
    """Load the OWASP Agentic-AI mapping table."""
    resolved, _ = _resolve_version(_AGENTIC_NAMESPACE, version)
    return _load_mapping(_AGENTIC_NAMESPACE, resolved)
