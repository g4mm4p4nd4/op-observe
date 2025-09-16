"""Core helpers for building security radar findings and reports."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence
import zipfile

try:  # Python >=3.11
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - fallback for local tooling
    import tomli as tomllib  # type: ignore


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_security_config(path: Path | None) -> Dict[str, Any]:
    """Load the security configuration file when present."""
    if path is None:
        return {}
    if not path.exists():
        raise FileNotFoundError(f"Security config not found: {path}")
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value]
    return [str(value)]


def _normalise_name(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z_]", "_", value)


def _agent_records(agents_cfg: Mapping[str, Any]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for name, data in sorted(agents_cfg.items()):
        records.append(
            {
                "name": name,
                "description": data.get("description", ""),
                "tools": _as_list(data.get("tools")),
                "mcp_servers": _as_list(data.get("mcp_servers")),
            }
        )
    return records


def _tool_records(tools_cfg: Mapping[str, Any], referenced_tools: Iterable[str]) -> List[Dict[str, Any]]:
    tools: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for name in referenced_tools:
        seen.add(name)
        data = tools_cfg.get(name, {})
        tools.append(
            {
                "name": name,
                "version": data.get("version", "unknown"),
                "source": data.get("source", "unknown"),
                "permissions": _as_list(data.get("permissions")),
                "owasp_llm": _as_list(data.get("owasp_llm")),
                "owasp_agentic": _as_list(data.get("owasp_agentic")),
                "notes": data.get("notes", ""),
            }
        )
    # include additional tool definitions for completeness
    for name, data in sorted(tools_cfg.items()):
        if name in seen:
            continue
        tools.append(
            {
                "name": name,
                "version": data.get("version", "unknown"),
                "source": data.get("source", "unknown"),
                "permissions": _as_list(data.get("permissions")),
                "owasp_llm": _as_list(data.get("owasp_llm")),
                "owasp_agentic": _as_list(data.get("owasp_agentic")),
                "notes": data.get("notes", ""),
            }
        )
    return tools


def _mcp_records(mcp_cfg: Mapping[str, Any], referenced: Iterable[str]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for name in referenced:
        seen.add(name)
        data = mcp_cfg.get(name, {})
        records.append(
            {
                "name": name,
                "endpoint": data.get("endpoint", name),
                "auth_mode": data.get("auth_mode", "unknown"),
                "capabilities": _as_list(data.get("capabilities")),
                "notes": data.get("notes", ""),
            }
        )
    for name, data in sorted(mcp_cfg.items()):
        if name in seen:
            continue
        records.append(
            {
                "name": name,
                "endpoint": data.get("endpoint", name),
                "auth_mode": data.get("auth_mode", "unknown"),
                "capabilities": _as_list(data.get("capabilities")),
                "notes": data.get("notes", ""),
            }
        )
    return records


def generate_radar_findings(config: Mapping[str, Any], *, commit: str | None = None) -> Dict[str, Any]:
    """Derive radar findings from the static configuration."""

    metadata = config.get("metadata", {})
    agents_cfg: Mapping[str, Any] = config.get("agents", {})
    tools_cfg: Mapping[str, Any] = config.get("tools", {})
    mcp_cfg: Mapping[str, Any] = config.get("mcp_servers", {})

    agents = _agent_records(agents_cfg)
    referenced_tools = [tool for agent in agents for tool in agent["tools"]]
    referenced_mcp = [mcp for agent in agents for mcp in agent["mcp_servers"]]

    workflow: List[Dict[str, str]] = []
    for agent in agents:
        agent_name = agent["name"]
        for tool in agent["tools"]:
            workflow.append({"source": agent_name, "target": tool, "type": "agent->tool"})
        for server in agent["mcp_servers"]:
            workflow.append({"source": agent_name, "target": server, "type": "agent->mcp"})

    findings = {
        "generated_at": _iso_now(),
        "metadata": {
            "project": metadata.get("project", "unknown"),
            "environment": metadata.get("environment", ""),
            "commit": commit,
        },
        "agents": agents,
        "tools": _tool_records(tools_cfg, referenced_tools),
        "mcp_servers": _mcp_records(mcp_cfg, referenced_mcp),
        "workflow": workflow,
    }
    return findings


def generate_dependency_findings(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Compile vulnerability findings for dependency inventories."""

    vuln_cfg: MutableMapping[str, Any] = config.get("vulnerabilities", {}) or {}
    entries: Sequence[MutableMapping[str, Any]] = vuln_cfg.get("entries", []) or []
    severity_breakdown: Dict[str, int] = {}
    owasp_llm: set[str] = set()
    owasp_agentic: set[str] = set()

    normalised_entries: List[Dict[str, Any]] = []
    for raw in entries:
        entry = {
            "component": raw.get("component", "unknown"),
            "version": raw.get("version", "unknown"),
            "cve": raw.get("cve", ""),
            "severity": raw.get("severity", "UNKNOWN").upper(),
            "fix_version": raw.get("fix_version", ""),
            "owasp_llm": _as_list(raw.get("owasp_llm")),
            "owasp_agentic": _as_list(raw.get("owasp_agentic")),
            "notes": raw.get("notes", ""),
        }
        severity_breakdown[entry["severity"]] = severity_breakdown.get(entry["severity"], 0) + 1
        owasp_llm.update(entry["owasp_llm"])
        owasp_agentic.update(entry["owasp_agentic"])
        normalised_entries.append(entry)

    findings = {
        "policy": vuln_cfg.get("policy", ""),
        "generated_at": _iso_now(),
        "entries": normalised_entries,
        "summary": {
            "total": len(normalised_entries),
            "severity_breakdown": severity_breakdown,
            "owasp_llm": sorted(owasp_llm),
            "owasp_agentic": sorted(owasp_agentic),
        },
    }
    return findings


