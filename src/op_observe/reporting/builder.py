"""Security report builder entry points."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .html_renderer import ReportHtmlRenderer, report_to_serializable
from .models import AgentSecurityReport


@dataclass
class ReportArtifacts:
    """Paths to the generated report artifacts."""

    html_path: Path
    json_path: Path


class ReportBuilder:
    """Persist agent security reports as HTML + JSON bundles."""

    def __init__(self, renderer: Optional[ReportHtmlRenderer] = None) -> None:
        self._renderer = renderer or ReportHtmlRenderer()

    def build(
        self,
        report: AgentSecurityReport,
        output_dir: Path,
        html_filename: str = "security_report.html",
        json_filename: str = "security_report.json",
    ) -> ReportArtifacts:
        """Render and persist a report bundle.

        Args:
            report: The populated agentic security report model.
            output_dir: Directory where the files should be written. It will be
                created if it does not already exist.
            html_filename: Name of the generated HTML file.
            json_filename: Name of the generated JSON file.
        Returns:
            A :class:`ReportArtifacts` instance pointing to the written files.
        """

        output_dir.mkdir(parents=True, exist_ok=True)

        html_content = self._renderer.render(report)
        html_path = output_dir / html_filename
        html_path.write_text(html_content, encoding="utf-8")

        serializable = report_to_serializable(report)
        json_path = output_dir / json_filename
        with json_path.open("w", encoding="utf-8") as handle:
            json.dump(serializable, handle, indent=2)
            handle.write("\n")

        return ReportArtifacts(html_path=html_path, json_path=json_path)

