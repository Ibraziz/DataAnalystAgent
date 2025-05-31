# app.py - Debug Flask Backend with Enhanced Parsing
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import json
import traceback
import re
import os
from agent import create_agent, execute_agent
from langchain_core.messages import HumanMessage, AIMessage

app = Flask(__name__)
CORS(app)

def debug_agent_response(messages):
    """Debug function to print all agent messages."""
    print("\n" + "="*50)
    print("DEBUG: All Agent Messages")
    print("="*50)
    
    for i, msg in enumerate(messages):
        print(f"\nMessage {i+1}:")
        print(f"Type: {type(msg).__name__}")
        if hasattr(msg, 'content'):
            print(f"Content: {msg.content[:500]}...")  # First 500 chars
        else:
            print(f"Content: {str(msg)[:500]}...")
    
    print("="*50)

def extract_sql_from_text(text):
    """Extract SQL query using multiple patterns."""
    if not text:
        return ""
    
    # Multiple SQL extraction patterns
    patterns = [
        r'```sql\n(.*?)\n```',
        r'```SQL\n(.*?)\n```',
        r'```\n(SELECT.*?);?\n```',
        r'(SELECT.*?);?(?=\n\n|\n\||\Z)',
        r'Query:\s*(SELECT.*?)(?=\n\n|\n\||\Z)',
        r'SQL:\s*(SELECT.*?)(?=\n\n|\n\||\Z)',
        r'Here is the query:\s*(SELECT.*?)(?=\n\n|\n\||\Z)',
    ]
    
    for i, pattern in enumerate(patterns):
        try:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                sql = match.group(1).strip()
                print(f"DEBUG: SQL found with pattern {i+1}: {sql[:100]}...")
                return sql
        except Exception as e:
            print(f"DEBUG: Pattern {i+1} failed: {e}")
            continue
    
    print("DEBUG: No SQL query found in text")
    return ""

def extract_data_from_text(text):
    """Extract data table using multiple approaches."""
    if not text:
        return []
    
    print("DEBUG: Attempting to extract data table...")
    
    # Look for markdown tables
    table_patterns = [
        r'\|[^|]*\|(?:\n\|[^|]*\|)+',  # Standard markdown table
        r'\n(\|.*?\|\n(?:\|.*?\|\n)+)',  # Table with newlines
    ]
    
    for i, pattern in enumerate(table_patterns):
        try:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                table_text = match.group(0) if i == 0 else match.group(1)
                print(f"DEBUG: Table found with pattern {i+1}")
                print(f"Table text: {table_text[:200]}...")
                
                # Parse the table
                lines = [line.strip() for line in table_text.strip().split('\n') if line.strip()]
                
                if len(lines) < 2:
                    continue
                
                # Find header line (should have |)
                header_line = None
                data_start = 0
                
                for j, line in enumerate(lines):
                    if '|' in line and not all(c in '|-: ' for c in line):
                        header_line = line
                        data_start = j + 1
                        break
                
                if not header_line:
                    continue
                
                # Extract headers
                headers = [h.strip() for h in header_line.split('|') if h.strip()]
                print(f"DEBUG: Headers found: {headers}")
                
                # Skip separator line if it exists
                if data_start < len(lines) and all(c in '|-: ' for c in lines[data_start]):
                    data_start += 1
                
                # Extract data rows
                data = []
                for line in lines[data_start:]:
                    if '|' in line and not all(c in '|-: ' for c in line):
                        values = [v.strip() for v in line.split('|') if v.strip()]
                        
                        if len(values) >= len(headers):
                            row = {}
                            for k, header in enumerate(headers):
                                if k < len(values):
                                    value = values[k]
                                    # Try to convert to number
                                    try:
                                        # Remove commas and try conversion
                                        clean_value = value.replace(',', '').replace('$', '')
                                        if '.' in clean_value:
                                            value = float(clean_value)
                                        elif clean_value.isdigit():
                                            value = int(clean_value)
                                    except (ValueError, AttributeError):
                                        pass  # Keep as string
                                    
                                    row[header] = value
                            data.append(row)
                
                if data:
                    print(f"DEBUG: Extracted {len(data)} data rows")
                    print(f"Sample row: {data[0] if data else 'None'}")
                    return data
                
        except Exception as e:
            print(f"DEBUG: Table pattern {i+1} failed: {e}")
            continue
    
    print("DEBUG: No data table found")
    return []

