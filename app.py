# app.py - Debug Flask Backend with Enhanced Parsing
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import json
import traceback
import re
import os
from agent import create_agent, execute_agent_with_results
from langchain_core.messages import HumanMessage, AIMessage

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
        use_proper_noun_tool = data.get('use_proper_noun_tool', False)
        
        if not question:
            return jsonify({'error': 'Question is required'}), 400
        
        print(f"\n{'='*60}")
        print(f"EXECUTING QUERY: {question}")
        print(f"Using proper noun tool: {use_proper_noun_tool}")
        print(f"{'='*60}")
        
        # Create agent
        agent = create_agent(use_proper_noun_tool=use_proper_noun_tool)
        
        response = execute_agent_with_results(agent, question)
        
        # If no data found, try alternative parsing
        if 'error' in response:
            print("DEBUG: No data found, trying alternative approach...")
            
        result = {
            'success': True,
            'question': question,
            'sql': response['sql'],
            'data': response['data'],
            'visualizations': response['visualizations']
        }
    
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
    print("Starting SQL Agent Web Interface with DEBUG mode...")
    print("Check the console output for detailed debugging information")
    print("Open your browser to: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)