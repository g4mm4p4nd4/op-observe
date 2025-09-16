# OP-Observe Security Automation

[![Security Radar CI](https://github.com/op-observe/op-observe/actions/workflows/security-ci.yml/badge.svg)](https://github.com/op-observe/op-observe/actions/workflows/security-ci.yml)
[![Nightly Security Radar](https://github.com/op-observe/op-observe/actions/workflows/security-ci.yml/badge.svg?event=schedule)](https://github.com/op-observe/op-observe/actions/workflows/security-ci.yml?query=event%3Aschedule)

This repository packages the CI/CD automation that powers OP-Observe's agentic-security plane. The
pipeline generates radar findings, audits dependencies, renders a shareable HTML security report,
produces JSON evidence for downstream tooling, and publishes an evidence bundle ready for board or
GRC review.

## What's included

- **Security Radar CI workflow** (`.github/workflows/security-ci.yml`)
  - Runs on merges, pull requests, manual dispatches, and a nightly schedule (03:00 UTC)
  - Generates radar and vulnerability findings from `config/security_targets.toml`
  - Builds HTML/JSON security reports and an evidence zip bundle
  - Uploads artifacts and summarises results in the GitHub Actions UI
  - Executes `pytest` to ensure report builders remain healthy
- **Reporting utilities** under `scripts/` and `security_pipeline/`
  - `run_radar_scan.py` → workflow graph, tool inventory, MCP detection
  - `run_vulnerability_audit.py` → dependency findings + OWASP mappings
  - `build_security_artifacts.py` → HTML/JSON/evidence bundle synthesis
- **Reference configuration** (`config/security_targets.toml`) describing agents, tools, MCP
  servers, guardrail posture, eval metrics, and vulnerability catalogues.
- **Tests & documentation** (`tests/`, `docs/ci-cd.md`) validating artifact generation and guiding
  operators through local execution or customisation.

## Local execution

```bash
python -m pip install -r requirements.txt
python scripts/run_radar_scan.py
python scripts/run_vulnerability_audit.py
python scripts/build_security_artifacts.py
pytest
```

Open `reports/security-report.html` to review the rendered report and inspect
`reports/security-evidence.zip` for the bundled evidence set.

## Customising

- Update `config/security_targets.toml` with your agents, tools, MCP servers, guardrail metrics,
  and vulnerability catalogue to reflect your deployment.
- Add new tests in `tests/` to extend guard-coverage or enforce additional policy checks.
- Tweak `.github/workflows/security-ci.yml` to adjust schedules, retention periods, or additional
  gates (e.g., Slack/webhook notifications).

For deeper guidance, see [docs/ci-cd.md](docs/ci-cd.md).
