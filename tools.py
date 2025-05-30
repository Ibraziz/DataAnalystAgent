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

def get_sql_tools():
    """Get SQL database tools."""
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    return toolkit.get_tools()

def create_proper_noun_tool():
    """Create a retriever tool for proper noun lookups."""
    # Example usage of proper noun tool (commented out as it requires specific data)
    # artists = query_as_list(db, "SELECT Name FROM Artist")
    # albums = query_as_list(db, "SELECT Title FROM Album")
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