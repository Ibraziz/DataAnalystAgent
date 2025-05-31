# Data Analyst Agent - Clean structured output version with chart extraction
from langgraph.prebuilt import create_react_agent
from models import llm, db, get_database_connection
from prompts import SYSTEM_MESSAGE, PROPER_NOUN_SUFFIX
from tools import get_sql_tools, create_proper_noun_tool, create_chart_configuration_prompt
from langchain_core.messages import AIMessage
from config import RECURSION_LIMIT, DIALECT
import json
import re

# UPDATED APPROACH - SIMPLIFIED SQL EXECUTION
# ==========================================
# 
# The previous implementation was complex and tried to parse AI messages for data.
# The new approach is much cleaner:
# 
# 1. Extract SQL query from LLM's tool calls (extract_sql_query_from_messages)
# 2. Execute the query directly on the database connection (execute_sql_query)
# 3. Parse the results cleanly using existing column extraction logic
# 
# This eliminates the need to parse complex AI message formats and makes
# the data extraction much more reliable and easier to debug.

def create_agent(use_proper_noun_tool=False, database_name=None):
    """Create an agent with the specified configuration."""
    # Get the appropriate database connection
    if database_name:
        agent_db = get_database_connection(database_name)
    else:
        agent_db = db
    
    tools = get_sql_tools(agent_db)
    
    # Add visualization instructions to the system prompt
    chart_prompt = create_chart_configuration_prompt()
    system_prompt = f"{SYSTEM_MESSAGE}\n\n{chart_prompt}"
    
    if use_proper_noun_tool:
        tools.append(create_proper_noun_tool(agent_db))
        system_prompt = f"{system_prompt}\n\n{PROPER_NOUN_SUFFIX}"
    
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



def execute_agent_with_results(agent, question, database_connection=None, recursion_limit=None, previous_context=None, generate_summary=False):
    """Execute agent and return clean structured results with SQL, description, and data."""
def execute_agent_with_results(agent, question, database_connection=None, recursion_limit=None):
    """Execute agent and return clean structured results with SQL, description, data, and charts."""
    if recursion_limit is None:
        recursion_limit = RECURSION_LIMIT
    
    try:
        # First, let the agent explore the database and generate the query
        messages = execute_agent(agent, question, recursion_limit)
        
        # Extract SQL query from the agent's messages - much simpler approach
        sql_query = extract_sql_query_from_messages(messages)
        
        # Execute the query directly on the database connection
        data = []
        if sql_query:
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
        
        # Generate enhanced insights and charts using the new function
        enhanced_result = generate_enhanced_insights_with_charts(
            original_question=question,
            sql_query=sql_query,
            data=data,
            database_connection=database_connection,
            previous_description=initial_description,
            previous_context=previous_context
        )
        
        # Prepare the result dictionary
        result = {
            'sql': sql_query,
            'description': enhanced_result.get('description', initial_description),
            'data': data,
            'charts': enhanced_result.get('charts', []),
            'question': question  # Add the question to the result for context
        }
        
        # Generate contextual summary if requested
        if generate_summary:
            summary = generate_contextual_summary(
                current_analysis=result,
                previous_context=previous_context,
                original_question=question
            )
            result['summary'] = summary        
        return result
        
    except Exception as e:
        result = {
            'sql': '',
            'description': f'Error occurred: {str(e)}',
            'data': [],
            'question': question,
            'charts': []
        }
        
        # Add empty summary if requested
        if generate_summary:
            result['summary'] = f'Unable to generate summary due to error: {str(e)}'
        
        return result

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
            
            # If no column names found, create generic ones
            if not column_names:
                column_names = [f'Column_{i+1}' for i in range(len(result[0]))]
            
            data = []
            for row in result:
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

