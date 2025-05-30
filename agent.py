from langgraph.prebuilt import create_react_agent
from models import llm
from prompts import SYSTEM_MESSAGE, PROPER_NOUN_SUFFIX
from tools import get_sql_tools, create_proper_noun_tool

def create_agent(use_proper_noun_tool=False):
    """Create an agent with the specified configuration."""
    tools = get_sql_tools()
    system_prompt = SYSTEM_MESSAGE
    
    if use_proper_noun_tool:
        tools.append(create_proper_noun_tool())
        system_prompt = f"{SYSTEM_MESSAGE}\n\n{PROPER_NOUN_SUFFIX}"
    
    return create_react_agent(llm, tools, prompt=system_prompt)

def execute_agent(agent, question):
    """Execute the agent with a given question."""
    for step in agent.stream(
        {"messages": [{"role": "user", "content": question}]},
        stream_mode="values",
    ):
        step["messages"][-1].pretty_print() 