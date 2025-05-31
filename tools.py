import ast
import re
import json
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain.agents.agent_toolkits import create_retriever_tool
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

def get_sql_tools(database_connection=None):
    """Get SQL database tools for the specified database connection."""
    target_db = database_connection if database_connection else db
    toolkit = SQLDatabaseToolkit(db=target_db, llm=llm)
    return toolkit.get_tools()

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

def create_visualization_tool():
    """Create a tool for suggesting data visualizations."""
    
    def generate_chart_config(inputs):
        """Generate chart configuration based on inputs."""
        try:
            # Parse inputs if it's a dictionary-like input
            if isinstance(inputs, dict):
                question = inputs.get('question', '')
                query = inputs.get('query', '')
                description = inputs.get('description', '')
                results = inputs.get('results', '')
            else:
                # If inputs is a string, try to parse it
                question = str(inputs)
                query = ''
                description = ''
                results = ''
            
            # Create the prompt for the LLM
            prompt_text = f"""{VISUALIZATION_SYSTEM_PROMPT}

Question: {question}
SQL Query: {query}
Natural Language Description: {description}
Results: {results}

Generate the JSON configuration for appropriate visualizations:"""
            
            # Get response from LLM
            response = llm.invoke(prompt_text)
            
            # Extract content from response
            if hasattr(response, 'content'):
                content = response.content
            else:
                content = str(response)
            
            # Try to extract JSON from the response
            try:
                # Look for JSON-like structure in the response
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    # Parse the JSON
                    chart_config = json.loads(json_str)
                    return chart_config
                else:
                    print(f"No JSON found in LLM response: {content}")
                    return None
            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON from LLM response: {e}")
                print(f"Response content: {content}")
                return None
                
        except Exception as e:
            print(f"Error in generate_chart_config: {e}")
            return None
    
    return Tool(
        name="data_visualization_suggester",
        func=generate_chart_config,
        description="Analyzes query and result structure to suggest appropriate visualizations. Returns JSON configuration for charts."
    )