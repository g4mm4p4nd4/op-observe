# Agentic-Security Minimal Template

This template demonstrates how the OP-Observe radar layer can analyse a LangGraph workflow and emit a shareable HTML report with OWASP mappings.

## What it shows

- LangGraph agent with planner → tool → responder flow.
- Radar scanner that inventories tools, MCP servers, and dependencies.
- Automated vulnerability detection with OWASP LLM Top-10 and Agentic-AI categories.
- Evidence bundle (HTML + JSON) suitable for security reviews.

## Run the demo

```bash
python -m templates.agentic_security_minimal.radar_report
```

Artifacts are stored in `artifacts/agentic_security/security_report.(html|json)` by default.

## Extend it

- Replace the static `SECURITY_METADATA` with hooks into the actual Agentic Radar CLI.
- Publish the HTML report to an internal portal or evidence registry.
- Feed the JSON bundle into dashboards to trend OWASP category regressions.
