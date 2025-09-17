import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

import importlib.util

MODULE_PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'push_sample_telemetry.py'
spec = importlib.util.spec_from_file_location('push_sample_telemetry', MODULE_PATH)
push_module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(push_module)
push_sample_payloads = push_module.push_sample_payloads


COMPOSE_FILE = Path(__file__).resolve().parents[1] / "otel_collector" / "docker-compose.yaml"


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("OP_OBSERVE_RUN_DOCKER_TESTS"),
    reason="Set OP_OBSERVE_RUN_DOCKER_TESTS=1 to run integration tests",
)
def test_end_to_end_docker_stack(tmp_path):
    if not shutil.which("docker"):
        pytest.skip("docker executable not available")

    env = os.environ.copy()
    env.setdefault("COMPOSE_PROJECT_NAME", f"opobserve_{int(time.time())}")
    up_cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d"]
    down_cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), "down", "-v"]

    try:
        subprocess.run(up_cmd, check=True, env=env)
        _wait_for_collector_ready()
        push_sample_payloads(endpoint="http://localhost:4318")
    finally:
        subprocess.run(down_cmd, check=False, env=env)


def _wait_for_collector_ready(timeout: int = 120):
    import urllib.request
    from urllib.error import URLError, HTTPError

    deadline = time.time() + timeout
    health_url = 'http://localhost:13133/healthz'
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=2) as response:
                if response.status == 200:
                    return
        except (URLError, HTTPError):
            pass
        time.sleep(2)
    raise TimeoutError('Collector health endpoint did not become ready in time')
