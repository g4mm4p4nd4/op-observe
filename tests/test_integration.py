"""Integration tests for the OP-Observe orchestrator."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from op_observe import Config, Orchestrator
from op_observe.agents import Document
from op_observe.orchestrator import GuardrailViolation


@pytest.fixture()
def sample_documents() -> list[Document]:
    return [
        Document(id="1", content="Observability telemetry integrates guardrails and radar signals."),
        Document(id="2", content="Security radar maps OWASP findings to mitigation guidance."),
        Document(id="3", content="Retrieval pipeline feeds evidence packaging."),
    ]


@pytest.fixture()
def sample_agent_specs() -> list[dict[str, object]]:
    return [
        {
            "name": "observability",
            "tools": [
                {"name": "openllmetry", "version": "0.3", "source": "internal"},
            ],
            "mcp_servers": [],
        },
        {
            "name": "security",
            "tools": [
                {"name": "agentic-radar", "version": "1.0", "source": "external"},
                {"name": "legacy-tool", "version": "0.8", "source": "external"},
            ],
            "mcp_servers": [
                {"endpoint": "https://security.local/mcp", "capabilities": ["scan", "test"], "auth": "token"}
            ],
        },
    ]


@pytest.fixture()
def sample_vulnerability_db() -> dict[str, dict[str, object]]:
    return {
        "legacy-tool": {
            "severity": "high",
            "cve": "CVE-2024-9999",
            "owasp_llm": ["LLM01", "LLM05"],
            "owasp_agentic": ["AGENTIC-01"],
            "notes": "Patch available in 0.9",
        }
    }


@pytest.fixture()
def orchestrator(sample_documents, sample_agent_specs, sample_vulnerability_db) -> Orchestrator:
    config = Config(
        documents=sample_documents,
        agent_specs=sample_agent_specs,
        vulnerability_db=sample_vulnerability_db,
    )
    orchestrator = Orchestrator(config)
    orchestrator.initialize_agents()
    return orchestrator


def test_rag_flow_runs_with_guardrails(orchestrator: Orchestrator) -> None:
    result = orchestrator.run_rag_search("security radar guidance", top_k=2)
    assert "security" in result.response.lower()
    assert result.guardrails is not None
    assert result.guardrails.approved
    assert orchestrator.telemetry_agent is not None
    snapshot = orchestrator.telemetry_agent.snapshot()
    assert snapshot["total_events"] >= 1


def test_guardrails_raise_on_banned_terms(sample_documents, sample_agent_specs, sample_vulnerability_db) -> None:
    docs = sample_documents + [Document(id="99", content="Classified leak detected")]  # banned term
    config = Config(
        documents=docs,
        agent_specs=sample_agent_specs,
        vulnerability_db=sample_vulnerability_db,
        banned_terms=("classified",),
    )
    orchestrator = Orchestrator(config)
    orchestrator.initialize_agents()
    with pytest.raises(GuardrailViolation):
        orchestrator.run_rag_search("classified leak", top_k=3)


def test_radar_scan_and_evidence_packaging(orchestrator: Orchestrator) -> None:
    radar_results = orchestrator.run_radar_scan(mode="scan")
    assert radar_results["findings"], "Expected at least one security finding"
    rag_result = orchestrator.run_rag_search("evidence packaging", top_k=2)
    bundle = orchestrator.package_evidence(rag_result, radar_results)
    assert bundle.digest
    parsed = json.loads(bundle.json_blob)
    assert parsed["radar_report"]["mode"] == "scan"
    assert parsed["rag_result"]["query"] == "evidence packaging"


def test_cli_rag_invocation() -> None:
    cmd = [sys.executable, "-m", "op_observe.cli", "rag", "observability"]
    completed = subprocess.run(cmd, capture_output=True, check=False, text=True)
    assert completed.returncode == 0, completed.stderr
    output = json.loads(completed.stdout)
    assert output["query"] == "observability"
    assert "response" in output
