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
        recursion_limit = data.get('recursion_limit', RECURSION_LIMIT)  # Allow override via API
        previous_context = data.get('previous_context', None)  # Allow passing previous context
        generate_summary = data.get('generate_summary', False)  # Allow requesting summary generation
        
        if not question:
            return jsonify({'error': 'Question is required'}), 400
        
        print(f"\n{'='*60}")
        print(f"EXECUTING QUERY: {question}")
        print(f"Database: {database}")
        print(f"Generate summary: {generate_summary}")
        if previous_context:
            print(f"Previous context items: {len(previous_context) if isinstance(previous_context, list) else 1}")
        print(f"{'='*60}")
        
        # Create agent with the selected database
        agent = DataAnalystAgent(
            database_name=database
        )
        
        # Execute agent and get structured results with optional summary
        results = agent.execute_with_results(
            question=question,
            recursion_limit=recursion_limit,
            previous_context=previous_context,
            generate_summary=generate_summary
        )
        
        print("DEBUG: Agent execution results:")
        print(f"  - SQL found: {bool(results.get('sql'))}")
        print(f"  - Data rows: {len(results.get('data', []))}")
        print(f"  - Has description: {bool(results.get('description'))}")
        print(f"  - Has chart properties: {bool(results.get('chart_properties'))}")
        
        if results.get('chart_properties'):
            print(f"  - Chart properties: {results.get('chart_properties')}")
        
        # Validate the results
        if not results.get('sql'):
            print("WARNING: No SQL query was generated")
        
        if not results.get('data'):
            print("WARNING: No data was returned from the query")
        
        # Return structured response
        result = {
            'success': True,
            'question': question,
            'database': database,
            'sql': results.get('sql', ''),
            'data': results.get('data', []),
            'description': results.get('description', ''),
            'charts': results.get('charts', []),  # Charts from the agent
            'debug_info': {
                'sql_found': bool(results.get('sql')),
                'data_rows': len(results.get('data', [])),
                'has_description': bool(results.get('description')),
                'has_summary': bool(results.get('summary')),
                'previous_context_provided': bool(previous_context),
                'charts_count': len(results.get('charts', []))
            }
        }
        
        # Add summary if generated
        if results.get('summary'):
            result['summary'] = results['summary']
        
        print(f"DEBUG: Returning result with {len(results.get('data', []))} rows and {len(results.get('charts', []))} charts")
        return jsonify(result)
        
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"ERROR in execute_query: {error_details}")
        
        # Return detailed error information for debugging
        return jsonify({
            'success': False,
            'error': f'An error occurred: {str(e)}',
            'error_type': type(e).__name__,
            'details': error_details,
            'debug_info': {
                'question': data.get('question', '') if 'data' in locals() else '',
                'database': data.get('database', '') if 'data' in locals() else '',
                'stage': 'unknown'
            }
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    try:        # Test database connections
        from models import db, get_database_connection
        from config import AVAILABLE_DATABASES
        
        db_status = {}
        for db_name in AVAILABLE_DATABASES:
            try:
                test_db = get_database_connection(db_name)
                # Try a simple query to test the connection
                test_db.run("SELECT 1")  # Test database connection
                db_status[db_name] = "healthy"
            except Exception as e:
                db_status[db_name] = f"error: {str(e)}"
        
        return jsonify({
            'status': 'healthy',
            'databases': db_status,
            'available_databases': list(AVAILABLE_DATABASES.keys())
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

@app.route('/api/databases', methods=['GET'])
def get_databases():
    """Get list of available databases."""
    try:
        from config import AVAILABLE_DATABASES
        return jsonify({
            'databases': list(AVAILABLE_DATABASES.keys()),
            'default': 'northwind'
        })
    except Exception as e:
        return jsonify({
            'error': f'Error retrieving databases: {str(e)}'
        }), 500

@app.route('/api/schema/<database_name>', methods=['GET'])
def get_schema(database_name):
    """Get schema information for a specific database."""
    try:
        from models import get_database_connection
        from config import AVAILABLE_DATABASES
        
        if database_name not in AVAILABLE_DATABASES:
            return jsonify({'error': f'Database {database_name} not found'}), 404
        
        db_connection = get_database_connection(database_name)
        
        # Get table names
        tables_query = "SELECT name FROM sqlite_master WHERE type='table';"
        tables_result = db_connection.run(tables_query)
        
        # Parse table names (they come as string representation of list)
        import ast
        table_names = [table[0] for table in ast.literal_eval(tables_result)]
        
        # Get schema for each table
        schema_info = {}
        for table_name in table_names:
            try:
                schema_query = f"PRAGMA table_info({table_name});"
                schema_result = db_connection.run(schema_query)
                schema_parsed = ast.literal_eval(schema_result)
                
                columns = []
                for col_info in schema_parsed:
                    columns.append({
                        'name': col_info[1],
                        'type': col_info[2],
                        'not_null': bool(col_info[3]),
                        'primary_key': bool(col_info[5])
                    })
                
                schema_info[table_name] = columns
            except Exception as e:
                schema_info[table_name] = f"Error: {str(e)}"
        
        return jsonify({
            'database': database_name,
            'tables': table_names,
            'schema': schema_info
        })
        
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"ERROR in get_schema: {error_details}")
        return jsonify({
            'error': f'Error retrieving schema: {str(e)}',
            'details': error_details
        }), 500

@app.route('/api/query_with_context', methods=['POST'])
def execute_query_with_context():
    """Execute a query with previous context and generate a summary."""
    try:
        data = request.json
        question = data.get('question', '').strip()
        database = data.get('database', 'northwind')
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
            'charts': results.get('charts', []),  # Charts from the agent
            'debug_info': {
                'sql_found': bool(results.get('sql')),
                'data_rows': len(results.get('data', [])),
                'has_description': bool(results.get('description')),
                'has_summary': bool(results.get('summary')),
                'context_items_processed': len(previous_context) if isinstance(previous_context, list) else 0,
                'charts_count': len(results.get('charts', []))
            }
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
        
        # Create agent instance for summary generation
        agent = DataAnalystAgent()
        
        # Generate the summary using the insight generator
        summary = agent.insight_generator.generate_contextual_summary(
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
    print("=" * 50)
    
    # Test database connections on startup
    try:
        from config import AVAILABLE_DATABASES
        from models import get_database_connection
        
        print("Testing database connections:")
        for db_name in AVAILABLE_DATABASES:
            try:
                test_db = get_database_connection(db_name)
                test_result = test_db.run("SELECT 1")
                print(f"  ✅ {db_name}: Connected successfully")
            except Exception as e:
                print(f"  ❌ {db_name}: Connection failed - {str(e)}")
        
        print("=" * 50)
        print("Server endpoints:")
        print("  🌐 Main interface: http://localhost:5000")
        print("  🔍 API endpoint: http://localhost:5000/api/query")
        print("  ❤️ Health check: http://localhost:5000/api/health")
        print("  📊 Databases: http://localhost:5000/api/databases")
        print("=" * 50)
        
    except Exception as e:
        print(f"❌ Error during startup checks: {e}")
    
    app.run(debug=True, host='0.0.0.0', port=5000)