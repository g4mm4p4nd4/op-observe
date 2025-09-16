# Security Agent Tasks

This agent implements the agentic‑security radar and vulnerability scanning layer for OP ‑Observe.

## Goals
- Parse agent code and configurations to extract agent graphs, tools, and MCP endpoints across supported frameworks (LangGraph, OpenAI Agents, CrewAI, etc.).
- Detect Multi‑Capability Platform (MCP) servers and external tool usage both statically and at runtime.
- Map dependencies to known vulnerabilities (OSV, pip‑audit) and categorize them using OWASP LLM Top‑10 and OWASP Agentic‑AI threat categories.
- Generate a shareable HTML and JSON security report containing workflow visualization, tool inventory, MCP server inventory, vulnerability table with OWASP mappings, guardrail and eval overlays, and evidence bundle.

## Tasks
1. **Parser implementation**
   - Write parsers that walk Python source code and configuration files to construct an agent graph of nodes (agents, tools, retrievers) and edges (calls, data flows).
   - Support frameworks including LangGraph, OpenAI Agents, CrewAI, n8n, and AutoGen by inspecting their specific APIs and configuration patterns.
   - Extract tool registrations, decorators, and dynamic tracing spans to identify external tools and MCP endpoints.
   - Write unit tests using small example projects to ensure the parser builds correct graphs.

2. **Detector and matcher components**
   - Implement detectors for MCP servers by scanning configuration and instrumenting client interceptors to log server URIs at runtime.
   - Integrate OSV‑Scanner and pip‑audit to collect vulnerabilities for Python and other ecosystems; cache feeds for air‑gapped mode.
   - Map each tool binary or package version to CVE identifiers, severity, and potential fix versions.
   - Implement a policy mapper that assigns OWASP LLM Top‑10 (LLM01–LLM10) categories and OWASP Agentic‑AI threat labels to each finding based on rule matching.

3. **Report builder**
   - Design a static HTML template (using Jinja and HTMX) that includes a workflow visualization (Mermaid or Graphviz), tool and MCP inventories, vulnerability table with columns [Component, Version, CVE/ID, Severity, Fix, OWASP‑LLM, OWASP‑Agentic, Notes], guardrail/eval overlays, evidence references, and appendices.
   - Generate a JSON bundle that mirrors the report data and includes trace IDs and configuration fingerprints.
   - Ensure the report is self‑contained with no external CDN dependencies and can be shared for audits or board reporting.

4. **CLI integration**
   - Provide command line interfaces `agentic-radar scan` and `agentic-radar test` that run the parser, detectors, and report builder against a given repository or project directory.
   - Implement options for CI mode, output directory specification, and policy thresholds that cause the CLI to exit with non‑zero status when high‑severity vulnerabilities or OWASP categories are present.
   - Write integration tests that invoke the CLI on sample projects and verify that reports are produced and policy gates trigger correctly.

5. **Evidence bundle and policy updates**
   - Implement utilities to package the HTML report, JSON findings, relevant trace IDs, and scanner versions into a compressed evidence bundle.
   - Maintain versioned mapping tables for OWASP LLM Top‑10 and OWASP Agentic‑AI threats; provide commands to update or verify these mappings.
   - Document how to store and retrieve evidence bundles in the artifact registry (Harbor) and link them to Phoenix and Grafana dashboards.

## Acceptance criteria
- Running `agentic-radar scan` on a sample agent project produces a valid HTML and JSON report with workflow visualization, inventories, vulnerability mappings, and evidence.
- The parser correctly identifies agent nodes, tools, and MCP endpoints across supported frameworks.
- OSV and pip‑audit integrations detect known vulnerabilities and map them to OWASP categories.
- CI mode exits with non‑zero status on high severity issues, enabling regression gates.
