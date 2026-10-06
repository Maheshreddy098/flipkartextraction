"""
Custom exceptions for Safexpress integration.

This module defines custom exception classes for better error handling
and more descriptive error messages.
"""


class SafexpressError(Exception):
    """Base exception for all Safexpress-related errors."""
    pass


class SafexpressAuthenticationError(SafexpressError):
    """Raised when authentication with Safexpress API fails."""
    pass


class SafexpressAPIError(SafexpressError):
    """Raised when Safexpress API returns an error response."""
    
    def __init__(self, message: str, status_code: int = None, response_text: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text
    
    def is_retryable(self) -> bool:
        """
        Check if this error should be retried.
        
        Returns:
            True if error is transient and should be retried, False otherwise
        """
        # "No waybill found" is a business logic case, not a transient error
        if "No waybill found" in self.args[0]:
            return False
        # Gateway timeout (504) is retryable
        if self.status_code == 504:
            return True
        # Network errors, timeouts, 5xx errors are retryable
        if self.status_code and self.status_code >= 500:
            return True
        # 4xx errors (except 404) are not retryable
        if self.status_code and 400 <= self.status_code < 500:
            return False
        # Default: retry on unknown errors (might be network issues)
        return True


class SafexpressWaybillNotFoundError(SafexpressAPIError):
    """Raised when waybill is not found for an invoice (business logic, not retryable)."""
    
    def __init__(self, message: str, invoice_number: str = None):
        super().__init__(message, status_code=404)
        self.invoice_number = invoice_number
    
    def is_retryable(self) -> bool:
        """Waybill not found is not retryable."""
        return False


class SafexpressPODNotFoundError(SafexpressError):
    """Raised when POD document is not found for a waybill."""
    pass


class SafexpressDateParsingError(SafexpressError):
    """Raised when delivery date cannot be parsed."""
    pass


class SafexpressSAPIntegrationError(SafexpressError):
    """Raised when SAP B1 integration fails."""
    pass


class SafexpressFileUploadError(SafexpressError):
    """Raised when POD file upload to S3 fails."""
    pass

