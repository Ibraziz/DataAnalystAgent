# Data Analyst Agent - Clean structured output version
from langgraph.prebuilt import create_react_agent
from models import llm, db, get_database_connection
from prompts import SYSTEM_MESSAGE, PROPER_NOUN_SUFFIX
from tools import get_sql_tools, create_proper_noun_tool
from langchain_core.messages import AIMessage
from config import RECURSION_LIMIT, DIALECT
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

def execute_agent(agent, question, recursion_limit=None):
    """Execute the agent with a given question and return structured results."""
    if recursion_limit is None:
        recursion_limit = RECURSION_LIMIT
    
    messages = []
    
    # Collect all messages from the stream
    for step in agent.stream(
        {"messages": [{"role": "user", "content": question}]},
        stream_mode="values",
        config={"recursion_limit": recursion_limit}
    ):
        if "messages" in step:
            messages.extend(step["messages"])
            # Print for debugging (optional)
            if step["messages"]:
                step["messages"][-1].pretty_print()
    
    return messages



def execute_agent_with_results(agent, question, database_connection=None, recursion_limit=None):
    """Execute agent and return clean structured results with SQL, description, and data."""
    if recursion_limit is None:
        recursion_limit = RECURSION_LIMIT
    
    try:
        # First, let the agent explore the database and generate the query
        messages = execute_agent(agent, question, recursion_limit)
          # Extract SQL query, data from the agent's messages
        sql_query = ""
        data = []
        
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
                        
                        # If no column names found, create generic ones                        if not column_names and data and isinstance(parsed_result[0], (list, tuple)):
                            column_names = [f'Column_{i+1}' for i in range(len(parsed_result[0]))]
                            data = []
                            for row in parsed_result:
                                row_dict = {}
                                for i, col_name in enumerate(column_names):
                                    if i < len(row):
                                        row_dict[col_name] = row[i]
                                data.append(row_dict)
                except (ValueError, SyntaxError):
                    pass        # If no data was extracted from tool messages but we have a SQL query, try executing it
        if not data and sql_query:
            data = execute_sql_query(sql_query, database_connection)
        
        # Extract the initial description from the agent's messages
        initial_description = ""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content and msg.content.strip():
                # Check if this is a final response (not just a tool call)
                if not hasattr(msg, 'tool_calls') or not msg.tool_calls:
                    # Extract description from the message content
                    full_text = msg.content.strip()
                    initial_description = extract_description(full_text)
                    break
        
        # Generate enhanced insights using the new function
        enhanced_description = generate_enhanced_insights(
            original_question=question,
            sql_query=sql_query,
            data=data,
            database_connection=database_connection,
            previous_description=initial_description
        )
        
        return {
            'sql': sql_query,
            'description': enhanced_description,
            'data': data
        }
        
    except Exception as e:
        return {
            'sql': '',
            'description': f'Error occurred: {str(e)}',
            'data': []
        }





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
    """Extract column names from SQL SELECT query, handling CTEs, subqueries, and complex syntax."""
    try:
        if not sql_query or not sql_query.strip():
            return []
        
        # Normalize the query
        query = sql_query.strip()
        
        # Find the main/final SELECT statement
        # For CTEs, we want the final SELECT after all WITH clauses
        main_select = _find_main_select(query)
        
        if not main_select:
            return []
        
        # Extract column names from the main SELECT
        columns = _parse_select_columns(main_select)
        
        return columns
    
    except Exception as e:
        print(f"Error extracting column names: {e}")
        return []


def _find_main_select(query):
    """Find the main/final SELECT statement in a query, handling CTEs and subqueries."""
    try:
        # Remove comments
        query = re.sub(r'--.*?(?=\n|$)', '', query)
        query = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)
        
        # If it starts with WITH, find the final SELECT after all CTEs
        if query.upper().strip().startswith('WITH'):
            # Find all CTE definitions and the final SELECT
            # Use a simple approach: find the last SELECT that's not inside parentheses at depth 0
            return _find_final_select_after_cte(query)
        else:
            # Regular query - find the first SELECT clause
            select_match = re.search(r'SELECT\s+(.*?)\s+FROM', query, re.IGNORECASE | re.DOTALL)
            if select_match:
                return select_match.group(0)
    
    except Exception:
        pass
    
    return None


