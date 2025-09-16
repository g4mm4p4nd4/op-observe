"""Core orchestrator that coordinates OP-Observe agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Sequence

from .agents import (
    EnablementAgent,
    ObservabilityAgent,
    RetrievalAgent,
    SecurityAgent,
    TelemetryAgent,
)
from .agents.enablement import EvidenceBundle
from .agents.observability import GuardrailResult
from .config import Config


class ModuleNotEnabledError(RuntimeError):
    """Raised when invoking a module that is disabled in the configuration."""


class GuardrailViolation(RuntimeError):
    """Raised when guardrails reject a response."""

    def __init__(self, result: GuardrailResult) -> None:
        super().__init__(f"Guardrails rejected response: {result.flagged_terms}")
        self.result = result


@dataclass(slots=True)
class RagResult:
    """Structured response returned by the RAG pipeline."""

    query: str
    response: str
    documents: List[Dict[str, object]]
    guardrails: GuardrailResult | None


class Orchestrator:
    """Coordinates observability, security, retrieval, telemetry, and enablement agents."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.telemetry_agent: TelemetryAgent | None = None
        self.observability_agent: ObservabilityAgent | None = None
        self.retrieval_agent: RetrievalAgent | None = None
        self.security_agent: SecurityAgent | None = None
        self.enablement_agent: EnablementAgent | None = None
        self._initialized = False

    def initialize_agents(self) -> None:
        if self.config.enable_telemetry:
            self.telemetry_agent = TelemetryAgent()
            self.telemetry_agent.initialize()
        if self.config.enable_observability:
            self.observability_agent = ObservabilityAgent(
                self.config.banned_terms,
                telemetry=self.telemetry_agent,
            )
            self.observability_agent.initialize()
        if self.config.enable_retrieval:
            self.retrieval_agent = RetrievalAgent(self.config.documents)
            self.retrieval_agent.initialize()
        if self.config.enable_security:
            self.security_agent = SecurityAgent(
                vulnerability_db=self.config.vulnerability_db,
                telemetry=self.telemetry_agent,
            )
            self.security_agent.initialize()
        if self.config.enable_enablement:
            self.enablement_agent = EnablementAgent()
            self.enablement_agent.initialize()
        self._initialized = True

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("Orchestrator.initialize_agents must be called before use")

    def _require_module(self, module: object | None, name: str) -> object:
        if module is None:
            raise ModuleNotEnabledError(f"Module '{name}' is not enabled in the current configuration")
        return module

    def run_rag_search(self, query: str, *, top_k: int = 3) -> RagResult:
        self._ensure_initialized()
        retrieval_agent = self._require_module(self.retrieval_agent, "retrieval")
        documents = retrieval_agent.search(query, top_k=top_k)
        response = " ".join(doc.content for doc in documents) if documents else "No documents found."
        guard_result: GuardrailResult | None = None
        if self.config.guardrails_enabled:
            observability_agent = self._require_module(self.observability_agent, "observability")
            guard_result = observability_agent.guard(query, response)
            if not guard_result.approved:
                raise GuardrailViolation(guard_result)
        telemetry = self.telemetry_agent
        if telemetry is not None:
            telemetry.record_event(
                "rag_search",
                {
                    "query": query,
                    "documents_returned": len(documents),
                },
            )
        return RagResult(
            query=query,
            response=response,
            documents=[{"id": doc.id, "content": doc.content, "metadata": doc.metadata} for doc in documents],
            guardrails=guard_result,
        )

    def run_radar_scan(self, *, mode: str = "scan") -> dict[str, object]:
        self._ensure_initialized()
        security_agent = self._require_module(self.security_agent, "security")
        telemetry_snapshot: Mapping[str, object] = (
            self.telemetry_agent.snapshot() if self.telemetry_agent is not None else {"total_events": 0, "events": []}
        )
        return security_agent.run(
            mode=mode,
            agent_specs=self.config.agent_specs,
            telemetry_snapshot=telemetry_snapshot,
        )

    def package_evidence(self, rag_result: RagResult, radar_results: Mapping[str, object]) -> EvidenceBundle:
        self._ensure_initialized()
        enablement_agent = self._require_module(self.enablement_agent, "enablement")
        telemetry_snapshot: Mapping[str, object] = (
            self.telemetry_agent.snapshot() if self.telemetry_agent is not None else {"total_events": 0, "events": []}
        )
        serialized_rag = {
            "query": rag_result.query,
            "response": rag_result.response,
            "documents": rag_result.documents,
            "guardrails": {
                "approved": rag_result.guardrails.approved,
                "flagged_terms": rag_result.guardrails.flagged_terms,
            }
            if rag_result.guardrails
            else None,
        }
        return enablement_agent.package(
            rag_result=serialized_rag,
            radar_results=radar_results,
            telemetry_snapshot=telemetry_snapshot,
        )

    def gather_agent_specs(self) -> Sequence[Mapping[str, object]]:
        """Return the configured agent specifications."""

        return self.config.agent_specs
