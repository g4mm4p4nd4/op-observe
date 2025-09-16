"""Configuration utilities for the OP-Observe orchestrator."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

from .agents.retrieval import Document


@dataclass(slots=True)
class Config:
    """Runtime configuration for the orchestrator and its agents."""

    enable_observability: bool = True
    enable_security: bool = True
    enable_retrieval: bool = True
    enable_telemetry: bool = True
    enable_enablement: bool = True
    guardrails_enabled: bool = True
    banned_terms: Sequence[str] = field(default_factory=lambda: ("classified", "leak"))
    documents: Sequence[Document] = field(default_factory=tuple)
    agent_specs: Sequence[Mapping[str, object]] = field(default_factory=tuple)
    vulnerability_db: Mapping[str, Mapping[str, object]] = field(default_factory=dict)

    @staticmethod
    def _parse_bool(value: str | None, default: bool) -> bool:
        if value is None:
            return default
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return default

    @classmethod
    def from_env(
        cls,
        *,
        documents: Iterable[Document] | None = None,
        agent_specs: Sequence[Mapping[str, object]] | None = None,
        vulnerability_db: Mapping[str, Mapping[str, object]] | None = None,
    ) -> "Config":
        """Create a configuration instance from environment variables."""

        enable_observability = cls._parse_bool(os.getenv("OPOBS_ENABLE_OBSERVABILITY"), True)
        enable_security = cls._parse_bool(os.getenv("OPOBS_ENABLE_SECURITY"), True)
        enable_retrieval = cls._parse_bool(os.getenv("OPOBS_ENABLE_RETRIEVAL"), True)
        enable_telemetry = cls._parse_bool(os.getenv("OPOBS_ENABLE_TELEMETRY"), True)
        enable_enablement = cls._parse_bool(os.getenv("OPOBS_ENABLE_ENABLEMENT"), True)
        guardrails_enabled = cls._parse_bool(os.getenv("OPOBS_ENABLE_GUARDRAILS"), True)

        banned_env = os.getenv("OPOBS_BANNED_TERMS")
        if banned_env:
            banned_terms: Sequence[str] = tuple(term.strip() for term in banned_env.split(",") if term.strip())
        else:
            banned_terms = ("classified", "leak")

        return cls(
            enable_observability=enable_observability,
            enable_security=enable_security,
            enable_retrieval=enable_retrieval,
            enable_telemetry=enable_telemetry,
            enable_enablement=enable_enablement,
            guardrails_enabled=guardrails_enabled,
            banned_terms=banned_terms,
            documents=tuple(documents or ()),
            agent_specs=tuple(agent_specs or ()),
            vulnerability_db=vulnerability_db or {},
        )