def extract_charts_from_response(response_text):
    """Extract Chart.js configuration objects from LLM response text."""
    charts = []
    
    try:
        print(f"DEBUG: Looking for charts in response text (length: {len(response_text)})")
        
        # Pattern 1: Look for ```json blocks
        json_pattern = r'```json\s*(.*?)\s*```'
        json_blocks = re.findall(json_pattern, response_text, re.DOTALL | re.IGNORECASE)
        
        print(f"DEBUG: Found {len(json_blocks)} JSON blocks")
        
        for i, block in enumerate(json_blocks):
            try:
                print(f"DEBUG: Processing JSON block {i}")
                
                # Clean up the JSON block - remove JavaScript functions
                cleaned_block = clean_json_for_parsing(block.strip())
                
                parsed = json.loads(cleaned_block)
                print(f"DEBUG: Successfully parsed JSON block {i}")
                
                if is_valid_chart_config(parsed):
                    print(f"DEBUG: Valid chart config found in block {i}")
                    charts.append(parsed)
                else:
                    print(f"DEBUG: Invalid chart config in block {i}")
                    
            except (json.JSONDecodeError, TypeError) as e:
                print(f"DEBUG: Failed to parse JSON block {i}: {e}")
                # Try to fix common issues and parse again
                try:
                    fixed_block = fix_common_json_issues(block.strip())
                    parsed = json.loads(fixed_block)
                    if is_valid_chart_config(parsed):
                        print(f"DEBUG: Fixed and parsed JSON block {i}")
                        charts.append(parsed)
                except Exception as fix_error:
                    print(f"DEBUG: Could not fix JSON block {i}: {fix_error}")
                    # Last resort: try to extract basic chart data
                    try:
                        basic_chart = extract_basic_chart_from_broken_json(block.strip())
                        if basic_chart:
                            print(f"DEBUG: Created basic chart from broken JSON block {i}")
                            charts.append(basic_chart)
                    except:
                        print(f"DEBUG: Could not create basic chart from block {i}")
                    continue
        
        # Pattern 2: Look for chart objects without json tags
        # Look for objects that start with common chart properties
        chart_patterns = [
            r'{\s*["\']?type["\']?\s*:\s*["\'](?:bar|line|pie|doughnut|radar|polarArea|scatter|bubble)["\'].*?(?=\n\n|\n```|\n#|$)',
        ]
        
        for pattern in chart_patterns:
            matches = re.findall(pattern, response_text, re.DOTALL | re.IGNORECASE)
            print(f"DEBUG: Found {len(matches)} pattern matches")
            
            for match in matches:
                try:
                    # Clean and parse
                    cleaned_match = clean_json_for_parsing(match)
                    parsed = json.loads(cleaned_match)
                    if is_valid_chart_config(parsed):
                        charts.append(parsed)
                        print(f"DEBUG: Added chart from pattern match")
                except:
                    continue
        
        print(f"DEBUG: Total charts extracted: {len(charts)}")
        
    except Exception as e:
        print(f"DEBUG: Error extracting charts from response: {e}")
    
    return charts

def clean_json_for_parsing(json_str):
    """Clean JSON string to make it parseable by removing JavaScript functions."""
    try:
        print(f"DEBUG: Original JSON length: {len(json_str)}")
        
        # First, remove the entire tooltip section since it contains JavaScript functions
        json_str = re.sub(r'"tooltip"\s*:\s*{[^}]*"callbacks"[^}]*function[^}]*}[^}]*}', '"tooltip": {}', json_str, flags=re.DOTALL)
        
        # More aggressive removal of any remaining function definitions
        json_str = re.sub(r'"callbacks"\s*:\s*{[^}]*}', '{}', json_str, flags=re.DOTALL)
        json_str = re.sub(r'function\s*\([^)]*\)\s*{[^}]*}', 'null', json_str, flags=re.DOTALL)
        
        # Remove any remaining JavaScript function references
        json_str = re.sub(r'"[^"]*"\s*:\s*function[^,}]*[,}]', '', json_str, flags=re.DOTALL)
        
        # Clean up multiple consecutive commas
        json_str = re.sub(r',\s*,', ',', json_str)
        
        # Remove trailing commas before closing braces/brackets
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
        
        # Remove commas after opening braces that might be left over
        json_str = re.sub(r'{\s*,', '{', json_str)
        json_str = re.sub(r':\s*,', ': null,', json_str)
        
        print(f"DEBUG: Cleaned JSON length: {len(json_str)}")
        print(f"DEBUG: First 200 chars of cleaned JSON: {json_str[:200]}")
        
        return json_str
        
    except Exception as e:
        print(f"DEBUG: Error cleaning JSON: {e}")
        return json_str

