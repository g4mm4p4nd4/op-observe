"""Dashboard specification models for Phoenix UI."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence


@dataclass(slots=True)
class PanelSpec:
    """Represents a single Phoenix dashboard panel."""

    title: str
    description: str
    query: str
    visualization: str = "time_series"
    unit: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "title": self.title,
            "description": self.description,
            "query": self.query,
            "visualization": self.visualization,
        }
        if self.unit:
            payload["unit"] = self.unit
        return payload


@dataclass(slots=True)
class DashboardSpec:
    """Collection of panels describing a Phoenix dashboard."""

    title: str
    description: str
    panels: List[PanelSpec] = field(default_factory=list)
    tags: Sequence[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "title": self.title,
            "description": self.description,
            "tags": list(self.tags),
            "panels": [panel.to_dict() for panel in self.panels],
        }
