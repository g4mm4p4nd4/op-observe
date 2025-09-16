"""
Telemetry module for OP-Observe. This package provides instrumentation and telemetry plumbing for all application components.

Responsibilities:
- Initialize and configure OpenLLMetry and OpenInference instrumentation for Python and JavaScript agents, ensuring spans include model, tool, and retriever semantics.
- Provide wrappers/decorators for instrumenting LangChain/LangGraph agents, RAG retrieval, tool calls, and LLM invocations. Record metadata such as agent names, tool names, input/output tokens, and latency.
- Set up OpenTelemetry exporters for Prometheus metrics, OTLP traces, and ClickHouse (optional) via OTEL collector pipelines. Ensure metrics like query latency, guardrail verdicts, and critic scores are emitted.
- Integrate Phoenix for trace and eval UI, exposing dataset clustering and eval results. Provide helper to attach metadata attributes (eval scores, guard verdicts).
- Expose initialization functions to configure and register instrumentation at application startup. Provide default configurations for local development vs. production.
- Future work: add support for distributed tracing across microservices; integrate with SigNoz/ClickHouse UI; implement custom metrics for agentic-security events.
"""
