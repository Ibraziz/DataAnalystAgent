import os

# API Keys
GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]

# Database Configuration
# Get the absolute path to the database directory
DATABASE_DIR = os.path.join(os.path.dirname(__file__), "database")

# Available databases
AVAILABLE_DATABASES = {
    "northwind": "Northwind.db",
    "chinook": "Chinook.db"
}

# Default database
DEFAULT_DATABASE = "northwind"

def get_database_path(database_name):
    """Get the full path for a database file."""
    if database_name not in AVAILABLE_DATABASES:
        database_name = DEFAULT_DATABASE
    filename = AVAILABLE_DATABASES[database_name]
    return os.path.join(DATABASE_DIR, filename)

def get_database_uri(database_name):
    """Get the database URI for a given database name."""
    path = get_database_path(database_name)
    return f"sqlite:///{path}"

# Legacy support - use default database
DATABASE_PATH = get_database_path(DEFAULT_DATABASE)
DATABASE_URI = get_database_uri(DEFAULT_DATABASE)

# Model Configuration
LLM_MODEL = "gemini-2.0-flash"
LLM_PROVIDER = "google_genai"

# Agent Configuration
TOP_K_RESULTS = 5
DIALECT = "SQLite"
RECURSION_LIMIT = 50  # Default recursion limit for LangGraph agents