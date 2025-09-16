"""Data models for Agentic Radar."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class Tool:
    """Representation of a tool used by an agent."""

    name: str
    version: Optional[str] = None
    source: Optional[str] = None
    scope: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "source": self.source,
            "scope": self.scope,
        }


@dataclass
class MCPServer:
    """Representation of an MCP server referenced by the project."""

    name: str
    endpoint: str
    capabilities: List[str] = field(default_factory=list)
    auth_mode: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "endpoint": self.endpoint,
            "capabilities": list(self.capabilities),
            "auth_mode": self.auth_mode,
        }


@dataclass
class Dependency:
    """Dependency inventory item."""

    name: str
    version: Optional[str] = None
    license: Optional[str] = None
    vulnerabilities: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "license": self.license,
            "vulnerabilities": list(self.vulnerabilities),
        }


@dataclass
class AgentComponent:
    """Agent component definition."""

    name: str
    description: Optional[str] = None
    tools: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "tools": list(self.tools),
        }


@dataclass
class ParsedProject:
    """Parsed representation of a project."""

    root: Path
    project_name: str
    agents: List[AgentComponent] = field(default_factory=list)
    tools: List[Tool] = field(default_factory=list)
    mcp_servers: List[MCPServer] = field(default_factory=list)
    dependencies: List[Dependency] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root": str(self.root),
            "project_name": self.project_name,
            "agents": [agent.to_dict() for agent in self.agents],
            "tools": [tool.to_dict() for tool in self.tools],
            "mcp_servers": [server.to_dict() for server in self.mcp_servers],
            "dependencies": [dep.to_dict() for dep in self.dependencies],
            "metadata": dict(self.metadata),
        }


def normalize_severity(value: str) -> str:
    """Normalize severity strings to a canonical lowercase form."""

    normalized = (value or "unknown").strip().lower()
    if normalized in {"critical", "high", "medium", "low", "info"}:
        return normalized
    return "unknown"


@dataclass
class RadarFinding:
    """Finding emitted by the radar detectors."""

    identifier: str
    title: str
    severity: str
    description: str
    owasp_llm: List[str] = field(default_factory=list)
    owasp_agentic: List[str] = field(default_factory=list)
    subject: Optional[str] = None
    remediation: Optional[str] = None
    detector: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.identifier,
            "title": self.title,
            "severity": normalize_severity(self.severity),
            "description": self.description,
            "owasp_llm": list(self.owasp_llm),
            "owasp_agentic": list(self.owasp_agentic),
            "subject": self.subject,
            "remediation": self.remediation,
            "detector": self.detector,
            "metadata": dict(self.metadata),
        }


@dataclass
class ScenarioResult:
    """Outcome of a scenario-based radar test."""

    name: str
    status: str
    details: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "details": self.details,
        }


@dataclass
class RadarReport:
    """Final report produced by the radar."""

    project_name: str
    mode: str
    generated_at: str = field(default_factory=_now_utc_iso)
    findings: List[RadarFinding] = field(default_factory=list)
    parsed_project: Optional[ParsedProject] = None
    summary: Dict[str, Any] = field(default_factory=dict)
    trace_ids: List[str] = field(default_factory=list)
    scenario_results: List[ScenarioResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        parsed = self.parsed_project.to_dict() if self.parsed_project else None
        return {
            "project_name": self.project_name,
            "mode": self.mode,
            "generated_at": self.generated_at,
            "summary": dict(self.summary),
            "findings": [finding.to_dict() for finding in self.findings],
            "parsed_project": parsed,
            "trace_ids": list(self.trace_ids),
            "scenario_results": [result.to_dict() for result in self.scenario_results],
            "metadata": dict(self.metadata),
        }

    def write_json(self, path: Path) -> None:
        import json

        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(self.to_dict(), file, indent=2)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "RadarReport":
        findings = [
            RadarFinding(
                identifier=item.get("id", "unknown"),
                title=item.get("title", ""),
                severity=item.get("severity", "unknown"),
                description=item.get("description", ""),
                owasp_llm=item.get("owasp_llm", []),
                owasp_agentic=item.get("owasp_agentic", []),
                subject=item.get("subject"),
                remediation=item.get("remediation"),
                detector=item.get("detector"),
                metadata=item.get("metadata", {}),
            )
            for item in payload.get("findings", [])
        ]
        scenario_results = [
            ScenarioResult(
                name=item.get("name", "unknown"),
                status=item.get("status", "unknown"),
                details=item.get("details"),
            )
            for item in payload.get("scenario_results", [])
        ]
        parsed_payload = payload.get("parsed_project")
        parsed_project = None
        if parsed_payload:
            parsed_project = ParsedProject(
                root=Path(parsed_payload.get("root", ".")),
                project_name=parsed_payload.get("project_name", "unknown"),
                agents=[
                    AgentComponent(
                        name=item.get("name", "unknown"),
                        description=item.get("description"),
                        tools=item.get("tools", []),
                    )
                    for item in parsed_payload.get("agents", [])
                ],
                tools=[
                    Tool(
                        name=item.get("name", "unknown"),
                        version=item.get("version"),
                        source=item.get("source"),
                        scope=item.get("scope"),
                    )
                    for item in parsed_payload.get("tools", [])
                ],
                mcp_servers=[
                    MCPServer(
                        name=item.get("name", "unknown"),
                        endpoint=item.get("endpoint", ""),
                        capabilities=item.get("capabilities", []),
                        auth_mode=item.get("auth_mode"),
                    )
                    for item in parsed_payload.get("mcp_servers", [])
                ],
                dependencies=[
                    Dependency(
                        name=item.get("name", "unknown"),
                        version=item.get("version"),
                        license=item.get("license"),
                        vulnerabilities=item.get("vulnerabilities", []),
                    )
                    for item in parsed_payload.get("dependencies", [])
                ],
                metadata=parsed_payload.get("metadata", {}),
            )
        return cls(
            project_name=payload.get("project_name", "unknown"),
            mode=payload.get("mode", "scan"),
            generated_at=payload.get("generated_at", _now_utc_iso()),
            findings=findings,
            parsed_project=parsed_project,
            summary=payload.get("summary", {}),
            trace_ids=payload.get("trace_ids", []),
            scenario_results=scenario_results,
            metadata=payload.get("metadata", {}),
        )

    @staticmethod
    def severity_totals(findings: Iterable[RadarFinding]) -> Dict[str, int]:
        totals: Dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0, "unknown": 0}
        for finding in findings:
            severity = normalize_severity(finding.severity)
            totals.setdefault(severity, 0)
            totals[severity] += 1
        totals["total"] = sum(v for k, v in totals.items() if k != "total")
        return totals
