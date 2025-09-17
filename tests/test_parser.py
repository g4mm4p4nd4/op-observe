from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from op_observe.security import AgentGraphParser


@pytest.fixture(scope="module")
def parsed_graph():
    samples_root = Path(__file__).parent / "samples"
    parser = AgentGraphParser(samples_root)
    return parser.parse().as_dict()


def test_nodes_cover_supported_frameworks(parsed_graph):
    nodes = {node["id"]: node for node in parsed_graph["nodes"]}

    assert nodes["planner"]["type"] == "agent"
    assert nodes["search_tool"]["type"] == "tool"
    assert nodes["support-agent"]["framework"] == "openai"
    assert nodes["lookup_order"]["type"] == "tool"
    assert nodes["retrieval"]["type"] == "retriever"
    assert nodes["researcher"]["framework"] == "crewai"
    assert nodes["search"]["framework"] == "crewai"
    assert nodes["assistant"]["framework"] == "autogen"
    assert nodes["web_search"]["framework"] == "autogen"
    assert nodes["Orchestrator Agent"]["framework"] == "n8n"
    assert nodes["Vector Retriever"]["type"] == "retriever"


def test_edges_include_calls_and_data_flows(parsed_graph):
    edges = {(edge["source"], edge["target"], edge["kind"]) for edge in parsed_graph["edges"]}

    assert ("planner", "researcher", "call") in edges
    assert ("researcher", "search_tool", "call") in edges
    assert ("support-agent", "lookup_order", "call") in edges
    assert ("support-agent", "retrieval", "call") in edges
    assert ("researcher", "search", "call") in edges
    assert ("assistant", "web_search", "call") in edges
    assert ("Orchestrator Agent", "HTTP Tool", "data_flow") in edges
    assert ("HTTP Tool", "Vector Retriever", "data_flow") in edges


def test_mcp_endpoints_are_collected(parsed_graph):
    endpoints = {entry["endpoint"] for entry in parsed_graph["mcp_endpoints"]}

    assert "mcp://langgraph/tools/search" in endpoints
    assert "https://mcp.local/api" in endpoints
    assert "https://mcp.crew/internal" in endpoints
    assert "http://autogen.local/mcp" in endpoints
    assert "http://n8n.local:3000/mcp" in endpoints
