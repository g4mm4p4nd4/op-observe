"""Build Grafana dashboards for guardrail observability."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List


def _panel(panel_id: int, title: str, expr: str, panel_type: str = "timeseries") -> Dict[str, object]:
    return {
        "id": panel_id,
        "type": panel_type,
        "title": title,
        "datasource": {
            "type": "prometheus",
            "uid": "PROMETHEUS_DS",
        },
        "targets": [
            {
                "expr": expr,
                "refId": "A",
            }
        ],
    }


def build_guardrail_dashboard(title: str = "Guardrail & Evals Overview") -> Dict[str, object]:
    """Return a Grafana dashboard definition for guardrail metrics."""

    panels: List[Dict[str, object]] = [
        _panel(
            1,
            "Guardrail verdicts (rate)",
            'sum(rate(guardrail_verdict_total[5m])) by (verdict)',
        ),
        _panel(
            2,
            "LLM-Critic score",
            'avg(llm_critic_score)',
        ),
        _panel(
            3,
            "System latency p95",
            'histogram_quantile(0.95, sum(rate(system_latency_ms_bucket[5m])) by (le))',
        ),
    ]

    return {
        "title": title,
        "panels": panels,
        "uid": f"guardrail-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    }
