"""
Validators - Input validation utilities
"""
import re
from typing import Optional, List
from datetime import datetime


def validate_sql(sql: str) -> tuple[bool, Optional[str]]:
    """
    Validate SQL query for safety
    
    Args:
        sql: SQL query string
        
    Returns:
        (is_valid, error_message)
    """
    # Block dangerous operations
    dangerous_keywords = [
        'DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE',
        'INSERT', 'UPDATE', 'GRANT', 'REVOKE'
    ]
    
    sql_upper = sql.upper()
    
    for keyword in dangerous_keywords:
        if re.search(rf'\b{keyword}\b', sql_upper):
            return False, f"Dangerous operation detected: {keyword}"
    
    # Check for comments (potential SQL injection)
    if '--' in sql or '/*' in sql:
        return False, "SQL comments not allowed"
    
    # Must be a SELECT query
    if not sql_upper.strip().startswith('SELECT'):
        return False, "Only SELECT queries allowed"
    
    return True, None


def validate_table_name(table_name: str) -> tuple[bool, Optional[str]]:
    """
    Validate table name format
    
    Args:
        table_name: Table name to validate
        
    Returns:
        (is_valid, error_message)
    """
    # Allow only alphanumeric and underscores
    if not re.match(r'^[a-zA-Z0-9_]+$', table_name):
        return False, "Table name can only contain letters, numbers, and underscores"
    
    # Check length
    if len(table_name) > 64:
        return False, "Table name too long (max 64 characters)"
    
    if len(table_name) < 1:
        return False, "Table name cannot be empty"
    
    return True, None


def validate_order_id(order_id: int) -> tuple[bool, Optional[str]]:
    """
    Validate SAP order ID
    
    Args:
        order_id: Order ID to validate
        
    Returns:
        (is_valid, error_message)
    """
    if not isinstance(order_id, int):
        return False, "Order ID must be an integer"
    
    if order_id <= 0:
        return False, "Order ID must be positive"
    
    if order_id > 9999999999:
        return False, "Order ID too large"
    
    return True, None


def validate_query_string(query: str, max_length: int = 500) -> tuple[bool, Optional[str]]:
    """
    Validate natural language query
    
    Args:
        query: Query string
        max_length: Maximum allowed length
        
    Returns:
        (is_valid, error_message)
    """
    if not query or not query.strip():
        return False, "Query cannot be empty"
    
    if len(query) > max_length:
        return False, f"Query too long (max {max_length} characters)"
    
    # Check for suspicious patterns
    suspicious_patterns = [
        r'<script',
        r'javascript:',
        r'eval\(',
        r'exec\(',
    ]
    
    query_lower = query.lower()
    for pattern in suspicious_patterns:
        if re.search(pattern, query_lower):
            return False, "Query contains suspicious content"
    
    return True, None


def validate_api_key(api_key: str) -> tuple[bool, Optional[str]]:
    """
    Validate API key format
    
    Args:
        api_key: API key to validate
        
    Returns:
        (is_valid, error_message)
    """
    if not api_key:
        return False, "API key cannot be empty"
    
    # Should be at least 16 characters
    if len(api_key) < 16:
        return False, "API key too short"
    
    # Should not contain spaces
    if ' ' in api_key:
        return False, "API key cannot contain spaces"
    
    return True, None


def validate_date_range(
    start_date: Optional[str],
    end_date: Optional[str],
    date_format: str = "%Y-%m-%d"
) -> tuple[bool, Optional[str]]:
    """
    Validate date range
    
    Args:
        start_date: Start date string
        end_date: End date string
        date_format: Expected date format
        
    Returns:
        (is_valid, error_message)
    """
    try:
        if start_date:
            start = datetime.strptime(start_date, date_format)
        else:
            start = None
        
        if end_date:
            end = datetime.strptime(end_date, date_format)
        else:
            end = None
        
        if start and end and start > end:
            return False, "Start date must be before end date"
        
        return True, None
        
    except ValueError as e:
        return False, f"Invalid date format: {str(e)}"


def validate_limit(limit: int, max_limit: int = 1000) -> tuple[bool, Optional[str]]:
    """
    Validate result limit parameter
    
    Args:
        limit: Requested limit
        max_limit: Maximum allowed limit
        
    Returns:
        (is_valid, error_message)
    """
    if not isinstance(limit, int):
        return False, "Limit must be an integer"
    
    if limit <= 0:
        return False, "Limit must be positive"
    
    if limit > max_limit:
        return False, f"Limit too large (max {max_limit})"
    
    return True, None


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal
    
    Args:
        filename: Filename to sanitize
        
    Returns:
        Safe filename
    """
    # Remove path separators
    filename = filename.replace('/', '_').replace('\\', '_')
    
    # Remove parent directory references
    filename = filename.replace('..', '')
    
    # Remove special characters
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    
    return filename


def validate_email(email: str) -> tuple[bool, Optional[str]]:
    """
    Validate email format
    
    Args:
        email: Email address
        
    Returns:
        (is_valid, error_message)
    """
    # Simple email regex
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(pattern, email):
        return False, "Invalid email format"
    
    return True, None
