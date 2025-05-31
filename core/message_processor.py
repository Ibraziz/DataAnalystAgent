from typing import List, Optional
from langchain_core.messages import AIMessage
import re

class MessageProcessor:
    """Handles processing of agent messages and SQL extraction."""
    
    @staticmethod
    def extract_sql_query(messages: List[AIMessage]) -> str:
        """Extract the SQL query from agent messages."""
        sql_query = ""
        
        # Look through messages to find SQL query tool calls
        for msg in messages:
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                # Look for SQL query tool calls
                for tool_call in msg.tool_calls:
                    if tool_call.get('name') == 'sql_db_query' and 'query' in tool_call.get('args', {}):
                        sql_query = tool_call['args']['query']
                        # Return the last (most recent) SQL query found
                        # This ensures we get the final working query if the agent tried multiple times
        
        return sql_query
    
    @staticmethod
    def extract_description(text: str) -> str:
        """Extract a meaningful description from the agent response."""
        # Remove SQL code blocks
        cleaned_text = re.sub(r'```sql.*?```', '', text, flags=re.DOTALL | re.IGNORECASE)
        cleaned_text = re.sub(r'```.*?```', '', cleaned_text, flags=re.DOTALL)
        
        # Remove tool calls and internal processing
        cleaned_text = re.sub(r'Calling tool:.*?with args:.*?\n', '', cleaned_text, flags=re.DOTALL)
        cleaned_text = re.sub(r'Tool.*?returned:.*?\n', '', cleaned_text, flags=re.DOTALL)
        
        # Get the meaningful parts
        lines = cleaned_text.split('\n')
        meaningful_lines = []
        
        for line in lines:
            line = line.strip()
            # Skip empty lines, debug info, and tool calls
            if (line and 
                not line.startswith('Calling tool') and 
                not line.startswith('Tool') and
                not line.startswith('```') and
                len(line) > 10):
                meaningful_lines.append(line)
        
        # Join and limit to reasonable length
        description = ' '.join(meaningful_lines)
        if len(description) > 500:
            description = description[:500] + "..."
        
        return description if description else "Query executed successfully"
    
    @staticmethod
    def get_final_response(messages: List[AIMessage]) -> Optional[str]:
        """Get the final response from the agent's messages."""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content and msg.content.strip():
                # Check if this is a final response (not just a tool call)
                if not hasattr(msg, 'tool_calls') or not msg.tool_calls:
                    return msg.content.strip()
        return None 