def build_security_payload(
    config: Mapping[str, Any],
    radar: Mapping[str, Any],
    vulnerabilities: Mapping[str, Any],
    *,
    commit: str | None = None,
) -> Dict[str, Any]:
    metadata = config.get("metadata", {})
    generated_at = _iso_now()
    payload = {
        "metadata": {
            "project": metadata.get("project", "OP-Observe"),
            "owner": metadata.get("owner", ""),
            "environment": metadata.get("environment", ""),
            "default_branch": metadata.get("default_branch", "main"),
            "report_contact": metadata.get("report_contact", ""),
            "owasp_mapping_version": metadata.get("owasp_mapping_version", ""),
            "policy_hash": metadata.get("policy_hash", ""),
            "generated_at": generated_at,
            "commit": commit or radar.get("metadata", {}).get("commit"),
        },
        "radar": dict(radar),
        "vulnerabilities": dict(vulnerabilities),
        "guards": config.get("guards", {}),
        "evals": config.get("evals", {}),
        "evidence": config.get("evidence", {}),
    }
    return payload


def _mermaid_diagram(radar: Mapping[str, Any]) -> str:
    lines: List[str] = ["graph TD"]
    agents = radar.get("agents", []) or []
    tools = radar.get("tools", []) or []
    mcp_servers = radar.get("mcp_servers", []) or []
    workflow = radar.get("workflow", []) or []

    for agent in agents:
        name = agent.get("name", "agent")
        lines.append(f"    {_normalise_name(name)}[\"Agent: {name}\"]:::agent")
    for tool in tools:
        name = tool.get("name", "tool")
        lines.append(f"    {_normalise_name(name)}[\"Tool: {name}\"]:::tool")
    for server in mcp_servers:
        name = server.get("name", "mcp")
        lines.append(f"    {_normalise_name(name)}[\"MCP: {name}\"]:::mcp")
    for link in workflow:
        src = _normalise_name(link.get("source", ""))
        tgt = _normalise_name(link.get("target", ""))
        relation = "uses" if link.get("type") == "agent->tool" else "connects"
        lines.append(f"    {src} -->|{relation}| {tgt}")
    lines.append("    classDef agent fill:#1f78b4,color:#fff,stroke:#0d3a58;")
    lines.append("    classDef tool fill:#33a02c,color:#fff,stroke:#0b3614;")
    lines.append("    classDef mcp fill:#ff7f00,color:#fff,stroke:#7f3f00;")
    return "\n".join(lines)


def _render_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    head_html = "".join(f"<th>{header}</th>" for header in headers)
    body_rows = []
    for row in rows:
        cols = "".join(f"<td>{cell}</td>" for cell in row)
        body_rows.append(f"<tr>{cols}</tr>")
    body_html = "".join(body_rows) or "<tr><td colspan='{len(headers)}'>No data</td></tr>"
    return f"<table><thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table>"


