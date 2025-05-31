# app.py - Flask Backend for Data Analyst Agent
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import traceback
import os
from agent import create_agent, execute_agent_with_results
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
        recursion_limit = data.get('recursion_limit', RECURSION_LIMIT)
        
        if not question:
            return jsonify({'error': 'Question is required'}), 400
        
        print(f"\n{'='*60}")
        print(f"EXECUTING QUERY: {question}")
        print(f"Database: {database}")
        print(f"Using proper noun tool: {use_proper_noun_tool}")
        print(f"Recursion limit: {recursion_limit}")
        print(f"{'='*60}")
        
        # Create agent with the selected database
        agent = create_agent(use_proper_noun_tool=use_proper_noun_tool, database_name=database)
        
        # Get the database connection for passing to the execution function
        from models import get_database_connection
        db_connection = get_database_connection(database)
        
        # Execute agent and get structured results
        results = execute_agent_with_results(agent, question, db_connection, recursion_limit)
        
        print(f"DEBUG: Agent execution results:")
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
            'description': results.get('description', 'Query executed successfully.'),
            'chart_properties': results.get('chart_properties'),
            'debug_info': {
                'sql_found': bool(results.get('sql')),
                'data_rows': len(results.get('data', [])),
                'has_description': bool(results.get('description')),
                'has_chart_properties': bool(results.get('chart_properties')),
                'recursion_limit_used': recursion_limit
            }
        }
        
        print(f"DEBUG: Returning response with:")
        print(f"  - Success: {result['success']}")
        print(f"  - Data rows: {len(result['data'])}")
        print(f"  - Chart properties present: {bool(result['chart_properties'])}")
        
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
    try:
        # Test database connections
        from models import db, get_database_connection
        from config import AVAILABLE_DATABASES
        
        db_status = {}
        for db_name in AVAILABLE_DATABASES:
            try:
                test_db = get_database_connection(db_name)
                # Try a simple query to test the connection
                test_result = test_db.run("SELECT 1")
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

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

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