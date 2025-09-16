TITLE: OP-Observe — Observability‑as‑a‑Service (On‑Prem) with TruLens & OpenLIT Evals, Guardrails (LLM‑Critic) Alerts, LangChain/LangGraph + OpenLLMetry Telemetry, Phoenix/OpenInference Tracing; Agentic‑Security Radar (MCP/Tools/Vuln Mapping + OWASP); ClickHouse Analytics; Sub‑200 ms Semantic Search; 3× Adoption Enablement
----------------------------------------------------------------------
0) SCOPE ADDENDUM (Agentic‑Security + Evidence)
----------------------------------------------------------------------
Add a first‑class security/GRC layer that analyzes agentic systems and emits a **shareable HTML Security Report** with:
• Workflow Visualization (graph of agent nodes/edges, tools, and dataflows)
• Tool Identification (external & custom tools; package and version inventory)
• MCP Server Detection (all MCP servers used by agents)
• Vulnerability Mapping (tools/dependencies → known vulns + OWASP categories)
• Evidence bundle (JSON + HTML + trace links) suitable for audits/board reporting

The rest of the platform remains fully on‑prem, reusing OTEL‑native telemetry, guardrails, and evals for real‑time enforcement.

----------------------------------------------------------------------
1) HIGH‑LEVEL ARCHITECTURE (amended)
----------------------------------------------------------------------
[ Clients / SDKs / Services ]
  └─> App(s): LangChain/LangGraph agents, RAG/Tools
     ├─ Guardrails (incl. LLM‑Critic validator) for I/O validation
     ├─ OpenLIT (eval metrics) + TruLens (feedback/evals)
     ├─ OpenInference + OpenLLMetry (OTel‑native tracing of LLM/Tools)
     └─ Content Safety: Presidio (PII), Llama Guard (policy classifier)

[ Observability / Control Plane ]
  ├─ OpenTelemetry Collector (OTLP)
  ├─ Phoenix (OpenInference‑native trace/eval UI)
  ├─ Prometheus + Alertmanager + Grafana (metrics & alerts)
  ├─ Loki (logs), Tempo (optional traces)
  └─ ClickHouse* (OLAP telemetry sink via OTEL ClickHouse exporter)
  (*see §5.3)

[ Agentic‑Security Plane ]
  ├─ Agentic Radar service (scanner + reporter)
  ├─ Dependency scanners (OSV‑Scanner, pip‑audit) — optional but recommended
  ├─ Policy Mapper (OWASP LLM Top‑10 + OWASP Agentic‑AI threats)
  └─ Report Builder (Jinja/HTMX static HTML + JSON evidence)

[ Retrieval / Models / Infra ]
  ├─ Vector DB: Qdrant (HNSW) on NVMe
  ├─ Embeddings: fast small model via ONNX Runtime (INT8) or vLLM
  ├─ LLM Inference: vLLM (primary), TGI alternative (GPU)
  ├─ Optional lightweight reranker (kept out of p95 path)
  ├─ Message Bus: Kafka/NATS for events/evidence
  ├─ Secrets/Policy: Vault + OPA/Gatekeeper; AuthN/Z: Keycloak (OIDC/RBAC)

[ Storage ]
  ├─ Phoenix → PostgreSQL (prod)
  ├─ Qdrant (snapshots → MinIO)
  ├─ Loki/Tempo backends (object store)
  └─ Artifact/Evidence registry: Harbor + MinIO

----------------------------------------------------------------------
2) AGENTIC‑SECURITY RADAR (design & data flow)
----------------------------------------------------------------------
2.1 Components
- Radar Worker: wraps `agentic-radar` CLI/library; supports frameworks incl. LangGraph, OpenAI Agents, CrewAI, n8n, AutoGen.
- Parsers: walk code/config to extract agent graphs, tools, MCP endpoints, package manifests.
- Detectors:
  • Tools: LangChain/Graph tool registries; decorators; dynamic tracing (tool span names)
  • MCP Servers: static scanning + runtime hooks (client interceptors) to log server URIs
  • Vuln Matchers: map tool binaries/deps → OSV & Python Advisory DB findings; attach CVE/ID and severity
