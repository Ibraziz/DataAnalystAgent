# schemas.py - Pydantic schemas for structured outputs
from pydantic import BaseModel

class QueryResult(BaseModel):
    """Schema for structured LLM query results."""
    query: str
    description: str
