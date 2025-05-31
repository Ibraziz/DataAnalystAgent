from langchain_community.utilities import SQLDatabase
from langchain.chat_models import init_chat_model
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore
from schemas import QueryResult
from config import (
    DATABASE_URI,
    LLM_MODEL,
    LLM_PROVIDER,
    EMBEDDING_MODEL
)

# Initialize base LLM for tools
llm = init_chat_model(LLM_MODEL, model_provider=LLM_PROVIDER)

# Initialize structured LLM for final responses
structured_llm = llm.with_structured_output(QueryResult)

# Initialize embeddings and vector store
embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)
vector_store = InMemoryVectorStore(embeddings)

# Initialize database
db = SQLDatabase.from_uri(DATABASE_URI) 