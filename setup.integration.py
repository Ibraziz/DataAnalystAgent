# setup_integration.py - Script to help set up the Flask integration
import os
import sys

def create_app_file():
    """Create the Flask app.py file in your project directory."""
    app_content = '''# app.py - Flask Backend for SQL Agent
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import json
import traceback
import re
from agent import create_agent
from enhanced_agent import execute_agent_with_results
from langchain_core.messages import HumanMessage, AIMessage

app = Flask(__name__)
CORS(app)

# Store the HTML template (embedded for simplicity)
HTML_TEMPLATE = open('web_interface.html', 'r').read()

@app.route('/')
def index():
    """Serve the main web interface."""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/query', methods=['POST'])
def execute_query():
    """Execute a query using the SQL agent."""
    try:
        data = request.json
        question = data.get('question', '').strip()
        use_proper_noun_tool = data.get('use_proper_noun_tool', False)
        
        if not question:
            return jsonify({'error': 'Question is required'}), 400
        
        print(f"Executing query: {question}")
        print(f"Using proper noun tool: {use_proper_noun_tool}")
        
        # Create agent
        agent = create_agent(use_proper_noun_tool=use_proper_noun_tool)
        
        # Execute agent and get structured results
        results = execute_agent_with_results(agent, question)
        
        if 'error' in results:
            return jsonify({
                'error': results['error'],
                'details': results.get('full_response', '')
            }), 500
        
        return jsonify({
            'success': True,
            'question': question,
            'sql': results['sql'],
            'data': results['data'],
            'visualizations': results['visualizations']
        })
        
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"Error in execute_query: {error_details}")
        return jsonify({
            'error': f'An error occurred: {str(e)}',
            'details': error_details
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'message': 'SQL Agent API is running'})

if __name__ == '__main__':
    print("Starting SQL Agent Web Interface...")
    print("Open your browser to: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
'''
    
    with open('app.py', 'w') as f:
        f.write(app_content)
    print("✅ Created app.py")

def create_web_interface_file():
    """Create the HTML file for the web interface."""
    # You would copy the HTML content from the artifact here
    # For brevity, I'll create a simplified version
    html_content = '''<!DOCTYPE html>
<html>
<head>
    <title>SQL Agent</title>
    <!-- Copy the full HTML content from the artifact here -->
</head>
<body>
    <!-- Full web interface content goes here -->
</body>
</html>'''
    
    with open('web_interface.html', 'w') as f:
        f.write(html_content)
    print("✅ Created web_interface.html (you need to copy the full content from the artifact)")

def update_requirements():
    """Update requirements.txt with Flask dependencies."""
    flask_requirements = [
        "flask==2.3.3",
        "flask-cors==4.0.0"
    ]
    
    # Read existing requirements
    existing_requirements = []
    if os.path.exists('requirements.txt'):
        with open('requirements.txt', 'r') as f:
            existing_requirements = f.read().splitlines()
    
    # Add Flask requirements if not already present
    for req in flask_requirements:
        if not any(req.split('==')[0] in line for line in existing_requirements):
            existing_requirements.append(req)
    
    # Write updated requirements
    with open('requirements.txt', 'w') as f:
        f.write('\\n'.join(existing_requirements))
    
    print("✅ Updated requirements.txt")

def create_run_script():
    """Create a script to run the web application."""
    run_content = '''#!/usr/bin/env python3
# run_web_app.py - Script to run the web application

import subprocess
import sys
import os

def install_requirements():
    """Install required packages."""
    print("Installing requirements...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

def run_app():
    """Run the Flask application."""
    print("Starting the SQL Agent Web Interface...")
    os.environ.setdefault('FLASK_ENV', 'development')
    subprocess.run([sys.executable, "app.py"])

if __name__ == "__main__":
    try:
        install_requirements()
        run_app()
    except KeyboardInterrupt:
        print("\\nShutting down...")
    except Exception as e:
        print(f"Error: {e}")
'''
    
    with open('run_web_app.py', 'w') as f:
        f.write(run_content)
    
    # Make it executable on Unix systems
    try:
        os.chmod('run_web_app.py', 0o755)
    except:
        pass
    
    print("✅ Created run_web_app.py")

def main():
    """Main setup function."""
    print("🚀 Setting up Flask integration for SQL Agent...")
    print("=" * 50)
    
    # Check if we're in the right directory
    required_files = ['agent.py', 'models.py', 'prompts.py', 'tools.py']
    missing_files = [f for f in required_files if not os.path.exists(f)]
    
    if missing_files:
        print(f"❌ Missing required files: {', '.join(missing_files)}")
        print("Please run this script in your SQL Agent project directory.")
        return
    
    try:
        create_app_file()
        create_web_interface_file()
        update_requirements()
        create_run_script()
        
        print("\\n" + "=" * 50)
        print("✅ Integration setup complete!")
        print("\\n📋 Next steps:")
        print("1. Copy the enhanced_agent.py content to a new file in your project")
        print("2. Copy the full HTML content from the web interface artifact to web_interface.html")
        print("3. Install dependencies: pip install -r requirements.txt")
        print("4. Run the application: python run_web_app.py")
        print("5. Open your browser to: http://localhost:5000")
        print("\\n🎉 Your SQL Agent will have a beautiful web interface!")
        
    except Exception as e:
        print(f"❌ Error during setup: {e}")

if __name__ == "__main__":
    main()
'''