def fix_common_json_issues(json_str):
    """Try to fix common JSON parsing issues more aggressively."""
    try:
        print("DEBUG: Attempting to fix JSON issues...")
        
        # Remove the entire tooltip object and its contents
        json_str = re.sub(r',?\s*"tooltip"\s*:\s*{[^{]*{[^}]*}[^}]*}', '', json_str, flags=re.DOTALL)
        
        # Remove any callbacks objects
        json_str = re.sub(r',?\s*"callbacks"\s*:\s*{[^}]*}', '', json_str, flags=re.DOTALL)
        
        # Remove any function definitions more broadly
        json_str = re.sub(r'function\s*\([^)]*\)\s*{[^}]*}', 'null', json_str, flags=re.DOTALL)
        
        # Remove any line that contains 'function'
        lines = json_str.split('\n')
        cleaned_lines = []
        in_function = False
        brace_count = 0
        
        for line in lines:
            if 'function' in line:
                in_function = True
                brace_count = line.count('{') - line.count('}')
                continue
            elif in_function:
                brace_count += line.count('{') - line.count('}')
                if brace_count <= 0:
                    in_function = False
                continue
            else:
                cleaned_lines.append(line)
        
        json_str = '\n'.join(cleaned_lines)
        
        # Clean up remaining issues
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)  # Remove trailing commas
        json_str = re.sub(r'([}\]]),(\s*[}\]])', r'\1\2', json_str)  # Remove commas before closing
        json_str = re.sub(r'{\s*,', '{', json_str)  # Remove commas after opening braces
        json_str = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas before closing braces
        
        print(f"DEBUG: Fixed JSON length: {len(json_str)}")
        print(f"DEBUG: First 300 chars of fixed JSON: {json_str[:300]}")
        
        return json_str
        
    except Exception as e:
        print(f"DEBUG: Error fixing JSON: {e}")
        return json_str

def extract_chart_from_js_block(js_code):
    """Extract chart configurations from JavaScript code blocks."""
    charts = []
    
    try:
        # Look for new Chart() declarations
        chart_matches = re.findall(r'new\s+Chart\s*\([^,]+,\s*(\{.*?\})\s*\)', js_code, re.DOTALL)
        
        for match in chart_matches:
            try:
                # Clean up the JS object notation and convert to JSON
                cleaned = clean_js_object_to_json(match)
                parsed = json.loads(cleaned)
                if is_valid_chart_config(parsed):
                    charts.append(parsed)
            except (json.JSONDecodeError, TypeError):
                continue
        
        # Look for chart configuration objects
        config_patterns = [
            r'(?:const|let|var)\s+\w+\s*=\s*(\{.*?type\s*:\s*["\'](?:bar|line|pie|doughnut|radar|polarArea|scatter|bubble)["\'].*?\});',
            r'chartConfig\s*[=:]\s*(\{.*?\});?',
            r'config\s*[=:]\s*(\{.*?\});?'
        ]
        
        for pattern in config_patterns:
            matches = re.findall(pattern, js_code, re.DOTALL | re.IGNORECASE)
            for match in matches:
                try:
                    cleaned = clean_js_object_to_json(match)
                    parsed = json.loads(cleaned)
                    if is_valid_chart_config(parsed):
                        charts.append(parsed)
                except (json.JSONDecodeError, TypeError):
                    continue
    
    except Exception as e:
        print(f"Error extracting charts from JS block: {e}")
    
    return charts

def clean_js_object_to_json(js_object_str):
    """Convert JavaScript object notation to valid JSON."""
    try:
        # Remove trailing semicolons
        js_object_str = js_object_str.rstrip(';')
        
        # Replace unquoted keys with quoted keys
        js_object_str = re.sub(r'\b([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:', r'"\1":', js_object_str)
        
        # Replace single quotes with double quotes
        js_object_str = re.sub(r"'([^']*)'", r'"\1"', js_object_str)
        
        # Handle function calls that might be in the data (remove them)
        js_object_str = re.sub(r':\s*[a-zA-Z_$][a-zA-Z0-9_$]*\s*\([^)]*\)', ': null', js_object_str)
        
        # Remove comments
        js_object_str = re.sub(r'//.*?(?=\n|$)', '', js_object_str)
        js_object_str = re.sub(r'/\*.*?\*/', '', js_object_str, flags=re.DOTALL)
        
        return js_object_str
    
    except Exception:
        return js_object_str

