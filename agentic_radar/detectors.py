"""Detectors for Agentic Radar findings."""

from __future__ import annotations

from typing import Iterable, List

from .models import ParsedProject, RadarFinding


class Detector:
    """Base detector."""

    name = "detector"

    def run(self, project: ParsedProject) -> List[RadarFinding]:
        raise NotImplementedError


class ToolInventoryDetector(Detector):
    """Ensure tool metadata is complete."""

    name = "tool-inventory"

    def run(self, project: ParsedProject) -> List[RadarFinding]:
        findings: List[RadarFinding] = []
        for tool in project.tools:
            if not tool.version:
                findings.append(
                    RadarFinding(
                        identifier=f"TOOL-NOVERSION::{tool.name}",
                        title=f"Tool '{tool.name}' is missing a pinned version",
                        severity="medium",
                        description=(
                            "Tools should be version pinned to ensure deterministic security reviews "
                            "and facilitate patch management."
                        ),
                        owasp_llm=["LLM02"],
                        owasp_agentic=["Agentic-Tooling"],
                        subject=tool.name,
                        remediation="Add an explicit version for the tool in the agent manifest.",
                        detector=self.name,
                        metadata={"source": tool.source},
                    )
                )
            if tool.source and tool.source.startswith("http"):
                findings.append(
                    RadarFinding(
                        identifier=f"TOOL-EXTERNAL::{tool.name}",
                        title=f"Tool '{tool.name}' is sourced from an external endpoint",
                        severity="low",
                        description=(
                            "External tool sources should be evaluated for supply-chain exposure and "
                            "guarded with allow-lists or sandboxes."
                        ),
                        owasp_llm=["LLM06"],
                        owasp_agentic=["Agentic-External-Tool"],
                        subject=tool.name,
                        remediation="Review the external tool source and enforce provenance controls.",
                        detector=self.name,
                        metadata={"source": tool.source},
                    )
                )
        return findings


class MCPDetector(Detector):
    """Detect misconfigurations in MCP server definitions."""

    name = "mcp-server"

    def run(self, project: ParsedProject) -> List[RadarFinding]:
        findings: List[RadarFinding] = []
        for server in project.mcp_servers:
            if not server.capabilities:
                findings.append(
                    RadarFinding(
                        identifier=f"MCP-NOCAP::{server.name}",
                        title=f"MCP server '{server.name}' does not declare capabilities",
                        severity="medium",
                        description=(
                            "Declare explicit MCP capabilities to apply least privilege controls and "
                            "map permissions to security policies."
                        ),
                        owasp_llm=["LLM08"],
                        owasp_agentic=["Agentic-MCP-LeastPrivilege"],
                        subject=server.name,
                        remediation="Document the MCP server capabilities and enforce policy checks.",
                        detector=self.name,
                        metadata={"endpoint": server.endpoint},
                    )
                )
            if server.auth_mode in (None, "anonymous", "none"):
                findings.append(
                    RadarFinding(
                        identifier=f"MCP-NOAUTH::{server.name}",
                        title=f"MCP server '{server.name}' has no authentication configured",
                        severity="high",
                        description=(
                            "Unprotected MCP servers expose powerful automation capabilities. Use "
                            "mutual authentication and scoped tokens."
                        ),
                        owasp_llm=["LLM04"],
                        owasp_agentic=["Agentic-MCP-Hardening"],
                        subject=server.name,
                        remediation="Require authentication and audit access for the MCP server.",
                        detector=self.name,
                        metadata={"endpoint": server.endpoint, "auth_mode": server.auth_mode},
                    )
                )
        return findings


class VulnerabilityDetector(Detector):
    """Emit findings for dependency vulnerabilities."""

    name = "dependency-vulnerability"

    severity_map = {
        "critical": "critical",
        "high": "high",
        "medium": "medium",
        "moderate": "medium",
        "low": "low",
    }

    def run(self, project: ParsedProject) -> List[RadarFinding]:
        findings: List[RadarFinding] = []
        for dependency in project.dependencies:
            for vulnerability in dependency.vulnerabilities:
                severity = vulnerability.get("severity", "unknown").lower()
                normalized = self.severity_map.get(severity, "unknown")
                identifier = vulnerability.get("id") or vulnerability.get("cve") or f"VULN::{dependency.name}"
                findings.append(
                    RadarFinding(
                        identifier=f"DEP-VULN::{dependency.name}::{identifier}",
                        title=f"Dependency '{dependency.name}' has a known vulnerability",
                        severity=normalized,
                        description=vulnerability.get(
                            "description",
                            "Dependency vulnerability reported by upstream advisory feeds.",
                        ),
                        owasp_llm=["LLM06"],
                        owasp_agentic=["Agentic-SupplyChain"],
                        subject=dependency.name,
                        remediation=vulnerability.get("fix_version"),
                        detector=self.name,
                        metadata={
                            "id": identifier,
                            "severity": severity,
                            "fix_version": vulnerability.get("fix_version"),
                        },
                    )
                )
        return findings


def run_detectors(project: ParsedProject, detectors: Iterable[Detector]) -> List[RadarFinding]:
    """Run detectors and aggregate findings."""

    findings: List[RadarFinding] = []
    for detector in detectors:
        findings.extend(detector.run(project))
    return findings
