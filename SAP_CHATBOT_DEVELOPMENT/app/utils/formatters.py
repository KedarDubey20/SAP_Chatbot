"""
Formatters - Response and data formatting utilities
"""
from typing import Any, Dict, List, Optional
import json
from datetime import datetime, date
from decimal import Decimal


def format_response(
    success: bool,
    data: Any = None,
    message: str = None,
    error: str = None,
    **kwargs
) -> Dict:
    """
    Format standard API response
    
    Args:
        success: Whether operation succeeded
        data: Response data
        message: Success message
        error: Error message
        **kwargs: Additional fields
        
    Returns:
        Formatted response dict
    """
    response = {
        "success": success,
        "timestamp": datetime.now().isoformat()
    }
    
    if data is not None:
        response["data"] = data
    
    if message:
        response["message"] = message
    
    if error:
        response["error"] = error
    
    response.update(kwargs)
    
    return response


def format_error_response(
    error: str,
    status_code: int = 500,
    details: Optional[Dict] = None
) -> Dict:
    """
    Format error response
    
    Args:
        error: Error message
        status_code: HTTP status code
        details: Additional error details
        
    Returns:
        Formatted error response
    """
    response = {
        "success": False,
        "error": error,
        "status_code": status_code,
        "timestamp": datetime.now().isoformat()
    }
    
    if details:
        response["details"] = details
    
    return response


def format_sql_results(
    results: List[Dict],
    include_metadata: bool = True
) -> Dict:
    """
    Format SQL query results
    
    Args:
        results: Query results
        include_metadata: Whether to include metadata
        
    Returns:
        Formatted results
    """
    response = {
        "results": results,
        "count": len(results)
    }
    
    if include_metadata and results:
        response["columns"] = list(results[0].keys())
        response["column_count"] = len(results[0])
    
    return response


def format_table_summary(
    table_name: str,
    record_count: int,
    columns: List[str],
    data_types: Optional[Dict[str, str]] = None
) -> Dict:
    """
    Format table summary
    
    Args:
        table_name: Table name
        record_count: Number of records
        columns: List of column names
        data_types: Optional column data types
        
    Returns:
        Formatted summary
    """
    summary = {
        "table": table_name,
        "records": record_count,
        "columns": columns,
        "column_count": len(columns)
    }
    
    if data_types:
        summary["data_types"] = data_types
    
    return summary


def format_currency(
    amount: float,
    currency: str = "USD",
    locale: str = "en_US"
) -> str:
    """
    Format currency value
    
    Args:
        amount: Amount to format
        currency: Currency code
        locale: Locale for formatting
        
    Returns:
        Formatted currency string
    """
    # Simple formatting (could use babel for production)
    if currency == "USD":
        return f"${amount:,.2f}"
    elif currency == "EUR":
        return f"€{amount:,.2f}"
    else:
        return f"{amount:,.2f} {currency}"


def format_number(
    value: float,
    decimals: int = 2,
    use_thousands_separator: bool = True
) -> str:
    """
    Format number with thousands separator
    
    Args:
        value: Number to format
        decimals: Number of decimal places
        use_thousands_separator: Whether to use comma separator
        
    Returns:
        Formatted number string
    """
    if use_thousands_separator:
        return f"{value:,.{decimals}f}"
    else:
        return f"{value:.{decimals}f}"


def format_percentage(value: float, decimals: int = 1) -> str:
    """
    Format percentage value
    
    Args:
        value: Value to format (e.g., 0.25 for 25%)
        decimals: Decimal places
        
    Returns:
        Formatted percentage string
    """
    return f"{value * 100:.{decimals}f}%"


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable format
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted duration (e.g., "2h 30m 15s")
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    
    minutes = int(seconds // 60)
    remaining_seconds = seconds % 60
    
    if minutes < 60:
        return f"{minutes}m {remaining_seconds:.0f}s"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    return f"{hours}h {remaining_minutes}m"


def format_json(
    data: Any,
    pretty: bool = True,
    sort_keys: bool = False
) -> str:
    """
    Format data as JSON string
    
    Args:
        data: Data to format
        pretty: Whether to pretty-print
        sort_keys: Whether to sort keys
        
    Returns:
        JSON string
    """
    def default_serializer(obj):
        """Handle special types"""
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return str(obj)
    
    if pretty:
        return json.dumps(
            data,
            indent=2,
            sort_keys=sort_keys,
            default=default_serializer
        )
    else:
        return json.dumps(
            data,
            sort_keys=sort_keys,
            default=default_serializer
        )


def format_list_as_string(
    items: List[str],
    separator: str = ", ",
    last_separator: str = " and "
) -> str:
    """
    Format list as human-readable string
    
    Args:
        items: List of items
        separator: Separator for items
        last_separator: Separator for last item
        
    Returns:
        Formatted string
        
    Example:
        ['a', 'b', 'c'] -> "a, b and c"
    """
    if not items:
        return ""
    
    if len(items) == 1:
        return items[0]
    
    if len(items) == 2:
        return f"{items[0]}{last_separator}{items[1]}"
    
    return separator.join(items[:-1]) + last_separator + items[-1]


def format_bytes(bytes: int, precision: int = 2) -> str:
    """
    Format bytes in human-readable format
    
    Args:
        bytes: Number of bytes
        precision: Decimal precision
        
    Returns:
        Formatted size (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if bytes < 1024.0:
            return f"{bytes:.{precision}f} {unit}"
        bytes /= 1024.0
    
    return f"{bytes:.{precision}f} EB"


def truncate_text(
    text: str,
    max_length: int = 100,
    ellipsis: str = "..."
) -> str:
    """
    Truncate text to max length
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        ellipsis: String to append if truncated
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(ellipsis)] + ellipsis
