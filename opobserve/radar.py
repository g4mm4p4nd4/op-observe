"""Agentic-security radar scanning + report generation primitives."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence

from .telemetry import TelemetryCollector


@dataclass
class RadarReport:
    findings: Dict[str, object]
    json_path: Path
    html_path: Path


class RadarScanner:
    """Produces a simplified radar scan for integration testing."""

    def __init__(
        self,
        owasp_mapping: Dict[str, Dict[str, str]],
        evidence_dir: Path,
    ) -> None:
        self.owasp_mapping = owasp_mapping
        self.evidence_dir = evidence_dir
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

    def scan(self, agent, telemetry: TelemetryCollector) -> RadarReport:
        with telemetry.span("radar.scan", component="radar") as span:
            workflow = agent.workflow_graph()
            tools = agent.tool_inventory()
            mcp_servers = agent.mcp_inventory()
            vulnerabilities = self._identify_vulnerabilities(tools)
            findings = {
                "workflow": workflow,
                "tools": tools,
                "mcp_servers": mcp_servers,
                "vulnerabilities": vulnerabilities,
                "owasp_summary": [
                    {
                        "component": vuln["component"],
                        "owasp": vuln["owasp"],
                        "severity": vuln["severity"],
                    }
                    for vuln in vulnerabilities
                ],
                "evidence": {
                    "trace_links": agent.trace_links(telemetry),
                    "metrics": telemetry.metrics,
                },
            }
            json_path = self.evidence_dir / "radar-findings.json"
            html_path = self.evidence_dir / "radar-report.html"
            json_path.write_text(json.dumps(findings, indent=2), encoding="utf-8")
            html_path.write_text(self._render_html(findings), encoding="utf-8")
        telemetry.record_metric("radar_findings", len(vulnerabilities))
        telemetry.record_log(
            "radar.scan.completed vulns=%s latency=%.2fms" % (len(vulnerabilities), span.span.duration_ms)
        )
        return RadarReport(findings=findings, json_path=json_path, html_path=html_path)

    # ---- helpers ------------------------------------------------------
    def _identify_vulnerabilities(self, tools: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
        vulnerabilities: List[Dict[str, object]] = []
        for tool in tools:
            risk = tool.get("risk_category", "low")
            mappings = self.owasp_mapping.get(risk, {"llm": "LLM10", "agentic": "A0"})
            severity = "high" if risk == "high" else ("medium" if risk == "medium" else "low")
            vulnerabilities.append(
                {
                    "component": tool["name"],
                    "version": tool.get("version", "unknown"),
                    "severity": severity,
                    "owasp": {
                        "llm": mappings.get("llm", "LLM10"),
                        "agentic": mappings.get("agentic", "A0"),
                    },
                    "notes": tool.get("description", ""),
                }
            )
        return vulnerabilities

    def _render_html(self, findings: Dict[str, object]) -> str:
        workflow_nodes = findings["workflow"]["nodes"]
        workflow_edges = findings["workflow"]["edges"]
        tools = findings["tools"]
        mcp_servers = findings["mcp_servers"]
        vulnerabilities = findings["vulnerabilities"]
        evidence = findings["evidence"]
        html_sections = [
            "<html><head><title>Agentic Radar Report</title></head><body>",
            "<h1>Agentic Security Radar Report</h1>",
            "<h2>Workflow Visualization</h2>",
            "<pre>%s</pre>" % json.dumps({"nodes": workflow_nodes, "edges": workflow_edges}, indent=2),
            "<h2>Tool Inventory</h2>",
            "<ul>",
        ]
        for tool in tools:
            html_sections.append(
                "<li><strong>{name}</strong> v{version} — {description} (risk: {risk})</li>".format(
                    name=tool["name"],
                    version=tool.get("version", "unknown"),
                    description=tool.get("description", "n/a"),
                    risk=tool.get("risk_category", "unknown"),
                )
            )
        html_sections.extend(["</ul>", "<h2>MCP Servers</h2>", "<ul>"])
        for server in mcp_servers:
            html_sections.append(
                "<li>{name} — {endpoint} ({auth_mode})</li>".format(
                    name=server["name"], endpoint=server["endpoint"], auth_mode=server["auth_mode"]
                )
            )
        html_sections.extend(["</ul>", "<h2>Vulnerability Mapping</h2>", "<table>", "<tr><th>Component</th><th>Severity</th><th>OWASP-LLM</th><th>OWASP-Agentic</th></tr>"])
        for vuln in vulnerabilities:
            html_sections.append(
                "<tr><td>{component}</td><td>{severity}</td><td>{llm}</td><td>{agentic}</td></tr>".format(
                    component=vuln["component"],
                    severity=vuln["severity"],
                    llm=vuln["owasp"]["llm"],
                    agentic=vuln["owasp"]["agentic"],
                )
            )
        html_sections.extend(
            [
                "</table>",
                "<h2>Evidence</h2>",
                "<p>Traces: %s</p>" % ", ".join(evidence.get("trace_links", [])),
                "<p>Metrics keys: %s</p>" % ", ".join(sorted(evidence.get("metrics", {}).keys())),
                "</body></html>",
            ]
        )
        return "\n".join(html_sections)
