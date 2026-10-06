"""
Utility functions for Safexpress integration.

This module contains helper functions for date parsing, retry logic,
and other common operations.
"""

import logging
import time
from datetime import datetime
from typing import Callable, Any, Optional, TypeVar
from functools import wraps

from .config import DATE_FORMATS
from .exceptions import SafexpressDateParsingError

logger = logging.getLogger(__name__)

T = TypeVar('T')


def parse_delivery_date(date_string: str) -> str:
    """
    Parse delivery date from Safexpress API response.
    
    Tries multiple date formats to handle different Safexpress date formats.
    
    Args:
        date_string: Raw date string from API response
        
    Returns:
        Formatted date string in YYYY-MM-DD format
        
    Raises:
        SafexpressDateParsingError: If date cannot be parsed with any format
    """
    if not date_string:
        raise SafexpressDateParsingError("Empty date string provided")
    
    date_string = date_string.strip()
    
    for date_format in DATE_FORMATS:
        try:
            parsed_date = datetime.strptime(date_string, date_format)
            return parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    raise SafexpressDateParsingError(
        f"Could not parse date '{date_string}' with any known format"
    )


def retry_with_backoff(
    max_attempts: int = 3,
    delay: float = 2.0,
    backoff_multiplier: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying function calls with exponential backoff.
    
    Only retries on retryable exceptions (transient errors).
    Business logic errors (like "waybill not found") are not retried.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay in seconds
        backoff_multiplier: Multiplier for exponential backoff
        exceptions: Tuple of exceptions to catch and retry on
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    # Check if exception is retryable
                    # Business logic errors (like waybill not found) should not be retried
                    if hasattr(e, 'is_retryable') and not e.is_retryable():
                        logger.debug(
                            f"Non-retryable error for {func.__name__}: {str(e)}. "
                            f"Skipping retry."
                        )
                        raise
                    
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {str(e)}. "
                            f"Retrying in {current_delay}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff_multiplier
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed for {func.__name__}: {str(e)}"
                        )
            
            raise last_exception
        return wrapper
    return decorator


def format_invoice_number(series_name: str, doc_number: str) -> str:
    """
    Format invoice number for Safexpress API.
    
    Args:
        series_name: Invoice series name (e.g., "KAIN24") or empty string
        doc_number: Document number
        
    Returns:
        Formatted invoice number (e.g., "KAIN24/12345")
        
    Note:
        If series_name is empty, returns just the doc_number.
        This should not happen in normal flow as empty series_name
        should trigger trying all prefixes before formatting.
    """
    if not series_name or series_name.strip() == "":
        # This shouldn't happen, but handle gracefully
        return doc_number
    return f"{series_name}/{doc_number}"


def truncate_error_message(message: str, max_length: int = 140) -> str:
    """
    Truncate error message to fit Frappe error log title limit.
    
    Args:
        message: Error message to truncate
        max_length: Maximum length (default 140 for Frappe)
        
    Returns:
        Truncated message
    """
    if len(message) <= max_length:
        return message
    return message[:max_length - 3] + "..."


def validate_docentry(docentry: Any) -> str:
    """
    Validate and convert docentry to string.
    
    Args:
        docentry: Document entry (can be string, int, etc.)
        
    Returns:
        String representation of docentry
        
    Raises:
        ValueError: If docentry is None or empty
    """
    if docentry is None:
        raise ValueError("DocEntry cannot be None")
    
    docentry_str = str(docentry).strip()
    if not docentry_str:
        raise ValueError("DocEntry cannot be empty")
    
    return docentry_str


def get_invoice_series_variants(series_name: str) -> list[str]:
    """
    Get possible variants of invoice series name for API calls.
    
    Args:
        series_name: Original series name
        
    Returns:
        List of possible series name variants (upper, lower, original)
    """
    variants = [series_name]
    
    upper = series_name.upper()
    lower = series_name.lower()
    
    if upper not in variants:
        variants.append(upper)
    if lower not in variants:
        variants.append(lower)
    
    return variants

