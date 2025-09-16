# Guarded-RAG Minimal Template

This template demonstrates a retrieval-augmented generation flow wired for governance.

## What it shows

- In-memory Qdrant vector store populated with OP-Observe knowledge base snippets.
- Deterministic embedder to keep tests fast and offline-friendly.
- Guardrails layer with an LLM-Critic style reviewer that enforces evidence citation.
- Lightweight evaluation metrics (recall/precision) derived from retrieval hits.

## Run the demo

```bash
python -m templates.guarded_rag_minimal.pipeline
```

The script prints the answer, guard verdict, and eval metrics for a sample question.

## Extend it

- Swap the deterministic embedder for OpenLIT or production embeddings.
- Replace the rule-based critic with the Guardrails Hub LLM-Critic validator.
- Push evaluation metrics to Phoenix/OpenInference for longitudinal analysis.
