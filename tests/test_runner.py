"""Tests for radar scan and test runners."""

from __future__ import annotations

import json
from pathlib import Path

from agentic_radar.runner import ScanConfig, TestConfig, run_scan, run_test


def _write_manifest(project_dir: Path, *, include_test_expectations: bool = False) -> None:
    manifest = {
        "project": "sample-app",
        "agents": [
            {"name": "orchestrator", "tools": ["search", "email"]},
        ],
        "tools": [
            {"name": "search", "version": None, "source": "https://example.com/search"},
            {"name": "email", "version": "1.2.3", "source": "internal"},
        ],
        "mcp_servers": [
            {"name": "inventory", "endpoint": "https://inventory.example", "capabilities": [], "auth_mode": "anonymous"}
        ],
        "dependencies": [
            {
                "name": "requests",
                "version": "2.0.0",
                "vulnerabilities": [
                    {
                        "id": "CVE-2024-9999",
                        "severity": "high",
                        "description": "SSL verification bypass",
                        "fix_version": "2.31.0",
                    }
                ],
            }
        ],
        "metadata": {"environment": "staging"},
    }
    if include_test_expectations:
        manifest["metadata"].update(
            {
                "test_expectations": {
                    "prompt-injection": "fail",
                    "pii-leakage": "pass",
                },
                "test_notes": {"prompt-injection": "Guardrail rejected prompt"},
            }
        )
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "agentic_radar.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def test_run_scan_produces_findings_and_stores(tmp_path):
    project_dir = tmp_path / "project"
    _write_manifest(project_dir)
    output_path = tmp_path / "report.json"
    store_path = tmp_path / "store"

    config = ScanConfig(
        root=project_dir,
        output_path=output_path,
        object_store_path=store_path,
        trace_ids=["trace-1"],
        metadata={"release": "2025.09"},
    )
    result = run_scan(config)

    assert output_path.exists()
    with output_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    assert payload["summary"]["findings"]["total"] >= 3
    assert payload["metadata"]["detectors"]
    assert payload["trace_ids"] == ["trace-1"]

    assert result.stored_artifact is not None
    assert result.stored_artifact.exists()
    assert list(store_path.glob("*.json"))


def test_run_test_records_scenarios(tmp_path):
    project_dir = tmp_path / "project"
    _write_manifest(project_dir, include_test_expectations=True)
    output_path = tmp_path / "test-report.json"

    config = TestConfig(
        root=project_dir,
        output_path=output_path,
        trace_ids=["trace-2"],
        scenarios=["prompt-injection", "pii-leakage"],
    )
    result = run_test(config)

    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    scenario_status = {item["name"]: item["status"] for item in payload["scenario_results"]}
    assert scenario_status["prompt-injection"] == "failed"
    assert scenario_status["pii-leakage"] == "passed"
    assert "prompt-injection" in payload["metadata"]["scenario_failures"]
    assert payload["summary"]["findings"]["high"] >= 1
    assert result.report.mode == "test"
    assert any(finding["id"].startswith("SCENARIO-FAIL") for finding in payload["findings"])
