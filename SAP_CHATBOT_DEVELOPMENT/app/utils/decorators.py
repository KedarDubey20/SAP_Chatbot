"""
Decorators - Reusable function decorators
"""
import time
import functools
from typing import Callable, Any
from loguru import logger


def timer(func: Callable) -> Callable:
    """
    Decorator to measure function execution time
    
    Usage:
        @timer
        def my_function():
            ...
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        
        logger.debug(f"⏱️ {func.__name__} took {duration:.3f}s")
        
        return result
    
    return wrapper


def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Decorator to retry function on failure
    
    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay between retries (seconds)
        backoff: Multiplier for delay after each attempt
    
    Usage:
        @retry(max_attempts=3, delay=1.0)
        def unstable_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts:
                        logger.error(
                            f"❌ {func.__name__} failed after {max_attempts} attempts"
                        )
                        raise
                    
                    logger.warning(
                        f"⚠️ {func.__name__} attempt {attempt} failed: {e}. "
                        f"Retrying in {current_delay}s..."
                    )
                    
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            return None
        
        return wrapper
    
    return decorator


def cache_result(ttl: int = 3600):
    """
    Decorator to cache function results
    
    Args:
        ttl: Time to live in seconds
    
    Usage:
        @cache_result(ttl=3600)
        def expensive_function(arg):
            ...
    """
    def decorator(func: Callable) -> Callable:
        cache = {}
        cache_times = {}
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from args
            key = str(args) + str(kwargs)
            current_time = time.time()
            
            # Check if cached and not expired
            if key in cache:
                if current_time - cache_times[key] < ttl:
                    logger.debug(f"💾 Cache hit for {func.__name__}")
                    return cache[key]
            
            # Execute and cache
            result = func(*args, **kwargs)
            cache[key] = result
            cache_times[key] = current_time
            
            return result
        
        return wrapper
    
    return decorator


def log_execution(level: str = "INFO"):
    """
    Decorator to log function execution
    
    Args:
        level: Log level (INFO, DEBUG, WARNING, ERROR)
    
    Usage:
        @log_execution(level="INFO")
        def my_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger.log(level, f"▶️ Executing {func.__name__}")
            
            try:
                result = func(*args, **kwargs)
                logger.log(level, f"✓ {func.__name__} completed successfully")
                return result
            except Exception as e:
                logger.error(f"❌ {func.__name__} failed: {e}")
                raise
        
        return wrapper
    
    return decorator


def validate_args(**validators):
    """
    Decorator to validate function arguments
    
    Args:
        **validators: Dict of arg_name -> validator_function
    
    Usage:
        @validate_args(name=lambda x: len(x) > 0, age=lambda x: x > 0)
        def create_user(name, age):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get function signature
            import inspect
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # Validate each argument
            for arg_name, validator in validators.items():
                if arg_name in bound_args.arguments:
                    value = bound_args.arguments[arg_name]
                    if not validator(value):
                        raise ValueError(
                            f"Validation failed for argument '{arg_name}': {value}"
                        )
            
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def async_timer(func: Callable) -> Callable:
    """
    Decorator to measure async function execution time
    
    Usage:
        @async_timer
        async def my_async_function():
            ...
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        duration = time.time() - start
        
        logger.debug(f"⏱️ {func.__name__} took {duration:.3f}s")
        
        return result
    
    return wrapper


def deprecated(message: str = "This function is deprecated"):
    """
    Decorator to mark function as deprecated
    
    Args:
        message: Deprecation message
    
    Usage:
        @deprecated("Use new_function() instead")
        def old_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger.warning(
                f"⚠️ {func.__name__} is deprecated: {message}"
            )
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def singleton(cls):
    """
    Decorator to make a class a singleton
    
    Usage:
        @singleton
        class MyClass:
            ...
    """
    instances = {}
    
    @functools.wraps(cls)
    def wrapper(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    
    return wrapper