- Policy Mapper: map findings to OWASP LLM Top‑10 categories and OWASP Agentic‑AI threats/mitigations.
- Report Builder: HTML+JSON bundle with (a) Graph (Mermaid/Graphviz), (b) Tool & MCP inventories, (c) Vulnerability table with CVEs and OWASP mappings, (d) guardrail/eval overlays (links to Phoenix traces).
- CI/CD job: runs on merges & nightly; stores artifacts in Harbor; posts summaries to ChatOps.

2.2 Dataflow
Repo / Artifact → Radar scan/test → Findings JSON → Policy Mapper (OWASP) → Evidence store (MinIO) → Report Builder (HTML) → Publish (Harbor/Portal) → Links to Phoenix traces + Grafana panels.

2.3 Report (HTML) — structure (upgraded)
- Header: project, commit, env, policy hash
- **Workflow Visualization**: agent graph (nodes: agents/tools; edges: calls/data; badges: MCP servers)
- **Tool Inventory**: name, version, source (PyPI/NPM/local), scopes, permissions
- **MCP Servers**: endpoint, auth mode, capability list
- **Vulnerability Mapping**: table [Component | Version | CVE/ID | Severity | Fix | **OWASP‑LLM** | **OWASP‑Agentic** | Notes]
- **Guards & Evals**: last 24h guardrail failures (S0/S1), TruLens/OpenLIT eval deltas
- **Evidence**: JSON bundle + trace IDs + config fingerprints
- **Appendix**: methodology; configuration YAML; scanner versions

----------------------------------------------------------------------
3) SECURITY SIGNALS & ACTIONS (runtime + offline)
----------------------------------------------------------------------
Runtime (per request):
- Input guards (PII, safety), retrieval integrity checks
- Output guards (schema, jailbreak/PII re‑emit)
- LLM‑Critic (Guardrails) for task‑specific quality criteria (routed to local models via LiteLLM → vLLM)
- Emit OTEL spans/metrics with guard verdicts and critic grades → Prometheus/ClickHouse → Alertmanager

Offline/batch:
- TruLens feedback (groundedness, completeness, retrieval quality) on sampled traffic
- Radar “test” mode for adversarial probes (prompt injection/PII/harmful content/fake news) on supported frameworks
- OWASP‑aligned regression gates: fail builds on increases in high‑severity categories or new S0 vulns

Automations:
- On surge in S0 guard failures → disable risky tools / increase retrieval redundancy / rate‑limit tenant
- On dependency CVE emergence → create fix ticket; block release if severity ≥ threshold

----------------------------------------------------------------------
4) SUB‑200 ms SEMANTIC SEARCH (unchanged targets; guard‑aware)
----------------------------------------------------------------------
Latency guardrails as in baseline: query embed ≤40 ms CPU INT8 (or ≤15 ms GPU), ANN 5–25 ms, optional rerank ≤60 ms when enabled; adaptive ef_search; hot caches; NUMA pinning. Keep heavy rerank out of p95 path; show async “refine” results when needed.

----------------------------------------------------------------------
5) TELEMETRY & STORAGE CHOICES (self‑host only)
----------------------------------------------------------------------
5.1 OpenLLMetry + OpenInference
- OpenLLMetry adds LLM‑aware spans on top of OpenTelemetry; integrate for Python/JS agents.
- OpenInference LangChain instrumentation enriches spans with model/tool/retriever semantics.
- Fan‑out: OTel Collector → Phoenix (trace/eval UI) + Prometheus (metrics) + ClickHouse (OLAP).

5.2 Phoenix (self‑host)
- Use Phoenix for trace/eval UX, dataset clustering/visualization, and quick eval experiments.
- Persist to Postgres; RBAC via Keycloak; store artifacts in object store.

5.3 ClickHouse path (optional but recommended)
- Ingest OTEL metrics/logs/traces via ClickHouse exporter in the OTel Collector.
- Use for long‑horizon analytics (drift trends, guard failure cohorts, incident forensics).
- Keep Grafana for SLO dashboards; optionally add SigNoz (OSS) if you prefer a single‑pane ClickHouse UI.

----------------------------------------------------------------------
6) INTEGRATIONS & IMPLEMENTATION NOTES
----------------------------------------------------------------------
6.1 Agentic Radar backend
- Packaged as a sidecar/Job with `agentic-radar scan ...` and `agentic-radar test ...`.
- Framework support matrix includes LangGraph scan + MCP detection; OpenAI Agents scan/test + MCP detection. (Keep CI jobs per framework.)
- Store JSON findings; render to HTML with a hardened, self‑contained template (no external CDNs).

