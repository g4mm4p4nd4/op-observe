# Observability Agent Tasks

This agent implements the observability layer for OP ‑Observe. It instruments LLM and agent frameworks to emit metrics, traces, logs and evaluations.

## Goals
- Provide instrumentation for LangChain, LangGraph and other agent frameworks using OpenLLMetry and OpenInference.
- Set up an OpenTelemetry pipeline (collector) that fans out spans and metrics to Phoenix, Prometheus/Grafana, Loki, Tempo and ClickHouse.
- Expose metrics for guardrail verdicts and LLM ‑Critic scores.
- Provide utilities for caching and context propagation.

## Tasks
1. **Instrumentation wrappers**
   - Create Python decorators or context managers to wrap tool/chain functions and capture OpenTelemetry spans.
   - Use OpenLLMetry to annotate spans with LLM-specific attributes (model name, prompt size, tool invocation).
   - Support instrumenting synchronous and asynchronous calls.
   - Write unit tests using pytest and an in-memory OTLP collector to verify spans are emitted.

2. **Collector configuration**
   - Provide a default OpenTelemetry collector configuration for on‑prem deployment.
   - Configure exporters for Prometheus (metrics), ClickHouse (metrics/logs/traces), and Phoenix (traces/evals).
   - Expose environment variables for customizing OTLP endpoint and authentication.
   - Write tests that spin up a local collector using docker-compose and validate metrics ingestion.

3. **Metric emission**
   - Instrument guardrail verdicts (PII, safety, schema validation) as Prometheus counters with labels for severity and tool.
   - Instrument LLM‑Critic scores as histograms or summaries.
   - Emit metrics for evaluation latency and throughput.
   - Provide example Grafana dashboards.

4. **Logging & tracing integration**
   - Integrate Python logging with OpenTelemetry logging exporter to forward logs to Loki via collector.
   - Ensure that traces link to corresponding log entries and metrics through trace and span IDs.
   - Write integration tests that verify logs appear in Loki and are correlated with traces.

5. **Documentation & usage**
   - Document how to instrument a LangChain or LangGraph agent using the provided wrappers.
   - Include example code snippets and configuration instructions.
   - Provide guidelines for customizing the collector pipeline.

## Acceptance criteria
- Unit tests confirm that instrumented functions emit the expected spans and metrics.
- Example application shows traces in Phoenix, metrics in Grafana, and logs in Loki.
- Collector configuration is valid and can be deployed via docker-compose.
