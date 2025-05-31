import ast
import re
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain.agents.agent_toolkits import create_retriever_tool
from models import db, llm, vector_store

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