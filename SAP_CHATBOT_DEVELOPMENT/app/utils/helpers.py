"""
Helper Functions - General utility functions
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
import hashlib
import json


def clean_table_name(filename: str) -> str:
    """
    Clean filename to extract table name
    
    Args:
        filename: Excel filename (e.g., "CSV Dump VBAK Header data.XLSX")
        
    Returns:
        Clean table name (e.g., "vbak")
    """
    # Remove file extension
    name = filename.replace('.xlsx', '').replace('.XLSX', '').replace('.csv', '').replace('.CSV', '')
    
    # Remove common prefixes
    name = name.replace('CSV Dump', '').replace('CSV_Dump', '').replace('Dump', '')
    name = name.replace('csv_dump_', '').replace('csv_', '')
    
    # Clean spaces and special chars
    name = name.strip().lower()
    name = name.replace(' ', '_').replace('-', '_').replace('.', '_')
    
    # Remove trailing underscores
    name = name.strip('_')
    
    return name


def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format datetime for display
    
    Args:
        dt: Datetime object
        format_str: Format string
        
    Returns:
        Formatted datetime string
    """
    return dt.strftime(format_str)


def format_file_size(bytes: int) -> str:
    """
    Format file size in human-readable format
    
    Args:
        bytes: File size in bytes
        
    Returns:
        Formatted size (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.1f} PB"


def generate_hash(data: str) -> str:
    """
    Generate MD5 hash of string
    
    Args:
        data: String to hash
        
    Returns:
        MD5 hash
    """
    return hashlib.md5(data.encode()).hexdigest()


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate string to max length
    
    Args:
        text: String to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def safe_get(dictionary: Dict, *keys, default=None) -> Any:
    """
    Safely get nested dictionary value
    
    Args:
        dictionary: Dict to search
        *keys: Keys to traverse
        default: Default value if not found
        
    Returns:
        Value or default
        
    Example:
        safe_get(data, 'user', 'profile', 'name', default='Unknown')
    """
    result = dictionary
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key)
            if result is None:
                return default
        else:
            return default
    return result


def merge_dicts(*dicts: Dict) -> Dict:
    """
    Merge multiple dictionaries
    
    Args:
        *dicts: Dictionaries to merge
        
    Returns:
        Merged dictionary
    """
    result = {}
    for d in dicts:
        result.update(d)
    return result


def remove_none_values(dictionary: Dict) -> Dict:
    """
    Remove keys with None values from dict
    
    Args:
        dictionary: Input dict
        
    Returns:
        Dict without None values
    """
    return {k: v for k, v in dictionary.items() if v is not None}


def chunk_list(lst: List, chunk_size: int) -> List[List]:
    """
    Split list into chunks
    
    Args:
        lst: List to chunk
        chunk_size: Size of each chunk
        
    Returns:
        List of chunks
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def flatten_dict(d: Dict, parent_key: str = '', sep: str = '.') -> Dict:
    """
    Flatten nested dictionary
    
    Args:
        d: Dictionary to flatten
        parent_key: Parent key prefix
        sep: Separator
        
    Returns:
        Flattened dictionary
        
    Example:
        {'a': {'b': 1}} -> {'a.b': 1}
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def parse_bool(value: Any) -> bool:
    """
    Parse boolean from various formats
    
    Args:
        value: Value to parse
        
    Returns:
        Boolean value
    """
    if isinstance(value, bool):
        return value
    
    if isinstance(value, str):
        return value.lower() in ('true', 'yes', '1', 'on', 'enabled')
    
    return bool(value)


def ensure_list(value: Any) -> List:
    """
    Ensure value is a list
    
    Args:
        value: Value to convert
        
    Returns:
        List
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
