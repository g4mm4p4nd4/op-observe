"""
Observability module for OP-Observe.

This package provides instrumentation and tracing capabilities using OpenTelemetry,
OpenLLMetry, Phoenix, Prometheus, Grafana, Loki, Tempo, and ClickHouse.

Components:
- OTLP exporters and collectors.
- Telemetry instrumentation for language models, tools, and retrieval frameworks.
- UI integration with Phoenix for trace/eval visualization.
- Metrics exposure via Prometheus and ClickHouse for OLAP analytics.
- Logging via Loki and Tempo.

Future work:
Implement instrumentation wrappers for LangChain/LangGraph agents, tracing middleware, 
metric recording, and connectors to ClickHouse.

"""
