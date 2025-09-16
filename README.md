# OP-Observe Golden Templates

This repository contains reference implementations for two security-first AI demos:

1. **Agentic-Security Minimal Template** – a LangGraph workflow instrumented with an agentic radar scanner that emits an HTML + JSON security report with OWASP mappings.
2. **Guarded-RAG Minimal Template** – an in-memory Qdrant retriever wrapped with guardrails, an LLM-Critic style reviewer, and lightweight evaluation metrics.

Both demos are written to be fast to run locally (no networked model calls) while showcasing the observability and governance hooks required by the OP-Observe platform.

## Getting Started

The demos ship without external dependencies, so you can run them directly with the
system Python. Creating a virtual environment is optional:

```bash
python -m venv .venv  # optional
source .venv/bin/activate
```

## Running the Templates

- Agentic-Security demo: `python -m templates.agentic_security_minimal.radar_report`
- Guarded-RAG demo: `python -m templates.guarded_rag_minimal.pipeline`

Each module prints a short summary of the artifacts created.

## Tests

Run the automated checks to validate that both templates execute end-to-end:

```bash
python -m unittest discover -s tests
```

The tests cover report generation, guardrail enforcement, and evaluation outputs to ensure the golden templates remain healthy.