6.2 Vulnerability sources
- OSV‑Scanner for multi‑ecosystem deps; pip‑audit for Python environments. Cache feeds locally; no egress in air‑gapped mode.
- Evidence normalization: dedupe across lockfiles/venvs; annotate with fix versions and policy exceptions.

6.3 Guardrails + LLM‑Critic
- Use Guardrails Hub LLM‑Critic validator; run with LiteLLM routing to local vLLM models (OpenAI‑compatible endpoint).
- Treat critic scores as metrics; alert on drops against baselines; record as Phoenix attributes.

6.4 MCP detection
- Static scan code/configs for MCP clients/servers; runtime hooks export MCP server names/URIs as span attrs; include in report.

6.5 OWASP mapping
- Maintain versioned mapping tables:
  • OWASP LLM Top‑10 (LLM01–LLM10)
  • OWASP Agentic‑AI threats/mitigations taxonomy
- Auto‑assign categories based on detector rules (e.g., external tool invocation without validation → LLM02/IO handling; prompt‑construction from untrusted source → LLM01/Injection; risky tool permission set → Agentic threat bucket).
- Show both mappings per finding in report + mitigations checklist.

----------------------------------------------------------------------
7) ENABLEMENT SUITE (updated)
----------------------------------------------------------------------
- One‑line bootstrap installs Radar, OSV/pip‑audit, OpenLLMetry, Phoenix, ClickHouse exporter, Grafana dashboards, Qdrant, vLLM, Vault, Keycloak.
- Golden templates now include:
  • Agentic‑Security minimal: LangGraph demo + Radar report + OWASP mapping
  • Guarded‑RAG minimal: Qdrant + guards + LLM‑Critic + evals
- CLI adds: `opobserve radar scan|test`, `opobserve evidence pack`, `opobserve owap-map verify`.

----------------------------------------------------------------------
8) SLOs, SLIs & EVIDENCE PACKAGES
----------------------------------------------------------------------
SLIs:
- Search p95 ≤200 ms; Trace completeness ≥99%
- Guard S0 ≤0.1%; LLM‑Critic median ≥ baseline; OWASP‑category incident rate trending downward week‑over‑week
- Radar coverage: ≥95% of agent repos scanned weekly; MCP detection on all agent apps

Evidence Pack (monthly/quarterly):
- Radar report HTML + JSON
- Trend panels: guard failures by category, critic scores, eval deltas, MCP inventory drift
- SBOM & dependency vuln diffs; policy hashes; Phoenix experiment diffs

----------------------------------------------------------------------
9) DELIVERY PHASES (delta from baseline)
----------------------------------------------------------------------
A. Wire OpenLLMetry + OpenInference on apps; confirm OTEL fan‑out.
B. Deploy Radar; scan representative repos; generate first HTML report; wire CI.
C. Add OSV/pip‑audit; enable ClickHouse exporter; build Grafana panels for OWASP categories/critic scores.
D. Enable Radar “test” mode where supported; set alert thresholds; ship evidence bundle CLI.
E. Hardening: air‑gapped feeds; MCP hook tests; red‑team runs; downgrade paths on false positives.

----------------------------------------------------------------------
10) ACCEPTANCE TESTS (security plane)
----------------------------------------------------------------------
- Radar scan produces HTML+JSON with: workflow graph, tools list, MCP list, vuln table, OWASP mappings.
- MCP servers observed at runtime match static inventory for ≥95% of flows.
- OWASP mapping ruleset passes unit tests; CI blocks release on S0/S1 deltas.
- Evidence bundle reproducible (hash‑stable) and references live traces/dashboards.

----------------------------------------------------------------------
11) TECH‑STACK VALIDATION (on‑prem fit)
----------------------------------------------------------------------
All components are open‑source/self‑hostable: agentic‑radar; OpenLLMetry; OpenInference/Phoenix; Guardrails + LLM‑Critic; TruLens; OpenLIT; Qdrant; vLLM/TGI; Prometheus/Grafana/Loki/Tempo; ClickHouse (+ OTEL exporter); Vault/Keycloak/OPA; MinIO/Harbor. See sources in Validation section.
