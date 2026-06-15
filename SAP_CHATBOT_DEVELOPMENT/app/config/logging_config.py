"""
Logging Configuration
Centralized logging setup using loguru
"""
from loguru import logger
import sys
from pathlib import Path


def setup_logging(
    log_level: str = "INFO",
    log_to_file: bool = True,
    log_file: str = "logs/sap_assistant.log"
):
    """
    Configure application logging
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_to_file: Whether to log to file
        log_file: Log file path
    """
    # Remove default logger
    logger.remove()
    
    # Console logging with colors
    logger.add(
        sys.stdout,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        level=log_level,
        colorize=True
    )
    
    # File logging (if enabled)
    if log_to_file:
        # Create logs directory
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.add(
            log_file,
            format=(
                "{time:YYYY-MM-DD HH:mm:ss} | "
                "{level: <8} | "
                "{name}:{function}:{line} | "
                "{message}"
            ),
            level=log_level,
            rotation="100 MB",  # Rotate when file reaches 100MB
            retention="30 days",  # Keep logs for 30 days
            compression="zip",  # Compress rotated logs
            enqueue=True  # Async logging
        )
        
        logger.info(f"✓ Logging to file: {log_file}")
    
    logger.info(f"✓ Logging configured: Level={log_level}")


def get_logger(name: str):
    """
    Get a logger instance with a specific name
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Logger instance
    """
    return logger.bind(name=name)
