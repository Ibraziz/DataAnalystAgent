import os

# API Keys
GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]

# Database Configuration
DATABASE_URI = "sqlite:///database/Northwind.db"

# Model Configuration
LLM_MODEL = "gemini-2.0-flash"
LLM_PROVIDER = "google_genai"
EMBEDDING_MODEL = "models/embedding-001"

# Agent Configuration
TOP_K_RESULTS = 5
DIALECT = "SQLite" 