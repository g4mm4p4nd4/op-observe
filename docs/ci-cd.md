# Security CI/CD Playbook

This repository ships a **Security Radar CI** workflow that runs radar scans, dependency
vulnerability audits, automated tests, and report generation on every merge to `main`,
pull request, manual dispatch, and on a nightly schedule (03:00 UTC).

## Workflow summary

| Workflow | File | Triggers | What it does |
| --- | --- | --- | --- |
| Security Radar CI | `.github/workflows/security-ci.yml` | `push`, `pull_request`, `workflow_dispatch`, nightly (`0 3 * * *`) | Generates radar findings, runs vulnerability auditing, builds HTML/JSON reports, zips evidence bundles, uploads artifacts, and executes unit tests. |

Key stages:

1. **Environment setup** – Checkout the repository, install Python 3.11, and install testing
   dependencies from `requirements.txt`.
2. **Radar scan** – `scripts/run_radar_scan.py` reads `config/security_targets.toml` and emits
   `reports/radar-findings.json` describing the workflow graph, tools, MCP servers, and metadata.
3. **Vulnerability audit** – `scripts/run_vulnerability_audit.py` compiles dependency and
   vulnerability mappings into `reports/dependency-vulnerabilities.json`.
4. **Report build** – `scripts/build_security_artifacts.py` merges the findings, renders the
   HTML dashboard, exports a machine-readable JSON report, generates a Markdown summary, and packs
   everything (including the raw findings) into `reports/security-evidence.zip`.
5. **Testing** – `pytest` validates the pipeline utilities and evidence bundle creation logic.
6. **Publishing** – The workflow uploads the HTML report, JSON report, and evidence bundle as
   GitHub Actions artifacts and appends the Markdown summary to the workflow job summary so it is
   visible in the Actions UI.

All steps run for both merge commits and the nightly schedule so the latest security posture is
always captured.

## Artifact reference

| Artifact | Location | Description |
| --- | --- | --- |
| `reports/radar-findings.json` | workspace + artifacts | Raw output of the radar scan step. |
| `reports/dependency-vulnerabilities.json` | workspace + artifacts | Normalized dependency vulnerability findings. |
| `reports/security-report.html` | workspace + artifacts | Human-friendly HTML report with workflow graph, tool/MCP inventories, OWASP mapping, guardrail & eval summaries, and evidence links. |
| `reports/security-report.json` | workspace + artifacts | Machine-readable report payload mirroring the HTML content. |
| `reports/security-summary.md` | workspace + job summary | Markdown digest appended to `$GITHUB_STEP_SUMMARY`. |
| `reports/security-evidence.zip` | workspace + artifacts | Evidence bundle containing the JSON report, radar & vulnerability findings, metadata, and Markdown summary. |

Artifacts are retained for 14 days (HTML/JSON) and 30 days (evidence bundle) by default.

## Customising the pipeline

- Edit `config/security_targets.toml` to update agents, tools, MCP servers, guardrail/eval data,
  or vulnerability entries. The scripts automatically pick up changes and include them in reports.
- Add new tests under `tests/` to enforce additional checks before reports are published.
- Adjust workflow triggers or retention periods by editing `.github/workflows/security-ci.yml`.
- The scripts accept CLI arguments so you can override paths or commit metadata when running
  locally. Use `python scripts/run_radar_scan.py --help` for the full CLI surface.

## Running locally

```bash
python -m pip install -r requirements.txt
python scripts/run_radar_scan.py
python scripts/run_vulnerability_audit.py
python scripts/build_security_artifacts.py
pytest
```

After running the commands above, open `reports/security-report.html` in a browser and inspect
`reports/security-evidence.zip` to verify the bundle contents.
