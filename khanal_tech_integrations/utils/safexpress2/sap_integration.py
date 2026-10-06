"""
SAP B1 Integration Module

Handles all interactions with SAP B1 API for updating invoices
and delivery notes with POD and tracking information.
"""

import logging
import json
from typing import Dict, Any, Optional
import frappe
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1

from .config import (
    SAP_FIELD_TRANSPORTER_NAME,
    SAP_FIELD_TRACKING_NUMBER,
    SAP_FIELD_POD_LINK,
    SAP_FIELD_POD_DATE,
    SAP_FIELD_TRANSPORTATION_CODE,
    TRANSPORTER_NAME_SAFEXPRESS,
    DEFAULT_TIMEOUT_SECONDS,
)
from .exceptions import SafexpressSAPIntegrationError

logger = logging.getLogger(__name__)


class SAPIntegration:
    """
    Handles SAP B1 API integration for invoice and delivery note updates.
    """
    
    def __init__(self):
        """Initialize SAP integration."""
        self._base_url = None
    
    def update_invoice_with_pod(
        self,
        invoice_docentry: str,
        waybill_number: str,
        pod_url: str,
        pod_date: Optional[str] = None,
    ) -> bool:
        """
        Update SAP B1 invoice with POD information.
        
        Args:
            invoice_docentry: SAP invoice DocEntry
            waybill_number: Safexpress waybill number
            pod_url: URL of uploaded POD document
            pod_date: POD delivery date (optional)
            
        Returns:
            True if update successful, False otherwise
            
        Raises:
            SafexpressSAPIntegrationError: If SAP update fails
        """
        try:
            session = self._get_session()
            url = self._get_invoice_url(invoice_docentry)
            
            payload = {
                SAP_FIELD_TRANSPORTER_NAME: TRANSPORTER_NAME_SAFEXPRESS,
                SAP_FIELD_TRANSPORTATION_CODE: 1,
                SAP_FIELD_TRACKING_NUMBER: waybill_number,
                SAP_FIELD_POD_LINK: pod_url,
                "U_FrappeGRNKey": "1",
            }

            if pod_date:
                payload[SAP_FIELD_POD_DATE] = pod_date
            
            logger.debug(
                f"Updating SAP invoice {invoice_docentry} with POD: {pod_url}"
            )
            
            response = session.request(
                "PATCH",
                url,
                headers=self._get_headers(),
                data=json.dumps(payload),
                verify=False,
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
            
            if response.status_code in [200, 204]:
                logger.info(
                    f"Successfully updated SAP invoice {invoice_docentry} with POD"
                )
                return True
            else:
                error_msg = (
                    f"SAP invoice update failed for {invoice_docentry}: "
                    f"{response.status_code} - {response.text}"
                )
                logger.error(error_msg)
                frappe.log_error(error_msg, "Safexpress SAP Integration")
                return False
                
        except Exception as e:
            error_msg = (
                f"Error updating SAP invoice {invoice_docentry} with POD: {str(e)}"
            )
            logger.error(error_msg)
            frappe.log_error(error_msg, "Safexpress SAP Integration")
            raise SafexpressSAPIntegrationError(error_msg) from e
    
    def update_delivery_note_with_tracking(
        self,
        delivery_note_docentry: str,
        waybill_number: str,
    ) -> bool:
        """
        Update SAP B1 delivery note with tracking information.
        
        Args:
            delivery_note_docentry: SAP delivery note DocEntry
            waybill_number: Safexpress waybill number
            
        Returns:
            True if update successful, False otherwise
            
        Raises:
            SafexpressSAPIntegrationError: If SAP update fails
        """
        try:
            session = self._get_session()
            url = self._get_delivery_note_url(delivery_note_docentry)
            
            payload = {
                SAP_FIELD_TRANSPORTER_NAME: TRANSPORTER_NAME_SAFEXPRESS,
                SAP_FIELD_TRACKING_NUMBER: waybill_number,
            }
            
            logger.debug(
                f"Updating SAP delivery note {delivery_note_docentry} "
                f"with tracking: {waybill_number}"
            )
            
            response = session.request(
                "PATCH",
                url,
                headers=self._get_headers(),
                data=json.dumps(payload),
                verify=False,
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
            
            if response.status_code in [200, 204]:
                logger.info(
                    f"Successfully updated SAP delivery note "
                    f"{delivery_note_docentry} with tracking"
                )
                return True
            else:
                error_msg = (
                    f"SAP delivery note update failed for {delivery_note_docentry}: "
                    f"{response.status_code} - {response.text}"
                )
                logger.error(error_msg)
                frappe.log_error(error_msg, "Safexpress SAP Integration")
                return False
                
        except Exception as e:
            error_msg = (
                f"Error updating SAP delivery note {delivery_note_docentry} "
                f"with tracking: {str(e)}"
            )
            logger.error(error_msg)
            frappe.log_error(error_msg, "Safexpress SAP Integration")
            raise SafexpressSAPIntegrationError(error_msg) from e
    
    def _get_session(self):
        """Get a fresh authenticated SAP B1 session (SAP sessions expire ~30 min)."""
        return AuthenticateSAPB1()
    
    def _get_base_url(self) -> str:
        """Get SAP B1 base URL from settings."""
        if self._base_url is None:
            doc_settings = frappe.get_doc("SAP Settings")
            self._base_url = doc_settings.sap_b1_url
        return self._base_url
    
    def _get_invoice_url(self, docentry: str) -> str:
        """Get SAP invoice API URL."""
        return f"{self._get_base_url()}Invoices({docentry})"
    
    def _get_delivery_note_url(self, docentry: str) -> str:
        """Get SAP delivery note API URL."""
        return f"{self._get_base_url()}DeliveryNotes({docentry})"
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for SAP API requests."""
        return {
            "Accept": "*/*",
            "User-Agent": "Khanal Tech",
            "Content-Type": "application/json",
        }


# Global instance for convenience
_sap_integration: Optional[SAPIntegration] = None


def get_sap_integration() -> SAPIntegration:
    """
    Get global SAP integration instance.
    
    Returns:
        SAPIntegration instance
    """
    global _sap_integration
    if _sap_integration is None:
        _sap_integration = SAPIntegration()
    return _sap_integration