def extract_chart_from_description(text):
    """Extract chart configurations from textual descriptions."""
    charts = []
    
    try:
        # Look for explicit mentions of chart types and data
        chart_type_patterns = {
            'bar': r'(?:bar\s+chart|column\s+chart)',
            'line': r'(?:line\s+chart|trend\s+chart)',
            'pie': r'(?:pie\s+chart|circular\s+chart)',
            'doughnut': r'(?:doughnut\s+chart|donut\s+chart)',
            'scatter': r'(?:scatter\s+plot|scatter\s+chart)',
            'radar': r'(?:radar\s+chart|spider\s+chart)',
            'polarArea': r'(?:polar\s+area|polar\s+chart)'
        }
        
        # This is a basic implementation - in practice, you might want to use
        # more sophisticated NLP techniques to extract structured data from descriptions
        
        for chart_type, pattern in chart_type_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                # Basic chart structure - you can enhance this based on your needs
                basic_chart = {
                    "type": chart_type,
                    "data": {
                        "labels": ["Category 1", "Category 2", "Category 3"],
                        "datasets": [{
                            "label": "Data Series",
                            "data": [10, 20, 30],
                            "backgroundColor": ["#3498db", "#e74c3c", "#2ecc71"]
                        }]
                    },
                    "options": {
                        "responsive": True,
                        "maintainAspectRatio": False,
                        "plugins": {
                            "title": {
                                "display": True,
                                "text": f"{chart_type.title()} Chart"
                            }
                        }
                    }
                }
                charts.append(basic_chart)
                break  # Only create one chart from description to avoid duplicates
    
    except Exception as e:
        print(f"Error extracting charts from description: {e}")
    
    return charts

def is_valid_chart_config(config):
    """Check if a parsed object is a valid Chart.js configuration."""
    try:
        if not isinstance(config, dict):
            print("DEBUG: Chart config is not a dict")
            return False
        
        # Must have a type field
        if 'type' not in config:
            print("DEBUG: Chart config missing 'type' field")
            return False
        
        # Type must be a valid Chart.js chart type
        valid_types = ['bar', 'line', 'pie', 'doughnut', 'radar', 'polarArea', 'scatter', 'bubble']
        if config['type'] not in valid_types:
            print(f"DEBUG: Invalid chart type: {config['type']}")
            return False
        
        # Should have data field
        if 'data' not in config:
            print("DEBUG: Chart config missing 'data' field")
            return False
        
        # Data should be a dict
        if not isinstance(config['data'], dict):
            print("DEBUG: Chart config 'data' is not a dict")
            return False
        
        print(f"DEBUG: Valid chart config found - type: {config['type']}")
        return True
    
    except Exception as e:
        print(f"DEBUG: Error validating chart config: {e}")
        return False

def generate_enhanced_insights_with_charts(original_question, sql_query, data, database_connection=None, previous_description=None):
    """
    Generate enhanced insights and extract chart configurations from LLM response.
    """
    try:
        if not data or not sql_query:
            return {"description": "No data available for analysis.", "charts": []}
        
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
        
        # Create an agent for generating insights with chart requirements
        tools = get_sql_tools(target_db)
        chart_prompt = create_chart_configuration_prompt()
        insight_agent = create_react_agent(llm, tools, prompt=f"""
You are a data analyst expert. Given the original question and previous analysis,
your task is to explore the database and find additional interesting insights that complement the original query results.

Focus on:
1. Creating a syntactically correct {DIALECT} query to run
2. Look at the results of the query and provide a detailed answer
3. The query should retrieve interesting information like trends, patterns, statistical insights or anomalies in the data

{chart_prompt}

Use the previous analysis as context to build upon and provide complementary insights with appropriate visualizations.

{context_string}

Generate enhanced insights and chart configurations based on this information.
""")
        
        # Execute the insight generation
        insight_messages = execute_agent(
            insight_agent, 
            f"Analyze the results, provide enhanced insights, and create chart visualizations for: {original_question}",
            recursion_limit=RECURSION_LIMIT
        )
          # Extract the enhanced description and charts from the insight agent's response
        enhanced_description = ""
        all_response_text = ""
        
        for msg in insight_messages:
            if isinstance(msg, AIMessage) and msg.content and msg.content.strip():
                all_response_text += msg.content + "\n"
        
        # Get the final response for description
        for msg in reversed(insight_messages):
            if isinstance(msg, AIMessage) and msg.content and msg.content.strip():
                # Check if this is a final response (not just a tool call)
                if not hasattr(msg, 'tool_calls') or not msg.tool_calls:
                    enhanced_description = msg.content.strip()
                    break
        
        # Extract charts from all response text
        charts = extract_charts_from_response(all_response_text)
        
        # Clean up the description
        if enhanced_description:
            # Remove code blocks from description
            enhanced_description = re.sub(r'```.*?```', '', enhanced_description, flags=re.DOTALL)
            enhanced_description = re.sub(r'Calling tool:.*?(?=\n)', '', enhanced_description, flags=re.DOTALL)
            enhanced_description = re.sub(r'Tool.*?returned:.*?(?=\n)', '', enhanced_description, flags=re.DOTALL)
            enhanced_description = re.sub(r'\n\s*\n', '\n', enhanced_description)
            enhanced_description = enhanced_description.strip()
        
        return {
            "description": enhanced_description if enhanced_description and len(enhanced_description) > 10 else "Analysis completed successfully with the provided data.",
            "charts": charts
        }
        
    except Exception as e:
        print(f"Error in generate_enhanced_insights_with_charts: {e}")
        return {
            "description": f"Unable to generate enhanced insights: {str(e)}",
            "charts": []
        }

