# Data Analyst Agent - Clean structured output version
from langgraph.prebuilt import create_react_agent
from models import llm, db, structured_llm, get_database_connection
from prompts import SYSTEM_MESSAGE, PROPER_NOUN_SUFFIX
from tools import get_sql_tools, create_proper_noun_tool
from langchain_core.messages import AIMessage
from schemas import QueryResult
import json
import re

def create_agent(use_proper_noun_tool=False, database_name=None):
    """Create an agent with the specified configuration."""
    # Get the appropriate database connection
    if database_name:
        agent_db = get_database_connection(database_name)
    else:
        agent_db = db
    
    tools = get_sql_tools(agent_db)
    system_prompt = SYSTEM_MESSAGE
    
    if use_proper_noun_tool:
        tools.append(create_proper_noun_tool(agent_db))
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

def execute_agent_structured(agent, question):
    """Execute agent and get structured JSON output directly from LLM."""
    try:
        # First, let the agent explore the database and understand the question
        messages = execute_agent(agent, question)
        
        # Extract the final AI response
        agent_response = None
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                agent_response = msg.content
                break
        
        if not agent_response:
            return {
                'query': '',
                'description': 'No response generated'
            }
        
        # Now ask the structured LLM to provide the final SQL query and description
        structured_prompt = f"""
        Based on the database exploration and analysis below, provide a final SQL query and description in JSON format.
        
        Original question: {question}
        
        Agent analysis: {agent_response}
        
        Please extract or generate the most appropriate SQL query to answer the original question, and provide a clear description.
        Your response must be in JSON format with two fields:
        - "query": The final SQL query to execute (should be a valid SQL SELECT statement)
        - "description": A clear description of what the query does and what results it returns
        """
        
        # Get structured output from LLM
        structured_result = structured_llm.invoke(structured_prompt)
        
        return {
            'query': structured_result.query,
            'description': structured_result.description
        }
        
    except Exception as e:
        return {
            'query': '',
            'description': f'Error occurred: {str(e)}'
        }

def execute_agent_with_results(agent, question, database_connection=None):
    """Execute agent and return clean structured results with SQL, description, and data."""
    try:
        # First, let the agent explore the database and generate the query
        messages = execute_agent(agent, question)
        
        # Extract SQL query, data, and description from the agent's messages
        sql_query = ""
        data = []
        description = ""
        
        # Look through messages to find SQL query and results
        for msg in messages:
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                # Look for SQL query tool calls
                for tool_call in msg.tool_calls:
                    if tool_call.get('name') == 'sql_db_query' and 'query' in tool_call.get('args', {}):
                        sql_query = tool_call['args']['query']
            elif hasattr(msg, 'name') and msg.name == 'sql_db_query':
                # This is a tool result message with query results
                try:
                    # Parse the results - they come as a string representation of list of tuples
                    import ast
                    parsed_result = ast.literal_eval(msg.content)
                    if isinstance(parsed_result, list):
                        # Convert to list of dictionaries
                        column_names = extract_column_names(sql_query) if sql_query else []
                        data = []
                        for row in parsed_result:
                            if isinstance(row, (list, tuple)) and column_names:
                                row_dict = {}
                                for i, col_name in enumerate(column_names):
                                    if i < len(row):
                                        row_dict[col_name] = row[i]
                                data.append(row_dict)
                            elif isinstance(row, dict):
                                data.append(row)
                        
                        # If no column names found, create generic ones
                        if not column_names and data and isinstance(parsed_result[0], (list, tuple)):
                            column_names = [f'Column_{i+1}' for i in range(len(parsed_result[0]))]
                            data = []
                            for row in parsed_result:
                                row_dict = {}
                                for i, col_name in enumerate(column_names):
                                    if i < len(row):
                                        row_dict[col_name] = row[i]
                                data.append(row_dict)
                except (ValueError, SyntaxError):
                    pass
            elif isinstance(msg, AIMessage) and not hasattr(msg, 'tool_calls'):
                # This is the final AI response
                description = msg.content
          # If no data was extracted from tool messages but we have a SQL query, try executing it
        if not data and sql_query:
            data = execute_sql_query(sql_query, database_connection)
          # Extract description from final AI message if we don't have one
        if not description:
            for msg in reversed(messages):
                if isinstance(msg, AIMessage) and not hasattr(msg, 'tool_calls'):
                    description = msg.content
                    break
        
        # If still no description, look for any AI message content
        if not description:
            for msg in reversed(messages):
                if isinstance(msg, AIMessage) and msg.content.strip():
                    description = msg.content
                    break
        
        return {
            'sql': sql_query,
            'description': description,
            'data': data
        }
        
    except Exception as e:
        return {
            'sql': '',
            'description': f'Error occurred: {str(e)}',
            'data': []
        }

