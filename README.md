# OP-Observe Telemetry Pipeline

This repository demonstrates how to forward application traces and metrics to
Prometheus and ClickHouse via the OpenTelemetry Collector. The integration is
used by the OP-Observe platform to stream guardrail and evaluation telemetry to
self-hosted analytics backends.

## Components

* **Python SDK** (`src/op_observe`): helper utilities that configure OTLP/HTTP
  exporters for traces and metrics.
* **OpenTelemetry Collector** (`otel-collector-config.yaml`): collector
  configuration that fans telemetry out to Prometheus and ClickHouse.
* **Docker Compose** (`deploy/docker-compose.metrics.yml`): local integration
  environment with Prometheus, ClickHouse, and the collector.
* **Integration Tests** (`tests/integration`): pytest-based tests that boot the
  compose environment, emit sample spans/metrics, and verify that both sinks
  received data.

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `OTEL_SERVICE_NAME` | `op-observe-service` | Name of the service recorded in spans/metrics. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4318` | Base OTLP endpoint used by the Python SDK. |
| `OTEL_EXPORTER_OTLP_HEADERS` | _unset_ | Optional comma-separated headers (`key=value`). |
| `OTEL_EXPORTER_OTLP_INSECURE` | `true` | When `true`, HTTP is used without TLS. |
| `OTEL_METRIC_EXPORT_INTERVAL` | `5` | Metric export interval in seconds. |
| `CLICKHOUSE_ENDPOINT` | `tcp://clickhouse:9000` | Network endpoint for the ClickHouse exporter. |
| `CLICKHOUSE_DATABASE` | `otel` | Database used by the ClickHouse exporter. |
| `CLICKHOUSE_USERNAME` | `default` | ClickHouse user for writes. |
| `CLICKHOUSE_PASSWORD` | _unset_ | ClickHouse password. |
| `CLICKHOUSE_TTL_DAYS` | `3` | TTL configuration for ClickHouse tables. |
| `OTEL_COLLECTOR_OTLP_GRPC_ENDPOINT` | `0.0.0.0:4317` | Collector gRPC endpoint (exposed for completeness). |
| `OTEL_COLLECTOR_OTLP_HTTP_ENDPOINT` | `0.0.0.0:4318` | Collector HTTP endpoint. |
| `OTEL_PROMETHEUS_EXPORTER_ENDPOINT` | `0.0.0.0:9464` | Address where the Prometheus exporter listens. |
| `OTEL_PROMETHEUS_NAMESPACE` | `opobserve` | Metric namespace for the Prometheus exporter. |

The collector configuration supports additional overrides using standard
OpenTelemetry Collector environment variable interpolation. See
`otel-collector-config.yaml` for the complete list.

## Running Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

# Emit telemetry to a running collector
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"
python -c "from op_observe.telemetry import generate_sample_telemetry; generate_sample_telemetry()"
```

To start the local observability stack:

```bash
export CLICKHOUSE_PASSWORD=""
docker compose -f deploy/docker-compose.metrics.yml up -d
```

After the stack is up, run the sample telemetry generator as shown above. You
can then query Prometheus (`http://localhost:9090`) and ClickHouse (`http://localhost:8123`)
to inspect the results.

## Integration Tests

Integration tests require Docker. They automatically skip if Docker is not
available.

```bash
pytest -m integration
```

The tests boot the docker-compose environment, publish sample telemetry, and
validate that Prometheus and ClickHouse both receive data.
