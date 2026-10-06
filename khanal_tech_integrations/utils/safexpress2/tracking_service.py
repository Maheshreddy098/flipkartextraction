"""
Tracking Service

Handles Safexpress tracking information updates for SAP delivery notes.
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
import frappe
from frappe.utils import add_to_date

from .auth import get_auth
from .api_client import SafexpressAPIClient
from .sap_integration import get_sap_integration
from .utils import validate_docentry
from .config import (
    DEFAULT_LOOKBACK_DAYS,
    MAX_LOOKBACK_DAYS,
    TRANSPORTER_NAME_SAFEXPRESS,
    INVOICE_SERIES_PREFIXES,
)
from .exceptions import SafexpressAPIError

logger = logging.getLogger(__name__)


def update_tracking_by_invoice(
    days: int = DEFAULT_LOOKBACK_DAYS,
) -> Dict[str, Any]:
    """
    Update Safexpress tracking for delivery notes via invoice numbers.
    
    Finds delivery notes without tracking information and updates them
    by looking up invoices and getting waybill numbers from Safexpress.
    
    Args:
        days: Number of days to look back (max 365)
        
    Returns:
        Dictionary with processing statistics
    """
    days = min(int(days), MAX_LOOKBACK_DAYS)
    today = frappe.utils.nowdate()
    filter_date = add_to_date(today, days=-days)
    
    stats = {
        "days": days,
        "filter_date": str(filter_date),
        "total_candidates": 0,
        "processed": 0,
        "failed": 0,
        "errors": [],
        "started_at": datetime.now().isoformat(),
    }
    
    logger.info(
        f"Updating tracking by invoice for last {days} days "
        f"(filter date: {filter_date})"
    )
    
    # Find delivery notes without tracking
    delivery_notes = frappe.db.get_list(
        "SAP Delivery Notes",
        filters={
            "tracking_id": ["in", ["", None]],
            "transporter_name": ["in", ["", None]],
            "updated": [">", filter_date],
        },
        pluck="docentry",
        order_by="updated desc",
        limit_page_length=10000,
    )
    
    stats["total_candidates"] = len(delivery_notes)
    logger.info(f"Found {len(delivery_notes)} delivery note(s) without tracking")
    
    if not delivery_notes:
        stats["finished_at"] = datetime.now().isoformat()
        return stats
    
    # Initialize API client
    auth = get_auth()
    api_client = SafexpressAPIClient(auth.get_authenticated_session())
    sap_integration = get_sap_integration()
    
    # Process each delivery note
    for docentry in delivery_notes:
        try:
            result = _update_delivery_note_tracking(
                docentry,
                api_client,
                sap_integration,
            )
            
            if result["success"]:
                stats["processed"] += 1
            else:
                stats["failed"] += 1
                stats["errors"].append({
                    "docentry": docentry,
                    "error": result.get("error", "Unknown error"),
                })
                
        except Exception as e:
            error_msg = f"Error updating tracking for DN {docentry}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            frappe.log_error(error_msg, "Safexpress Tracking")
            stats["failed"] += 1
            stats["errors"].append({"docentry": docentry, "error": str(e)})
    
    stats["finished_at"] = datetime.now().isoformat()
    logger.info(f"Tracking update complete. Stats: {stats}")
    
    return stats


def update_tracking_by_waybill() -> Dict[str, Any]:
    """
    Update Safexpress tracking for delivery notes using existing waybills.
    
    Refreshes tracking status for delivery notes that already have
    Safexpress waybill numbers.
    
    Returns:
        Dictionary with processing statistics
    """
    stats = {
        "total_candidates": 0,
        "processed": 0,
        "failed": 0,
        "errors": [],
        "started_at": datetime.now().isoformat(),
    }
    
    logger.info("Updating tracking by waybill")
    
    # Find delivery notes with Safexpress waybills
    delivery_notes = frappe.db.get_list(
        "SAP Delivery Notes",
        filters={
            "transporter_name": ["=", TRANSPORTER_NAME_SAFEXPRESS],
            "tracking_id": ["!=", ""],
        },
        pluck="docentry",
        limit_page_length=10000,
    )
    
    stats["total_candidates"] = len(delivery_notes)
    logger.info(f"Found {len(delivery_notes)} delivery note(s) with waybills")
    
    if not delivery_notes:
        stats["finished_at"] = datetime.now().isoformat()
        return stats
    
    # Initialize API client
    auth = get_auth()
    api_client = SafexpressAPIClient(auth.get_authenticated_session())
    
    # Process each delivery note
    for docentry in delivery_notes:
        try:
            result = _refresh_delivery_note_tracking(docentry, api_client)
            
            if result["success"]:
                stats["processed"] += 1
            else:
                stats["failed"] += 1
                stats["errors"].append({
                    "docentry": docentry,
                    "error": result.get("error", "Unknown error"),
                })
                
        except Exception as e:
            error_msg = f"Error refreshing tracking for DN {docentry}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            frappe.log_error(error_msg, "Safexpress Tracking")
            stats["failed"] += 1
            stats["errors"].append({"docentry": docentry, "error": str(e)})
    
    stats["finished_at"] = datetime.now().isoformat()
    logger.info(f"Tracking refresh complete. Stats: {stats}")
    
    return stats


def _update_delivery_note_tracking(
    docentry: str,
    api_client: SafexpressAPIClient,
    sap_integration: Any,
) -> Dict[str, Any]:
    """
    Update tracking for a single delivery note by finding its invoice.
    
    Args:
        docentry: Delivery note DocEntry
        api_client: API client instance
        sap_integration: SAP integration instance
        
    Returns:
        Dictionary with success status and optional error message
    """
    docentry = validate_docentry(docentry)
    
    try:
        # Get invoices linked to this delivery note
        invoices = frappe.db.get_list(
            "SAP AR Invoice",
            filters={"ref_delivery_note": docentry},
            pluck="docnum",
        )
        
        if not invoices:
            return {"success": False, "error": "No invoices found for delivery note"}
        
        # Try to get tracking for each invoice
        for invoice_number in invoices:
            for prefix in INVOICE_SERIES_PREFIXES:
                try:
                    tracking_info = api_client.get_tracking_by_invoice(
                        prefix,
                        invoice_number,
                    )
                    
                    # Found waybill, update delivery note
                    waybill = tracking_info["shipment"]["waybill"]
                    delivery_status = tracking_info["shipment"].get("status", "Unknown")
                    
                    dn_doc = frappe.get_doc("SAP Delivery Notes", docentry)
                    dn_doc.transporter_name = TRANSPORTER_NAME_SAFEXPRESS
                    dn_doc.tracking_id = waybill
                    dn_doc.shipping_details = tracking_info
                    dn_doc.delivery_status = delivery_status
                    dn_doc.save()
                    frappe.db.commit()
                    
                    # Update SAP B1
                    sap_integration.update_delivery_note_with_tracking(
                        docentry,
                        waybill,
                    )
                    
                    logger.info(
                        f"Updated tracking for DN {docentry} with waybill {waybill}"
                    )
                    return {"success": True, "waybill": waybill}
                    
                except SafexpressAPIError:
                    # Try next prefix
                    continue
        
        return {"success": False, "error": "No waybill found for any invoice"}
        
    except Exception as e:
        logger.error(f"Error updating tracking for DN {docentry}: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}


def _refresh_delivery_note_tracking(
    docentry: str,
    api_client: SafexpressAPIClient,
) -> Dict[str, Any]:
    """
    Refresh tracking status for a delivery note using its waybill.
    
    Args:
        docentry: Delivery note DocEntry
        api_client: API client instance
        
    Returns:
        Dictionary with success status and optional error message
    """
    docentry = validate_docentry(docentry)
    
    try:
        dn_doc = frappe.get_doc("SAP Delivery Notes", docentry)
        
        if not dn_doc.tracking_id:
            return {"success": False, "error": "No tracking ID found"}
        
        # Get updated tracking information
        tracking_info = api_client.get_tracking_by_waybill(dn_doc.tracking_id)
        
        # Update delivery note
        if tracking_info.get("shipment"):
            shipment = tracking_info["shipment"]
            
            if shipment.get("result") == "success":
                dn_doc.shipping_details = tracking_info
                dn_doc.delivery_status = shipment.get("status", "Unknown")
            else:
                dn_doc.delivery_status = "Data Not Found"
            
            dn_doc.save()
            frappe.db.commit()
            
            logger.info(f"Refreshed tracking for DN {docentry}: {dn_doc.delivery_status}")
            return {"success": True, "status": dn_doc.delivery_status}
        else:
            return {"success": False, "error": "Invalid tracking response"}
            
    except SafexpressAPIError as e:
        logger.warning(f"API error refreshing tracking for DN {docentry}: {str(e)}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Error refreshing tracking for DN {docentry}: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}

