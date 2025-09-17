from __future__ import annotations

import textwrap

from agentic_radar.detectors.tools import ToolDetector


def test_tool_detector_identifies_multiple_tool_patterns(tmp_path) -> None:
    source = textwrap.dedent(
        """
        from langchain.tools import tool, Tool, BaseTool

        @tool
        def search(query: str) -> str:
            '''Search through a document index.'''
            return "ok"

        class MathHelper(BaseTool):
            description = "Perform arithmetic"

        custom = Tool(name="custom", func=lambda: None)


        def unrelated(value: int) -> int:
            return value
        """
    )
    path = tmp_path / "sample_tools.py"
    path.write_text(source, encoding="utf-8")

    findings = ToolDetector().scan_paths([path])
    finding_lookup = {finding.name: finding for finding in findings}

    assert {finding.definition_type for finding in findings} == {"function", "class", "assignment"}
    assert finding_lookup["search"].metadata["docstring"] == "Search through a document index."
    assert "BaseTool" in finding_lookup["MathHelper"].metadata["bases"]
    assert finding_lookup["custom"].metadata["call"].endswith("Tool")
    assert "unrelated" not in finding_lookup
