# app.py - Flask Backend for Data Analyst Agent
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import traceback
import os
from agent import create_agent, execute_agent_with_results

app = Flask(__name__)
CORS(app)

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
        database = data.get('database', 'northwind')  # Default to northwind
        use_proper_noun_tool = data.get('use_proper_noun_tool', False)
        
        if not question:
            return jsonify({'error': 'Question is required'}), 400
        
        print(f"\n{'='*60}")
        print(f"EXECUTING QUERY: {question}")
        print(f"Database: {database}")
        print(f"Using proper noun tool: {use_proper_noun_tool}")
        print(f"{'='*60}")
          # Create agent with the selected database
        agent = create_agent(use_proper_noun_tool=use_proper_noun_tool, database_name=database)
        
        # Get the database connection for passing to the execution function
        from models import get_database_connection
        db_connection = get_database_connection(database)
        
        # Execute agent and get structured results
        results = execute_agent_with_results(agent, question, db_connection)
        
        # Return structured response
        result = {
            'success': True,
            'question': question,
            'database': database,
            'sql': results.get('sql', ''),
            'data': results.get('data', []),
            'description': results.get('description', ''),
            'debug_info': {
                'sql_found': bool(results.get('sql')),
                'data_rows': len(results.get('data', [])),
                'has_description': bool(results.get('description'))
            }
        }
        
        print(f"DEBUG: Returning result with {len(results.get('data', []))} rows")
        return jsonify(result)
        
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"ERROR in execute_query: {error_details}")
        return jsonify({
            'error': f'An error occurred: {str(e)}',
            'details': error_details
        }), 500

# Create templates directory if it doesn't exist
if not os.path.exists('templates'):
    os.makedirs('templates')

if __name__ == '__main__':
    print("Starting SQL Agent Web Interface...")
    print("Open your browser to: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