def _find_final_select_after_cte(query):
    """Find the final SELECT statement after CTE definitions."""
    try:
        # Split by SELECT and track parentheses depth
        parts = re.split(r'\bSELECT\b', query, flags=re.IGNORECASE)
        
        if len(parts) < 2:
            return None
        
        # Find the last SELECT that's at the main level (not in subquery)
        for i in range(len(parts) - 1, 0, -1):
            # Reconstruct the SELECT statement
            before_select = ''.join(parts[:i])
            select_part = parts[i]
            
            # Check if this SELECT is at the main level by counting parentheses
            paren_depth = before_select.count('(') - before_select.count(')')
            
            if paren_depth == 0:
                # This is likely the main SELECT
                from_match = re.search(r'\s+FROM\b', select_part, re.IGNORECASE)
                if from_match:
                    columns_part = select_part[:from_match.start()]
                    return f"SELECT {columns_part} FROM"
        
        return None
    
    except Exception:
        return None


def _parse_select_columns(select_clause):
    """Parse column names from a SELECT clause."""
    try:
        # Extract the columns part between SELECT and FROM
        match = re.search(r'SELECT\s+(.*?)\s+FROM', select_clause, re.IGNORECASE | re.DOTALL)
        
        if not match:
            return []
        
        columns_str = match.group(1).strip()
        
        # Handle SELECT *
        if columns_str.strip() == '*':
            return []
        
        # Split by comma, but be careful about commas inside functions/expressions
        column_parts = _smart_split_columns(columns_str)
        
        columns = []
        for col in column_parts:
            col = col.strip()
            if not col:
                continue
            
            # Extract the column alias or name
            column_name = _extract_column_alias(col)
            if column_name:
                columns.append(column_name)
        
        return columns
    
    except Exception:
        return []


def _smart_split_columns(columns_str):
    """Split columns by comma, respecting parentheses and function calls."""
    try:
        parts = []
        current_part = ""
        paren_depth = 0
        in_quotes = False
        quote_char = None
        
        i = 0
        while i < len(columns_str):
            char = columns_str[i]
            
            # Handle quotes
            if char in ('"', "'", '`') and not in_quotes:
                in_quotes = True
                quote_char = char
                current_part += char
            elif char == quote_char and in_quotes:
                in_quotes = False
                quote_char = None
                current_part += char
            elif in_quotes:
                current_part += char
            # Handle parentheses (only when not in quotes)
            elif char == '(':
                paren_depth += 1
                current_part += char
            elif char == ')':
                paren_depth -= 1
                current_part += char
            # Handle comma (only split when not in quotes and at depth 0)
            elif char == ',' and paren_depth == 0:
                parts.append(current_part.strip())
                current_part = ""
            else:
                current_part += char
            
            i += 1
        
        # Add the last part
        if current_part.strip():
            parts.append(current_part.strip())
        
        return parts
    
    except Exception:
        # Fallback to simple split
        return columns_str.split(',')