def extract_sql_query(text):
    """Extract SQL query from agent response."""
    # Look for SQL code blocks first
    sql_patterns = [
        r'```sql\s*\n(.*?)\n```',
        r'```SQL\s*\n(.*?)\n```',
        r'```\s*\n(SELECT.*?)\n```',
    ]
    
    for pattern in sql_patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            query = match.group(1).strip()
            # Clean up the query
            query = re.sub(r'["\',\s]*$', '', query)  # Remove trailing quotes and commas
            if query.endswith(';'):
                query = query[:-1]
            return query
    
    # Look for JSON format query
    json_pattern = r'"query":\s*"(.*?)"'
    match = re.search(json_pattern, text, re.DOTALL)
    if match:
        query = match.group(1).strip()
        # Clean up escaped characters and extra quotes
        query = query.replace('\\"', '"').replace('\\n', ' ')
        query = re.sub(r'["\',\s]*$', '', query)  # Remove trailing quotes and commas
        if query.endswith(';'):
            query = query[:-1]
        return query
    
    # Look for plain SQL statements
    plain_sql_pattern = r'(SELECT\s+.*?(?:LIMIT\s+\d+|;|$))'
    match = re.search(plain_sql_pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        query = match.group(1).strip()
        query = re.sub(r'["\',\s]*$', '', query)  # Remove trailing quotes and commas
        if query.endswith(';'):
            query = query[:-1]
        return query
    
    return ""



def execute_sql_query(sql_query, database_connection=None):
    """Execute SQL query and return data as list of dictionaries."""
    try:
        if not sql_query.strip():
            return []
        
        # Use the specified database connection or fall back to default
        target_db = database_connection if database_connection else db
        result = target_db.run(sql_query)
        
        # Handle different result types
        if result is None:
            return []
            
        # If result is already a list of dictionaries, return it
        if isinstance(result, list) and result and isinstance(result[0], dict):
            return result
            
        # If result is a string representation of a list, parse it
        if isinstance(result, str):
            try:
                # Try to parse as list of tuples
                import ast
                parsed_result = ast.literal_eval(result)
                
                if isinstance(parsed_result, list):
                    # Get column names from the query
                    column_names = extract_column_names(sql_query)
                    
                    # Convert to list of dictionaries
                    data = []
                    for row in parsed_result:
                        if isinstance(row, (list, tuple)) and column_names:
                            row_dict = {}
                            for i, col_name in enumerate(column_names):
                                if i < len(row):
                                    row_dict[col_name] = row[i]
                            data.append(row_dict)
                        elif isinstance(row, dict):
                            data.append(row)
                    
                    return data
            except (ValueError, SyntaxError):
                pass
        
        # If result is a list of tuples, convert it
        if isinstance(result, list) and result and isinstance(result[0], (list, tuple)):
            column_names = extract_column_names(sql_query)
            
            data = []
            for row in result:
                if column_names:
                    row_dict = {}
                    for i, col_name in enumerate(column_names):
                        if i < len(row):
                            row_dict[col_name] = row[i]
                    data.append(row_dict)
            
            return data
        
        return []
    
    except Exception as e:
        print(f"Error executing SQL query: {e}")
        return []
        return []


def extract_column_names(sql_query):
    """Extract column names from SQL SELECT query."""
    try:
        # Simple regex to extract column names from SELECT clause
        select_pattern = r'SELECT\s+(.*?)\s+FROM'
        match = re.search(select_pattern, sql_query, re.IGNORECASE | re.DOTALL)
        
        if match:
            columns_str = match.group(1).strip()
            
            # Handle SELECT *
            if columns_str.strip() == '*':
                return []
            
            # Split by comma and clean up
            columns = []
            for col in columns_str.split(','):
                col = col.strip()
                # Remove table prefixes and aliases - handle AS keyword properly
                if ' as ' in col.lower():
                    # Take everything after 'as'
                    col = col.lower().split(' as ')[-1].strip()
                elif '.' in col and ' ' not in col:  # Only remove table prefix if no alias
                    col = col.split('.')[-1].strip()
                
                # Remove quotes
                col = col.strip('"\'`')
                columns.append(col)
            
            return columns
    
    except Exception:
        pass
    
    return []


def extract_description(text):
    """Extract a meaningful description from the agent response."""
    # Remove SQL code blocks
    cleaned_text = re.sub(r'```sql.*?```', '', text, flags=re.DOTALL | re.IGNORECASE)
    cleaned_text = re.sub(r'```.*?```', '', cleaned_text, flags=re.DOTALL)
    
    # Remove tool calls and internal processing
    cleaned_text = re.sub(r'Calling tool:.*?with args:.*?\n', '', cleaned_text, flags=re.DOTALL)
    cleaned_text = re.sub(r'Tool.*?returned:.*?\n', '', cleaned_text, flags=re.DOTALL)
    
    # Get the meaningful parts
    lines = cleaned_text.split('\n')
    meaningful_lines = []
    
    for line in lines:
        line = line.strip()
        # Skip empty lines, debug info, and tool calls
        if (line and 
            not line.startswith('Calling tool') and 
            not line.startswith('Tool') and
            not line.startswith('```') and
            len(line) > 10):
            meaningful_lines.append(line)
    
    # Join and limit to reasonable length
    description = ' '.join(meaningful_lines)
    if len(description) > 500:
        description = description[:500] + "..."
    
    return description if description else "Query executed successfully"

# Backwards compatibility
def execute_agent_original(agent, question):
    """Original execute_agent function for backwards compatibility."""
    for step in agent.stream(
        {"messages": [{"role": "user", "content": question}]},
        stream_mode="values",
    ):
        step["messages"][-1].pretty_print()