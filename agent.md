# Core Agent Tasks

This core agent orchestrates the various sub‑agents defined in the repository. It provides guidance on when to leverage each module (observability, security, retrieval, telemetry, enablement) and coordinates their execution to build a cohesive OP‑Observe platform.

## Purpose
- **Glue layer:** Bridge the functionality of the specialized agents. For example, after the retrieval agent serves search results, the observability and telemetry agents should emit traces/metrics, and the security agent should analyze the workflow for policy violations.
- **Execution order:** Define typical workflows so that CI/CD pipelines and developers know which agents to run at what stages (e.g., run security scans before merging, run observability and telemetry instrumentation at runtime, use enablement tools for installation).
- **Task delegation:** Point to each module’s `agent.md` for detailed tasks and ensure responsibilities are clearly separated.

## When to Use Each Agent
| Agent Module | Use Case | Key Responsibilities |
|--------------|---------|---------------------|
| **observability** | Instrumentation and tracing for LangChain/LangGraph apps and tools | Wrap agents/tools with OpenLLMetry & OpenInference spans; export metrics to OTEL collector; integrate with Phoenix, Prometheus/Grafana, Loki/Tempo; emit guardrail and LLM‑Critic metrics |
| **security** | Static and dynamic analysis of agentic systems | Run agentic‑radar scans on code/config to generate HTML+JSON reports with graphs, tool inventories, MCP server detection, vulnerability mapping, and OWASP categorization; integrate OSV‑Scanner and pip‑audit; build evidence bundles |
| **retrieval** | Semantic search and data retrieval | Provide low‑latency vector search via Qdrant; implement embedding pipelines (ONNX/vLLM); manage caching and optional re‑ranking; expose API for semantic search queries |
| **telemetry** | Metrics/logs/traces export and analysis | Configure OTEL collectors and exporters (Prometheus, ClickHouse); integrate Phoenix UI; send guardrail verdicts and critic scores; provide logs integration via Loki/Tempo |
| **enablement** | Installation, templates, and CLI | Supply one‑line installers; deliver golden templates (agentic‑security minimal, guarded‑rag minimal); implement `opobserve` CLI for radar scans, evidence packing, and OWASP verification; manage environment variables and secrets

## High‑Level Workflow
1. **Setup**
   - Use the enablement agent to install OP‑Observe on the target environment and deploy the golden template relevant to your use case.
2. **Development**
   - Build your LangGraph/RAG application. Instrument it with the observability agent wrappers to emit traces and metrics automatically.
   - Use the retrieval agent to integrate semantic search capabilities into your application.
3. **Security & Compliance**
   - Before merging or releasing, run the security agent (`opobserve radar scan`) on the repository to produce a shareable HTML/JSON report and map vulnerabilities to OWASP categories.
   - Address any high‑severity findings; incorporate guardrails and adjust tool permissions accordingly.
4. **Runtime Operations**
   - Deploy the application with telemetry exporters enabled. The telemetry agent ensures metrics and logs flow into Prometheus/Grafana, Phoenix, and ClickHouse.
   - Continuously monitor guardrail failures and critic scores; configure Alertmanager rules for S0/S1 incidents.
5. **Evidence & Reporting**
   - Periodically run `opobserve evidence pack` (enablement agent CLI) to assemble evidence bundles (security reports, metrics trends, SBOM diffs) for audit and compliance.

## Meta‑Tasks for Codex
- Implement orchestration scripts or CI jobs that chain these agents in the recommended order.
- Ensure that each module publishes artifacts (e.g., reports, dashboards) to a common evidence store (MinIO/Harbor) where the core agent can reference them.
- Write integration tests across modules verifying that traces contain security annotations, that vulnerability reports link back to Phoenix trace IDs, and that retrieval results adhere to guardrail verdicts.
- Continuously update documentation and diagrams to reflect the evolving architecture.

## Acceptance Criteria
- Developers can follow this guide to understand when and how to invoke each sub‑agent.
- CI pipelines referencing this core agent will run the appropriate sub‑agents in sequence and fail on unresolved S0/S1 security issues or missing telemetry.
- Integrated system demonstrations (using golden templates) show observability instrumentation, security scanning, retrieval operations, telemetry export, and evidence packaging working together.
