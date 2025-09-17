from __future__ import annotations

import hashlib
from pathlib import Path
from runpy import run_path

run_path(Path(__file__).resolve().with_name("_baseline_imports.py"))

from op_observe.telemetry import (  # noqa: E402  # pylint: disable=wrong-import-position
    GuardrailDirection,
    GuardrailMetrics,
    GuardrailSeverity,
    create_memory_registry,
)


def test_guardrail_failure_metrics_recording() -> None:
    registry = create_memory_registry()
    metrics = GuardrailMetrics(registry=registry)

    metrics.record_input_guard_failure(GuardrailSeverity.S0)
    metrics.record_output_guard_failure(GuardrailSeverity.S1)
    metrics.record_guard_verdict(True, GuardrailDirection.INPUT, GuardrailSeverity.S1)
    metrics.record_guard_verdict(False, GuardrailDirection.OUTPUT, GuardrailSeverity.S1)

    totals = metrics.guard_failure_totals()
    expected_keys = {
        (GuardrailDirection.INPUT, GuardrailSeverity.S0),
        (GuardrailDirection.OUTPUT, GuardrailSeverity.S1),
    }
    assert set(totals) == expected_keys
    assert totals[(GuardrailDirection.INPUT, GuardrailSeverity.S0)] == 1
    assert totals[(GuardrailDirection.OUTPUT, GuardrailSeverity.S1)] == 2

    counter = registry.get_counter("guardrail_failures_total")
    assert counter is not None
    collected = counter.collect()
    assert collected[(GuardrailDirection.INPUT.value, GuardrailSeverity.S0.value)] == 1
    assert collected[(GuardrailDirection.OUTPUT.value, GuardrailSeverity.S1.value)] == 2


def test_critic_score_histogram_distribution() -> None:
    registry = create_memory_registry()
    metrics = GuardrailMetrics(registry=registry)

    metrics.record_critic_score(0.2, verdict="pass")
    metrics.record_critic_score(0.85, verdict="fail")
    metrics.record_critic_score(1.2, verdict="fail")

    snapshot = metrics.critic_score_snapshot()
    assert snapshot.count == 3
    assert snapshot.total == 0.2 + 0.85 + 1.2
    assert snapshot.buckets[0.25] == 1
    assert snapshot.buckets[0.9] == 2
    assert snapshot.buckets[float("inf")] == 3

    histogram = registry.get_histogram("llm_critic_score")
    assert histogram is not None
    collected = histogram.collect()
    assert collected[("pass",)][0] == 1
    assert collected[("fail",)][0] == 2
    assert collected[("fail",)][2][0.9] == 1
    assert collected[("fail",)][2][float("inf")] == 2


BASELINE_HASHES = {
    ".gitignore": "e0be2082334b81c09ce89e621142b628f71283bd5f5f85d2636a488d78a6c6b6",
    "op_observe/__init__.py": "be12923ea303147b4c6672acda5f937baeba89f41b3199b55aa5889880888d35",
    "tests/conftest.py": "d002420ac337c9760731d0524039331716184ec5401facd1eae596db95b4db26",
}


def test_baseline_files_unchanged() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    for relative, digest in BASELINE_HASHES.items():
        file_path = repo_root / relative
        data = file_path.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        assert (
            actual == digest
        ), f"Baseline file {relative} was unexpectedly modified"
