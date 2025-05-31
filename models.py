from langchain_community.utilities import SQLDatabase
from langchain.chat_models import init_chat_model
from schemas import QueryResult
from config import (
    DATABASE_URI,
    LLM_MODEL,
    LLM_PROVIDER,
    get_database_uri
)

# Initialize base LLM for tools
llm = init_chat_model(LLM_MODEL, model_provider=LLM_PROVIDER)

# Initialize structured LLM for final responses
structured_llm = llm.with_structured_output(QueryResult)

# Initialize default database
db = SQLDatabase.from_uri(DATABASE_URI)

def get_database_connection(database_name):
    """Get a database connection for the specified database."""
    database_uri = get_database_uri(database_name)
    return SQLDatabase.from_uri(database_uri)
