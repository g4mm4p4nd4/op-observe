"""LangGraph-based agent workflow used by the agentic security template."""
from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class AgentState(TypedDict, total=False):
    """State tracked across LangGraph nodes."""

    question: str
    plan: str
    tool_input: str
    tool_output: str
    answer: str


def planner(state: AgentState) -> AgentState:
    """Plan the work that should be carried out by downstream nodes."""

    question = state["question"]
    plan = f"Search project security controls related to: {question}"
    return {
        "plan": plan,
        "tool_input": f"controls for {question}",
    }


def filesystem_writer(query: str) -> str:
    """A toy tool that simulates writing data to the local file system."""

    return f"[filesystem] created evidence file for query: {query}"


def tool_executor(state: AgentState) -> AgentState:
    """Invoke the risky tool without additional validation to simulate a finding."""

    tool_input = state["tool_input"]
    return {
        "tool_output": filesystem_writer(tool_input),
    }


def responder(state: AgentState) -> AgentState:
    """Compose the final response that would be sent back to the caller."""

    question = state["question"]
    tool_output = state["tool_output"]
    answer = (
        "Audit completed. {tool_output}. Recommend enabling guardrails and validating "
        "filesystem writes for '{question}'."
    ).format(tool_output=tool_output, question=question)
    return {"answer": answer}


def build_agentic_security_graph() -> StateGraph:
    """Create and compile the LangGraph workflow used in the demo."""

    graph = StateGraph(AgentState)
    graph.add_node("planner", planner)
    graph.add_node("tool_executor", tool_executor)
    graph.add_node("responder", responder)
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "tool_executor")
    graph.add_edge("tool_executor", "responder")
    graph.add_edge("responder", END)
    return graph


# Metadata exported for the radar scanner. In a production system this information would
# be derived automatically, but for the template we provide it explicitly so tests can run
# without external scanners.
SECURITY_METADATA = {
    "workflow": {
        "nodes": [
            {
                "id": "planner",
                "kind": "llm",
                "description": "LLM planner that orchestrates tool usage",
                "outputs": ["plan", "tool_input"],
            },
            {
                "id": "tool_executor",
                "kind": "tool",
                "description": "Calls filesystem_writer without sanitising inputs",
                "tool": "filesystem_writer",
                "permissions": ["write"],
            },
            {
                "id": "responder",
                "kind": "llm",
                "description": "Summarises actions and advisories",
                "outputs": ["answer"],
            },
        ],
        "edges": [
            {"source": START, "target": "planner"},
            {"source": "planner", "target": "tool_executor"},
            {"source": "tool_executor", "target": "responder"},
            {"source": "responder", "target": END},
        ],
    },
    "tools": [
        {
            "name": "filesystem_writer",
            "origin": "local",
            "description": "Writes evidence to disk without path allow-listing",
            "permissions": ["write"],
            "input_validation": False,
        }
    ],
    "mcp_servers": [
        {
            "name": "local_fs",
            "uri": "mcp://localhost/filesystem",
            "capabilities": ["read", "write"],
            "auth": "none",
        }
    ],
    "dependencies": [
        {
            "name": "filesystem-writer-plugin",
            "version": "0.1.0",
            "licenses": ["Apache-2.0"],
        }
    ],
}


def run_demo(question: str) -> AgentState:
    """Execute the compiled graph and return the final state for demonstration."""

    graph = build_agentic_security_graph().compile()
    result = graph.invoke({"question": question})
    return result


__all__ = [
    "AgentState",
    "SECURITY_METADATA",
    "build_agentic_security_graph",
    "run_demo",
]
