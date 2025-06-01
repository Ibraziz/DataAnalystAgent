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

# Fixed app.py chart processing section

# Add this helper function at the top of app.py, outside any route

def is_valid_chart_config(chart_config):
    """Validate that a chart config has the required structure."""
    if not isinstance(chart_config, dict):
        return False
    
    # Must have type and data
    if 'type' not in chart_config or 'data' not in chart_config:
        return False
    
    # Data must be a dict
    if not isinstance(chart_config['data'], dict):
        return False
    
    # Data should have datasets (for most chart types)
    data = chart_config['data']
    if 'datasets' not in data:
        return False
    
    # Datasets should be a list
    if not isinstance(data['datasets'], list) or len(data['datasets']) == 0:
        return False
    
    return True

def get_chart_fingerprint(chart_config):
    """Create a unique fingerprint for a chart to detect duplicates."""
    try:
        chart_type = chart_config.get('type', '')
        data = chart_config.get('data', {})
        labels = str(sorted(data.get('labels', [])))
        
        # Create fingerprint from datasets
        datasets_fingerprint = []
        for dataset in data.get('datasets', []):
            dataset_data = str(sorted(dataset.get('data', [])))
            dataset_label = dataset.get('label', '')
            datasets_fingerprint.append(f"{dataset_label}:{dataset_data}")
        
        fingerprint = f"{chart_type}:{labels}:{':'.join(sorted(datasets_fingerprint))}"
        return fingerprint
    except Exception as e:
        print(f"DEBUG: Error creating fingerprint: {e}")
        return str(chart_config)  # Fallback to string representation

# Then in your execute_query route, replace the chart processing section:

@app.route('/api/query', methods=['POST'])
def execute_query():
    """Execute a query using the SQL agent."""
    try:
        data = request.json
        question = data.get('question', '').strip()
        database = data.get('database', 'northwind')
        recursion_limit = data.get('recursion_limit', RECURSION_LIMIT)
        previous_context = data.get('previous_context', None)
        generate_summary = False
        
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
        agent = DataAnalystAgent(database_name=database)
        
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
        print(f"  - Total charts: {len(results.get('charts', []))}")
        
        # Process charts to separate main and secondary relevancy
        charts = results.get('charts', [])
        main_charts = []
        secondary_charts = []
        
        print(f"DEBUG: Processing {len(charts)} total charts")
        
        # Use a set to track chart fingerprints and avoid duplicates
        seen_chart_fingerprints = set()
        
        for i, chart in enumerate(charts):
            print(f"DEBUG: Processing chart {i}")
            
            if not isinstance(chart, dict):
                print(f"DEBUG: Chart {i} is not a dict, skipping")
                continue
            
            # Extract chart config and metadata
            chart_config = None
            relevancy = None
            user_input = None
            
            if 'relevancy' in chart and 'chart_config' in chart:
                # New structure with separate config
                relevancy = chart['relevancy']
                chart_config = chart['chart_config']
                user_input = chart.get('user_input')
                print(f"DEBUG: Chart {i} has relevancy structure: {relevancy}")
            elif 'relevancy' in chart and 'type' in chart and 'data' in chart:
                # Direct chart config with relevancy field
                relevancy = chart['relevancy']
                user_input = chart.get('user_input')
                # Create clean chart config without relevancy field
                chart_config = {k: v for k, v in chart.items() 
                              if k not in ['relevancy', 'user_input']}
                print(f"DEBUG: Chart {i} has direct relevancy structure: {relevancy}")
            elif 'type' in chart and 'data' in chart:
                # Standard chart config without relevancy
                chart_config = chart
                relevancy = 'main'  # Default to main if no relevancy specified
                print(f"DEBUG: Chart {i} is standard config, defaulting to main")
            else:
                print(f"DEBUG: Chart {i} doesn't match expected structure, skipping")
                continue
            
            # Validate chart config
            if not is_valid_chart_config(chart_config):
                print(f"DEBUG: Chart {i} has invalid config, skipping")
                continue
            
            # Check for duplicates
            fingerprint = get_chart_fingerprint(chart_config)
            if fingerprint in seen_chart_fingerprints:
                print(f"DEBUG: Chart {i} is a duplicate, skipping")
                continue
            
            seen_chart_fingerprints.add(fingerprint)
            
            # Assign to appropriate category
            if relevancy == 'secondary':
                # For secondary charts, preserve the full structure with metadata
                secondary_chart = {
                    'relevancy': 'secondary',
                    'chart_config': chart_config
                }
                if user_input:
                    secondary_chart['user_input'] = user_input
                
                secondary_charts.append(secondary_chart)
                print(f"DEBUG: Added chart {i} to secondary_charts")
            else:
                # For main charts, just use the clean chart config
                main_charts.append(chart_config)
                print(f"DEBUG: Added chart {i} to main_charts")
        
        print(f"DEBUG: Final separation - Main: {len(main_charts)}, Secondary: {len(secondary_charts)}")
        
        # Log chart details for debugging
        for i, chart in enumerate(main_charts):
            chart_type = chart.get('type', 'unknown')
            title = ""
            if 'options' in chart and 'plugins' in chart['options'] and 'title' in chart['options']['plugins']:
                title = chart['options']['plugins']['title'].get('text', '')
            print(f"DEBUG: Main chart {i}: type={chart_type}, title='{title}'")
        
        for i, chart in enumerate(secondary_charts):
            chart_config = chart.get('chart_config', {})
            chart_type = chart_config.get('type', 'unknown')
            title = ""
            if 'options' in chart_config and 'plugins' in chart_config['options'] and 'title' in chart_config['options']['plugins']:
                title = chart_config['options']['plugins']['title'].get('text', '')
            user_input = chart.get('user_input', '')
            print(f"DEBUG: Secondary chart {i}: type={chart_type}, title='{title}', user_input='{user_input[:50]}...'")
        
        # Return structured response
        result = {
            'success': True,
            'question': question,
            'database': database,
            'sql': results.get('sql', ''),
            'data': results.get('data', []),
            'description': results.get('description', ''),
            'main_charts': main_charts,
            'secondary_charts': secondary_charts,
            'debug_info': {
                'sql_found': bool(results.get('sql')),
                'data_rows': len(results.get('data', [])),
                'has_description': bool(results.get('description')),
                'has_summary': bool(results.get('summary')),
                'previous_context_provided': bool(previous_context),
                'main_charts_count': len(main_charts),
                'secondary_charts_count': len(secondary_charts),
                'total_charts_processed': len(charts),
                'duplicates_removed': len(charts) - len(main_charts) - len(secondary_charts)
            }
        }
        
        # Add summary if generated
        if results.get('summary'):
            result['summary'] = results['summary']
        
        print(f"DEBUG: Returning result with {len(results.get('data', []))} rows, {len(main_charts)} main charts, and {len(secondary_charts)} secondary charts")
        return jsonify(result)
        
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"ERROR in execute_query: {error_details}")
        
        return jsonify({
            'success': False,
            'error': f'An error occurred: {str(e)}',
            'error_type': type(e).__name__,
            'details': error_details,
            'debug_info': {
                'question': data.get('question', '') if 'data' in locals() else '',
                'database': data.get('database', '') if 'data' in locals() else '',
                'stage': 'chart_processing'
            }
        }), 500

