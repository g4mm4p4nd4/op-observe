"""Phoenix dashboard definitions for OP-Observe."""

from .models import DashboardSpec, PanelSpec
from .phoenix import default_dashboards, iter_dashboard_dicts

__all__ = ["DashboardSpec", "PanelSpec", "default_dashboards", "iter_dashboard_dicts"]
