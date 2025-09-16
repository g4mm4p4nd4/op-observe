"""Agentic Radar style report generation for the LangGraph demo."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .agent_graph import SECURITY_METADATA, run_demo


@dataclass
class Vulnerability:
    component: str
    issue: str
    severity: str
    recommendation: str
    owasp_llm: List[str]
    owasp_agentic: List[str]
    evidence: Dict[str, Any]


def _detect_vulnerabilities(metadata: Dict[str, Any]) -> List[Vulnerability]:
    """Derive simple vulnerability findings from the supplied metadata."""

    findings: List[Vulnerability] = []
    for tool in metadata.get("tools", []):
        if "write" in tool.get("permissions", []) and not tool.get("input_validation", True):
            findings.append(
                Vulnerability(
                    component=tool["name"],
                    issue="Filesystem writes occur without sanitising user-controlled input",
                    severity="HIGH",
                    recommendation="Introduce path allow-listing and guardrail approval before writes",
                    owasp_llm=["LLM02: Insecure Output Handling", "LLM05: Supply Chain Vulnerabilities"],
                    owasp_agentic=["AA04: Over-Privileged Tools", "AA08: Unsafe Tool Invocation"],
                    evidence={"permissions": tool.get("permissions"), "input_validation": tool.get("input_validation")},
                )
            )
    for node in metadata.get("workflow", {}).get("nodes", []):
        if node.get("kind") == "llm":
            findings.append(
                Vulnerability(
                    component=node["id"],
                    issue="LLM node operates on untrusted prompts without schema validation",
                    severity="MEDIUM",
                    recommendation="Apply guardrails and schema enforcement for planner/responders",
                    owasp_llm=["LLM01: Prompt Injection", "LLM06: Sensitive Information Disclosure"],
                    owasp_agentic=["AA02: Input Validation Gaps"],
                    evidence={"outputs": node.get("outputs", [])},
                )
            )
    for server in metadata.get("mcp_servers", []):
        if "write" in server.get("capabilities", []):
            findings.append(
                Vulnerability(
                    component=server["name"],
                    issue="MCP server exposes write capability without authentication",
                    severity="HIGH",
                    recommendation="Require authentication tokens and scoped permissions for MCP endpoints",
                    owasp_llm=["LLM10: Model Theft"],
                    owasp_agentic=["AA07: Untrusted Integrations"],
                    evidence={"auth": server.get("auth"), "capabilities": server.get("capabilities")},
                )
            )
    return findings


def _render_workflow(workflow: Dict[str, Any]) -> str:
    """Create a text representation of the workflow graph suitable for HTML output."""

    lines = ["Nodes:"]
    for node in workflow.get("nodes", []):
        lines.append(f"  - {node['id']} ({node['kind']}): {node.get('description', '')}")
    lines.append("Edges:")
    for edge in workflow.get("edges", []):
        lines.append(f"  - {edge['source']} -> {edge['target']}")
    return "\n".join(lines)


def _render_table(headers: Iterable[str], rows: Iterable[Iterable[Any]]) -> str:
    head_html = "".join(f"<th>{header}</th>" for header in headers)
    row_html = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows
    )
    return f"<table><thead><tr>{head_html}</tr></thead><tbody>{row_html}</tbody></table>"


def _build_report_bundle(question: str, run_state: Dict[str, Any]) -> Dict[str, Any]:
    """Assemble the JSON bundle that mirrors the HTML report."""

    metadata = SECURITY_METADATA
    vulnerabilities = _detect_vulnerabilities(metadata)
    return {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "question": question,
        "answer": run_state.get("answer"),
        "workflow": metadata.get("workflow"),
        "tools": metadata.get("tools"),
        "mcp_servers": metadata.get("mcp_servers"),
        "dependencies": metadata.get("dependencies"),
        "vulnerabilities": [
            {
                "component": finding.component,
                "issue": finding.issue,
                "severity": finding.severity,
                "recommendation": finding.recommendation,
                "owasp_llm": finding.owasp_llm,
                "owasp_agentic": finding.owasp_agentic,
                "evidence": finding.evidence,
            }
            for finding in vulnerabilities
        ],
        "evidence": {
            "state": run_state,
            "policy_hash": "demo-policy-v1",
        },
    }


def _render_html(bundle: Dict[str, Any]) -> str:
    workflow_section = _render_workflow(bundle.get("workflow", {}))
    tools_section = _render_table(
        ["Tool", "Origin", "Permissions", "Validation"],
        (
            (
                tool.get("name"),
                tool.get("origin"),
                ", ".join(tool.get("permissions", [])),
                "✅" if tool.get("input_validation") else "⚠️",
            )
            for tool in bundle.get("tools", [])
        ),
    )
    mcp_section = _render_table(
        ["Server", "URI", "Capabilities", "Auth"],
        (
            (
                server.get("name"),
                server.get("uri"),
                ", ".join(server.get("capabilities", [])),
                server.get("auth"),
            )
            for server in bundle.get("mcp_servers", [])
        ),
    )
    vuln_section = _render_table(
        [
            "Component",
            "Issue",
            "Severity",
            "OWASP LLM",
            "OWASP Agentic",
            "Recommendation",
        ],
        (
            (
                vuln.get("component"),
                vuln.get("issue"),
                vuln.get("severity"),
                "<br/>".join(vuln.get("owasp_llm", [])),
                "<br/>".join(vuln.get("owasp_agentic", [])),
                vuln.get("recommendation"),
            )
            for vuln in bundle.get("vulnerabilities", [])
        ),
    )
    evidence_json = json.dumps(bundle.get("evidence", {}), indent=2)
    return f"""
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <title>Agentic Security Radar Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 1.5rem; }}
    th, td {{ border: 1px solid #ddd; padding: 0.5rem; text-align: left; }}
    th {{ background-color: #0d1b2a; color: #f8f9fa; }}
    pre {{ background: #f1f3f5; padding: 1rem; overflow-x: auto; }}
  </style>
</head>
<body>
  <h1>Agentic Security Radar Report</h1>
  <p><strong>Generated:</strong> {bundle.get("generated_at")}</p>
  <p><strong>Question:</strong> {bundle.get("question")}</p>
  <h2>Workflow Visualization</h2>
  <pre>{workflow_section}</pre>
  <h2>Tool Inventory</h2>
  {tools_section}
  <h2>MCP Servers</h2>
  {mcp_section}
  <h2>Vulnerability Mapping</h2>
  {vuln_section}
  <h2>Evidence</h2>
  <pre>{evidence_json}</pre>
</body>
</html>
"""


def generate_security_report(
    question: str = "How are filesystem tools governed?",
    output_dir: Path | None = None,
) -> Tuple[Path, Path]:
    """Run the demo workflow and emit HTML + JSON security artifacts."""

    if output_dir is None:
        output_dir = Path.cwd() / "artifacts" / "agentic_security"
    output_dir.mkdir(parents=True, exist_ok=True)
    run_state = run_demo(question)
    bundle = _build_report_bundle(question, run_state)
    html_path = output_dir / "security_report.html"
    json_path = output_dir / "security_report.json"
    html_path.write_text(_render_html(bundle), encoding="utf-8")
    json_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    return html_path, json_path


def main() -> None:
    html_path, json_path = generate_security_report()
    print("Generated report:", html_path)
    print("Generated evidence bundle:", json_path)


if __name__ == "__main__":
    main()
