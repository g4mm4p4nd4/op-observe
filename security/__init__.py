"""
Security module for OP-Observe.

This package implements the agentic security radar, dependency scanning,
vulnerability mapping, and report generation capabilities.

Components:
- Radar worker integration with supported agent frameworks (LangGraph, OpenAI Agents, CrewAI, n8n, AutoGen).
- Parsers for extracting agent graphs, tools, MCP endpoints, and package manifests.
- Detectors for tool registrations, MCP server endpoints, and vulnerability matching (OSV, pip-audit).
- Policy mapper implementing OWASP LLM Top-10 and Agentic AI threat mappings.
- Report builder producing HTML+JSON reports with workflow visualizations, tool inventories,
  MCP server inventories, vulnerability tables, and guard/eval overlays.
- Evidence packaging and CI integration.

Future work:
Implement CLI wrappers, asynchronous scanning jobs, OWASP mapping rulesets, and integration
with CI/CD pipelines and artifact storage.

"""
