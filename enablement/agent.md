# Enablement Agent Tasks

The enablement agent handles packaging, installation, and user enablement workflows for OP‑Observe. It should provide easy bootstrapping, templates, and CLI interfaces for operators.

## Objectives
- Deliver a **one-line installation** that sets up all required services (Radar, OSV‑Scanner, pip‑audit, OpenLLMetry, Phoenix, ClickHouse exporter, Prometheus/Grafana dashboards, Qdrant, vLLM, Vault, Keycloak). Support both Linux and macOS where feasible.
- Provide **golden templates** for common scenarios (Agentic‑Security minimal, Guarded‑RAG minimal). Each template should include sample LangGraph app code, guardrail/eval configs, and a scripted bootstrap.
- Implement a **CLI wrapper** (`opobserve`) with subcommands:
  - `opobserve radar scan|test` – run the agentic‑radar scanner and produce HTML+JSON reports.
  - `opobserve evidence pack` – package monthly evidence bundles (reports, JSON, metrics panels) into an archive and upload to Harbor/MinIO.
  - `opobserve owasp-map verify` – validate OWASP mapping tables and policy versions.
- Manage **environment variables**, secrets, and config files. Provide helpers to generate `.env` and YAML configuration templates that integrate with Vault and Keycloak.
- Add **CI tasks** that build the installers, run installation tests on clean VMs/containers, and publish templates/assets to the artifact registry.
- Document usage clearly in README files and embed comments within scripts.

## Tasks
1. **Bootstrap installer script**
   - Write a Bash (and optional PowerShell) script that installs system dependencies (Python, Git, Docker), clones the OP‑Observe repo, installs Python packages in a virtualenv, and configures services via Docker Compose/Kubernetes manifests.
   - Verify idempotency: running the script twice should not break the environment.
   - Provide flags for air‑gapped mode (use cached OSV/pip‑audit feeds) and offline installation.
2. **Golden template generation**
   - Create two template directories:
     - `templates/agentic_security_minimal`: minimal LangGraph demo with Radar scan/evidence generation and OWASP mapping.
     - `templates/guarded_rag_minimal`: minimal RAG pipeline with Qdrant, guardrails, LLM‑Critic, TruLens/OpenLIT evals.
   - Each template should include code files, a sample configuration YAML, and instructions for launching the demo.
3. **CLI implementation**
   - Implement an `opobserve` Python CLI using `typer` or `click` with subcommands defined above.
   - Wire subcommands to call the underlying modules in `observability`, `security`, `retrieval`, and `telemetry` packages.
   - Provide helpful error messages and verbose logging options.
4. **Environment & secrets management**
   - Write functions to load configuration from `.env` files and merge with command‑line arguments.
   - Integrate with Vault to retrieve secrets (e.g., API keys, database passwords) and with Keycloak for OIDC flows.
   - Expose helper to generate base `.env` and `config.yaml` files with sensible defaults.
5. **CI/CD integration**
   - Add GitHub Actions or GitLab CI pipelines that test the bootstrap installer on fresh runners (Linux/macOS), build the CLI, and publish golden templates as release assets.
   - Include regression tests ensuring that Radar, OSV/pip‑audit, and telemetry exporters start correctly after installation.
6. **Documentation**
   - Write README files for the `enablement` module and each template explaining prerequisites, installation steps, and expected outputs.
   - Provide usage examples for the `opobserve` CLI, including scanning a repo, packaging evidence, and verifying OWASP mappings.

## Acceptance Criteria
- Running the one‑line installer on a clean Linux machine deploys all required services and starts them without errors.
- Golden templates can be launched and demonstrate working flows (Radar report for agentic security, RAG retrieval with guardrails and evals).
- The `opobserve` CLI executes successfully with each subcommand and returns results (e.g., HTML report, evidence archive).
- CI pipelines pass and publish artifacts; installation remains idempotent across runs.
- Documentation is clear, up‑to‑date, and covers troubleshooting tips.
