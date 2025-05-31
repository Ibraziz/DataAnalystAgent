import ast
import re
import json
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain.agents.agent_toolkits import create_retriever_tool
from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
from langchain_core.tools import BaseTool
from typing import Type, Optional
from pydantic import BaseModel, Field
from models import db, llm, vector_store
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.tools import Tool
from prompts import VISUALIZATION_SYSTEM_PROMPT

def query_as_list(db, query):
    """Convert database query results to a list of strings."""
    res = db.run(query)
    res = [el for sub in ast.literal_eval(res) for el in sub if el]
    res = [re.sub(r"\b\d+\b", "", string).strip() for string in res]
    return list(set(res))

class VisualizationQuerySQLTool(QuerySQLDataBaseTool):
    """Enhanced SQL query tool that includes visualization instructions."""
    
    name: str = "sql_db_query_with_viz"
    description: str = """
    Execute a SQL query against the database and provide visualization suggestions.
    
    After executing your query, also provide Chart.js configuration objects for visualizing the results.
    
    Input should be a valid SQL query string.
    
    **IMPORTANT**: Along with your SQL results analysis, include complete Chart.js configuration objects in JSON format within ```json code blocks.
    
    Example visualization format:
    ```json
    {
        "type": "bar",
        "data": {
            "labels": ["Category A", "Category B", "Category C"],
            "datasets": [{
                "label": "Revenue",
                "data": [1000, 2000, 1500],
                "backgroundColor": ["#3498db", "#e74c3c", "#2ecc71"]
            }]
        },
        "options": {
            "responsive": true,
            "maintainAspectRatio": false,
            "plugins": {
                "title": {
                    "display": true,
                    "text": "Your Chart Title"
                }
            }
        }
    }
    ```
    
    Choose appropriate chart types based on the data:
    - Bar charts for categorical comparisons
    - Line charts for trends over time
    - Pie charts for proportional data (when categories < 8)
    - Scatter plots for correlation analysis
    - Doughnut charts for part-to-whole relationships
    
    Always provide at least one chart configuration that best represents the query results.
    """

def get_sql_tools(database_connection=None):
    """Get SQL database tools with visualization capabilities for the specified database connection."""
    target_db = database_connection if database_connection else db
    
    # Create standard toolkit
    toolkit = SQLDatabaseToolkit(db=target_db, llm=llm)
    tools = toolkit.get_tools()
    
    # Replace the standard SQL query tool with our enhanced visualization tool
    enhanced_tools = []
    for tool in tools:
        if isinstance(tool, QuerySQLDataBaseTool):
            # Replace with our enhanced tool
            viz_tool = VisualizationQuerySQLTool(db=target_db)
            enhanced_tools.append(viz_tool)
        else:
            enhanced_tools.append(tool)
    
    return enhanced_tools

def create_proper_noun_tool(database_connection=None):
    """Create a retriever tool for proper noun lookups."""
    target_db = database_connection if database_connection else db
    
    # Example usage of proper noun tool (commented out as it requires specific data)
    # When enabled, the target_db variable would be used like this:
    # artists = query_as_list(target_db, "SELECT Name FROM Artist")
    # albums = query_as_list(target_db, "SELECT Title FROM Album")
    # vector_store.add_texts(artists + albums)
    
    retriever = vector_store.as_retriever(search_kwargs={"k": 5})
    description = (
        "Use to look up values to filter on. Input is an approximate spelling "
        "of the proper noun, output is valid proper nouns. Use the noun most "
        "similar to the search."
    )
    return create_retriever_tool(
        retriever,
        name="search_proper_nouns",
        description=description,
    )

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

Example format for simple chart:
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