def render_html_report(payload: Mapping[str, Any]) -> str:
    metadata = payload.get("metadata", {})
    radar = payload.get("radar", {})
    vulnerabilities = payload.get("vulnerabilities", {})
    guards = payload.get("guards", {})
    evals = payload.get("evals", {})
    evidence = payload.get("evidence", {})

    tool_rows: List[List[str]] = []
    for tool in radar.get("tools", []) or []:
        tool_rows.append(
            [
                tool.get("name", ""),
                tool.get("version", ""),
                tool.get("source", ""),
                ", ".join(tool.get("permissions", [])),
                ", ".join(tool.get("owasp_llm", [])),
                ", ".join(tool.get("owasp_agentic", [])),
                tool.get("notes", ""),
            ]
        )

    mcp_rows: List[List[str]] = []
    for server in radar.get("mcp_servers", []) or []:
        mcp_rows.append(
            [
                server.get("name", ""),
                server.get("endpoint", ""),
                server.get("auth_mode", ""),
                ", ".join(server.get("capabilities", [])),
                server.get("notes", ""),
            ]
        )

    vuln_rows: List[List[str]] = []
    for entry in vulnerabilities.get("entries", []) or []:
        vuln_rows.append(
            [
                entry.get("component", ""),
                entry.get("version", ""),
                entry.get("cve", ""),
                entry.get("severity", ""),
                entry.get("fix_version", ""),
                ", ".join(entry.get("owasp_llm", [])),
                ", ".join(entry.get("owasp_agentic", [])),
                entry.get("notes", ""),
            ]
        )

    guard_rows: List[List[str]] = []
    for event in guards.get("events", []) or []:
        guard_rows.append(
            [event.get("name", ""), event.get("severity", ""), str(event.get("count", ""))]
        )

    eval_rows: List[List[str]] = []
    for metric in evals.get("metrics", []) or []:
        eval_rows.append(
            [
                metric.get("name", ""),
                str(metric.get("baseline", "")),
                str(metric.get("current", "")),
                metric.get("trend", ""),
            ]
        )

    evidence_links = evidence.get("links", []) or []
    evidence_list = "".join(
        f"<li><a href='{link.get('url')}'>{link.get('label')}</a></li>" for link in evidence_links
    ) or "<li>No external evidence links provided.</li>"

    mermaid = _mermaid_diagram(radar)

    css = """
    body { font-family: 'Segoe UI', Helvetica, Arial, sans-serif; margin: 2rem; color: #222; }
    header { border-bottom: 3px solid #1f78b4; margin-bottom: 2rem; padding-bottom: 1rem; }
    h1 { margin: 0; }
    h2 { margin-top: 2.5rem; color: #1f78b4; }
    table { border-collapse: collapse; width: 100%; margin-bottom: 1.5rem; }
    th, td { border: 1px solid #ccc; padding: 0.5rem; text-align: left; }
    th { background-color: #f4f6fb; }
    code { background-color: #f4f6fb; padding: 0.25rem 0.5rem; border-radius: 4px; }
    .meta-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr)); gap: 0.5rem 2rem; }
    .meta-grid div { background: #f9fafc; padding: 0.75rem; border-radius: 6px; border: 1px solid #e1e4ed; }
    footer { margin-top: 3rem; font-size: 0.9rem; color: #666; }
    .mermaid { background: #f9fafc; padding: 1rem; border-radius: 8px; border: 1px solid #e1e4ed; }
    """

    html = f"""<!DOCTYPE html>
<html lang='en'>
<head>
<meta charset='utf-8' />
<title>{metadata.get('project', 'Security Report')} — Security Report</title>
<style>{css}</style>
</head>
<body>
<header>
  <h1>{metadata.get('project', 'Security Report')} — Security Report</h1>
  <div class='meta-grid'>
    <div><strong>Owner:</strong> {metadata.get('owner', 'n/a')}</div>
    <div><strong>Environment:</strong> {metadata.get('environment', 'n/a')}</div>
    <div><strong>Generated:</strong> {metadata.get('generated_at', '')}</div>
    <div><strong>Commit:</strong> {metadata.get('commit', 'n/a')}</div>
    <div><strong>OWASP Mapping:</strong> {metadata.get('owasp_mapping_version', 'n/a')}</div>
    <div><strong>Policy Hash:</strong> {metadata.get('policy_hash', 'n/a')}</div>
    <div><strong>Contact:</strong> {metadata.get('report_contact', 'n/a')}</div>
  </div>
</header>
<section>
  <h2>Workflow Visualization</h2>
  <pre class='mermaid'>{mermaid}</pre>
</section>
<section>
  <h2>Tool Inventory</h2>
  {_render_table(['Tool', 'Version', 'Source', 'Permissions', 'OWASP LLM', 'OWASP Agentic', 'Notes'], tool_rows)}
</section>
<section>
  <h2>MCP Servers</h2>
  {_render_table(['Server', 'Endpoint', 'Auth', 'Capabilities', 'Notes'], mcp_rows)}
</section>
<section>
  <h2>Vulnerability Mapping</h2>
  {_render_table(['Component', 'Version', 'CVE/ID', 'Severity', 'Fix Version', 'OWASP LLM', 'OWASP Agentic', 'Notes'], vuln_rows)}
</section>
<section>
  <h2>Guardrail Activity (24h)</h2>
  {_render_table(['Event', 'Severity', 'Count'], guard_rows)}
  <p><strong>S0 Budget:</strong> {guards.get('slo', {}).get('s0_budget', 'n/a')} • <strong>Latest S0:</strong> {guards.get('slo', {}).get('latest_s0', 'n/a')} • <strong>Latest S1:</strong> {guards.get('slo', {}).get('latest_s1', 'n/a')}</p>
</section>
<section>
  <h2>Evals & Quality Metrics</h2>
  {_render_table(['Metric', 'Baseline', 'Current', 'Trend'], eval_rows)}
</section>
<section>
  <h2>Evidence Bundle</h2>
  <ul>{evidence_list}</ul>
  <p>Evidence bundle contains the JSON report, radar findings, vulnerability audit, and summary markdown.</p>
</section>
<footer>
  Generated by OP-Observe security automation on {metadata.get('generated_at', '')}. Default branch: {metadata.get('default_branch', 'main')}.
</footer>
</body>
</html>"""
    return html