# Remove the manual chart generation functions since charts come ready from LLM
def generate_basic_charts_from_data(data, question):
    """Fallback function - not needed since charts come ready from LLM."""
    return []

def extract_basic_chart_from_broken_json(broken_json):
    """Extract basic chart information from broken JSON and create a simplified chart."""
    try:
        print("DEBUG: Attempting to extract basic chart from broken JSON")
        
        # Try to extract chart type
        type_match = re.search(r'"type"\s*:\s*"([^"]*)"', broken_json)
        chart_type = type_match.group(1) if type_match else "bar"
        
        # Try to extract labels
        labels_match = re.search(r'"labels"\s*:\s*\[(.*?)\]', broken_json, re.DOTALL)
        labels = []
        if labels_match:
            labels_str = labels_match.group(1)
            # Extract quoted strings
            labels = re.findall(r'"([^"]*)"', labels_str)
        
        # Try to extract data arrays
        data_matches = re.findall(r'"data"\s*:\s*\[([\d\s,.-]+)\]', broken_json)
        datasets = []
        
        # Extract dataset labels
        dataset_labels = re.findall(r'"label"\s*:\s*"([^"]*)"', broken_json)
        
        # Extract background colors
        color_matches = re.findall(r'"backgroundColor"\s*:\s*"([^"]*)"', broken_json)
        
        for i, data_match in enumerate(data_matches):
            try:
                # Parse the numbers
                numbers = re.findall(r'[\d.-]+', data_match)
                data_values = [float(num) for num in numbers]
                
                if data_values:
                    dataset = {
                        "label": dataset_labels[i] if i < len(dataset_labels) else f"Dataset {i+1}",
                        "data": data_values,
                        "backgroundColor": color_matches[i] if i < len(color_matches) else generate_colors(1)[0]
                    }
                    datasets.append(dataset)
            except:
                continue
        
        # Create basic chart if we have the minimum required data
        if chart_type and (labels or datasets):
            # If no labels but we have data, create generic labels
            if not labels and datasets and datasets[0]['data']:
                labels = [f"Item {i+1}" for i in range(len(datasets[0]['data']))]
            
            basic_chart = {
                "type": chart_type,
                "data": {
                    "labels": labels,
                    "datasets": datasets
                },
                "options": {
                    "responsive": True,
                    "maintainAspectRatio": False,
                    "plugins": {
                        "title": {
                            "display": True,
                            "text": f"{chart_type.title()} Chart"
                        }
                    }
                }
            }
            
            print(f"DEBUG: Created basic chart with {len(labels)} labels and {len(datasets)} datasets")
            return basic_chart
    
    except Exception as e:
        print(f"DEBUG: Error extracting basic chart: {e}")
    
    return None
    """Utility function for colors - kept for potential future use."""
    base_colors = [
        "#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6",
        "#1abc9c", "#34495e", "#e67e22", "#95a5a6", "#f1c40f"
    ]
    
    if border:
        border_colors = [
            "#2980b9", "#c0392b", "#27ae60", "#d68910", "#8e44ad",
            "#16a085", "#2c3e50", "#d35400", "#7f8c8d", "#f4d03f"
        ]
        base_colors = border_colors
    
    if count <= len(base_colors):
        return base_colors[:count]
    
    colors = base_colors.copy()
    for i in range(len(base_colors), count):
        hue = (i * 137.508) % 360
        colors.append(f"hsl({hue}, 70%, {60 if not border else 50}%)")
    
    return colors

