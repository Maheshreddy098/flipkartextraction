"""
POD (Proof of Delivery) Service

Handles POD retrieval, processing, and attachment to SAP invoices.
"""

import logging
import time
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
import frappe
from frappe.utils import add_to_date

from .auth import get_auth
from .api_client import SafexpressAPIClient
from .sap_integration import get_sap_integration
from .utils import parse_delivery_date, validate_docentry, truncate_error_message
from .exceptions import (
    SafexpressError,
    SafexpressPODNotFoundError,
    SafexpressDateParsingError,
    SafexpressFileUploadError,
    SafexpressWaybillNotFoundError,
    SafexpressAPIError,
)
from .config import (
    INVOICE_SERIES_PREFIXES,
    DEFAULT_LOOKBACK_DAYS,
    MAX_LOOKBACK_DAYS,
    DEFAULT_BATCH_SIZE,
    DEFAULT_UPLOAD_TIMEOUT_SECONDS,
    POD_STATUS_COMPLETED,
    POD_STATUS_PENDING,
    S3_BUCKET_URL,
    S3_UPLOAD_URL,
)

logger = logging.getLogger(__name__)


def process_invoices_without_pod(
    days: int = DEFAULT_LOOKBACK_DAYS,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> Dict[str, Any]:
    """
    Process SAP AR invoices without POD for the last N days.
    
    Finds invoices missing POD information and processes them to:
    1. Get waybill number from Safexpress
    2. Get delivery date
    3. Download and upload POD document
    4. Update SAP B1 invoice
    
    Args:
        days: Number of days to look back (max 365)
        batch_size: Number of invoices to process before committing
        
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
        "already_completed": 0,
        "processed": 0,
        "pending_sap": 0,
        "skipped": 0,
        "failed": 0,
        "errors": [],
        "started_at": datetime.now().isoformat(),
    }
    
    banner = "=" * 80
    print(banner)
    print(f"Safexpress2: Processing invoices without POD")
    print(f"  - Lookback period: {days} days")
    print(f"  - Filter date: {filter_date}")
    print(f"  - Batch size: {batch_size}")
    print(banner)
    
    logger.info(
        f"Processing invoices without POD for last {days} days "
        f"(filter date: {filter_date})"
    )
    
    # Find invoices missing POD
    candidates = _find_invoices_without_pod(filter_date)
    stats["total_candidates"] = len(candidates)
    
    print(f"\nFound {len(candidates)} invoice(s) without POD")
    logger.info(f"Found {len(candidates)} invoice(s) without POD")
    
    if not candidates:
        stats["finished_at"] = datetime.now().isoformat()
        return stats
    
    # Process each invoice
    auth = get_auth()
    api_client = SafexpressAPIClient(auth.get_authenticated_session())
    sap_integration = get_sap_integration()
    
    for idx, docentry in enumerate(candidates, start=1):
        try:
            # Print progress
            print(f"\n[{idx}/{len(candidates)}] Processing invoice DocEntry: {docentry}")
            
            result = process_pod_for_invoice(
                docentry,
                api_client=api_client,
                sap_integration=sap_integration,
                auth=auth,
            )
            
            status = result["status"]
            if status == "completed":
                stats["processed"] += 1
                print(f"  Completed - POD processed successfully")
            elif status == "pending_sap":
                stats["pending_sap"] += 1
                print(f"  Pending SAP - POD uploaded to S3, SAP PATCH failed (will retry)")
            elif status == "already_completed":
                stats["already_completed"] += 1
                print(f"  Skipped - POD already completed")
            else:
                stats["skipped"] += 1
                reason = result.get("reason", "Unknown")
                print(f"  Skipped - {reason}")
                
        except Exception as e:
            # Get error message and truncate for Frappe
            error_msg_full = f"Error processing invoice {docentry}: {str(e)}"
            truncated_msg = truncate_error_message(error_msg_full)
            print(f"  ❌ Failed - {truncated_msg}")
            
            logger.error(error_msg_full, exc_info=True)
            try:
                frappe.log_error(truncated_msg, "Safexpress POD Processing")
            except Exception as log_error:
                # If logging fails, just print it
                print(f"  ⚠️  Could not log error to Frappe: {str(log_error)}")
            
            stats["failed"] += 1
            # Store truncated error in stats to avoid issues
            error_for_stats = truncate_error_message(str(e), max_length=200)
            stats["errors"].append({"docentry": docentry, "error": error_for_stats})
        
        # Commit in batches
        if idx % batch_size == 0:
            frappe.db.commit()
            print(f"\n  💾 Committed batch: {idx}/{len(candidates)} processed")
            logger.info(f"Committed batch: {idx}/{len(candidates)} processed")
    
    stats["finished_at"] = datetime.now().isoformat()
    
    # Print final summary
    print("\n" + "=" * 80)
    print("Processing Complete - Summary")
    print("=" * 80)
    print(f"  Total candidates: {stats['total_candidates']}")
    print(f"  Processed:     {stats['processed']}")
    print(f"  Pending SAP:   {stats['pending_sap']}")
    print(f"  Already done:  {stats['already_completed']}")
    print(f"  Skipped:       {stats['skipped']}")
    print(f"  Failed:        {stats['failed']}")
    if stats['errors']:
        print(f"\n  Errors: {len(stats['errors'])} invoice(s) failed")
    print("=" * 80)
    
    logger.info(f"POD processing complete. Stats: {stats}")
    
    return stats


def process_pod_for_invoice(
    docentry: str,
    api_client: Optional[SafexpressAPIClient] = None,
    sap_integration: Optional[Any] = None,
    auth: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Process POD for a single invoice.
    
    Args:
        docentry: SAP AR Invoice Detail DocEntry
        api_client: Optional API client instance (for testing)
        sap_integration: Optional SAP integration instance (for testing)
        auth: Optional auth instance (for testing)
        
    Returns:
        Dictionary with processing result
    """
    docentry = validate_docentry(docentry)
    
    try:
        # Get invoice document
        invoice_doc = frappe.get_doc("SAP AR Invoice Detail", docentry)
        
        # Check if already completed
        if invoice_doc.pod_url and invoice_doc.pod_status == POD_STATUS_COMPLETED:
            logger.debug(f"Invoice {docentry} already has POD")
            return {"status": "already_completed", "docentry": docentry}

        # Initialize dependencies if not provided
        if auth is None:
            auth = get_auth()
        if api_client is None:
            api_client = SafexpressAPIClient(auth.get_authenticated_session())
        if sap_integration is None:
            sap_integration = get_sap_integration()

        # Fast-path: SAP PATCH previously failed but pod_url + waybill already saved
        if (
            invoice_doc.pod_status == "Pending_SAP"
            and invoice_doc.pod_url
            and invoice_doc.way_bill_number
        ):
            logger.info(f"Invoice {docentry} is Pending_SAP — retrying SAP PATCH only")
            try:
                sap_ok = sap_integration.update_invoice_with_pod(
                    invoice_doc.docentry,
                    invoice_doc.way_bill_number,
                    invoice_doc.pod_url,
                    str(invoice_doc.pod_date) if invoice_doc.pod_date else None,
                )
            except Exception as sap_exc:
                frappe.log_error(
                    f"SAP PATCH retry raised exception for docentry {docentry}: {sap_exc}",
                    "Safexpress2 POD SAP Patch Retry",
                )
                sap_ok = False

            if sap_ok:
                invoice_doc.pod_status = POD_STATUS_COMPLETED
                invoice_doc.save()
                frappe.db.commit()
                print(f"  SAP retry succeeded for {docentry}")
                return {"status": "completed", "docentry": docentry, "pod_url": invoice_doc.pod_url}
            else:
                frappe.log_error(
                    f"SAP PATCH retry failed for docentry {docentry} — still Pending_SAP.",
                    "Safexpress2 POD SAP Patch Retry",
                )
                return {"status": "skipped", "docentry": docentry, "reason": "SAP PATCH retry failed"}

        # Step 1: Get waybill number
        # Handle invoices without series_name - API client will try all prefixes
        series_name = invoice_doc.series_name or ""
        
        if not series_name:
            logger.info(
                f"Invoice {docentry} (docnum: {invoice_doc.docnum}) has no series_name, "
                f"will try all configured prefixes"
            )
        
        try:
            tracking_info = api_client.get_tracking_by_invoice(
                series_name,
                invoice_doc.docnum,
            )
        except SafexpressWaybillNotFoundError:
            # Waybill not found - this is normal for some invoices, skip gracefully
            logger.info(
                f"No waybill found for invoice {docentry} (docnum: {invoice_doc.docnum}). "
                f"This invoice may not be shipped via Safexpress."
            )
            return {
                "status": "skipped",
                "docentry": docentry,
                "reason": "No waybill found - invoice may not be shipped via Safexpress"
            }
        
        waybill_number = tracking_info["shipment"]["waybill"]
        invoice_doc.way_bill_number = waybill_number
        invoice_doc.save()
        frappe.db.commit()
        
        print(f"  📦 Found waybill: {waybill_number}")
        logger.info(f"Found waybill {waybill_number} for invoice {docentry}")
        
        # Step 2: Parse and save delivery date
        delivery_date_raw = tracking_info["shipment"].get("deliveryDate")
        if delivery_date_raw:
            try:
                delivery_date = parse_delivery_date(delivery_date_raw)
                invoice_doc.pod_date = delivery_date
                invoice_doc.save()
                frappe.db.commit()
                logger.debug(f"Saved delivery date {delivery_date} for invoice {docentry}")
            except SafexpressDateParsingError as e:
                logger.warning(f"Could not parse delivery date: {str(e)}")
        
        # Step 3: Get and upload POD document
        # Use the successful series variant from tracking info, or fallback to invoice series_name, or "UNKNOWN"
        # The API client adds _successful_series to the result when it finds a waybill
        series_for_filename = (
            tracking_info.get("_successful_series") or 
            invoice_doc.series_name or 
            "UNKNOWN"
        )
        pod_url = _download_and_upload_pod(
            waybill_number,
            series_for_filename,
            invoice_doc.docnum,
            auth,
            api_client,
        )
        
        if pod_url:
            # Step 4: Two-phase commit — persist S3 URL to Frappe before touching SAP
            # so a network exception from update_invoice_with_pod never loses the upload.
            invoice_doc.pod_url = pod_url
            invoice_doc.pod_status = "Pending_SAP"
            invoice_doc.save()
            frappe.db.commit()

            # Step 5: PATCH SAP B1 — catch exceptions so Pending_SAP retry can handle them
            try:
                sap_ok = sap_integration.update_invoice_with_pod(
                    invoice_doc.docentry,
                    waybill_number,
                    pod_url,
                    str(invoice_doc.pod_date) if invoice_doc.pod_date else None,
                )
            except Exception as sap_exc:
                frappe.log_error(
                    f"SAP PATCH raised exception for docentry {docentry}: {sap_exc}",
                    "Safexpress2 POD SAP Patch",
                )
                sap_ok = False

            if sap_ok:
                invoice_doc.pod_status = POD_STATUS_COMPLETED
                invoice_doc.save()
                frappe.db.commit()
                print(f"  POD uploaded and SAP updated: {pod_url}")
                logger.info(f"Successfully processed POD for invoice {docentry}")
                return {"status": "completed", "docentry": docentry, "pod_url": pod_url}
            else:
                frappe.log_error(
                    f"SAP B1 PATCH failed for docentry {docentry} — "
                    f"pod_url saved, pod_status=Pending_SAP for retry.",
                    "Safexpress2 POD SAP Patch",
                )
                print(f"  POD uploaded to S3 but SAP PATCH failed: {pod_url}")
                logger.warning(f"POD uploaded but SAP PATCH failed for invoice {docentry}")
                return {"status": "pending_sap", "docentry": docentry, "pod_url": pod_url}
        else:
            invoice_doc.pod_status = POD_STATUS_PENDING
            invoice_doc.save()
            frappe.db.commit()
            return {"status": "skipped", "docentry": docentry, "reason": "POD not available"}
            
    except SafexpressPODNotFoundError:
        logger.warning(f"POD not found for invoice {docentry}")
        return {"status": "skipped", "docentry": docentry, "reason": "POD not found"}
    except Exception as e:
        logger.error(f"Error processing POD for invoice {docentry}: {str(e)}", exc_info=True)
        raise


def get_all_pods_from_last_year(
    days: int = MAX_LOOKBACK_DAYS,
    include_completed: bool = True,
) -> Dict[str, Any]:
    """
    Get all PODs and dates from the last N days.
    
    Args:
        days: Number of days to look back (max 365)
        include_completed: If True, include invoices with completed PODs
        
    Returns:
        Dictionary containing POD statistics and invoice details
    """
    days = min(int(days), MAX_LOOKBACK_DAYS)
    today = frappe.utils.nowdate()
    filter_date = add_to_date(today, days=-days)
    
    stats = {
        "days": days,
        "filter_date": str(filter_date),
        "total_invoices": 0,
        "with_pod": 0,
        "without_pod": 0,
        "with_dates": 0,
        "without_dates": 0,
        "invoices": [],
        "started_at": datetime.now().isoformat(),
    }
    
    logger.info(f"Retrieving all PODs from last {days} days")
    
    # Build filters - include invoices with or without series_name
    # First get invoices with series_name in prefixes
    filters_with_series = {
        "series_name": ["in", INVOICE_SERIES_PREFIXES],
        "lastupdated_date": [">", filter_date],
    }
    
    if not include_completed:
        filters_with_series["pod_url"] = ["in", ["", None]]
    
    invoices_with_series = frappe.db.get_list(
        "SAP AR Invoice Detail",
        filters=filters_with_series,
        fields=[
            "docentry",
            "docnum",
            "series_name",
            "pod_url",
            "pod_status",
            "pod_date",
            "way_bill_number",
            "lastupdated_date",
        ],
        order_by="lastupdated_date desc",
        limit_page_length=50000,
    )
    
    # Get invoices without series_name
    filters_without_series = {
        "series_name": ["in", ["", None]],
        "lastupdated_date": [">", filter_date],
    }
    
    if not include_completed:
        filters_without_series["pod_url"] = ["in", ["", None]]
    
    invoices_without_series = frappe.db.get_list(
        "SAP AR Invoice Detail",
        filters=filters_without_series,
        fields=[
            "docentry",
            "docnum",
            "series_name",
            "pod_url",
            "pod_status",
            "pod_date",
            "way_bill_number",
            "lastupdated_date",
        ],
        order_by="lastupdated_date desc",
        limit_page_length=50000,
    )
    
    # Combine and deduplicate by docentry
    all_docentries = set()
    invoices = []
    
    for inv in invoices_with_series + invoices_without_series:
        if inv.docentry not in all_docentries:
            all_docentries.add(inv.docentry)
            invoices.append(inv)
    
    stats["total_invoices"] = len(invoices)
    
    for invoice in invoices:
        invoice_data = {
            "docentry": invoice.docentry,
            "docnum": invoice.docnum,
            "series_name": invoice.series_name,
            "pod_url": invoice.pod_url or None,
            "pod_status": invoice.pod_status or None,
            "pod_date": str(invoice.pod_date) if invoice.pod_date else None,
            "way_bill_number": invoice.way_bill_number or None,
            "lastupdated_date": str(invoice.lastupdated_date) if invoice.lastupdated_date else None,
        }
        
        if invoice_data["pod_url"]:
            stats["with_pod"] += 1
        else:
            stats["without_pod"] += 1
        
        if invoice_data["pod_date"]:
            stats["with_dates"] += 1
        else:
            stats["without_dates"] += 1
        
        stats["invoices"].append(invoice_data)
    
    stats["finished_at"] = datetime.now().isoformat()
    logger.info(f"Retrieved {len(invoices)} invoices. Stats: {stats}")
    
    return stats


def _find_invoices_without_pod(filter_date: str) -> List[str]:
    """
    Find SafeExpress invoices that need POD processing.

    Three groups are collected and deduplicated:
      1. Invoices with a known SafeExpress series_name and no pod_url yet
      2. Invoices with no series_name yet (may be SafeExpress — non-SafeExpress
         transporters are explicitly excluded to avoid hitting the wrong API)
      3. Invoices stuck on Pending_SAP (pod_url exists but SAP PATCH failed)

    Args:
        filter_date: Date to filter from

    Returns:
        List of invoice DocEntries
    """
    # Transporters that are definitely NOT SafeExpress — never attempt their invoices
    non_safexpress_transporters = [
        "DP World", "Delhivery", "Local delivery partner",
        "Platform Fulfilled", "DSR Logistics",
    ]

    # Group 1: known SafeExpress series, no POD yet, not a known non-SafeExpress transporter
    # (DSR Logistics invoices share the same series names, so transporter must be checked)
    invoices_by_series = frappe.db.get_list(
        "SAP AR Invoice Detail",
        filters={
            "series_name": ["in", INVOICE_SERIES_PREFIXES],
            "transporter_type": ["not in", non_safexpress_transporters],
            "lastupdated_date": [">", filter_date],
            "pod_url": ["in", ["", None]],
        },
        pluck="docentry",
        order_by="lastupdated_date desc",
        limit_page_length=10000,
    )

    # Group 2: no series_name yet, but not a known non-SafeExpress transporter
    invoices_no_series = frappe.db.get_list(
        "SAP AR Invoice Detail",
        filters={
            "series_name": ["in", ["", None]],
            "transporter_type": ["not in", non_safexpress_transporters],
            "lastupdated_date": [">", filter_date],
            "pod_url": ["in", ["", None]],
        },
        pluck="docentry",
        order_by="lastupdated_date desc",
        limit_page_length=10000,
    )

    # Group 3a: known series, SAP PATCH previously failed
    # Must also exclude non-SafeExpress transporters — DSR shares series names and
    # has its own Pending_SAP invoices that must not be patched with SafeExpress values.
    invoices_pending_sap_series = frappe.db.get_list(
        "SAP AR Invoice Detail",
        filters={
            "series_name": ["in", INVOICE_SERIES_PREFIXES],
            "transporter_type": ["not in", non_safexpress_transporters],
            "lastupdated_date": [">", filter_date],
            "pod_status": "Pending_SAP",
        },
        pluck="docentry",
        order_by="lastupdated_date desc",
        limit_page_length=10000,
    )

    # Group 3b: no series_name, SAP PATCH previously failed
    # These were originally picked up by Group 2. Once they upload POD to S3 they have
    # pod_url set, so Group 2 (pod_url empty) no longer matches them. Without this
    # group they would be permanently stuck in Pending_SAP with no retry path.
    invoices_pending_sap_no_series = frappe.db.get_list(
        "SAP AR Invoice Detail",
        filters={
            "series_name": ["in", ["", None]],
            "transporter_type": ["not in", non_safexpress_transporters],
            "lastupdated_date": [">", filter_date],
            "pod_status": "Pending_SAP",
        },
        pluck="docentry",
        order_by="lastupdated_date desc",
        limit_page_length=10000,
    )

    invoices_pending_sap = invoices_pending_sap_series + invoices_pending_sap_no_series
    all_invoices = list(set(invoices_by_series + invoices_no_series + invoices_pending_sap))

    logger.debug(
        f"Found {len(invoices_by_series)} by series, "
        f"{len(invoices_no_series)} no-series (non-SafeExpress excluded), "
        f"{len(invoices_pending_sap)} Pending_SAP ({len(invoices_pending_sap_series)} with series, {len(invoices_pending_sap_no_series)} without), "
        f"{len(all_invoices)} total unique"
    )

    return all_invoices


def _download_and_upload_pod(
    waybill_number: str,
    series_name: str,
    doc_number: str,
    auth: Any,
    api_client: SafexpressAPIClient,
) -> Optional[str]:
    """
    Download POD from Safexpress and upload to S3.
    
    Args:
        waybill_number: Safexpress waybill number
        series_name: Invoice series name
        doc_number: Invoice document number
        auth: Authentication instance
        api_client: API client instance
        
    Returns:
        S3 URL of uploaded POD, or None if upload failed
    """
    try:
        # Get POD document
        pod_data = api_client.get_pod_document(
            waybill_number,
            auth.get_pod_url(),
        )
        
        # Generate filename
        timestamp = str(int(time.time()))
        filename = f"{series_name}_{doc_number}_{timestamp}.tiff"
        
        # Upload to S3
        upload_url = f"{S3_UPLOAD_URL}{filename}"
        headers = {"Content-Type": "image/tiff"}
        
        response = requests.put(
            upload_url,
            headers=headers,
            data=pod_data,
            timeout=DEFAULT_UPLOAD_TIMEOUT_SECONDS,
            verify=False,
        )
        
        if response.status_code in [200, 201]:
            pod_url = f"{S3_BUCKET_URL}{filename}"
            logger.info(f"Uploaded POD to S3: {pod_url}")
            return pod_url
        else:
            error_msg = (
                f"S3 upload failed for waybill {waybill_number}: "
                f"{response.status_code} - {response.text}"
            )
            logger.error(error_msg)
            # Truncate error message for Frappe
            truncated_msg = truncate_error_message(error_msg)
            try:
                frappe.log_error(truncated_msg, "Safexpress POD Upload")
            except Exception:
                # If logging fails, continue without logging
                pass
            raise SafexpressFileUploadError(error_msg)
            
    except SafexpressPODNotFoundError:
        logger.warning(f"POD not found for waybill: {waybill_number}")
        return None
    except SafexpressAPIError as e:
        # Handle 504 Gateway Timeout - it will be retried by the decorator
        if e.status_code == 504:
            logger.warning(f"Gateway timeout getting POD for waybill {waybill_number}, will retry")
            raise  # Re-raise to trigger retry
        # Other API errors
        error_msg = f"API error getting POD for waybill {waybill_number}: {str(e)}"
        logger.error(error_msg)
        truncated_msg = truncate_error_message(error_msg)
        try:
            frappe.log_error(truncated_msg, "Safexpress POD Upload")
        except Exception:
            # If logging fails, continue without logging
            pass
        raise SafexpressFileUploadError(error_msg) from e
    except Exception as e:
        error_msg = f"Error uploading POD for waybill {waybill_number}: {str(e)}"
        logger.error(error_msg)
        # Truncate error message for Frappe
        truncated_msg = truncate_error_message(error_msg)
        try:
            frappe.log_error(truncated_msg, "Safexpress POD Upload")
        except Exception:
            # If logging fails, continue without logging
            pass
        raise SafexpressFileUploadError(error_msg) from e

