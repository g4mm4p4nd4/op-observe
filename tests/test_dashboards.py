from __future__ import annotations

from op_observe.dashboards import phoenix


def test_default_dashboards_structure() -> None:
    dashboards = phoenix.default_dashboards()
    assert len(dashboards) == 2

    overview, evaluation = dashboards
    assert overview.title == "Phoenix Trace Observatory"
    assert len(overview.panels) == 3
    assert overview.panels[0].query.startswith("SELECT $__timeGroupAlias")

    evaluation_queries = [panel.query for panel in evaluation.panels]
    assert any("evaluation_results" in query for query in evaluation_queries)
    assert evaluation.title == "Phoenix Evaluation Monitor"


def test_iter_dashboard_dicts_serialises() -> None:
    payloads = list(phoenix.iter_dashboard_dicts())
    assert len(payloads) == 2
    first_panel = payloads[0]["panels"][0]
    assert {"title", "query"}.issubset(first_panel.keys())