def _is_valid_chart_config(chart_config):
    """Validate that a chart config has the required structure."""
    if not isinstance(chart_config, dict):
        return False
    
    # Must have type and data
    if 'type' not in chart_config or 'data' not in chart_config:
        return False
    
    # Data must be a dict
    if not isinstance(chart_config['data'], dict):
        return False
    
    # Data should have datasets (for most chart types)
    data = chart_config['data']
    if 'datasets' not in data:
        return False
    
    # Datasets should be a list
    if not isinstance(data['datasets'], list) or len(data['datasets']) == 0:
        return False
    
    return True

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
        
        # Process charts to separate main and secondary relevancy
        charts = results.get('charts', [])
        main_charts = []
        secondary_charts = []
        
        for chart in charts:
            if isinstance(chart, dict) and 'relevancy' in chart:
                if chart['relevancy'] == 'main':
                    main_charts.append(chart.get('chart_config', chart))
                elif chart['relevancy'] == 'secondary':
                    secondary_charts.append(chart)
            else:
                main_charts.append(chart)
        
        # Return structured response with summary
        result = {
            'success': True,
            'question': question,
            'database': database,
            'sql': results.get('sql', ''),
            'data': results.get('data', []),
            'description': results.get('description', ''),
            'summary': results.get('summary', ''),
            'main_charts': main_charts,
            'secondary_charts': secondary_charts,
            'debug_info': {
                'sql_found': bool(results.get('sql')),
                'data_rows': len(results.get('data', [])),
                'has_description': bool(results.get('description')),
                'has_summary': bool(results.get('summary')),
                'context_items_processed': len(previous_context) if isinstance(previous_context, list) else 0,
                'main_charts_count': len(main_charts),
                'secondary_charts_count': len(secondary_charts)
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

@app.route('/api/dataset_overview', methods=['GET'])
def get_dataset_overview():
    """Get an overview of the specified database using the LLM."""
    try:
        database = request.args.get('database', 'northwind')  # Default to northwind
        
        print(f"\n{'='*60}")
        print(f"GENERATING DATASET OVERVIEW FOR: {database}")
        print(f"{'='*60}")
        
        # Create agent with the selected database
        agent = DataAnalystAgent(database_name=database)
        
        # Generate overview using a predefined question
        results = agent.execute_with_results(
            question="Give me a comprehensive overview of this database. Include information about the tables, their relationships, and some key statistics. Make it informative for a business user.",
            generate_summary=False
        )
        
        # Process charts to separate main and secondary relevancy
        charts = results.get('charts', [])
        main_charts = []
        secondary_charts = []
        
        for chart in charts:
            if isinstance(chart, dict) and 'relevancy' in chart:
                if chart['relevancy'] == 'main':
                    main_charts.append(chart.get('chart_config', chart))
                elif chart['relevancy'] == 'secondary':
                    secondary_charts.append(chart)
            else:
                main_charts.append(chart)
        
        # Return structured response
        result = {
            'success': True,
            'database': database,
            'overview': results.get('description', ''),
            'main_charts': main_charts,
            'secondary_charts': secondary_charts,
            'debug_info': {
                'has_description': bool(results.get('description')),
                'main_charts_count': len(main_charts),
                'secondary_charts_count': len(secondary_charts)
            }
        }
        
        return jsonify(result)
        
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"ERROR in get_dataset_overview: {error_details}")
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