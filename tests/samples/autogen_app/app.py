from autogen import AssistantAgent, UserProxyAgent, tool


@tool
def web_search(query: str) -> str:
    """Search the web."""
    return "results"


def build_agents():
    assistant = AssistantAgent(name="assistant", tools=[web_search])
    user = UserProxyAgent(name="user")
    assistant_config = {"mcp_endpoint": "http://autogen.local/mcp"}
    return assistant, user, assistant_config
