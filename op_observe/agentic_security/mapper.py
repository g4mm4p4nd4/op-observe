"""Map radar findings to OWASP categories."""

from __future__ import annotations

from typing import Sequence

from .loader import get_agentic_ai_mapping, get_llm_top10_mapping
from .models import Category, FindingMapping, MappingTable, RadarFinding


def _match_categories(finding: RadarFinding, table: MappingTable) -> tuple[Category, ...]:
    matches: list[Category] = []
    for category in table:
        if category.matchers.matches(finding):
            matches.append(category)
    return tuple(matches)


def map_finding_to_tables(
    finding: RadarFinding,
    *,
    llm_mapping: MappingTable | None = None,
    agentic_mapping: MappingTable | None = None,
    extra_tables: Sequence[MappingTable] | None = None,
) -> FindingMapping:
    """Return the mapping for a finding against the available OWASP tables."""

    tables = []
    if llm_mapping is None:
        llm_mapping = get_llm_top10_mapping()
    if agentic_mapping is None:
        agentic_mapping = get_agentic_ai_mapping()

    tables.extend(table for table in (llm_mapping, agentic_mapping) if table is not None)
    if extra_tables:
        tables.extend(extra_tables)

    matches: dict[str, tuple[Category, ...]] = {}
    for table in tables:
        matched = _match_categories(finding, table)
        if matched:
            matches[table.scheme] = matched
    return FindingMapping(finding=finding, matches=matches)
