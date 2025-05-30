from langchain_community.utilities import SQLDatabase
from langchain.chat_models import init_chat_model
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore
from config import (
    GOOGLE_API_KEY,
    DATABASE_URI,
    LLM_MODEL,
    LLM_PROVIDER,
    EMBEDDING_MODEL
)

# Initialize LLM
llm = init_chat_model(LLM_MODEL, model_provider=LLM_PROVIDER)

# Initialize embeddings and vector store
embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)
vector_store = InMemoryVectorStore(embeddings)

# Initialize database
db = SQLDatabase.from_uri(DATABASE_URI) 