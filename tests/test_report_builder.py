from __future__ import annotations

import json
from datetime import datetime

import pytest

from op_observe.reporting import (
    AgentSecurityReport,
    EvidenceLink,
    EvaluationSummary,
    GuardrailSummary,
    MCPServer,
    ReportBuilder,
    ReportMetadata,
    ToolInventoryEntry,
    VulnerabilityFinding,
    WorkflowEdge,
    WorkflowGraph,
    WorkflowNode,
)
from op_observe.reporting.html_renderer import WorkflowGraphRenderer


@pytest.fixture
def sample_report() -> AgentSecurityReport:
    metadata = ReportMetadata(
        project_name="LangGraph Demo",
        environment="staging",
        revision="a1b2c3d",
        generated_at=datetime(2024, 5, 12, 9, 30, 0),
        policy_hash="abc123policy",
        scanner_version="radar-1.4.0",
        additional_context={"Scan Mode": "full"},
    )
    nodes = [
        WorkflowNode(id="orchestrator", label="Primary Agent", kind="agent"),
        WorkflowNode(id="retriever", label="Knowledge Base", kind="tool"),
        WorkflowNode(id="mcp_vector", label="Vector Store MCP", kind="mcp"),
    ]
    edges = [
        WorkflowEdge(source="orchestrator", target="retriever", label="invoke"),
        WorkflowEdge(source="retriever", target="mcp_vector", label="persist"),
    ]
    workflow = WorkflowGraph(nodes=nodes, edges=edges)

    tools = [
        ToolInventoryEntry(
            name="Knowledge Tool",
            version="2.1.0",
            source="pypi",
            description="RAG retriever",
            scopes=["documents:read"],
            permissions=["vector:query"],
            evidence=[EvidenceLink(description="Tool span", uri="otel://trace/123")],
        ),
        ToolInventoryEntry(
            name="Slack Alerts",
            version="0.9.4",
            source="internal",
            scopes=["alerts:write"],
            permissions=["chat:post"],
        ),
    ]

    mcp_servers = [
        MCPServer(
            name="VectorStore",
            endpoint="https://mcp.internal/vector",
            capabilities=["search", "upsert"],
            auth_mode="mtls",
            notes="Mirrors production index",
        )
    ]

    vulnerabilities = [
        VulnerabilityFinding(
            component="knowledge-tool",
            version="2.1.0",
            cve_ids=["CVE-2024-1111"],
            severity="high",
            fix_version="2.1.1",
            owasp_llm_categories=["LLM01", "LLM06"],
            owasp_agentic_categories=["Agentic-03"],
            notes="Upgrade recommended within 7 days",
            references=[EvidenceLink(description="OSV", uri="https://osv.dev/vuln/123")],
        )
    ]

    guardrails = [
        GuardrailSummary(
            name="LLM Critic",
            status="stable",
            window="24h",
            total_failures=2,
            critical_failures=1,
            severity_breakdown={"S0": 1, "S1": 1},
            notes="One injection blocked",
        )
    ]

    evaluations = [
        EvaluationSummary(
            name="Groundedness",
            metric="tru_score",
            value=0.82,
            delta=0.05,
            window="7d rolling",
            notes="Improved after prompt patch",
        )
    ]

    evidence = [
        EvidenceLink(description="Phoenix Trace", uri="phoenix://trace/456"),
        EvidenceLink(description="Grafana Panel", uri="grafana://dashboards/owasp"),
    ]

    return AgentSecurityReport(
        metadata=metadata,
        workflow=workflow,
        tools=tools,
        mcp_servers=mcp_servers,
        vulnerabilities=vulnerabilities,
        guardrail_summaries=guardrails,
        evaluation_summaries=evaluations,
        evidence_links=evidence,
        appendix="Scanned via automated radar job",
    )


def test_report_builder_generates_html_and_json(tmp_path, sample_report):
    builder = ReportBuilder()
    artifacts = builder.build(sample_report, tmp_path)

    html_text = artifacts.html_path.read_text(encoding="utf-8")
    assert "<section id=\"workflow\">" in html_text
    assert "<svg" in html_text
    assert "CVE-2024-1111" in html_text
    assert "OWASP LLM" in html_text
    assert "Phoenix Trace" in html_text
    assert "Agentic Security Report" in html_text

    json_data = json.loads(artifacts.json_path.read_text(encoding="utf-8"))
    assert json_data["metadata"]["project_name"] == "LangGraph Demo"
    assert json_data["workflow"]["nodes"][0]["id"] == "orchestrator"
    assert json_data["tools"][0]["scopes"] == ["documents:read"]
    assert json_data["vulnerabilities"][0]["owasp_llm_categories"] == ["LLM01", "LLM06"]
    assert json_data["guardrail_summaries"][0]["severity_breakdown"]["S0"] == 1


def test_graph_renderer_handles_empty_graph():
    renderer = WorkflowGraphRenderer()
    html_fragment = renderer.render(WorkflowGraph(nodes=[], edges=[]))
    assert "No workflow graph data" in html_fragment

