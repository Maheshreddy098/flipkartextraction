"""
Safexpress API Client

Handles all HTTP communication with Safexpress API endpoints.
Provides a clean interface for tracking and POD operations.
"""

import logging
import requests
from typing import Dict, Any, Optional

from .config import (
    SAFEXPRESS_TRACKING_API_URL,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_POD_FETCH_TIMEOUT_SECONDS,
    DOC_TYPE_INVOICE,
    DOC_TYPE_WAYBILL,
    INVOICE_SERIES_PREFIXES,
)
from .exceptions import (
    SafexpressAPIError,
    SafexpressPODNotFoundError,
    SafexpressWaybillNotFoundError,
)
from .utils import retry_with_backoff, format_invoice_number, get_invoice_series_variants

logger = logging.getLogger(__name__)


class SafexpressAPIClient:
    """
    Client for interacting with Safexpress API.
    
    Handles all HTTP requests to Safexpress endpoints with proper
    error handling and retry logic.
    """
    
    def __init__(self, auth_headers: Dict[str, str]):
        """
        Initialize API client with authentication headers.
        
        Args:
            auth_headers: Dictionary containing authentication headers
        """
        self.auth_headers = auth_headers
        self.base_headers = {
            "Accept": "*/*",
            "User-Agent": "Khanal Tech",
            "Content-Type": "application/json",
        }
    
    @retry_with_backoff(max_attempts=3, delay=2.0)
    def get_tracking_by_invoice(
        self,
        series_name: str,
        invoice_number: str
    ) -> Dict[str, Any]:
        """
        Get tracking information by invoice number.
        
        Tries multiple series name variants (upper, lower, original)
        to find matching waybill. If series_name is empty, tries all
        configured prefixes.
        
        Args:
            series_name: Invoice series name (e.g., "KAIN24") or empty string
            invoice_number: Invoice document number
            
        Returns:
            Tracking information dictionary containing waybill and shipment details
            
        Raises:
            SafexpressAPIError: If API request fails
        """
        # If series_name is empty, try all configured prefixes
        if not series_name or series_name.strip() == "":
            logger.debug(
                f"No series_name provided for invoice {invoice_number}, "
                f"trying all configured prefixes"
            )
            series_variants = INVOICE_SERIES_PREFIXES
        else:
            # Get variants of the provided series_name
            series_variants = get_invoice_series_variants(series_name)
        
        for variant in series_variants:
            try:
                formatted_invoice = format_invoice_number(variant, invoice_number)
                payload = {
                    "docNo": formatted_invoice,
                    "docType": DOC_TYPE_INVOICE,
                }
                
                logger.debug(
                    f"Requesting tracking for invoice: {formatted_invoice}"
                )
                
                response = requests.post(
                    SAFEXPRESS_TRACKING_API_URL,
                    headers=self.base_headers,
                    json=payload,
                    timeout=DEFAULT_TIMEOUT_SECONDS,
                    verify=False,
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Check if waybill exists in response
                    if result.get("shipment") and result["shipment"].get("waybill"):
                        logger.info(
                            f"Found waybill for invoice {formatted_invoice}: "
                            f"{result['shipment']['waybill']}"
                        )
                        # Add the successful series variant to the result for filename generation
                        result["_successful_series"] = variant
                        return result
                    else:
                        logger.debug(
                            f"No waybill found for invoice {formatted_invoice} "
                            f"with series variant {variant}"
                        )
                else:
                    logger.warning(
                        f"API returned status {response.status_code} for "
                        f"invoice {formatted_invoice}: {response.text}"
                    )
                    
            except requests.exceptions.RequestException as e:
                logger.warning(
                    f"Request failed for invoice {formatted_invoice} "
                    f"with variant {variant}: {str(e)}"
                )
                continue
        
        # No waybill found with any variant - this is a business logic case, not an error
        if series_name:
            error_msg = f"No waybill found for invoice {series_name}/{invoice_number}"
        else:
            error_msg = f"No waybill found for invoice {invoice_number} (tried all prefixes: {', '.join(INVOICE_SERIES_PREFIXES[:5])}...)"
        
        raise SafexpressWaybillNotFoundError(
            error_msg,
            invoice_number=invoice_number,
        )
    
    @retry_with_backoff(max_attempts=3, delay=2.0)
    def get_tracking_by_waybill(self, waybill_number: str) -> Dict[str, Any]:
        """
        Get tracking information by waybill number.
        
        Args:
            waybill_number: Safexpress waybill number
            
        Returns:
            Tracking information dictionary
            
        Raises:
            SafexpressAPIError: If API request fails
        """
        payload = {
            "docNo": waybill_number,
            "docType": DOC_TYPE_WAYBILL,
        }
        
        logger.debug(f"Requesting tracking for waybill: {waybill_number}")
        
        try:
            response = requests.post(
                SAFEXPRESS_TRACKING_API_URL,
                headers=self.base_headers,
                json=payload,
                timeout=DEFAULT_TIMEOUT_SECONDS,
                verify=False,
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Check for invalid request
            if (
                result.get("shipment")
                and result["shipment"].get("message") == "Invalid Request"
            ):
                raise SafexpressAPIError(
                    f"Invalid waybill number: {waybill_number}",
                    status_code=400,
                )
            
            logger.info(f"Retrieved tracking for waybill: {waybill_number}")
            return result
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to get tracking for waybill {waybill_number}: {str(e)}"
            logger.error(error_msg)
            raise SafexpressAPIError(error_msg) from e
    
    @retry_with_backoff(max_attempts=3, delay=2.0)
    def get_pod_document(self, waybill_number: str, pod_url: str) -> bytes:
        """
        Get POD document (TIFF image) for a waybill.
        
        Args:
            waybill_number: Safexpress waybill number
            pod_url: Base POD API URL from settings
            
        Returns:
            POD document as bytes (TIFF image)
            
        Raises:
            SafexpressPODNotFoundError: If POD not found
            SafexpressAPIError: If API request fails
        """
        full_url = f"{pod_url}{waybill_number}"
        
        logger.debug(f"Requesting POD document for waybill: {waybill_number}")
        
        try:
            # Use longer timeout for POD API as it can be slow
            response = requests.get(
                full_url,
                headers=self.auth_headers,
                timeout=DEFAULT_POD_FETCH_TIMEOUT_SECONDS,
                verify=False,
            )
            
            if response.status_code == 404:
                raise SafexpressPODNotFoundError(
                    f"POD not found for waybill: {waybill_number}"
                )
            
            response.raise_for_status()
            result = response.json()
            
            # Extract base64 encoded POD
            if (
                not result.get("data")
                or not result["data"].get("base64String")
                or result["data"]["base64String"] == "null"
            ):
                raise SafexpressPODNotFoundError(
                    f"No POD data available for waybill: {waybill_number}"
                )
            
            import base64
            pod_data = base64.b64decode(result["data"]["base64String"])
            
            logger.info(f"Retrieved POD document for waybill: {waybill_number}")
            return pod_data
            
        except requests.exceptions.HTTPError as e:
            # 504 Gateway Timeout is retryable
            if e.response and e.response.status_code == 504:
                error_msg = f"Gateway timeout getting POD for waybill {waybill_number}"
                logger.warning(error_msg)
                raise SafexpressAPIError(error_msg, status_code=504) from e
            elif e.response and e.response.status_code == 404:
                raise SafexpressPODNotFoundError(
                    f"POD not found for waybill: {waybill_number}"
                )
            else:
                error_msg = f"HTTP error getting POD for waybill {waybill_number}: {e.response.status_code if e.response else 'Unknown'}"
                logger.error(error_msg)
                raise SafexpressAPIError(
                    error_msg,
                    status_code=e.response.status_code if e.response else None
                ) from e
        except requests.exceptions.RequestException as e:
            error_msg = f"Request error getting POD for waybill {waybill_number}: {str(e)}"
            logger.error(error_msg)
            raise SafexpressAPIError(error_msg) from e

