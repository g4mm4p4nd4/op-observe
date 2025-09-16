"""CLI integration tests for Agentic Radar."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from agentic_radar.cli import main


def _write_manifest(project_dir: Path) -> None:
    manifest = {
        "project": "sample-app",
        "agents": [{"name": "controller", "tools": ["search"]}],
        "tools": [
            {"name": "search", "version": None, "source": "https://example.com/tool"},
        ],
        "mcp_servers": [],
        "dependencies": [],
        "metadata": {},
    }
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "agentic_radar.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def test_cli_scan_and_evidence_pack(tmp_path, capsys):
    project_dir = tmp_path / "project"
    _write_manifest(project_dir)

    report_path = tmp_path / "cli-report.json"
    store_path = tmp_path / "store"
    exit_code = main(
        [
            "scan",
            str(project_dir),
            "--output",
            str(report_path),
            "--object-store",
            str(store_path),
            "--trace-id",
            "trace-xyz",
            "--label",
            "env=dev",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Report written to" in captured.out
    assert report_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["project_name"] == "sample-app"
    assert payload["trace_ids"] == ["trace-xyz"]
    assert payload["metadata"]["detectors"]
    assert list(store_path.glob("*.json"))

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "radar.log").write_text("radar log entry", encoding="utf-8")

    pack_path = tmp_path / "evidence.zip"
    evidence_store = tmp_path / "evidence-store"
    exit_code = main(
        [
            "evidence",
            "pack",
            "--findings",
            str(report_path),
            "--logs",
            str(logs_dir),
            "--trace-id",
            "trace-xyz",
            "--object-store",
            str(evidence_store),
            "--output",
            str(pack_path),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Evidence pack created" in captured.out
    assert pack_path.exists()
    with zipfile.ZipFile(pack_path, "r") as archive:
        metadata = json.loads(archive.read("metadata.json").decode("utf-8"))
    assert metadata["findings"]
    assert metadata["trace_ids"] == ["trace-xyz"]
    assert list(evidence_store.glob("*.zip"))