def build_summary_markdown(payload: Mapping[str, Any]) -> str:
    metadata = payload.get("metadata", {})
    vulnerabilities = payload.get("vulnerabilities", {})
    severity_breakdown = vulnerabilities.get("summary", {}).get("severity_breakdown", {})
    severity_lines = "\n".join(
        f"- {severity}: {count}" for severity, count in sorted(severity_breakdown.items())
    ) or "- None"
    policy = vulnerabilities.get("policy", "n/a")
    total_findings = vulnerabilities.get("summary", {}).get("total", 0)
    summary = (
        f"## Security Radar Summary — {metadata.get('project', 'OP-Observe')}\n\n"
        f"*Generated:* {metadata.get('generated_at', '')} (commit {metadata.get('commit', 'n/a')})\n\n"
        f"### Vulnerability Posture\n"
        f"Total findings: {total_findings}\n"
        f"Policy: {policy}\n"
        f"Severity breakdown:\n{severity_lines}\n\n"
        f"### Guardrail Snapshot\n"
        f"S0 budget: {payload.get('guards', {}).get('slo', {}).get('s0_budget', 'n/a')} — "
        f"Latest S0: {payload.get('guards', {}).get('slo', {}).get('latest_s0', 'n/a')}\n\n"
        f"### Evidence\n"
    )
    for link in payload.get("evidence", {}).get("links", []) or []:
        summary += f"- {link.get('label')}: {link.get('url')}\n"
    if not payload.get("evidence", {}).get("links"):
        summary += "- No evidence links configured.\n"
    return summary


def write_security_artifacts(
    payload: Mapping[str, Any],
    *,
    html_path: Path,
    json_path: Path,
    evidence_path: Path,
    summary_path: Path | None = None,
    attachments: Iterable[Path] | None = None,
) -> str:
    html_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    if summary_path is not None:
        summary_path.parent.mkdir(parents=True, exist_ok=True)

    html = render_html_report(payload)
    html_path.write_text(html, encoding="utf-8")

    json_data = json.dumps(payload, indent=2)
    json_path.write_text(json_data, encoding="utf-8")

    summary = build_summary_markdown(payload)
    if summary_path is not None:
        summary_path.write_text(summary, encoding="utf-8")

    attachments = list(attachments or [])

    with zipfile.ZipFile(evidence_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.write(json_path, arcname=json_path.name)
        for item in attachments:
            item_path = Path(item)
            if item_path.exists():
                bundle.write(item_path, arcname=item_path.name)
        bundle.writestr("metadata.json", json.dumps(payload.get("metadata", {}), indent=2))
        bundle.writestr("summary.md", summary)

    return summary
