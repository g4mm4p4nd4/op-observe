from __future__ import annotations

import json

from agentic_radar.detectors.mcp import MCPServerDetector


def test_mcp_detector_parses_python_and_config(tmp_path) -> None:
    python_source = """
from mcp import MCPClient
import mcp

client = MCPClient("mcp://inventory", capabilities=["search", "store"])


async def connect() -> None:
    return await mcp.Client.connect(uri="https://mcp.internal/api", capabilities=["query"])
"""
    py_path = tmp_path / "app.py"
    py_path.write_text(python_source, encoding="utf-8")

    config = {
        "agents": [
            {
                "name": "rag-agent",
                "mcp": {
                    "endpoint": "https://mcp.example/api",
                    "capabilities": ["ingest"],
                },
            }
        ]
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    detector = MCPServerDetector()
    findings = detector.scan_paths([tmp_path])

    endpoints = {finding.endpoint for finding in findings if finding.endpoint}
    assert "mcp://inventory" in endpoints
    assert "https://mcp.internal/api" in endpoints
    assert "https://mcp.example/api" in endpoints

    client_call = next(f for f in findings if f.metadata.get("call") == "MCPClient")
    assert set(client_call.metadata.get("capabilities", [])) == {"search", "store"}

    config_finding = next(f for f in findings if f.endpoint == "https://mcp.example/api")
    assert config_finding.metadata.get("capabilities") == ["ingest"]
