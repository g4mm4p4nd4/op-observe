from openai import OpenAI

client = OpenAI()

support_agent = client.beta.agents.create(
    name="support-agent",
    instructions="Help our customers",
    model="gpt-4o-mini",
    tools=[
        {"type": "retrieval"},
        {"type": "function", "function": {"name": "lookup_order"}},
    ],
)

settings = {"mcp_server": "https://mcp.local/api"}
