"""Data models for the security report builder."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, Sequence


@dataclass
class ReportMetadata:
    """Metadata that appears in the report header."""

    project_name: str
    environment: str
    revision: str
    generated_at: datetime
    policy_hash: Optional[str] = None
    scanner_version: Optional[str] = None
    additional_context: Dict[str, str] = field(default_factory=dict)


@dataclass
class WorkflowNode:
    """Node definition for the agent workflow graph."""

    id: str
    label: str
    kind: str = "agent"
    description: Optional[str] = None


@dataclass
class WorkflowEdge:
    """Directed edge connecting two nodes in the workflow graph."""

    source: str
    target: str
    label: Optional[str] = None


@dataclass
class WorkflowGraph:
    """Collection of workflow nodes and edges."""

    nodes: Sequence[WorkflowNode]
    edges: Sequence[WorkflowEdge]


@dataclass
class ToolInventoryEntry:
    """Represents an installed tool or integration used by an agent."""

    name: str
    version: str
    source: str
    description: Optional[str] = None
    scopes: Sequence[str] = field(default_factory=list)
    permissions: Sequence[str] = field(default_factory=list)
    evidence: Sequence[EvidenceLink] = field(default_factory=list)


@dataclass
class MCPServer:
    """Metadata for a Model Context Protocol server."""

    name: str
    endpoint: str
    capabilities: Sequence[str]
    auth_mode: str
    notes: Optional[str] = None


@dataclass
class VulnerabilityFinding:
    """Security finding tied to a dependency or tool."""

    component: str
    version: str
    cve_ids: Sequence[str]
    severity: str
    fix_version: Optional[str] = None
    owasp_llm_categories: Sequence[str] = field(default_factory=list)
    owasp_agentic_categories: Sequence[str] = field(default_factory=list)
    notes: Optional[str] = None
    references: Sequence[EvidenceLink] = field(default_factory=list)


@dataclass
class GuardrailSummary:
    """Aggregated information about guardrail verdicts."""

    name: str
    status: str
    window: str
    total_failures: int
    critical_failures: int
    severity_breakdown: Dict[str, int] = field(default_factory=dict)
    notes: Optional[str] = None


@dataclass
class EvaluationSummary:
    """Summaries of evaluation runs (TruLens/OpenLIT/etc.)."""

    name: str
    metric: str
    value: float
    delta: Optional[float] = None
    window: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class EvidenceLink:
    """Evidence artifacts that back the report."""

    description: str
    uri: str


@dataclass
class AgentSecurityReport:
    """Container for all information required to build the report."""

    metadata: ReportMetadata
    workflow: WorkflowGraph
    tools: Sequence[ToolInventoryEntry]
    mcp_servers: Sequence[MCPServer]
    vulnerabilities: Sequence[VulnerabilityFinding]
    guardrail_summaries: Sequence[GuardrailSummary] = field(default_factory=list)
    evaluation_summaries: Sequence[EvaluationSummary] = field(default_factory=list)
    evidence_links: Sequence[EvidenceLink] = field(default_factory=list)
    appendix: Optional[str] = None

