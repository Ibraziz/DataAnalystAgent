import os

# API Keys
GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]

# Database Configuration
# Get the absolute path to the database file
DATABASE_DIR = os.path.join(os.path.dirname(__file__), "database")
DATABASE_PATH = os.path.join(DATABASE_DIR, "Northwind.db")
DATABASE_URI = f"sqlite:///{DATABASE_PATH}"

# Model Configuration
LLM_MODEL = "gemini-2.0-flash"
LLM_PROVIDER = "google_genai"
EMBEDDING_MODEL = "models/embedding-001"

# Agent Configuration
TOP_K_RESULTS = 5
DIALECT = "SQLite" 