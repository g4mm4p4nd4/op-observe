"""Telemetry utilities for OP-Observe instrumentation.

This package bundles lightweight helpers that integrate guardrail verdicts and
LLM-Critic evaluations with OpenTelemetry- and Prometheus-compatible metrics.
The helpers are intentionally framework agnostic so that projects embedding
:mod:`op_observe` can reuse the same recording logic regardless of whether a
full OpenTelemetry stack is present at runtime.
"""

from __future__ import annotations

from .metrics import (
    CriticScoreSnapshot,
    GuardFailureKey,
    GuardrailDirection,
    GuardrailMetrics,
    GuardrailSeverity,
    create_memory_registry,
    default_guardrail_metrics,
    get_guardrail_metrics,
    record_critic_score,
    record_guard_failure,
)

__all__ = [
    "CriticScoreSnapshot",
    "GuardFailureKey",
    "GuardrailDirection",
    "GuardrailMetrics",
    "GuardrailSeverity",
    "create_memory_registry",
    "default_guardrail_metrics",
    "get_guardrail_metrics",
    "record_critic_score",
    "record_guard_failure",
]
