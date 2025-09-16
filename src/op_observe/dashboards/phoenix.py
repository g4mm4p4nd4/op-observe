"""Default Phoenix dashboard definitions."""
from __future__ import annotations

from typing import Iterable, List

from .models import DashboardSpec, PanelSpec


TRACE_OVERVIEW_DASHBOARD = DashboardSpec(
    title="Phoenix Trace Observatory",
    description=(
        "Operational overview of OpenInference traces exported from the telemetry "
        "pipeline into Phoenix. Panels assume metrics were written to the Phoenix "
        "Postgres warehouse via the collector."
    ),
    tags=("phoenix", "traces", "opobserve"),
    panels=[
        PanelSpec(
            title="Trace Throughput",
            description="Requests per minute for the selected dataset",
            query=(
                "SELECT $__timeGroupAlias(start_time, '1 minute') AS time, "
                "COUNT(*) AS requests_per_minute "
                "FROM phoenix.traces "
                "WHERE dataset_name = $dataset AND $__timeFilter(start_time) "
                "GROUP BY 1 ORDER BY 1"
            ),
            visualization="time_series",
            unit="req/min",
        ),
        PanelSpec(
            title="LLM Latency (p95)",
            description="95th percentile span latency grouped by operation",
            query=(
                "SELECT operation_name, percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) "
                "AS p95_latency_ms FROM phoenix.spans "
                "WHERE dataset_name = $dataset AND $__timeFilter(start_time) "
                "GROUP BY operation_name ORDER BY p95_latency_ms DESC"
            ),
            visualization="bar",
            unit="ms",
        ),
        PanelSpec(
            title="Guardrail Verdict Rate",
            description="Share of traces flagged by guardrail verdict attributes",
            query=(
                "SELECT $__timeGroupAlias(start_time, '5 minutes') AS time, "
                "AVG(CASE WHEN attributes->>'guardrail.verdict' = 'fail' THEN 1 ELSE 0 END) * 100 AS failure_rate "
                "FROM phoenix.traces "
                "WHERE dataset_name = $dataset AND attributes ? 'guardrail.verdict' "
                "AND $__timeFilter(start_time) GROUP BY 1 ORDER BY 1"
            ),
            visualization="time_series",
            unit="percent",
        ),
    ],
)

EVALUATION_MONITOR_DASHBOARD = DashboardSpec(
    title="Phoenix Evaluation Monitor",
    description="Aggregated evaluation metrics as emitted by the exporter.",
    tags=("phoenix", "evaluations", "opobserve"),
    panels=[
        PanelSpec(
            title="Evaluation Scores",
            description="Distribution of evaluation scores per evaluation name",
            query=(
                "SELECT evaluation_name, percentile_cont(0.5) WITHIN GROUP (ORDER BY score) AS median_score, "
                "percentile_cont(0.9) WITHIN GROUP (ORDER BY score) AS p90_score "
                "FROM phoenix.evaluations WHERE dataset_id = $dataset_id GROUP BY evaluation_name"
            ),
            visualization="table",
        ),
        PanelSpec(
            title="LLM-Critic Trend",
            description="Time series of LLM-Critic scores from evaluation metadata",
            query=(
                "SELECT $__timeGroupAlias(timestamp, '15 minutes') AS time, AVG(results->'metrics'->>'critic_score')::float AS critic_score "
                "FROM phoenix.evaluation_results WHERE evaluation_name = 'llm_critic' "
                "AND dataset_id = $dataset_id AND $__timeFilter(timestamp) GROUP BY 1 ORDER BY 1"
            ),
            visualization="time_series",
        ),
        PanelSpec(
            title="Evaluation Failures",
            description="Count of failed evaluations grouped by failure reason",
            query=(
                "SELECT metadata->>'failure_reason' AS reason, COUNT(*) AS failures "
                "FROM phoenix.evaluation_results WHERE dataset_id = $dataset_id "
                "AND metadata ? 'failure_reason' GROUP BY reason ORDER BY failures DESC"
            ),
            visualization="bar",
        ),
    ],
)


def default_dashboards() -> List[DashboardSpec]:
    """Return the default dashboard specifications for Phoenix."""

    return [TRACE_OVERVIEW_DASHBOARD, EVALUATION_MONITOR_DASHBOARD]


def iter_dashboard_dicts() -> Iterable[dict]:
    """Yield dashboard payloads as dictionaries."""

    for dashboard in default_dashboards():
        yield dashboard.to_dict()
