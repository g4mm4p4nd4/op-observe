"""Scenario-based testing utilities for Agentic Radar."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

from .models import ParsedProject, RadarFinding, ScenarioResult


DEFAULT_SCENARIOS = [
    "prompt-injection",
    "pii-leakage",
    "harmful-content",
    "tool-abuse",
]


class TestRunner:
    """Run adversarial scenarios and map failures to findings."""

    def __init__(self, scenarios: Optional[Sequence[str]] = None) -> None:
        self.scenarios = list(scenarios) if scenarios else list(DEFAULT_SCENARIOS)

    def run(
        self,
        project: ParsedProject,
        override_scenarios: Optional[Sequence[str]] = None,
    ) -> Tuple[List[RadarFinding], List[ScenarioResult]]:
        scenario_names = list(override_scenarios) if override_scenarios else self.scenarios
        expectations = project.metadata.get("test_expectations", {})
        notes = project.metadata.get("test_notes", {})

        findings: List[RadarFinding] = []
        results: List[ScenarioResult] = []

        for scenario in scenario_names:
            expectation = str(expectations.get(scenario, "pass")).lower()
            detail = notes.get(scenario)
            if expectation in {"fail", "failed"}:
                results.append(ScenarioResult(name=scenario, status="failed", details=detail))
                findings.append(
                    RadarFinding(
                        identifier=f"SCENARIO-FAIL::{scenario}",
                        title=f"Scenario '{scenario}' failed security tests",
                        severity="high",
                        description=f"Scenario '{scenario}' produced an unsafe response during radar tests.",
                        owasp_llm=["LLM01"],
                        owasp_agentic=["Agentic-Adversarial"],
                        subject=scenario,
                        remediation="Review guardrails and mitigations for this scenario.",
                        detector="scenario-runner",
                    )
                )
            elif expectation in {"warn", "warning"}:
                results.append(ScenarioResult(name=scenario, status="warning", details=detail))
                findings.append(
                    RadarFinding(
                        identifier=f"SCENARIO-WARN::{scenario}",
                        title=f"Scenario '{scenario}' produced warning signals",
                        severity="medium",
                        description=f"Scenario '{scenario}' triggered warning-level mitigations.",
                        owasp_llm=["LLM03"],
                        owasp_agentic=["Agentic-Adversarial"],
                        subject=scenario,
                        remediation="Investigate mitigations and tighten guard thresholds.",
                        detector="scenario-runner",
                    )
                )
            else:
                results.append(ScenarioResult(name=scenario, status="passed", details=detail))
        return findings, results
