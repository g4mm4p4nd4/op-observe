"""Simplified LangGraph-style agent primitives used in integration tests."""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Sequence

from .telemetry import TelemetryCollector


@dataclass
class Document:
    doc_id: str
    text: str
    metadata: Dict[str, str]


@dataclass
class Tool:
    name: str
    version: str
    source: str
    description: str
    permissions: Sequence[str] = field(default_factory=list)
    risk_category: str = "low"


@dataclass
class MCPServer:
    name: str
    endpoint: str
    capabilities: Sequence[str]
    auth_mode: str


class InMemoryRetriever:
    """Vector-style retrieval over a small in-memory corpus."""

    def __init__(self, documents: Iterable[Document], latency_ms: float = 75.0, top_k: int = 2) -> None:
        self._documents = list(documents)
        self.latency_ms = latency_ms
        self.top_k = top_k

    def retrieve(self, query: str, telemetry: TelemetryCollector) -> List[Document]:
        with telemetry.span("retriever.vector_search", component="retrieval") as span:
            # Simulate ANN lookup latency without external dependencies.
            simulated_latency = max(self.latency_ms / 1000.0, 0.001)
            time.sleep(simulated_latency)
            scored = [
                (self._similarity(query, doc.text), doc)
                for doc in self._documents
            ]
            scored.sort(key=lambda pair: pair[0], reverse=True)
            results = [doc for _, doc in scored[: self.top_k]]
        telemetry.record_metric("search_latency_ms", span.span.duration_ms)
        telemetry.record_metric("retrieved_documents", len(results))
        telemetry.increment("retrieval_calls")
        telemetry.record_log(
            "retrieval.ok docs=%s latency=%.2fms" % (len(results), span.span.duration_ms)
        )
        return results

    @staticmethod
    def _similarity(query: str, text: str) -> float:
        query_terms = set(query.lower().split())
        text_terms = set(text.lower().split())
        if not query_terms:
            return 0.0
        return len(query_terms.intersection(text_terms)) / math.sqrt(len(text_terms) or 1)


class Guardrails:
    """Very small rule-based guardrail implementation for demo purposes."""

    def __init__(self, banned_keywords: Sequence[str]) -> None:
        self.banned_keywords = [kw.lower() for kw in banned_keywords]

    def validate(self, query: str, documents: Sequence[Document], telemetry: TelemetryCollector) -> Dict[str, object]:
        with telemetry.span("guardrails.validation", component="guardrails") as span:
            flagged: List[Document] = []
            for doc in documents:
                content = doc.text.lower()
                if any(kw in content for kw in self.banned_keywords):
                    flagged.append(doc)
        telemetry.record_metric("guardrail_pass", 0 if flagged else 1)
        telemetry.record_metric("guardrail_violations", len(flagged))
        telemetry.record_metric("guardrail_latency_ms", span.span.duration_ms)
        telemetry.record_log(
            "guardrails.%s violations=%s latency=%.2fms"
            % ("fail" if flagged else "pass", len(flagged), span.span.duration_ms)
        )
        return {"passed": not flagged, "flagged_documents": flagged}


class MockLLM:
    """Simulates an LLM call and generates deterministic output."""

    def __init__(self, model_name: str = "demo-llm", latency_ms: float = 55.0) -> None:
        self.model_name = model_name
        self.latency_ms = latency_ms

    def generate(self, query: str, documents: Sequence[Document], telemetry: TelemetryCollector) -> str:
        with telemetry.span("llm.synthesize", component="llm", model=self.model_name) as span:
            time.sleep(max(self.latency_ms / 1000.0, 0.001))
            highlighted = " ".join(doc.text for doc in documents)
            response = f"Answering '{query}' using context: {highlighted}".strip()
        telemetry.record_metric("llm_latency_ms", span.span.duration_ms)
        telemetry.record_metric("llm_tokens", len(response.split()))
        telemetry.record_log(
            "llm.generated model=%s tokens=%s latency=%.2fms"
            % (self.model_name, len(response.split()), span.span.duration_ms)
        )
        return response


@dataclass
class AgentRunResult:
    documents: Sequence[Document]
    guardrail_result: Dict[str, object]
    response: str


class LangGraphAgent:
    """Minimal LangGraph-like agent with retrieval, guardrails, and a mock LLM."""

    def __init__(
        self,
        retriever: InMemoryRetriever,
        guardrails: Guardrails,
        llm: MockLLM,
        tools: Sequence[Tool],
        mcp_servers: Sequence[MCPServer],
        telemetry: TelemetryCollector,
    ) -> None:
        self.retriever = retriever
        self.guardrails = guardrails
        self.llm = llm
        self.tools = list(tools)
        self.mcp_servers = list(mcp_servers)
        self.telemetry = telemetry

    def run(self, query: str) -> AgentRunResult:
        self.telemetry.record_log("agent.start query=%s" % query)
        documents = self.retriever.retrieve(query, self.telemetry)
        guardrail_result = self.guardrails.validate(query, documents, self.telemetry)
        response = self.llm.generate(query, documents, self.telemetry)
        self.telemetry.record_log("agent.complete response_tokens=%s" % len(response.split()))
        return AgentRunResult(documents=documents, guardrail_result=guardrail_result, response=response)

    # ---- Radar helpers -------------------------------------------------
    def workflow_graph(self) -> Dict[str, object]:
        return {
            "nodes": [
                {"id": "retriever", "type": "retrieval", "description": "Vector search over demo corpus"},
                {"id": "guardrails", "type": "guardrail", "description": "Keyword allow/block list"},
                {"id": "llm", "type": "llm", "description": self.llm.model_name},
            ],
            "edges": [
                {"source": "retriever", "target": "guardrails"},
                {"source": "guardrails", "target": "llm"},
            ],
        }

    def tool_inventory(self) -> List[Dict[str, object]]:
        inventory: List[Dict[str, object]] = []
        for tool in self.tools:
            inventory.append(
                {
                    "name": tool.name,
                    "version": tool.version,
                    "source": tool.source,
                    "description": tool.description,
                    "permissions": list(tool.permissions),
                    "risk_category": tool.risk_category,
                }
            )
        return inventory

    def mcp_inventory(self) -> List[Dict[str, object]]:
        return [
            {
                "name": server.name,
                "endpoint": server.endpoint,
                "auth_mode": server.auth_mode,
                "capabilities": list(server.capabilities),
            }
            for server in self.mcp_servers
        ]

    def trace_links(self, telemetry: TelemetryCollector) -> List[str]:
        random.seed(42)
        return [f"trace-{idx}-{int(span.duration_ms)}" for idx, span in enumerate(telemetry.spans)]
