from __future__ import annotations

import json
from pathlib import Path
from typing import List

import pytest

from scripts import bootstrap


class DummyCompletedProcess:
    def __init__(self, cmd: List[str]):
        self.cmd = cmd


def test_bootstrap_dry_run_generates_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPOBS_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("OPOBS_DATA_DIR", "data")
    monkeypatch.setenv("OPOBS_LOGS_DIR", "logs")

    # Avoid hitting the host for docker availability.
    monkeypatch.setattr(bootstrap, "ensure_dependencies", lambda *_: None)

    called = []

    def fake_run(*_args, **_kwargs):  # pragma: no cover - should not be called in dry run
        called.append(True)

    monkeypatch.setattr(bootstrap.subprocess, "run", fake_run)

    exit_code = bootstrap.main(["--dry-run"])
    assert exit_code == 0
    assert not called

    compose_path = Path(tmp_path) / "docker-compose.yaml"
    assert compose_path.exists()

    compose_data = json.loads(compose_path.read_text())
    services = compose_data["services"]
    expected = {
        "qdrant",
        "vllm",
        "otel-collector",
        "phoenix",
        "phoenix-db",
        "prometheus",
        "grafana",
        "loki",
        "vault",
        "keycloak",
        "clickhouse",
        "clickhouse-exporter",
        "minio",
        "nats",
        "agentic-radar",
        "trulens-evaluator",
    }
    assert expected.issubset(services.keys())

    env_file = Path(tmp_path) / ".opobserve.env"
    assert env_file.exists()
    env_content = env_file.read_text().splitlines()
    assert any(line.startswith("QDRANT_PORT=") for line in env_content)

    # Support configuration files should also be present.
    for filename in ["otel-collector.yaml", "prometheus.yml", "loki-config.yaml"]:
        assert (Path(tmp_path) / filename).exists()


def test_bootstrap_starts_services(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPOBS_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("OPOBS_DATA_DIR", "data")
    monkeypatch.setenv("OPOBS_LOGS_DIR", "logs")

    compose_calls = {}

    def fake_ensure_dependencies(cmd):
        compose_calls["cmd"] = cmd

    monkeypatch.setattr(bootstrap, "ensure_dependencies", fake_ensure_dependencies)

    executed = {}

    def fake_run(cmd, check, env):
        executed["cmd"] = cmd
        executed["check"] = check
        executed["env"] = env
        return DummyCompletedProcess(cmd)

    monkeypatch.setattr(bootstrap.subprocess, "run", fake_run)

    exit_code = bootstrap.main(["--project-name", "testproj", "--config-dir", str(tmp_path)])
    assert exit_code == 0
    assert compose_calls["cmd"] == ["docker", "compose"]

    compose_path = Path(tmp_path) / "docker-compose.yaml"
    assert executed["cmd"] == [
        "docker",
        "compose",
        "-p",
        "testproj",
        "-f",
        str(compose_path),
        "up",
        "-d",
    ]
    assert executed["check"] is True
    assert "QDRANT_PORT" in executed["env"]
