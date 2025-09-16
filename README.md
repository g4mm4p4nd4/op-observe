# OP-Observe Telemetry Utilities

This repository provides lightweight helpers for wiring correlated tracing and logging
pipelines. The implementation is intentionally self-contained to avoid external
dependencies and demonstrates how to forward structured log records to a Grafana Loki
endpoint while emitting trace spans that can be ingested by Tempo-compatible systems.

## Running the tests

The test suite boots a local in-memory Loki-compatible HTTP server and validates that
logs carry trace and span identifiers that match the exported spans. Execute the tests
with the project sources on the `PYTHONPATH`:

```bash
PYTHONPATH=src pytest
```
