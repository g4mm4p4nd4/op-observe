from __future__ import annotations

import json
from pathlib import Path
import zipfile

from security_pipeline import (
    build_security_payload,
    generate_dependency_findings,
    generate_radar_findings,
    load_security_config,
    write_security_artifacts,
)


CONFIG_PATH = Path("config/security_targets.toml")


def test_generate_radar_findings_builds_workflow(tmp_path):
    config = load_security_config(CONFIG_PATH)
    findings = generate_radar_findings(config, commit="abc123")
    assert findings["agents"], "Expected agents to be discovered"
    assert any(link["type"] == "agent->tool" for link in findings["workflow"])


def test_write_security_artifacts_creates_bundle(tmp_path):
    config = load_security_config(CONFIG_PATH)
    radar = generate_radar_findings(config, commit="abc123")
    vulnerabilities = generate_dependency_findings(config)
    payload = build_security_payload(config, radar, vulnerabilities, commit="abc123")

    html_path = tmp_path / "security-report.html"
    json_path = tmp_path / "security-report.json"
    evidence_path = tmp_path / "security-evidence.zip"
    summary_path = tmp_path / "security-summary.md"

    # Persist radar/vulnerability inputs so they can be attached to the bundle
    radar_path = tmp_path / "radar-findings.json"
    vuln_path = tmp_path / "dependency-vulnerabilities.json"
    radar_path.write_text(json.dumps(radar, indent=2), encoding="utf-8")
    vuln_path.write_text(json.dumps(vulnerabilities, indent=2), encoding="utf-8")

    summary = write_security_artifacts(
        payload,
        html_path=html_path,
        json_path=json_path,
        evidence_path=evidence_path,
        summary_path=summary_path,
        attachments=[radar_path, vuln_path],
    )

    assert html_path.exists()
    html_content = html_path.read_text(encoding="utf-8")
    assert "Workflow Visualization" in html_content
    assert "Vulnerability Mapping" in html_content

    assert json_path.exists()
    report_data = json.loads(json_path.read_text(encoding="utf-8"))
    assert report_data["metadata"]["commit"] == "abc123"

    assert summary_path.exists()
    assert "Security Radar Summary" in summary

    assert evidence_path.exists()
    with zipfile.ZipFile(evidence_path) as bundle:
        members = set(bundle.namelist())
        assert json_path.name in members
        assert radar_path.name in members
        assert vuln_path.name in members
        assert "summary.md" in members
