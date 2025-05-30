from typing_extensions import TypedDict

class State(TypedDict):
    """Type definition for the agent's state."""
    question: str
    query: str
    result: str
    answer: str 