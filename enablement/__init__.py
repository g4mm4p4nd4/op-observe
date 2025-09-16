"""
Enablement module for OP-Observe.

This package provides installation scripts, configuration templates and CLI helpers to bootstrap OP-Observe in on-prem environments. Responsibilities include:
- Packaging one-line installers to deploy components like Radar, OSV-Scanner, pip-audit, OpenLLMetry, Phoenix, ClickHouse exporter, Grafana dashboards, Qdrant, vLLM, Vault, Keycloak.
- Providing golden templates for minimal environments (Agentic-Security minimal, Guarded-RAG minimal) including sample code, config files, and CI jobs.
- Implementing bootstrap CLI commands (e.g., `opobserve radar scan|test`, `opobserve evidence pack`, `opobserve owap-map verify`) that wrap underlying tools and orchestrate tasks.
- Managing environment variables, secrets injection, and preflight checks for dependencies.
- Future extensions may include interactive TUI/GUI installers, upgrade management, and integration with package managers.

The module should strive for idempotent operations and air-gapped compatibility; avoid external CDNs and ensure all artifacts can be served from local registries.
"""