def _extract_column_alias(column_expr):
    """Extract the column name/alias from a column expression."""
    try:
        column_expr = column_expr.strip()
        
        # Handle AS keyword (case insensitive)
        as_match = re.search(r'\s+AS\s+(.+)$', column_expr, re.IGNORECASE)
        if as_match:
            alias = as_match.group(1).strip()
            # Remove quotes if present
            alias = alias.strip('"\'`')
            return alias
        
        # Handle implicit alias (space-separated)
        # Look for patterns like "expression alias" but be careful with function calls
        words = column_expr.split()
        if len(words) >= 2:
            # Check if the last word could be an alias
            last_word = words[-1].strip()
              # If the last word doesn't contain operators or special chars, it might be an alias
            if (not re.search(r'[()/*+-=<>]', last_word) and 
                last_word.upper() not in ('AND', 'OR', 'NOT', 'IS', 'NULL', 'LIKE', 'IN') and
                not last_word.startswith('\'') and not last_word.startswith('"')):
                
                # Additional check: make sure it's not part of a function or expression
                before_last = ' '.join(words[:-1])
                if not before_last.endswith('(') and not re.search(r'[()]\s*$', before_last):
                    return last_word.strip('"\'`')
        
        # No explicit alias - try to extract a meaningful name
        # Remove table prefixes
        if '.' in column_expr and not re.search(r'[()/*+-]', column_expr):
            # Simple column reference like "table.column"
            parts = column_expr.split('.')
            return parts[-1].strip('"\'`')
        
        # For complex expressions, try to find a meaningful part
        # Remove common SQL functions and operators to get the core column name
        cleaned = re.sub(r'\b(SUM|COUNT|AVG|MIN|MAX|COALESCE|CASE|WHEN|THEN|ELSE|END)\b', '', column_expr, flags=re.IGNORECASE)
        cleaned = re.sub(r'[()/*+-]', ' ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
          # Take the first meaningful word that looks like a column name
        words = cleaned.split()
        for word in words:
            word = word.strip('"\'`')
            if (word and 
                word.upper() not in ('AS', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'IS', 'NULL', 'LIKE', 'IN') and
                not word.isdigit() and
                re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', word)):
                return word
        
        # Fallback: return the original expression (cleaned up)
        fallback = re.sub(r'[()/*+-]', '', column_expr).strip()
        fallback = re.sub(r'\s+', '_', fallback)
        return fallback[:50] if fallback else 'column'
    
    except Exception:
        return 'column'


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

def generate_enhanced_insights(original_question, sql_query, data, database_connection=None, previous_description=None):
    """
    Generate enhanced insights by prompting the LLM to find additional interesting information
    related to the original query results.
    """
    try:
        if not data or not sql_query:
            return "No data available for analysis."
        
        # Use the specified database connection or fall back to default
        target_db = database_connection if database_connection else db
        
        # Create a summary of the data for context
        data_summary = []
        if len(data) <= 5:
            data_summary = data
        else:
            data_summary = data[:3] + [{"...": f"and {len(data) - 3} more rows"}]
        
        # Build the context with previous description if available
        context_parts = [
            f"Original Question: {original_question}",
            f"Original SQL Query: {sql_query}",
            f"Sample Results: {json.dumps(data_summary, indent=2)}"
        ]
        
        if previous_description and previous_description.strip():
            context_parts.insert(-1, f"Previous Analysis: {previous_description}")
        
        context_string = "\n".join(context_parts)
        
        # Create an agent for generating insights
        tools = get_sql_tools(target_db)
        insight_agent = create_react_agent(llm, tools, prompt=f"""
You are a data analyst expert. Given the original question and previous analysis,
your task is to explore the database and find additional interesting insights that complement the original query results, just provide one more additional insight.

Focus on:
1. Creating a syntactically correct {DIALECT} query to run
2. Look at the results of the query and provide a detailed answer
3. the query should retrieve interesting information like Trends, patterns, statistical insights or anomalies in the data.

Provide a comprehensive analysis with specific findings. Execute additional queries as needed to gather supporting information, but focus on generating insights rather than just showing raw data.

Use the previous analysis as context to build upon and provide complementary insights.

{context_string}

Generate enhanced insights and analysis based on this information.
""")
        
        # Execute the insight generation
        insight_messages = execute_agent(
            insight_agent, 
            f"Analyze the results and provide enhanced insights for: {original_question}",
            recursion_limit=RECURSION_LIMIT
        )
          # Extract the enhanced description from the insight agent's response
        enhanced_description = ""
        for msg in reversed(insight_messages):
            if isinstance(msg, AIMessage) and msg.content and msg.content.strip():
                # Check if this is a final response (not just a tool call)
                if not hasattr(msg, 'tool_calls') or not msg.tool_calls:
                    enhanced_description = msg.content.strip()
                    break
        
        # Clean up the description if we found one
        if enhanced_description:
            # Remove SQL code blocks and tool call references (more gentle cleaning)
            enhanced_description = re.sub(r'```sql.*?```', '', enhanced_description, flags=re.DOTALL | re.IGNORECASE)
            enhanced_description = re.sub(r'```[a-zA-Z]*\n.*?```', '', enhanced_description, flags=re.DOTALL)
            enhanced_description = re.sub(r'Calling tool:.*?(?=\n)', '', enhanced_description, flags=re.DOTALL)
            enhanced_description = re.sub(r'Tool.*?returned:.*?(?=\n)', '', enhanced_description, flags=re.DOTALL)
            # Clean up extra whitespace
            enhanced_description = re.sub(r'\n\s*\n', '\n', enhanced_description)
            enhanced_description = enhanced_description.strip()
            
            # Additional check: if the description is too short or empty after cleaning, 
            # try to find a better message
            if len(enhanced_description) < 50:
                for msg in reversed(insight_messages):
                    if isinstance(msg, AIMessage) and msg.content and len(msg.content.strip()) > 50:
                        # Less aggressive cleaning for backup option
                        backup_desc = re.sub(r'```sql.*?```', '', msg.content, flags=re.DOTALL | re.IGNORECASE)
                        backup_desc = backup_desc.strip()
                        if len(backup_desc) > 50:
                            enhanced_description = backup_desc
                            break
        
        return enhanced_description if enhanced_description and len(enhanced_description) > 10 else "Analysis completed successfully with the provided data."
        
    except Exception as e:
        return f"Unable to generate enhanced insights: {str(e)}"

# Backwards compatibility
def execute_agent_original(agent, question, recursion_limit=None):
    """Original execute_agent function for backwards compatibility."""
    if recursion_limit is None:
        recursion_limit = RECURSION_LIMIT
    
    for step in agent.stream(
        {"messages": [{"role": "user", "content": question}]},
        stream_mode="values",
        config={"recursion_limit": recursion_limit}
    ):
        step["messages"][-1].pretty_print()