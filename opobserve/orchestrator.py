"""Core orchestrator wiring for integration tests."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .agent import (
    Document,
    Guardrails,
    InMemoryRetriever,
    LangGraphAgent,
    MCPServer,
    MockLLM,
    Tool,
)
from .radar import RadarReport, RadarScanner
from .telemetry import TelemetryCollector


@dataclass
class CoreOrchestratorConfig:
    documents: List[Document]
    banned_keywords: List[str]
    tools: List[Tool]
    mcp_servers: List[MCPServer]
    retriever_latency_ms: float = 65.0
    retriever_top_k: int = 2
    llm_latency_ms: float = 55.0
    llm_model: str = "demo-llm"
    owasp_mapping: Optional[Dict[str, Dict[str, str]]] = None

    @staticmethod
    def demo() -> "CoreOrchestratorConfig":
        return CoreOrchestratorConfig(
            documents=[
                Document(
                    doc_id="doc-1",
                    text="Observability platform with guardrails, vector search, and agentic radar.",
                    metadata={"source": "kb"},
                ),
                Document(
                    doc_id="doc-2",
                    text="Agent security report includes MCP inventory and OWASP mappings.",
                    metadata={"source": "kb"},
                ),
                Document(
                    doc_id="doc-3",
                    text="Latency budgets require search responses under 200 milliseconds.",
                    metadata={"source": "kb"},
                ),
            ],
            banned_keywords=["classified"],
            tools=[
                Tool(
                    name="qdrant-vector-search",
                    version="1.6.0",
                    source="internal",
                    description="Provides ANN retrieval for semantic search",
                    permissions=["read:vector_store"],
                    risk_category="medium",
                ),
                Tool(
                    name="guardrails-critic",
                    version="0.5.0",
                    source="pypi",
                    description="LLM-Critic validator enforcing guard policies",
                    permissions=["invoke:model"],
                    risk_category="low",
                ),
            ],
            mcp_servers=[
                MCPServer(
                    name="compliance-policy-mcp",
                    endpoint="mcp://compliance/policy",
                    capabilities=["policies", "exceptions"],
                    auth_mode="token",
                )
            ],
            owasp_mapping={
                "high": {"llm": "LLM02", "agentic": "AA04"},
                "medium": {"llm": "LLM05", "agentic": "AA02"},
                "low": {"llm": "LLM09", "agentic": "AA01"},
            },
        )


@dataclass
class OrchestratorResult:
    response: str
    telemetry: TelemetryCollector
    guardrail_result: Dict[str, object]
    documents: List[Document]
    radar_report: RadarReport


class CoreOrchestrator:
    def __init__(self, config: Optional[CoreOrchestratorConfig] = None) -> None:
        self.config = config or CoreOrchestratorConfig.demo()

    def _build_agent(self, telemetry: TelemetryCollector) -> LangGraphAgent:
        config = self.config
        retriever = InMemoryRetriever(
            documents=config.documents,
            latency_ms=config.retriever_latency_ms,
            top_k=config.retriever_top_k,
        )
        guardrails = Guardrails(config.banned_keywords)
        llm = MockLLM(model_name=config.llm_model, latency_ms=config.llm_latency_ms)
        return LangGraphAgent(
            retriever=retriever,
            guardrails=guardrails,
            llm=llm,
            tools=config.tools,
            mcp_servers=config.mcp_servers,
            telemetry=telemetry,
        )

    def run(self, query: str, artifact_dir: Path) -> OrchestratorResult:
        telemetry = TelemetryCollector()
        telemetry.record_log("orchestrator.start query=%s" % query)
        agent = self._build_agent(telemetry)
        with telemetry.span("orchestrator.run", component="orchestrator") as span:
            agent_result = agent.run(query)
            radar_report = self._run_radar_scan(agent, telemetry, artifact_dir)
        telemetry.record_metric("orchestrator_latency_ms", span.span.duration_ms)
        telemetry.record_log(
            "orchestrator.complete latency=%.2fms" % span.span.duration_ms
        )
        return OrchestratorResult(
            response=agent_result.response,
            telemetry=telemetry,
            guardrail_result=agent_result.guardrail_result,
            documents=list(agent_result.documents),
            radar_report=radar_report,
        )

    def _run_radar_scan(
        self, agent: LangGraphAgent, telemetry: TelemetryCollector, artifact_dir: Path
    ) -> RadarReport:
        mapping = self.config.owasp_mapping or {}
        scanner = RadarScanner(mapping, artifact_dir)
        report = scanner.scan(agent, telemetry)
        # Provide a stable hash summary for evidence bundling.
        telemetry.record_metric(
            "radar_report_checksum",
            hash(report.json_path.read_text(encoding="utf-8")) & 0xFFFFFFFF,
        )
        return report
