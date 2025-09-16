"""Security radar module with OWASP-oriented reporting."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from html import escape
from typing import Iterable, List, Mapping, Sequence

from .telemetry import TelemetryAgent


@dataclass(slots=True)
class SecurityFinding:
    """Represents a radar finding."""

    agent: str
    component: str
    version: str | None
    severity: str
    cve: str | None
    owasp_llm: Sequence[str] = field(default_factory=tuple)
    owasp_agentic: Sequence[str] = field(default_factory=tuple)
    notes: str | None = None


class SecurityAgent:
    """Performs lightweight radar scans over agent specs."""

    def __init__(
        self,
        vulnerability_db: Mapping[str, Mapping[str, object]] | None = None,
        telemetry: TelemetryAgent | None = None,
    ) -> None:
        self._vuln_db = vulnerability_db or {}
        self._telemetry = telemetry
        self._initialized = False

    def initialize(self) -> None:
        self._initialized = True

    def scan(self, agent_specs: Iterable[Mapping[str, object]]) -> List[SecurityFinding]:
        if not self._initialized:
            raise RuntimeError("SecurityAgent must be initialized before scanning")

        agent_specs_list = list(agent_specs)
        findings: List[SecurityFinding] = []
        for agent in agent_specs_list:
            agent_name = str(agent.get("name", "unknown"))
            tools = agent.get("tools", [])
            for tool in tools:
                tool_name = str(tool.get("name", "tool"))
                tool_version = tool.get("version")
                vuln_info = self._vuln_db.get(tool_name)
                if vuln_info:
                    findings.append(
                        SecurityFinding(
                            agent=agent_name,
                            component=tool_name,
                            version=str(tool_version) if tool_version is not None else None,
                            severity=str(vuln_info.get("severity", "unknown")),
                            cve=str(vuln_info.get("cve")) if vuln_info.get("cve") else None,
                            owasp_llm=tuple(vuln_info.get("owasp_llm", [])),
                            owasp_agentic=tuple(vuln_info.get("owasp_agentic", [])),
                            notes=str(vuln_info.get("notes")) if vuln_info.get("notes") else None,
                        )
                    )

        if self._telemetry:
            self._telemetry.record_event(
                "radar_scan",
                {
                    "total_agents": len(agent_specs_list),
                    "findings": len(findings),
                },
            )
        return findings

    def _render_workflow(self, agent_specs: Sequence[Mapping[str, object]]) -> str:
        lines = ["Agents and tool flows:"]
        for agent in agent_specs:
            name = escape(str(agent.get("name", "unknown")))
            tools = agent.get("tools", [])
            tool_names = ", ".join(escape(str(tool.get("name", "tool"))) for tool in tools) or "No tools"
            lines.append(f"- {name}: {tool_names}")
        return "\n".join(lines)

    def _collect_tools(self, agent_specs: Sequence[Mapping[str, object]]) -> List[Mapping[str, object]]:
        inventory: List[Mapping[str, object]] = []
        for agent in agent_specs:
            for tool in agent.get("tools", []):
                inventory.append(
                    {
                        "agent": agent.get("name", "unknown"),
                        "name": tool.get("name", "tool"),
                        "version": tool.get("version"),
                        "source": tool.get("source", "internal"),
                    }
                )
        return inventory

    def _collect_mcp(self, agent_specs: Sequence[Mapping[str, object]]) -> List[Mapping[str, object]]:
        servers: List[Mapping[str, object]] = []
        for agent in agent_specs:
            for server in agent.get("mcp_servers", []) or []:
                servers.append(
                    {
                        "agent": agent.get("name", "unknown"),
                        "endpoint": server.get("endpoint"),
                        "capabilities": server.get("capabilities", []),
                        "auth": server.get("auth", "unknown"),
                    }
                )
        return servers

    def render_report(
        self,
        *,
        agent_specs: Sequence[Mapping[str, object]],
        findings: Sequence[SecurityFinding],
        telemetry_snapshot: Mapping[str, object],
        mode: str,
    ) -> str:
        """Render a minimal HTML report satisfying the acceptance criteria."""

        workflow = escape(self._render_workflow(agent_specs))
        tool_inventory = "".join(
            f"<tr><td>{escape(str(tool['agent']))}</td><td>{escape(str(tool['name']))}</td>"
            f"<td>{escape(str(tool.get('version', 'n/a')))}</td><td>{escape(str(tool.get('source', 'internal')))}</td></tr>"
            for tool in self._collect_tools(agent_specs)
        )
        mcp_inventory = "".join(
            f"<tr><td>{escape(str(server['agent']))}</td><td>{escape(str(server.get('endpoint', '')))}</td>"
            f"<td>{escape(', '.join(server.get('capabilities', [])))}" 
            f"</td><td>{escape(str(server.get('auth', 'unknown')))}</td></tr>"
            for server in self._collect_mcp(agent_specs)
        )
        vuln_rows = "".join(
            f"<tr><td>{escape(finding.agent)}</td><td>{escape(finding.component)}</td>"
            f"<td>{escape(finding.version or 'n/a')}</td><td>{escape(finding.cve or 'n/a')}</td>"
            f"<td>{escape(finding.severity)}</td>"
            f"<td>{escape(', '.join(finding.owasp_llm))}</td><td>{escape(', '.join(finding.owasp_agentic))}</td>"
            f"<td>{escape(finding.notes or '')}</td></tr>"
            for finding in findings
        )
        telemetry_summary = escape(str(telemetry_snapshot))

        return f"""
<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\" />
<title>OP-Observe Security Report</title>
</head>
<body>
<h1>Security Report</h1>
<p>Mode: {escape(mode)}</p>
<section>
<h2>Workflow Visualization</h2>
<pre>{workflow}</pre>
</section>
<section>
<h2>Tool Inventory</h2>
<table><tr><th>Agent</th><th>Tool</th><th>Version</th><th>Source</th></tr>{tool_inventory or '<tr><td colspan="4">No tools</td></tr>'}</table>
</section>
<section>
<h2>MCP Servers</h2>
<table><tr><th>Agent</th><th>Endpoint</th><th>Capabilities</th><th>Auth</th></tr>{mcp_inventory or '<tr><td colspan="4">None</td></tr>'}</table>
</section>
<section>
<h2>Vulnerability Mapping</h2>
<table><tr><th>Agent</th><th>Component</th><th>Version</th><th>CVE</th><th>Severity</th><th>OWASP-LLM</th><th>OWASP-Agentic</th><th>Notes</th></tr>{vuln_rows or '<tr><td colspan="8">No findings</td></tr>'}</table>
</section>
<section>
<h2>Guards &amp; Evals</h2>
<p>{telemetry_summary}</p>
</section>
</body>
</html>
"""

    def run(
        self,
        *,
        mode: str,
        agent_specs: Sequence[Mapping[str, object]],
        telemetry_snapshot: Mapping[str, object],
    ) -> dict[str, object]:
        agent_specs_list = list(agent_specs)
        findings = self.scan(agent_specs_list)
        report_html = self.render_report(
            agent_specs=agent_specs_list,
            findings=findings,
            telemetry_snapshot=telemetry_snapshot,
            mode=mode,
        )
        report_json = {
            "mode": mode,
            "workflow": [
                {
                    "agent": agent.get("name", "unknown"),
                    "tools": agent.get("tools", []),
                    "mcp_servers": agent.get("mcp_servers", []),
                }
                for agent in agent_specs_list
            ],
            "findings": [asdict(finding) for finding in findings],
        }
        return {
            "mode": mode,
            "findings": findings,
            "report_html": report_html,
            "report_json": report_json,
        }
