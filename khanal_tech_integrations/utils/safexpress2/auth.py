"""
Safexpress Authentication Module

Handles authentication with Safexpress API including token management
and automatic renewal when tokens expire.
"""

import logging
from typing import Optional
import frappe
import requests
from frappe.utils import add_to_date, get_datetime, now_datetime

from .exceptions import SafexpressAuthenticationError
from .config import DEFAULT_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


class SafexpressAuth:
    """
    Handles Safexpress API authentication with automatic token renewal.
    
    This class manages the authentication lifecycle, including:
    - Token retrieval and storage
    - Token expiration checking
    - Automatic token renewal
    """
    
    SETTINGS_DOCTYPE = "Safexpress Settings"
    
    def __init__(self):
        """Initialize Safexpress authentication."""
        self._settings_doc = None
        self._cached_token = None
    
    def get_authenticated_session(self) -> dict:
        """
        Get authenticated session with valid access token.
        
        Automatically renews token if expired or missing.
        
        Returns:
            Dictionary containing authentication headers:
            - x-api-key
            - authorization
            - Identifier
            
        Raises:
            SafexpressAuthenticationError: If authentication fails
        """
        settings = self._get_settings()
        
        # Check if token needs renewal
        if self._is_token_expired(settings):
            logger.info("Safexpress token expired or missing, renewing...")
            settings = self._renew_token(settings)
        
        return {
            "x-api-key": settings.api_key,
            "authorization": settings.access_token,
            "Identifier": settings.identifier,
        }
    
    def get_pod_url(self) -> str:
        """
        Get POD API URL from settings.
        
        Returns:
            POD API base URL
        """
        settings = self._get_settings()
        return settings.pod_url
    
    def _get_settings(self):
        """Get Safexpress settings document."""
        if self._settings_doc is None:
            try:
                self._settings_doc = frappe.get_doc(self.SETTINGS_DOCTYPE)
            except Exception as e:
                error_msg = f"Failed to load Safexpress Settings: {str(e)}"
                logger.error(error_msg)
                raise SafexpressAuthenticationError(error_msg) from e
        
        return self._settings_doc
    
    def _is_token_expired(self, settings) -> bool:
        """
        Check if current token is expired or missing.
        
        Args:
            settings: Safexpress settings document
            
        Returns:
            True if token needs renewal, False otherwise
        """
        expires_on = frappe.db.get_single_value(
            self.SETTINGS_DOCTYPE,
            "expires_on"
        )
        
        # No expiration date means token needs renewal
        if not expires_on:
            return True
        
        # Check if current time is past expiration
        try:
            expiration_time = get_datetime(settings.expires_on)
            return now_datetime() >= expiration_time
        except Exception as e:
            logger.warning(f"Error checking token expiration: {str(e)}")
            return True
    
    def _renew_token(self, settings) -> dict:
        """
        Renew Safexpress authentication token.
        
        Args:
            settings: Safexpress settings document
            
        Returns:
            Updated settings document
            
        Raises:
            SafexpressAuthenticationError: If token renewal fails
        """
        try:
            login_url = settings.login_url
            payload = {
                "grant_type": "client_credentials",
                "scope": "server/waybillapps",
                "username": settings.username,
                "password": settings.password,
            }
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "*/*",
                "Authorization": "Basic Zm1xYWRsY2ZyY29jdW5hY2xyaWxodTRsbTpqamZ0M3Izb2ZtOWxsbmJudmZxMHZic2FwN2oxZWRrNm4wYzE5am5yM2VlMWVxcnNxNWE=",
                "Cookie": "XSRF-TOKEN=5de4fefb-a52f-439f-83c2-ad473f2cef5b",
            }
            
            logger.info(f"Renewing Safexpress token via {login_url}")
            
            response = requests.post(
                login_url,
                headers=headers,
                data=payload,
                timeout=DEFAULT_TIMEOUT_SECONDS,
                verify=False,
            )
            
            response.raise_for_status()
            response_data = response.json()
            
            # Update settings with new token
            settings.access_token = response_data["access_token"]
            settings.expires_on = add_to_date(
                now_datetime(),
                seconds=int(response_data["expires_in"])
            )
            settings.save()
            frappe.db.commit()
            
            logger.info("Safexpress token renewed successfully")
            return settings
            
        except requests.exceptions.Timeout as e:
            error_msg = f"Safexpress authentication timeout: {str(e)}"
            logger.error(error_msg)
            frappe.log_error(error_msg, "Safexpress Auth - Timeout")
            raise SafexpressAuthenticationError(error_msg) from e
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Safexpress authentication request failed: {str(e)}"
            logger.error(error_msg)
            frappe.log_error(error_msg, "Safexpress Auth - Request Error")
            raise SafexpressAuthenticationError(error_msg) from e
            
        except (ValueError, KeyError) as e:
            error_msg = f"Safexpress authentication response parsing failed: {str(e)}"
            logger.error(error_msg)
            frappe.log_error(error_msg, "Safexpress Auth - Response Error")
            raise SafexpressAuthenticationError(error_msg) from e
            
        except Exception as e:
            error_msg = f"Unexpected error during Safexpress authentication: {str(e)}"
            logger.error(error_msg)
            frappe.log_error(error_msg, "Safexpress Auth - Unexpected Error")
            raise SafexpressAuthenticationError(error_msg) from e


# Global instance for convenience
_auth_instance: Optional[SafexpressAuth] = None


def get_auth() -> SafexpressAuth:
    """
    Get global Safexpress authentication instance.
    
    Returns:
        SafexpressAuth instance
    """
    global _auth_instance
    if _auth_instance is None:
        _auth_instance = SafexpressAuth()
    return _auth_instance

