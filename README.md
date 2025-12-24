# OP-Observe

## Overview & Purpose
OP-Observe provides an on premise observability‑as‑a‑service platform for agentic AI systems. It integrates telemetry, evaluation, tracing and security scanning into a single stack so teams can monitor and control language‑model based agents and tools. The goal is to deliver trustworthy, compliant and high‑performance applications by combining metrics, logs, traces and evaluation feedback with strong security guardrails.

## Features & Tech Stack
- OpenTelemetry instrumentation and collection for metrics, logs and traces.
- Integration with evaluation frameworks such as TruLens and OpenLIT for real‑time quality and safety feedback.
- Agentic‑security radar that scans agent workflows, tools and dependencies for vulnerabilities and policy violations.
- Dashboarding and alerting via Prometheus, Grafana, Phoenix/OpenInference and Alertmanager.
- Sub‑200 ms semantic search using Qdrant and vLLM with optional reranking.
- Bootstrap script that generates a Docker Compose deployment for the whole stack.

| Component      | Technology/Tool            |
|---------------|----------------------------|
| Language      | Python                     |
| Frameworks    | OpenTelemetry, LangChain/LangGraph, Guardrails, TruLens, OpenLIT |
| Databases     | PostgreSQL, ClickHouse, Qdrant |
| Observability | Prometheus, Grafana, Loki, Tempo, Phoenix/OpenInference |
| Security      | Keycloak (OIDC/RBAC), Vault, OSV‑Scanner, pip‑audit |
| Deployment    | Docker Compose via bootstrap script |

## Installation & Usage
1. Clone the repository and enter its directory:
   ```bash
   git clone https://github.com/g4mm4p4nd4/op-observe.git
   cd op-observe
   ```
2. Create a virtual environment and install Python dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Generate a Docker Compose configuration and start the stack:
   ```bash
   python scripts/bootstrap.py
   docker compose up -d
   ```
4. Navigate to the exposed service endpoints (Grafana, Phoenix, Prometheus) to explore metrics, traces and evaluation dashboards.

## Business & Entrepreneurial Value
OP‑Observe can be packaged as an on‑premise subscription offering for enterprises that need to monitor and secure AI applications. The platform enables tiered licensing models, from community editions to premium enterprise versions with support and customization. Businesses can upsell advanced analytics, managed hosting or integration services. Because OP‑Observe is modular and built on open standards, it can scale with customer needs and integrate with existing observability pipelines, reducing implementation costs and shortening time to value. Automation of security scanning and compliance reporting also lowers operational risk, making it attractive for highly regulated industries.

## Consumer Value
For developers and data scientists, OP‑Observe provides an easy‑to‑use observability stack that delivers actionable insights into agentic workflows. Users can quickly instrument their applications, monitor latency and quality metrics, and receive guardrail alerts without piecing together multiple tools. The platform saves time by automating telemetry collection and evaluation, allowing teams to focus on building features rather than maintaining infrastructure. With built‑in privacy and policy enforcement, end users gain confidence that their data and interactions are processed securely and transparently, leading to higher trust and better overall experience.