def generate_contextual_summary(current_analysis, previous_context=None, original_question=None):
    """
    Generate a comprehensive summary by combining current analysis with previous context.
    
    Args:
        current_analysis (dict): Current analysis results with 'sql', 'description', 'data'
        previous_context (list): List of previous analysis results or context
        original_question (str): The original user question
    
    Returns:
        str: A comprehensive summary combining all information
    """
    try:
        # Prepare the context for the summary prompt
        context_parts = []
        
        if original_question:
            context_parts.append(f"Original Question: {original_question}")
        
        # Add previous context if available
        if previous_context:
            context_parts.append("\n=== Previous Context ===")
            if isinstance(previous_context, list):
                for i, context_item in enumerate(previous_context, 1):
                    if isinstance(context_item, dict):
                        context_parts.append(f"\nPrevious Analysis {i}:")
                        if context_item.get('question'):
                            context_parts.append(f"Question: {context_item['question']}")
                        if context_item.get('description'):
                            context_parts.append(f"Findings: {context_item['description']}")
                        if context_item.get('sql'):
                            context_parts.append(f"Query Used: {context_item['sql']}")
                    elif isinstance(context_item, str):
                        context_parts.append(f"\nPrevious Context {i}: {context_item}")
            else:
                context_parts.append(f"\nPrevious Context: {previous_context}")
        
        # Add current analysis
        context_parts.append("\n=== Current Analysis ===")
        if current_analysis.get('description'):
            context_parts.append(f"Current Findings: {current_analysis['description']}")
        if current_analysis.get('sql'):
            context_parts.append(f"Current Query: {current_analysis['sql']}")
        
        # Create data summary for context
        current_data = current_analysis.get('data', [])
        if current_data:
            if len(current_data) <= 3:
                data_summary = current_data
            else:
                data_summary = current_data[:2] + [{"...": f"and {len(current_data) - 2} more rows"}]
            context_parts.append(f"Current Data Sample: {json.dumps(data_summary, indent=2)}")
        
        context_string = "\n".join(context_parts)
        
        # Create summary prompt
        summary_prompt = f"""
You data analyst creating a comprehensive concise summary. 

Your task is to analyze all the provided information and create a cohesive, insightful summary that:
- start your words by explaining what the query do, then continue to other findings
- Focus on business value and actionable insights
- Highlight any contradictions or confirmations between previous and current findings
- Use specific data points and numbers to support your conclusions
- Keep the summary concise but comprehensive (aim for 2-3 paragraphs)
- Avoid repeating the same information - synthesize and add value

Context and Data:
{context_string}

Generate a comprehensive executive summary based on all the above information, provide the information in a clear form as a human.
"""
        
        # Use the LLM to generate the summary
        from models import llm
        response = llm.invoke(summary_prompt)
        
        if hasattr(response, 'content'):
            summary = response.content.strip()
        else:
            summary = str(response).strip()
        
        # Clean up the summary
        summary = re.sub(r'\n\s*\n', '\n\n', summary)  # Clean up extra whitespace
        
        return summary if summary else "Summary generation completed successfully."
        
    except Exception as e:
        return f"Unable to generate contextual summary: {str(e)}"


# Backwards compatibility
def generate_enhanced_insights(original_question, sql_query, data, database_connection=None, previous_description=None):
    """
    Legacy function for backwards compatibility - now returns just the description.
    """
    result = generate_enhanced_insights_with_charts(
        original_question, sql_query, data, database_connection, previous_description
    )
    return result.get('description', 'Analysis completed successfully.')

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

def extract_sql_query_from_messages(messages):
    """Extract the SQL query from agent messages - simpler approach."""
    sql_query = ""
    
    # Look through messages to find SQL query tool calls
    for msg in messages:
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            # Look for SQL query tool calls
            for tool_call in msg.tool_calls:
                if tool_call.get('name') == 'sql_db_query' and 'query' in tool_call.get('args', {}):
                    sql_query = tool_call['args']['query']
                    # Return the last (most recent) SQL query found
                    # This ensures we get the final working query if the agent tried multiple times
    
    return sql_query