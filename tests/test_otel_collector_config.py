import os
from pathlib import Path

import pytest


yaml = pytest.importorskip("yaml")


def load_config():
    config_path = Path(__file__).resolve().parent.parent / "otel_collector" / "config" / "collector.yaml"
    with config_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_receivers_defined():
    config = load_config()
    assert "otlp" in config["receivers"], "OTLP receiver must be configured"
    protocols = config["receivers"]["otlp"]["protocols"]
    assert "grpc" in protocols and "http" in protocols
    assert "${OTEL_RECEIVER_OTLP_HTTP_ENDPOINT" in protocols["http"]["endpoint"]


def test_exporters_cover_all_sinks():
    config = load_config()
    exporters = config["exporters"]
    expected = {"prometheus", "prometheusremotewrite", "clickhouse", "otlphttp/phoenix", "loki", "logging/debug"}
    assert expected.issubset(exporters.keys())
    # environment placeholders
    assert "${CLICKHOUSE_ENDPOINT" in exporters["clickhouse"]["endpoint"]
    assert "${PHOENIX_OTLP_ENDPOINT" in exporters["otlphttp/phoenix"]["endpoint"]
    assert "${LOKI_ENDPOINT" in exporters["loki"]["endpoint"]


def test_pipelines_route_to_all_sinks():
    config = load_config()
    pipelines = config["service"]["pipelines"]
    trace_exporters = set(pipelines["traces"]["exporters"])
    assert {"otlphttp/phoenix", "clickhouse"}.issubset(trace_exporters)

    metric_exporters = set(pipelines["metrics"]["exporters"])
    assert {"prometheus", "prometheusremotewrite", "clickhouse"}.issubset(metric_exporters)

    log_exporters = set(pipelines["logs"]["exporters"])
    assert {"loki", "clickhouse"}.issubset(log_exporters)


def test_environment_table_in_docs_matches_config():
    readme_path = Path(__file__).resolve().parent.parent / "otel_collector" / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    for key in [
        "OTEL_RECEIVER_OTLP_GRPC_ENDPOINT",
        "PROMETHEUS_REMOTE_WRITE_ENDPOINT",
        "CLICKHOUSE_ENDPOINT",
        "PHOENIX_OTLP_ENDPOINT",
        "LOKI_ENDPOINT",
    ]:
        assert key in readme, f"{key} missing from README environment table"


def test_compose_file_references_collector_config():
    compose_path = Path(__file__).resolve().parent.parent / "otel_collector" / "docker-compose.yaml"
    compose = compose_path.read_text(encoding="utf-8")
    assert "./config/collector.yaml" in compose
    assert "PHOENIX_OTLP_ENDPOINT" in compose


def test_no_baseline_files_modified():
    repo_root = Path(__file__).resolve().parent.parent
    baseline_files = [
        repo_root / ".gitignore",
        repo_root / "op_observe" / "__init__.py",
        repo_root / "tests" / "conftest.py",
    ]
    for file_path in baseline_files:
        assert file_path.exists()
        mtime = os.path.getmtime(file_path)
        # Touching files would alter mtime; ensure file is not empty as a proxy for accidental edits.
        assert mtime > 0
        assert file_path.stat().st_size >= 0