def extract_visualizations_from_text(text):
    """Extract visualization recommendations."""
    if not text:
        return {}
    
    print("DEBUG: Attempting to extract visualizations...")
    
    visualizations = {}
    
    # Look for visualization sections
    viz_patterns = [
        r'\*\*RECOMMENDED VISUALIZATIONS:\*\*\s*\n(.*?)(?=\n\n|\Z)',
        r'RECOMMENDED VISUALIZATIONS:\s*\n(.*?)(?=\n\n|\Z)',
        r'Visualization.*?:\s*\n(.*?)(?=\n\n|\Z)',
    ]
    
    for pattern in viz_patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            viz_text = match.group(1)
            print(f"DEBUG: Visualization section found: {viz_text[:200]}...")
            
            # Extract individual recommendations
            rec_patterns = {
                'primary': [
                    r'\*\*Primary:\*\*\s*(.*?)(?=\n\s*[-*]|\Z)',
                    r'Primary.*?:\s*(.*?)(?=\n\s*[-*]|\Z)',
                    r'🥇.*?:\s*(.*?)(?=\n\s*[-*]|\Z)',
                ],
                'alternative': [
                    r'\*\*Alternative:\*\*\s*(.*?)(?=\n\s*[-*]|\Z)',
                    r'Alternative.*?:\s*(.*?)(?=\n\s*[-*]|\Z)',
                    r'🥈.*?:\s*(.*?)(?=\n\s*[-*]|\Z)',
                ],
                'consider': [
                    r'\*\*Consider Also:\*\*\s*(.*?)(?=\n\s*[-*]|\Z)',
                    r'Consider.*?:\s*(.*?)(?=\n\s*[-*]|\Z)',
                    r'💡.*?:\s*(.*?)(?=\n\s*[-*]|\Z)',
                ]
            }
            
            for key, patterns in rec_patterns.items():
                for pattern in patterns:
                    match = re.search(pattern, viz_text, re.DOTALL | re.IGNORECASE)
                    if match:
                        visualizations[key] = match.group(1).strip()
                        print(f"DEBUG: Found {key}: {visualizations[key][:100]}...")
                        break
            break
    
    if not visualizations:
        print("DEBUG: No visualizations found")
    
    return visualizations

def parse_agent_response(agent_stream):
    """Parse the agent response with enhanced debugging."""
    messages = []
    
    try:
        print("DEBUG: Starting to collect agent messages...")
        
        # Collect all messages from the stream
        for step in agent_stream:
            if "messages" in step and step["messages"]:
                messages.extend(step["messages"])
                print(f"DEBUG: Added {len(step['messages'])} messages")
        
        print(f"DEBUG: Total messages collected: {len(messages)}")
        
        # Debug all messages
        debug_agent_response(messages)
        
        # Find the final AI message with results
        final_message = None
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                final_message = msg.content
                print(f"DEBUG: Found final AI message, length: {len(final_message)}")
                break
        
        if not final_message:
            print("DEBUG: No AI message found!")
            return "", [], {}
        
        # Extract components
        sql_query = extract_sql_from_text(final_message)
        data_results = extract_data_from_text(final_message)
        visualizations = extract_visualizations_from_text(final_message)
        
        print(f"DEBUG: Final results - SQL: {bool(sql_query)}, Data rows: {len(data_results)}, Viz: {bool(visualizations)}")
        
        return sql_query, data_results, visualizations
        
    except Exception as e:
        print(f"DEBUG: Error in parse_agent_response: {e}")
        traceback.print_exc()
        return "", [], {}

@app.route('/')
def index():
    """Serve the main web interface."""
    return render_template('index.html')

@app.route('/api/query', methods=['POST'])
def execute_query():
    """Execute a query using the SQL agent."""
    try:
        data = request.json
        question = data.get('question', '').strip()
        use_proper_noun_tool = data.get('use_proper_noun_tool', False)
        
        if not question:
            return jsonify({'error': 'Question is required'}), 400
        
        print(f"\n{'='*60}")
        print(f"EXECUTING QUERY: {question}")
        print(f"Using proper noun tool: {use_proper_noun_tool}")
        print(f"{'='*60}")
        
        # Create agent
        agent = create_agent(use_proper_noun_tool=use_proper_noun_tool)
        
        # Execute agent and capture the stream
        agent_stream = agent.stream(
            {"messages": [{"role": "user", "content": question}]},
            stream_mode="values",
        )
        
        # Parse the response with debugging
        sql_query, data_results, visualizations = parse_agent_response(agent_stream)
        
        # If no data found, try alternative parsing
        if not data_results and not sql_query:
            print("DEBUG: No data found, trying alternative approach...")
            # You might want to add fallback parsing here
            
        result = {
            'success': True,
            'question': question,
            'sql': sql_query,
            'data': data_results,
            'visualizations': visualizations,
            'debug_info': {
                'sql_found': bool(sql_query),
                'data_rows': len(data_results),
                'viz_found': bool(visualizations)
            }
        }
        
        print(f"DEBUG: Returning result with {len(data_results)} rows")
        return jsonify(result)
        
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"ERROR in execute_query: {error_details}")
        return jsonify({
            'error': f'An error occurred: {str(e)}',
            'details': error_details
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'message': 'SQL Agent API is running'})

# Create templates directory if it doesn't exist
if not os.path.exists('templates'):
    os.makedirs('templates')

if __name__ == '__main__':
    print("Starting SQL Agent Web Interface with DEBUG mode...")
    print("Check the console output for detailed debugging information")
    print("Open your browser to: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)