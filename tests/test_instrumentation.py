import asyncio

import pytest

from op_observe import (
    InMemoryOTLPCollector,
    StatusCode,
    instrument_langchain_tool,
    instrument_langgraph_node,
    reset_tracer_provider,
    set_tracer_provider,
)


@pytest.fixture()
def collector():
    collector = InMemoryOTLPCollector()
    set_tracer_provider(collector.tracer_provider)
    yield collector
    reset_tracer_provider()


def test_langchain_tool_emits_span_with_attributes(collector):
    @instrument_langchain_tool(tool_name="search", llm_model="gpt-test")
    def search_tool(query: str, limit: int = 3) -> str:
        return f"results for {query} (limit={limit})"

    output = search_tool("observability", limit=5)
    assert "observability" in output

    spans = collector.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.name == "LangChain.search"
    assert span.status == StatusCode.OK
    assert span.attributes["openinference.framework"] == "langchain"
    assert span.attributes["openinference.span.kind"] == "tool"
    assert span.attributes["openinference.tool.name"] == "search"
    assert span.attributes["openllmetry.llm.model"] == "gpt-test"
    assert "observability" in span.attributes["openinference.inputs"]["args"]
    assert "results for" in span.attributes["openinference.outputs"]


def test_langgraph_async_node_records_output(collector):
    @instrument_langgraph_node(node_name="planner", node_type="decision", llm_model="gpt-async")
    async def planner_node(goal: str) -> dict:
        await asyncio.sleep(0)
        return {"goal": goal, "status": "planned"}

    result = asyncio.run(planner_node("ship"))
    assert result["status"] == "planned"

    spans = collector.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.name == "LangGraph.planner"
    assert span.attributes["openinference.graph.node.name"] == "planner"
    assert span.attributes["openinference.graph.node.type"] == "decision"
    assert span.attributes["openllmetry.llm.model"] == "gpt-async"
    assert span.status == StatusCode.OK
    assert "planned" in span.attributes["openinference.outputs"]


def test_exception_marks_span_as_error(collector):
    @instrument_langchain_tool(tool_name="failing")
    def failing_tool() -> None:
        raise ValueError("tool failure")

    with pytest.raises(ValueError):
        failing_tool()

    spans = collector.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.status == StatusCode.ERROR
    assert span.attributes["error"] is True
    assert span.attributes["error.type"] == "ValueError"
    assert "tool failure" in span.attributes["error.message"]
    assert span.attributes["openinference.tool.name"] == "failing"
