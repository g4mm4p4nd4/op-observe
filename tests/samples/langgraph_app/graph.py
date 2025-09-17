from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

search_tool = object()

builder = StateGraph()
builder.add_node("planner", lambda state: state)
builder.add_node("researcher", lambda state: state)

mcp_server = "mcp://langgraph/tools/search"

tool_node = ToolNode("search_tool", tool=search_tool)
builder.add_node("search_tool", tool_node)

builder.add_edge("planner", "researcher")
builder.add_edge("researcher", "search_tool")
