import ast
import re
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
from models import db, llm

def query_as_list(db, query):
    """Convert database query results to a list of strings."""
    res = db.run(query)
    res = [el for sub in ast.literal_eval(res) for el in sub if el]
    res = [re.sub(r"\b\d+\b", "", string).strip() for string in res]
    return list(set(res))


def get_sql_tools(database_connection=None):
    """Get SQL database tools with visualization capabilities for the specified database connection."""
    target_db = database_connection if database_connection else db
    
    # Create standard toolkit
    toolkit = SQLDatabaseToolkit(db=target_db, llm=llm)
    tools = toolkit.get_tools()
    
    # Replace the standard SQL query tool with our enhanced visualization tool
    enhanced_tools = []
    for tool in tools:
        
        enhanced_tools.append(tool)
    
    return enhanced_tools



# Additional helper function for chart type recommendations
def get_chart_type_recommendation(query_text: str, result_data: list) -> str:
    """
    Analyze query and results to recommend appropriate chart types.
    This is a helper function that could be used by the LLM.
    """
    query_lower = query_text.lower()
    
    # Time-based queries
    if any(word in query_lower for word in ['time', 'date', 'month', 'year', 'day', 'trend', 'over']):
        return "line"
    
    # Counting/aggregation queries
    if any(word in query_lower for word in ['count', 'sum', 'total', 'avg', 'average']):
        if any(word in query_lower for word in ['by', 'per', 'each', 'category']):
            return "bar"
    
    # Distribution queries
    if any(word in query_lower for word in ['distribution', 'breakdown', 'percentage', 'proportion']):
        # Check if we have few categories (good for pie chart)
        if result_data and len(result_data) <= 8:
            return "pie"
        else:
            return "bar"
    
    # Comparison queries
    if any(word in query_lower for word in ['compare', 'vs', 'versus', 'against', 'top', 'bottom', 'highest', 'lowest']):
        return "bar"
    
    # Default to bar chart for most categorical data
    return "bar"

def create_chart_configuration_prompt():
    """
    Create a standardized prompt section for chart configuration that can be
    added to system messages.
    """
    return """
VISUALIZATION REQUIREMENTS:
When providing analysis results, always include appropriate Chart.js configuration objects to visualize the data.

Follow these guidelines:
1. Provide complete, valid Chart.js configuration objects in ```json code blocks
2. Choose appropriate chart types based on data characteristics:
   - Bar charts: for categorical comparisons, rankings, counts
   - Line charts: for time series, trends, continuous data
   - Pie/Doughnut charts: for proportional data with ≤8 categories
   - Scatter plots: for correlation analysis, two continuous variables
3. Use meaningful titles and labels
4. Include proper color schemes using colors like: #3498db, #e74c3c, #2ecc71, #f39c12, #9b59b6
5. Ensure responsive: true and maintainAspectRatio: false in options
6. Provide at least one chart per analysis when data is suitable for visualization
7. You are allowed to have complex charts for complex queries. Keep it simple for simple queries.
8. If no graph suitable for the data, just say "No graph suitable for the data"
9. Return format should be a list of dictionaries with the following keys:
    - relevancy: either main or secondary
    - user_input: if it's main relevancy, it should be exactly what the user wants to see with as their input result. Do not try to infer or add anything to do user input. If it's secondary relevancy, it should be the verbal query that yields the secondary chart when translated to SQL.
    - chart_config: the Chart.js configuration object
The main relevancy should be the chart of the main query. The secondary relevencies are the charts of other queries that the user might find interesting and related to what the user asked.
You should have maximum 2 main and at least 5 secondary relevancy charts.
Pie charts and polar area charts are encouraged for secondary relevancy charts (if applicable).

Example format for simple Chart.js configuration object:
```json
{
    "type": "bar",
    "data": {
        "labels": ["Label1", "Label2", "Label3"],
        "datasets": [{
            "label": "Dataset Name",
            "data": [value1, value2, value3],
            "backgroundColor": ["#3498db", "#e74c3c", "#2ecc71"]
        }]
    },
    "options": {
        "responsive": true,
        "maintainAspectRatio": false,
        "plugins": {
            "title": {
                "display": true,
                "text": "Descriptive Chart Title"
            }
        }
    }
}
```
"""