from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from urllib import error as urlerror
from urllib import parse, request

import pytest

pytest.importorskip("opentelemetry")

from op_observe.telemetry import generate_sample_telemetry

COMPOSE_DIR = Path(__file__).resolve().parents[2] / "deploy"
COMPOSE_FILE = COMPOSE_DIR / "docker-compose.metrics.yml"
PROJECT_NAME = "opobserve_integration"


def _docker_compose_command() -> list[str] | None:
    if shutil.which("docker"):
        return ["docker", "compose"]
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    return None


def _http_get(url: str, timeout: float = 5.0) -> tuple[int, str]:
    req = request.Request(url)
    try:
        with request.urlopen(req, timeout=timeout) as resp:  # type: ignore[arg-type]
            return resp.status, resp.read().decode()
    except urlerror.HTTPError as exc:  # pragma: no cover - network dependent
        body = exc.read().decode()
        return exc.code, body


def _wait_for_port(host: str, port: int, timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            time.sleep(1)
    return False


def _wait_for_http(url: str, timeout: float = 60.0) -> tuple[int, str]:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            status, body = _http_get(url)
            if status < 500:
                return status, body
        except urlerror.URLError as exc:  # pragma: no cover - network dependent
            last_error = exc
        time.sleep(1)
    raise AssertionError(f"Endpoint {url} not ready: {last_error}")


def _poll_metrics(url: str, metric_name: str, timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            status, body = _http_get(url)
            if status == 200 and metric_name in body:
                return True
        except urlerror.URLError:  # pragma: no cover - network dependent
            pass
        time.sleep(1)
    return False


def _clickhouse_query(base_url: str, query: str) -> dict:
    params = parse.urlencode({"query": query})
    url = f"{base_url}?{params}"
    status, body = _http_get(url, timeout=10)
    if status >= 400:
        raise RuntimeError(f"ClickHouse query failed: {status} {body}")
    return json.loads(body)


def _poll_clickhouse_for_spans(base_url: str, minimum: int = 1, timeout: float = 60.0) -> bool:
    database = os.getenv("CLICKHOUSE_DATABASE", "otel")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            tables = _clickhouse_query(
                base_url,
                f"SELECT name FROM system.tables WHERE database='{database}' AND name LIKE 'otel_traces%' FORMAT JSON",
            )
            table_names = [row["name"] for row in tables.get("data", [])]
            for table in table_names:
                result = _clickhouse_query(
                    base_url,
                    f"SELECT count() AS c FROM {database}.{table} FORMAT JSON",
                )
                count = int(result["data"][0]["c"]) if result.get("data") else 0
                if count >= minimum:
                    return True
        except (urlerror.URLError, KeyError, ValueError, IndexError, RuntimeError):  # pragma: no cover - network dependent
            pass
        time.sleep(1)
    return False


@pytest.mark.integration
def test_pipeline_exports_metrics_and_traces():
    command = _docker_compose_command()
    if not command:
        pytest.skip("Docker is required for integration tests")

    env = os.environ.copy()
    env.setdefault("CLICKHOUSE_PASSWORD", "")
    env.setdefault("CLICKHOUSE_DATABASE", "otel")
    env.setdefault("CLICKHOUSE_USERNAME", "default")

    subprocess.run(
        command + ["-p", PROJECT_NAME, "-f", str(COMPOSE_FILE), "up", "-d"],
        check=True,
        cwd=str(COMPOSE_DIR),
        env=env,
    )

    try:
        assert _wait_for_port("localhost", 4318, timeout=120)
        assert _wait_for_port("localhost", 8123, timeout=120)
        _wait_for_http("http://localhost:9090/-/ready", timeout=120)

        os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
        os.environ.setdefault("OTEL_EXPORTER_OTLP_INSECURE", "true")
        os.environ.setdefault("OTEL_SERVICE_NAME", "op-observe-integration")

        generate_sample_telemetry(iterations=4, delay=0.02)

        assert _poll_metrics("http://localhost:9464/metrics", "op_observe_sample_request_count")
        assert _poll_clickhouse_for_spans("http://localhost:8123")
    finally:
        subprocess.run(
            command + ["-p", PROJECT_NAME, "-f", str(COMPOSE_FILE), "down", "-v"],
            check=False,
            cwd=str(COMPOSE_DIR),
            env=env,
        )
