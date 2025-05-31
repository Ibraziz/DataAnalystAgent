# enhanced_agent.py - Enhanced version with better result capture
from langgraph.prebuilt import create_react_agent
from models import llm
from prompts import SYSTEM_MESSAGE, PROPER_NOUN_SUFFIX
from tools import get_sql_tools, create_proper_noun_tool
from langchain_core.messages import HumanMessage, AIMessage

def create_agent(use_proper_noun_tool=False):
    """Create an agent with the specified configuration."""
    tools = get_sql_tools()
    system_prompt = SYSTEM_MESSAGE
    
    if use_proper_noun_tool:
        tools.append(create_proper_noun_tool())
        system_prompt = f"{SYSTEM_MESSAGE}\n\n{PROPER_NOUN_SUFFIX}"
    
    return create_react_agent(llm, tools, prompt=system_prompt)

def execute_agent(agent, question):
    """Execute the agent with a given question and return structured results."""
    messages = []
    
    # Collect all messages from the stream
    for step in agent.stream(
        {"messages": [{"role": "user", "content": question}]},
        stream_mode="values",
    ):
        if "messages" in step:
            messages.extend(step["messages"])
            # Print for debugging (optional)
            if step["messages"]:
                step["messages"][-1].pretty_print()
    
    return messages

def execute_agent_with_results(agent, question):
    """Execute agent and return structured results for web interface."""
    try:
        # Execute the agent
        messages = execute_agent(agent, question)
        
        # Extract the final AI response
        final_response = ""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                final_response = msg.content
                break
        
        # Parse the response to extract structured data
        result = {
            'sql': extract_sql_query(final_response),
            'data': extract_data_table(final_response),
            'visualizations': extract_visualizations(final_response),
            'full_response': final_response
        }
        
        return result
        
    except Exception as e:
        return {
            'error': str(e),
            'sql': '',
            'data': [],
            'visualizations': {},
            'full_response': ''
        }

def extract_sql_query(text):
    """Extract SQL query from agent response."""
    import re
    
    # Look for SQL code blocks
    sql_patterns = [
        r'```sql\n(.*?)\n```',
        r'```SQL\n(.*?)\n```',
        r'```\n(SELECT.*?);?\n```',
        r'(SELECT.*?);'
    ]
    
    for pattern in sql_patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return ""

def extract_data_table(text):
    """Extract tabular data from agent response."""
    import re
    
    # Look for markdown tables
    table_pattern = r'\|.*?\|(?:\n\|.*?\|)+'
    match = re.search(table_pattern, text)
    
    if not match:
        return []
    
    table_text = match.group(0)
    lines = table_text.strip().split('\n')
    
    if len(lines) < 3:  # Need at least header, separator, and one data row
        return []
    
    # Parse headers
    headers = [h.strip() for h in lines[0].split('|')[1:-1]]
    
    # Parse data rows (skip header and separator)
    data = []
    for line in lines[2:]:
        if '|' in line:
            values = [v.strip() for v in line.split('|')[1:-1]]
            if len(values) == len(headers):
                row = {}
                for i, header in enumerate(headers):
                    value = values[i]
                    # Try to convert to appropriate data type
                    try:
                        # Check if it's a number
                        if '.' in value and value.replace('.', '').replace('-', '').isdigit():
                            value = float(value)
                        elif value.replace('-', '').isdigit():
                            value = int(value)
                        elif value.lower() in ['true', 'false']:
                            value = value.lower() == 'true'
                    except (ValueError, AttributeError):
                        pass  # Keep as string
                    
                    row[header] = value
                data.append(row)
    
    return data

def extract_visualizations(text):
    """Extract visualization recommendations from agent response."""
    import re
    
    visualizations = {}
    
    # Look for the visualization section
    viz_pattern = r'\*\*RECOMMENDED VISUALIZATIONS:\*\*\s*\n(.*?)(?=\n\n|\Z)'
    viz_match = re.search(viz_pattern, text, re.DOTALL)
    
    if not viz_match:
        # Try alternative patterns
        viz_pattern = r'RECOMMENDED VISUALIZATIONS:\s*\n(.*?)(?=\n\n|\Z)'
        viz_match = re.search(viz_pattern, text, re.DOTALL)
    
    if viz_match:
        viz_text = viz_match.group(1)
        
        # Extract individual recommendations
        patterns = {
            'primary': r'\*\*Primary:\*\*\s*(.*?)(?=\n\s*[-*]|\Z)',
            'alternative': r'\*\*Alternative:\*\*\s*(.*?)(?=\n\s*[-*]|\Z)',
            'consider': r'\*\*Consider Also:\*\*\s*(.*?)(?=\n\s*[-*]|\Z)'
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, viz_text, re.DOTALL | re.IGNORECASE)
            if match:
                visualizations[key] = match.group(1).strip()
    
    return visualizations

# Backwards compatibility
def execute_agent_original(agent, question):
    """Original execute_agent function for backwards compatibility."""
    for step in agent.stream(
        {"messages": [{"role": "user", "content": question}]},
        stream_mode="values",
    ):
        step["messages"][-1].pretty_print()