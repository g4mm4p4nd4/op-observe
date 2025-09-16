import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = REPO_ROOT / "bootstrap.sh"


def run_bootstrap(tmp_path, extra_args=None):
    env = os.environ.copy()
    env.setdefault("OP_OBSERVE_SKIP_DOWNLOADS", "1")
    prefix = tmp_path / "install"
    args = ["bash", str(BOOTSTRAP), "--prefix", str(prefix)]
    if extra_args:
        args.extend(extra_args)
    subprocess.run(args, check=True, cwd=REPO_ROOT, env=env)
    return prefix


def test_bootstrap_generates_stack(tmp_path):
    prefix = run_bootstrap(tmp_path)

    # docker-compose file contains all major services
    compose_file = prefix / "docker-compose.yml"
    assert compose_file.is_file()
    compose_content = compose_file.read_text()
    for service in [
        "radar:",
        "otel-collector:",
        "phoenix:",
        "clickhouse:",
        "grafana:",
        "qdrant:",
        "vllm:",
        "vault:",
        "keycloak:",
    ]:
        assert service in compose_content

    # binaries (stubs or installed) must be present and executable
    for binary in ["agentic-radar", "osv-scanner", "pip-audit"]:
        path = prefix / "bin" / binary
        assert path.is_file()
        assert os.access(path, os.X_OK)

    # Validate Grafana dashboard provisioned
    dashboard = prefix / "config" / "grafana" / "dashboards" / "opobserve.json"
    content = json.loads(dashboard.read_text())
    assert content["title"] == "OP-Observe Overview"

    # Manifest includes all components with valid statuses
    manifest_path = prefix / "install-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    required_components = {
        "radar",
        "osv-scanner",
        "pip-audit",
        "openllmetry",
        "phoenix",
        "clickhouse-exporter",
        "grafana",
        "qdrant",
        "vllm",
        "vault",
        "keycloak",
    }
    assert required_components.issubset(manifest["components"].keys())
    allowed_statuses = {"installed", "present", "configured", "stubbed"}
    for name, data in manifest["components"].items():
        assert data["status"] in allowed_statuses
        extra_field = "path" if "path" in data else "service"
        assert extra_field in data
        value = data[extra_field]
        if extra_field == "path":
            assert Path(value).exists()

    # Ensure OpenTelemetry config references ClickHouse exporter
    otel_config = (prefix / "config" / "opentelemetry" / "collector.yaml").read_text()
    assert "clickhouse" in otel_config
    assert "receivers:" in otel_config


def test_bootstrap_idempotent(tmp_path):
    prefix = run_bootstrap(tmp_path)
    # Second run should not fail and should keep manifest intact
    run_bootstrap(tmp_path, extra_args=["--force"])
    manifest = json.loads((prefix / "install-manifest.json").read_text())
    assert manifest["install_root"].endswith(str(prefix))
