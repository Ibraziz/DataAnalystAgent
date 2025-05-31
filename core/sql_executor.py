from typing import List, Dict, Any, Optional
from models import get_database_connection
from utils.sql_parser import extract_column_names

class SQLExecutor:
    """Handles SQL query execution and result processing."""
    
    def __init__(self, database_connection=None):
        """Initialize with optional database connection."""
        self.db = database_connection if database_connection else get_database_connection(None)
    
    def execute_query(self, sql_query: str) -> List[Dict[str, Any]]:
        """Execute SQL query and return data as list of dictionaries."""
        try:
            if not sql_query.strip():
                return []
            
            result = self.db.run(sql_query)
            
            # Handle different result types
            if result is None:
                return []
                
            # If result is already a list of dictionaries, return it
            if isinstance(result, list) and result and isinstance(result[0], dict):
                return result
                
            # If result is a string representation of a list, parse it
            if isinstance(result, str):
                try:
                    import ast
                    parsed_result = ast.literal_eval(result)
                    
                    if isinstance(parsed_result, list):
                        # Get column names from the query
                        column_names = extract_column_names(sql_query)
                        
                        # Convert to list of dictionaries
                        data = []
                        for row in parsed_result:
                            if isinstance(row, (list, tuple)) and column_names:
                                row_dict = {}
                                for i, col_name in enumerate(column_names):
                                    if i < len(row):
                                        row_dict[col_name] = row[i]
                                data.append(row_dict)
                            elif isinstance(row, dict):
                                data.append(row)
                        
                        return data
                except (ValueError, SyntaxError):
                    pass
            
            # If result is a list of tuples, convert it
            if isinstance(result, list) and result and isinstance(result[0], (list, tuple)):
                column_names = extract_column_names(sql_query)
                
                # If no column names found, create generic ones
                if not column_names:
                    column_names = [f'Column_{i+1}' for i in range(len(result[0]))]
                
                data = []
                for row in result:
                    row_dict = {}
                    for i, col_name in enumerate(column_names):
                        if i < len(row):
                            row_dict[col_name] = row[i]
                    data.append(row_dict)
                
                return data
            
            return []
        
        except Exception as e:
            print(f"Error executing SQL query: {e}")
            return []
    
    def get_column_names(self, sql_query: str) -> List[str]:
        """Get column names from a SQL query."""
        return extract_column_names(sql_query) 