"""Mitigation checklist helpers for mapped findings."""

from __future__ import annotations

from typing import Iterable

from .models import FindingMapping, MitigationChecklistEntry


def generate_mitigation_checklist(
    mappings: Iterable[FindingMapping],
) -> tuple[MitigationChecklistEntry, ...]:
    """Aggregate mitigations across mappings for reporting and remediation."""

    aggregated: dict[str, dict[str, object]] = {}

    for mapping in mappings:
        for category in mapping.all_categories():
            key = category.reference
            bucket = aggregated.setdefault(
                key,
                {
                    "category": category,
                    "finding_ids": set(),
                },
            )
            bucket["finding_ids"].add(mapping.finding.id)

    def _sort_key(entry: dict[str, object]) -> tuple[str, str]:
        category = entry["category"]
        return (category.table_scheme, category.id)

    checklist: list[MitigationChecklistEntry] = []
    for entry in sorted(aggregated.values(), key=_sort_key):
        category = entry["category"]
        finding_ids = tuple(sorted(entry["finding_ids"]))
        checklist.append(
            MitigationChecklistEntry(
                category=category,
                finding_ids=finding_ids,
                mitigations=category.mitigations,
            )
        )

    return tuple(checklist)
