"""Command-line interface for the OP-Observe orchestrator."""

from __future__ import annotations

import argparse
import json
import sys
from typing import List

from . import Config, Orchestrator
from .agents import Document

DEFAULT_DOCUMENTS: List[Document] = [
    Document(
        id="obs-1",
        content="Observability pipelines ensure telemetry coverage across agents.",
        metadata={"category": "observability"},
    ),
    Document(
        id="sec-1",
        content="Agentic security radar maps OWASP findings to actionable mitigations.",
        metadata={"category": "security"},
    ),
    Document(
        id="rag-1",
        content="Retrieval augmented generation coordinates guardrails and evidence packing.",
        metadata={"category": "retrieval"},
    ),
]

DEFAULT_AGENT_SPECS = (
    {
        "name": "observability-agent",
        "tools": [
            {"name": "openllmetry", "version": "0.4", "source": "internal"},
        ],
        "mcp_servers": [],
    },
    {
        "name": "security-radar",
        "tools": [
            {"name": "agentic-radar", "version": "1.2", "source": "external"},
            {"name": "osv-scanner", "version": "2.0", "source": "external"},
        ],
        "mcp_servers": [
            {"endpoint": "https://mcp.local/security", "capabilities": ["scan"], "auth": "token"}
        ],
    },
)

DEFAULT_VULNERABILITY_DB = {
    "agentic-radar": {
        "severity": "medium",
        "cve": "CVE-2024-1234",
        "owasp_llm": ["LLM02"],
        "owasp_agentic": ["AGENTIC-04"],
        "notes": "Update to 1.3 to address sandbox bypass",
    },
    "osv-scanner": {
        "severity": "low",
        "cve": None,
        "owasp_llm": ["LLM10"],
        "owasp_agentic": ["AGENTIC-09"],
        "notes": "Monitor upstream feed sync windows",
    },
}


def build_orchestrator() -> Orchestrator:
    config = Config.from_env(
        documents=DEFAULT_DOCUMENTS,
        agent_specs=DEFAULT_AGENT_SPECS,
        vulnerability_db=DEFAULT_VULNERABILITY_DB,
    )
    orchestrator = Orchestrator(config)
    orchestrator.initialize_agents()
    return orchestrator


def handle_rag(args: argparse.Namespace) -> int:
    orchestrator = build_orchestrator()
    try:
        result = orchestrator.run_rag_search(args.query, top_k=args.top_k)
    except Exception as exc:  # pragma: no cover - surfaced to CLI users
        print(f"Error executing RAG search: {exc}", file=sys.stderr)
        return 1
    output = {
        "query": result.query,
        "response": result.response,
        "documents": result.documents,
    }
    print(json.dumps(output, indent=2))
    return 0


def handle_radar(args: argparse.Namespace) -> int:
    orchestrator = build_orchestrator()
    try:
        results = orchestrator.run_radar_scan(mode=args.mode)
    except Exception as exc:  # pragma: no cover - surfaced to CLI users
        print(f"Error running radar scan: {exc}", file=sys.stderr)
        return 1
    printable = results["report_json"]
    print(json.dumps(printable, indent=2))
    return 0


def handle_evidence(args: argparse.Namespace) -> int:
    orchestrator = build_orchestrator()
    try:
        rag_result = orchestrator.run_rag_search(args.query, top_k=args.top_k)
        radar_results = orchestrator.run_radar_scan(mode=args.mode)
        bundle = orchestrator.package_evidence(rag_result, radar_results)
    except Exception as exc:  # pragma: no cover - surfaced to CLI users
        print(f"Error packaging evidence: {exc}", file=sys.stderr)
        return 1
    output = {
        "digest": bundle.digest,
        "created_at": bundle.created_at,
        "json_blob": json.loads(bundle.json_blob),
    }
    print(json.dumps(output, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OP-Observe orchestration CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    rag_parser = subparsers.add_parser("rag", help="Execute a RAG query")
    rag_parser.add_argument("query", help="User query to execute")
    rag_parser.add_argument("--top-k", type=int, default=3, help="Number of documents to retrieve")
    rag_parser.set_defaults(func=handle_rag)

    radar_parser = subparsers.add_parser("radar", help="Run the security radar")
    radar_parser.add_argument("--mode", default="scan", choices=["scan", "test"], help="Radar mode to execute")
    radar_parser.set_defaults(func=handle_radar)

    evidence_parser = subparsers.add_parser("evidence", help="Package an evidence bundle")
    evidence_parser.add_argument("--query", required=True, help="Query to use for the RAG run")
    evidence_parser.add_argument("--top-k", type=int, default=3, help="Number of documents to retrieve")
    evidence_parser.add_argument("--mode", default="scan", choices=["scan", "test"], help="Radar mode to execute")
    evidence_parser.set_defaults(func=handle_evidence)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
