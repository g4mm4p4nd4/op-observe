"""Observability and guardrail helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from .telemetry import TelemetryAgent


@dataclass(slots=True)
class GuardrailResult:
    """Result of a guardrail evaluation."""

    flagged_terms: List[str]
    approved: bool


class ObservabilityAgent:
    """Applies lightweight guardrails and emits telemetry signals."""

    def __init__(self, banned_terms: Iterable[str], telemetry: TelemetryAgent | None = None) -> None:
        self._banned_terms = [term.lower() for term in banned_terms]
        self._telemetry = telemetry
        self._initialized = False

    def initialize(self) -> None:
        self._initialized = True

    def guard(self, query: str, response: str) -> GuardrailResult:
        if not self._initialized:
            raise RuntimeError("ObservabilityAgent must be initialized before running guardrails")

        lowered = response.lower()
        flagged = [term for term in self._banned_terms if term and term in lowered]
        approved = not flagged
        if self._telemetry:
            self._telemetry.record_event(
                "guardrail_check",
                {
                    "query": query,
                    "response_length": len(response),
                    "flagged_terms": flagged,
                },
            )
        return GuardrailResult(flagged_terms=flagged, approved=approved)
