import re
from typing import List, Optional

def extract_column_names(sql_query: str) -> List[str]:
    """Extract column names from SQL SELECT query, handling CTEs, subqueries, and complex syntax."""
    try:
        if not sql_query or not sql_query.strip():
            return []
        
        # Normalize the query
        query = sql_query.strip()
        
        # Find the main/final SELECT statement
        # For CTEs, we want the final SELECT after all WITH clauses
        main_select = _find_main_select(query)
        
        if not main_select:
            return []
        
        # Extract column names from the main SELECT
        columns = _parse_select_columns(main_select)
        
        return columns
    
    except Exception as e:
        print(f"Error extracting column names: {e}")
        return []

def _find_main_select(query: str) -> Optional[str]:
    """Find the main/final SELECT statement in a query, handling CTEs and subqueries."""
    try:
        # Remove comments
        query = re.sub(r'--.*?(?=\n|$)', '', query)
        query = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)
        
        # If it starts with WITH, find the final SELECT after all CTEs
        if query.upper().strip().startswith('WITH'):
            # Find all CTE definitions and the final SELECT
            # Use a simple approach: find the last SELECT that's not inside parentheses at depth 0
            return _find_final_select_after_cte(query)
        else:
            # Regular query - find the first SELECT clause
            select_match = re.search(r'SELECT\s+(.*?)\s+FROM', query, re.IGNORECASE | re.DOTALL)
            if select_match:
                return select_match.group(0)
    
    except Exception:
        pass
    
    return None

def _find_final_select_after_cte(query: str) -> Optional[str]:
    """Find the final SELECT statement after CTE definitions."""
    try:
        # Split by SELECT and track parentheses depth
        parts = re.split(r'\bSELECT\b', query, flags=re.IGNORECASE)
        
        if len(parts) < 2:
            return None
        
        # Find the last SELECT that's at the main level (not in subquery)
        for i in range(len(parts) - 1, 0, -1):
            # Reconstruct the SELECT statement
            before_select = ''.join(parts[:i])
            select_part = parts[i]
            
            # Check if this SELECT is at the main level by counting parentheses
            paren_depth = before_select.count('(') - before_select.count(')')
            
            if paren_depth == 0:
                # This is likely the main SELECT
                from_match = re.search(r'\s+FROM\b', select_part, re.IGNORECASE)
                if from_match:
                    columns_part = select_part[:from_match.start()]
                    return f"SELECT {columns_part} FROM"
        
        return None
    
    except Exception:
        return None

def _parse_select_columns(select_clause: str) -> List[str]:
    """Parse column names from a SELECT clause."""
    try:
        # Extract the columns part between SELECT and FROM
        match = re.search(r'SELECT\s+(.*?)\s+FROM', select_clause, re.IGNORECASE | re.DOTALL)
        
        if not match:
            return []
        
        columns_str = match.group(1).strip()
        
        # Handle SELECT *
        if columns_str.strip() == '*':
            return []
        
        # Split by comma, but be careful about commas inside functions/expressions
        column_parts = _smart_split_columns(columns_str)
        
        columns = []
        for col in column_parts:
            col = col.strip()
            if not col:
                continue
            
            # Extract the column alias or name
            column_name = _extract_column_alias(col)
            if column_name:
                columns.append(column_name)
        
        return columns
    
    except Exception:
        return []

def _smart_split_columns(columns_str: str) -> List[str]:
    """Split columns by comma, respecting parentheses and function calls."""
    try:
        parts = []
        current_part = ""
        paren_depth = 0
        in_quotes = False
        quote_char = None
        
        i = 0
        while i < len(columns_str):
            char = columns_str[i]
            
            # Handle quotes
            if char in ('"', "'", '`') and not in_quotes:
                in_quotes = True
                quote_char = char
                current_part += char
            elif char == quote_char and in_quotes:
                in_quotes = False
                quote_char = None
                current_part += char
            elif in_quotes:
                current_part += char
            # Handle parentheses (only when not in quotes)
            elif char == '(':
                paren_depth += 1
                current_part += char
            elif char == ')':
                paren_depth -= 1
                current_part += char
            # Handle comma (only split when not in quotes and at depth 0)
            elif char == ',' and paren_depth == 0:
                parts.append(current_part.strip())
                current_part = ""
            else:
                current_part += char
            
            i += 1
        
        # Add the last part
        if current_part.strip():
            parts.append(current_part.strip())
        
        return parts
    
    except Exception:
        # Fallback to simple split
        return columns_str.split(',')

def _extract_column_alias(column_expr: str) -> str:
    """Extract the column name/alias from a column expression."""
    try:
        column_expr = column_expr.strip()
        
        # Handle AS keyword (case insensitive)
        as_match = re.search(r'\s+AS\s+(.+)$', column_expr, re.IGNORECASE)
        if as_match:
            alias = as_match.group(1).strip()
            # Remove quotes if present
            alias = alias.strip('"\'`')
            return alias
        
        # Handle implicit alias (space-separated)
        # Look for patterns like "expression alias" but be careful with function calls
        words = column_expr.split()
        if len(words) >= 2:
            # Check if the last word could be an alias
            last_word = words[-1].strip()
            # If the last word doesn't contain operators or special chars, it might be an alias
            if (not re.search(r'[()/*+-=<>]', last_word) and 
                last_word.upper() not in ('AND', 'OR', 'NOT', 'IS', 'NULL', 'LIKE', 'IN') and
                not last_word.startswith('\'') and not last_word.startswith('"')):
                
                # Additional check: make sure it's not part of a function or expression
                before_last = ' '.join(words[:-1])
                if not before_last.endswith('(') and not re.search(r'[()]\s*$', before_last):
                    return last_word.strip('"\'`')
        
        # No explicit alias - try to extract a meaningful name
        # Remove table prefixes
        if '.' in column_expr and not re.search(r'[()/*+-]', column_expr):
            # Simple column reference like "table.column"
            parts = column_expr.split('.')
            return parts[-1].strip('"\'`')
        
        # For complex expressions, try to find a meaningful part
        # Remove common SQL functions and operators to get the core column name
        cleaned = re.sub(r'\b(SUM|COUNT|AVG|MIN|MAX|COALESCE|CASE|WHEN|THEN|ELSE|END)\b', '', column_expr, flags=re.IGNORECASE)
        cleaned = re.sub(r'[()/*+-]', ' ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        # Take the first meaningful word that looks like a column name
        words = cleaned.split()
        for word in words:
            word = word.strip('"\'`')
            if (word and 
                word.upper() not in ('AS', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'IS', 'NULL', 'LIKE', 'IN') and
                not word.isdigit() and
                re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', word)):
                return word
        
        # Fallback: return the original expression (cleaned up)
        fallback = re.sub(r'[()/*+-]', '', column_expr).strip()
        fallback = re.sub(r'\s+', '_', fallback)
        return fallback[:50] if fallback else 'column'
    
    except Exception:
        return 'column' 