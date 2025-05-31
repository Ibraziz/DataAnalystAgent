# app.py - Flask Backend for Data Analyst Agent
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import traceback
import os
from core import DataAnalystAgent
from config import RECURSION_LIMIT

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
        recursion_limit = data.get('recursion_limit', RECURSION_LIMIT)  # Allow override via API
        previous_context = data.get('previous_context', None)  # Allow passing previous context
        generate_summary = data.get('generate_summary', False)  # Allow requesting summary generation
        
        if not question:
            return jsonify({'error': 'Question is required'}), 400
        
        print(f"\n{'='*60}")
        print(f"EXECUTING QUERY: {question}")
        print(f"Database: {database}")
        print(f"Using proper noun tool: {use_proper_noun_tool}")
        print(f"Generate summary: {generate_summary}")
        if previous_context:
            print(f"Previous context items: {len(previous_context) if isinstance(previous_context, list) else 1}")
        print(f"{'='*60}")
        
        # Create agent with the selected database
        agent = DataAnalystAgent(
            use_proper_noun_tool=use_proper_noun_tool,
            database_name=database
        )
        
        # Execute agent and get structured results with optional summary
        results = agent.execute_with_results(
            question=question,
            recursion_limit=recursion_limit,
            previous_context=previous_context,
            generate_summary=generate_summary
        )
        
        # Return structured response
        result = {
            'success': True,
            'question': question,
            'database': database,
            'sql': results.get('sql', ''),
            'data': results.get('data', []),
            'description': results.get('description', ''),
            'charts': results.get('charts', []),  # New charts key
            'debug_info': {
                'sql_found': bool(results.get('sql')),
                'data_rows': len(results.get('data', [])),
                'has_description': bool(results.get('description')),
                'has_summary': bool(results.get('summary')),
                'previous_context_provided': bool(previous_context)
            },
            'chart_properties': get_chart_template('bar', ['Category A', 'Category B', 'Category C'], 'Sample Values', [100, 200, 300], 'Sample Bar Chart')
        }
        
        # Add summary if generated
        if results.get('summary'):
            result['summary'] = results['summary']
        
        print(f"DEBUG: Returning result with {len(results.get('data', []))} rows")
        return jsonify(result)
        
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"ERROR in execute_query: {error_details}")
        return jsonify({
            'error': f'An error occurred: {str(e)}',
            'details': error_details
        }), 500

@app.route('/api/query_with_context', methods=['POST'])
def execute_query_with_context():
    """Execute a query with previous context and generate a summary."""
    try:
        data = request.json
        question = data.get('question', '').strip()
        database = data.get('database', 'northwind')
        use_proper_noun_tool = data.get('use_proper_noun_tool', False)
        recursion_limit = data.get('recursion_limit', RECURSION_LIMIT)
        previous_context = data.get('previous_context', [])
        
        if not question:
            return jsonify({'error': 'Question is required'}), 400
        
        print(f"\n{'='*60}")
        print(f"EXECUTING QUERY WITH CONTEXT: {question}")
        print(f"Database: {database}")
        print(f"Previous context items: {len(previous_context) if isinstance(previous_context, list) else 0}")
        print(f"{'='*60}")
        
        # Create agent with the selected database
        agent = DataAnalystAgent(
            use_proper_noun_tool=use_proper_noun_tool,
            database_name=database
        )
        
        # Execute agent with context and summary generation
        results = agent.execute_with_results(
            question=question,
            recursion_limit=recursion_limit,
            previous_context=previous_context,
            generate_summary=True  # Always generate summary for this endpoint
        )
        
        # Return structured response with summary
        result = {
            'success': True,
            'question': question,
            'database': database,
            'sql': results.get('sql', ''),
            'data': results.get('data', []),
            'description': results.get('description', ''),
            'summary': results.get('summary', ''),
            'debug_info': {
                'sql_found': bool(results.get('sql')),
                'data_rows': len(results.get('data', [])),
                'has_description': bool(results.get('description')),
                'has_summary': bool(results.get('summary')),
                'context_items_processed': len(previous_context) if isinstance(previous_context, list) else 0
            },
            'chart_properties': get_chart_template('bar', ['Category A', 'Category B', 'Category C'], 'Sample Values', [100, 200, 300], 'Sample Bar Chart')
        }
        
        print(f"DEBUG: Returning result with summary: {bool(results.get('summary'))}")
        return jsonify(result)
        
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"ERROR in execute_query_with_context: {error_details}")
        return jsonify({
            'error': f'An error occurred: {str(e)}',
            'details': error_details
        }), 500

@app.route('/api/generate_summary', methods=['POST'])
def generate_summary_only():
    """Generate a summary from existing analysis results and context."""
    try:
        data = request.json
        current_analysis = data.get('current_analysis', {})
        previous_context = data.get('previous_context', [])
        original_question = data.get('original_question', '')
        
        if not current_analysis:
            return jsonify({'error': 'Current analysis is required'}), 400
        
        print(f"\n{'='*60}")
        print(f"GENERATING SUMMARY FOR: {original_question}")
        print(f"Previous context items: {len(previous_context) if isinstance(previous_context, list) else 0}")
        print(f"{'='*60}")
        
        # Import the summary generation function
        from agent import generate_contextual_summary
        
        # Generate the summary
        summary = generate_contextual_summary(
            current_analysis=current_analysis,
            previous_context=previous_context,
            original_question=original_question
        )
        
        result = {
            'success': True,
            'summary': summary,
            'debug_info': {
                'context_items_processed': len(previous_context) if isinstance(previous_context, list) else 0,
                'has_current_analysis': bool(current_analysis)
            }
        }
        
        print(f"DEBUG: Generated summary with {len(summary)} characters")
        return jsonify(result)
        
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"ERROR in generate_summary_only: {error_details}")
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