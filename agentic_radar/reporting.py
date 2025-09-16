"""Report builder for Agentic Radar."""

from __future__ import annotations

from typing import Iterable, List, Optional

from .models import ParsedProject, RadarFinding, RadarReport, ScenarioResult


class ReportBuilder:
    """Construct structured radar reports."""

    def __init__(self, include_project_snapshot: bool = True) -> None:
        self.include_project_snapshot = include_project_snapshot

    def build(
        self,
        project: ParsedProject,
        findings: Iterable[RadarFinding],
        *,
        mode: str,
        trace_ids: Optional[Iterable[str]] = None,
        scenario_results: Optional[Iterable[ScenarioResult]] = None,
        metadata: Optional[dict] = None,
    ) -> RadarReport:
        findings_list = list(findings)
        trace_id_list = list(trace_ids or [])
        scenario_list = list(scenario_results or [])
        summary = {
            "findings": RadarReport.severity_totals(findings_list),
            "inventory": {
                "agents": len(project.agents),
                "tools": len(project.tools),
                "mcp_servers": len(project.mcp_servers),
                "dependencies": len(project.dependencies),
            },
            "mode": mode,
        }
        report = RadarReport(
            project_name=project.project_name,
            mode=mode,
            findings=findings_list,
            parsed_project=project if self.include_project_snapshot else None,
            summary=summary,
            trace_ids=trace_id_list,
            scenario_results=scenario_list,
            metadata=dict(metadata or {}),
        )
        return report


def build_report(
    project: ParsedProject,
    findings: Iterable[RadarFinding],
    *,
    mode: str,
    trace_ids: Optional[Iterable[str]] = None,
    scenario_results: Optional[Iterable[ScenarioResult]] = None,
    metadata: Optional[dict] = None,
    include_project_snapshot: bool = True,
) -> RadarReport:
    builder = ReportBuilder(include_project_snapshot=include_project_snapshot)
    return builder.build(
        project,
        findings,
        mode=mode,
        trace_ids=trace_ids,
        scenario_results=scenario_results,
        metadata=metadata,
    )
