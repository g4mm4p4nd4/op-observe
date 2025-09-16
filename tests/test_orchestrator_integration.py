"""Integration tests for the demo core orchestrator."""
from __future__ import annotations

import json

import pytest

from opobserve import CoreOrchestrator, CoreOrchestratorConfig


@pytest.fixture()
def orchestrator() -> CoreOrchestrator:
    # Use the demo configuration but tighten latencies so the CI environment stays quick.
    config = CoreOrchestratorConfig.demo()
    config.retriever_latency_ms = 90.0
    config.llm_latency_ms = 45.0
    return CoreOrchestrator(config=config)


def test_orchestrator_produces_full_observability(orchestrator: CoreOrchestrator, tmp_path) -> None:
    result = orchestrator.run("observability security posture", artifact_dir=tmp_path)

    # Guardrails should pass and retrieval should yield context.
    assert result.guardrail_result["passed"] is True
    assert result.telemetry.metrics["retrieved_documents"] >= 1
    assert "observability" in result.response.lower()

    # Metrics cover the key SLIs we expect (search latency, guard verdicts, radar checksum).
    metrics = result.telemetry.metrics
    assert metrics["search_latency_ms"] < 200
    assert metrics["guardrail_pass"] == 1
    assert metrics["radar_findings"] == len(result.radar_report.findings["vulnerabilities"])
    assert metrics["radar_report_checksum"] > 0
    assert metrics["orchestrator_latency_ms"] >= metrics["search_latency_ms"]

    # Latency metric should match the retrieval span duration very closely.
    retrieval_span = result.telemetry.latest_span("retriever.vector_search")
    assert retrieval_span is not None
    assert abs(retrieval_span.duration_ms - metrics["search_latency_ms"]) < 5

    # Logs record each stage of the workflow.
    logs = "\n".join(result.telemetry.logs)
    assert "retrieval.ok" in logs
    assert "guardrails.pass" in logs
    assert "llm.generated" in logs
    assert "radar.scan.completed" in logs
    assert "orchestrator.complete" in logs

    # Traces capture each major component including the orchestrator umbrella span.
    span_names = [span.name for span in result.telemetry.spans]
    assert span_names[:4] == [
        "retriever.vector_search",
        "guardrails.validation",
        "llm.synthesize",
        "radar.scan",
    ]
    assert span_names[-1] == "orchestrator.run"

    # Reports are materialised to disk and contain the expected sections.
    radar_report = result.radar_report
    assert radar_report.json_path.exists()
    assert radar_report.html_path.exists()

    data = json.loads(radar_report.json_path.read_text(encoding="utf-8"))
    assert {"workflow", "tools", "mcp_servers", "vulnerabilities", "evidence"} <= data.keys()
    assert any(node["id"] == "retriever" for node in data["workflow"]["nodes"])
    assert any(tool["name"] == "qdrant-vector-search" for tool in data["tools"])
    assert data["mcp_servers"][0]["name"] == "compliance-policy-mcp"
    assert all("owasp" in vuln for vuln in data["vulnerabilities"])
    assert data["evidence"]["metrics"]["search_latency_ms"] == pytest.approx(metrics["search_latency_ms"], rel=0.1)
    assert data["evidence"]["trace_links"]

    html_contents = radar_report.html_path.read_text(encoding="utf-8")
    for section in [
        "Workflow Visualization",
        "Tool Inventory",
        "MCP Servers",
        "Vulnerability Mapping",
        "Evidence",
    ]:
        assert section in html_contents

    # Snapshot the consolidated summary to help with debugging if the integration fails.
    summary = result.telemetry.as_summary()
    assert summary["metrics"]["search_latency_ms"] == pytest.approx(metrics["search_latency_ms"], rel=0.01)
    assert len(summary["traces"]) >= 5
