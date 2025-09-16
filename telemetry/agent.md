# Telemetry Agent Tasks for OP-Observe

## Goal
Implement the telemetry integration layer enabling rich observability for OP ‑Observe's LLM and agentic workloads. This module instrument LLM calls, tool invocations, and retrieval operations using OpenLLMetry and OpenInference, exports metrics/traces/logs to the OTEL Collector, and surfaces insights via Phoenix, Prometheus, Loki and ClickHouse.

## Tasks
- Integrate OpenLLMetry and OpenInference instrumentation for Python/JS agents:
  - Wrap LangChain/LangGraph agents and tools to emit LLM-aware spans, capturing model names, prompt/response tokens, and tool names.
  - Instrument RAG retrieval operations and caching layers (Qdrant) to record query latency and vector search metrics.
  - Decorate custom tools, MCP client calls, and guardrails to emit distinct OTEL spans.
  - Ensure spans are enriched with context (tenant/app name, agent ID) using span attributes.

- Set up metrics export:
  - Configure OTEL Collector exporters for Prometheus and ClickHouse; define resource attributes for environment and service name.
  - Define counters/gauges/histograms for guardrail verdicts (S0/S1), LLM‑Critic scores, retrieval latency (p50/p95), and other SLIs.
  - Register metrics instruments via OpenLLMetry; expose a `/metrics` endpoint if using Prometheus scraping.

- Enable Phoenix integration:
  - Send traces to Phoenix for interactive exploration; integrate Phoenix UI with Keycloak for RBAC.
  - Provide functions to link Phoenix trace IDs back to evidence bundles and guard/eval reports.

- Logging integration:
  - Use OTEL SDK to export logs to Loki/Tempo; structure logs with JSON and context.
  - Include fields for user queries, agent chain steps, tools called, and error details while respecting PII redaction via Presidio.

- Utility functions:
  - Provide an initialization function to register instrumentation and metrics sinks (e.g., `init_telemetry(config: TelemetryConfig) -> None`).
  - Allow dynamic enabling/disabling of exporters based on environment (dev/test/prod).
  - Document configuration options (sampling rates, batch sizes, endpoint URIs) in a sample config file.

- Testing:
  - Write unit tests validating that spans and metrics are emitted correctly for simple agent runs using pytest/pytest-asyncio.
  - Use OTEL test exporters to capture spans/metrics and assert on attributes and histogram values.
  - Provide example code demonstrating instrumentation integration with a LangGraph agent.

## Acceptance Criteria
- LLM and tool operations emit OpenLLMetry spans with correct metadata and hierarchy.
- Metrics for guard verdicts, critic scores, and retrieval latencies are captured and exposed.
- Phoenix UI shows complete traces with semantic annotations for agents and tools.
- Configuration functions allow toggling exporters and customizing endpoints.
- Tests cover instrumentation and metrics export with at least 80% coverage.
