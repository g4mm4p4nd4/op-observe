from crewai import Agent, Crew, Task
from crewai_tools import Tool

search_tool = Tool(name="search", description="Search the web", url="https://mcp.crew/internal")

researcher = Agent(
    name="researcher",
    role="Collects intelligence",
    goal="Find useful data",
    tools=[search_tool],
)

task = Task(description="Research market", agent=researcher)

crew = Crew(agents=[researcher], tasks=[task])
