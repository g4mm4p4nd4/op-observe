# OpenTelemetry Collector Configuration for OP-Observe

This module delivers a hardened OpenTelemetry Collector configuration that fans in OTLP telemetry and fans it out to Prometheus, ClickHouse, Phoenix, and Loki. The configuration embraces environment-variable overrides for all externally facing endpoints and credentials so the collector can run across local, staging, and production footprints without edits to the baseline YAML.

## Layout

```
otel_collector/
├── README.md                     # This file
├── config/collector.yaml         # Default collector configuration
├── docker-compose.yaml           # Reference stack for local validation
├── prometheus/prometheus.yml     # Prometheus scrape configuration
└── loki/config.yaml              # Loki single-binary configuration
```

## Environment Variables

Key overrides exposed by `collector.yaml`:

| Variable | Purpose | Default |
| --- | --- | --- |
| `OTEL_RECEIVER_OTLP_GRPC_ENDPOINT` | OTLP gRPC listener | `0.0.0.0:4317` |
| `OTEL_RECEIVER_OTLP_HTTP_ENDPOINT` | OTLP HTTP listener | `0.0.0.0:4318` |
| `OTEL_RESOURCE_ENVIRONMENT` | Resource attribute identifying the environment | `local` |
| `PROMETHEUS_EXPORTER_ENDPOINT` | Prometheus scrape endpoint exposed by the collector | `0.0.0.0:8889` |
| `PROMETHEUS_REMOTE_WRITE_ENDPOINT` | Remote write target for metrics | `http://prometheus:9090/api/v1/write` |
| `PROMETHEUS_REMOTE_WRITE_AUTH` | Authorization header for remote write | *(empty)* |
| `CLICKHOUSE_ENDPOINT` | ClickHouse HTTP endpoint | `http://clickhouse:8123` |
| `CLICKHOUSE_DATABASE` | Database name used by the ClickHouse exporter | `otel` |
| `CLICKHOUSE_USERNAME`/`CLICKHOUSE_PASSWORD` | Credentials for ClickHouse | `default` / *(empty)* |
| `PHOENIX_OTLP_ENDPOINT` | Phoenix OTLP HTTP endpoint | `http://phoenix:6006` |
| `PHOENIX_API_KEY` | Phoenix API key header | *(empty)* |
| `LOKI_ENDPOINT` | Loki push endpoint | `http://loki:3100/loki/api/v1/push` |
| `LOKI_TENANT_ID` | Loki tenant header | `default` |

Additional knobs exist for batch sizes, memory limits, TLS behaviour, and logging verbosity. Refer to the YAML file for the complete catalogue.

## Reference Docker Compose Stack

The `docker-compose.yaml` file spins up:

* `otel-collector`: OpenTelemetry Collector Contrib image using the provided configuration
* `prometheus`: Scrapes the collector's Prometheus exporter for metrics
* `clickhouse`: Receives OTEL traces/metrics/logs via the ClickHouse exporter
* `phoenix`: Runs the Arize Phoenix observability UI (receives traces over OTLP HTTP)
* `loki`: Ingests logs via the Loki exporter

### Quickstart

```bash
docker compose -f otel_collector/docker-compose.yaml up -d
python tests/scripts/push_sample_telemetry.py --endpoint http://localhost:4318
```

Phoenix will be available at http://localhost:6006. Prometheus will be available at http://localhost:9090. Loki exposes its API at http://localhost:3100.

### Shutdown

```bash
docker compose -f otel_collector/docker-compose.yaml down -v
```

## Automated Verification

Two pytest suites are provided:

1. `tests/test_otel_collector_config.py` validates the structure of `collector.yaml`.
2. `tests/integration/test_otel_collector_docker.py` (opt-in via `OP_OBSERVE_RUN_DOCKER_TESTS=1`) boots the Docker Compose stack and sends sample traces/metrics/logs to verify end-to-end delivery.

Run them with:

```bash
pytest
OP_OBSERVE_RUN_DOCKER_TESTS=1 pytest tests/integration/test_otel_collector_docker.py
```

Both tests keep the repository's baseline files untouched as required.
