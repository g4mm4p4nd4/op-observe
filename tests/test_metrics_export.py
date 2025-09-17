from datetime import datetime

from op_observe.telemetry import (
    ClickHouseExporterConfig,
    MetricsRegistry,
    PrometheusExporterConfig,
    build_collector_config,
    build_guardrail_dashboard,
)


def test_collector_config_includes_prometheus_and_clickhouse():
    config = build_collector_config(
        PrometheusExporterConfig(endpoint="127.0.0.1", port=9000),
        ClickHouseExporterConfig(table="guard_metrics"),
    )

    assert "receivers" in config
    assert config["receivers"]["otlp"]["protocols"] == {"grpc": {}, "http": {}}

    exporters = config["exporters"]
    assert "prometheus" in exporters
    assert exporters["prometheus"]["endpoint"] == "127.0.0.1:9000"
    assert "clickhouse" in exporters
    assert exporters["clickhouse"]["table"] == "guard_metrics"

    pipeline = config["service"]["pipelines"]["metrics"]
    assert pipeline["receivers"] == ["otlp"]
    assert "prometheus" in pipeline["exporters"]
    assert "clickhouse" in pipeline["exporters"]


class _FixedClock:
    def __init__(self):
        self._now = datetime(2024, 1, 1)

    def __call__(self):
        return self._now


def test_registry_exports_prometheus_text():
    clock = _FixedClock()
    registry = MetricsRegistry(now=clock)
    registry.record_guardrail_verdict("pass")
    registry.record_guardrail_verdict("fail", weight=2)
    registry.record_llm_critic_score("customer_onboarding", 0.87)
    registry.observe_latency(120, stage="overall")
    registry.observe_latency(40, stage="retrieval")
    registry.observe_latency(80, stage="retrieval")

    text = registry.as_prometheus()

    assert "# TYPE guardrail_verdict_total counter" in text
    assert 'guardrail_verdict_total{verdict="fail"} 2.0' in text
    assert 'llm_critic_score{scenario="customer_onboarding"} 0.87' in text
    assert 'system_latency_ms_bucket{le="+Inf",stage="overall"} 1' in text
    assert 'system_latency_ms_count{stage="retrieval"} 2' in text


def test_registry_exports_clickhouse_rows():
    clock = _FixedClock()
    registry = MetricsRegistry(now=clock)
    registry.record_guardrail_verdict("pass")
    registry.record_llm_critic_score("triage", 0.6)
    registry.observe_latency(300, stage="overall")

    rows = registry.as_clickhouse_rows()
    histogram_entries = len(registry.system_latency_ms.buckets) + 1  # +Inf bucket
    assert len(rows) == 1 + 1 + histogram_entries + 2

    counter = next(row for row in rows if row["metric"] == "guardrail_verdict_total")
    assert counter["type"] == "counter"
    assert counter["labels"] == {"verdict": "pass"}

    bucket_rows = [r for r in rows if r["metric"].endswith("_bucket")]
    assert any(row["labels"]["le"] == "+Inf" for row in bucket_rows)
    for row in rows:
        assert row["timestamp"] == datetime(2024, 1, 1).isoformat()


def test_grafana_dashboard_has_expected_panels():
    dashboard = build_guardrail_dashboard()
    assert dashboard["title"] == "Guardrail & Evals Overview"
    panel_titles = [panel["title"] for panel in dashboard["panels"]]
    assert "Guardrail verdicts (rate)" in panel_titles
    assert "LLM-Critic score" in panel_titles
    assert "System latency p95" in panel_titles
    assert dashboard["uid"].startswith("guardrail-")
