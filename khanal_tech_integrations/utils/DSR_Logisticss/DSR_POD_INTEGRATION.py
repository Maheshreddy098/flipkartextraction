"""
DSR Logistics POD (Proof of Delivery) Email Processing Module

This module processes emails from DSR Logistics containing POD attachments,
uploads them to S3, and updates SAP AR Invoice records with POD information.

Features:
- Automated email processing with IMAP
- S3 file upload with proper error handling
- SAP B1 integration for invoice updates
- Comprehensive error logging and notifications
- Retry logic for transient failures
- Two-phase commit for DB/SAP consistency

Usage:
    # Normal run — processes only UNSEEN emails
    bench --site <site_name> execute khanal_tech_integrations.utils.DSR_Logisticss.DSR_POD_INTEGRATION.process_dsr_emails

    # Reprocess ALL emails (skips invoices already completed)
    bench --site khanaltech.com execute khanal_tech_integrations.utils.DSR_Logisticss.DSR_POD_INTEGRATION.reprocess_dsr_emails
"""

import imaplib
import logging
import functools
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple, Any
from contextlib import contextmanager
import email
import boto3
from botocore.exceptions import ClientError, BotoCoreError
import mimetypes
import io
import os
import frappe
import time
import json
import requests
from email import policy
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1

# Configure logging
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SAP_HEADERS = {
    "Accept": "*/*",
    "User-Agent": "Khanal Tech",
    "Content-Type": "application/json",
}

EMAIL_LABELS = {
    "Processed": "\\Seen",
    "Error": "\\Flagged",
    "No_Attachments": "\\Seen",
}

MAX_RETRIES = 3
RETRY_DELAY = 2       # seconds
S3_UPLOAD_TIMEOUT = 60  # seconds
SAP_REQUEST_TIMEOUT = 30  # seconds

# POD status values — centralised so they never drift between functions
POD_STATUS_PENDING     = "Pending"
POD_STATUS_PENDING_SAP = "Pending_SAP"   # DB written, SAP not yet confirmed
POD_STATUS_COMPLETED   = "Completed"


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class DSRProcessingError(Exception):
    """Raised for configuration or business-logic errors."""


class EmailConnectionError(Exception):
    """Raised when IMAP connection or login fails."""


# ---------------------------------------------------------------------------
# Settings helpers  (cached per Frappe request context)
# ---------------------------------------------------------------------------

def get_s3_settings() -> Dict[str, str]:
    """
    Retrieve S3 settings from the AWS doctype.

    Cached for the lifetime of the current Frappe request so that processing
    many attachments in one run does not hammer the database.

    Returns:
        Dict with keys: access_key, secret_key, region, bucket, prefix

    Raises:
        DSRProcessingError
    """
    cache_key = "dsr_pod_s3_settings"
    cached = frappe.cache().get_value(cache_key)
    if cached:
        return cached

    try:
        s3 = frappe.get_single("AWS")
        if not s3.access_key_id or not s3.secret_access_key:
            raise DSRProcessingError("S3 credentials are not configured in AWS doctype.")
        if not s3.bucket_name_dsr:
            raise DSRProcessingError("S3 bucket name (bucket_name_dsr) is not configured.")

        settings = {
            "access_key": s3.access_key_id,
            "secret_key": s3.secret_access_key,
            "region":     s3.region,
            "bucket":     s3.bucket_name_dsr,
            "prefix":     s3.folder_prefix or "DSR_Logistics_POD",
        }
        # Cache for 10 minutes — short enough to pick up changes, long enough to help
        frappe.cache().set_value(cache_key, settings, expires_in_sec=600)
        return settings

    except frappe.DoesNotExistError:
        raise DSRProcessingError("AWS Settings doctype not found. Please configure it.")
    except DSRProcessingError:
        raise
    except Exception as e:
        logger.error(f"Failed to load S3 settings: {e}", exc_info=True)
        raise DSRProcessingError(f"Failed to load S3 settings: {e}")


def get_dsr_settings() -> Dict[str, Any]:
    """
    Retrieve DSR email settings.

    Cached per-run like get_s3_settings().

    Returns:
        Dict with keys: email, password, notification_recipients (list)

    Raises:
        DSRProcessingError
    """
    cache_key = "dsr_pod_dsr_settings"
    cached = frappe.cache().get_value(cache_key)
    if cached:
        return cached

    try:
        doc = frappe.get_doc("DSR Settings")
        email_address = doc.email
        password = doc.app_password or doc.password

        if not email_address or not password:
            raise DSRProcessingError("DSR email credentials are not configured.")

        # Parse comma-separated recipients; fall back to sensible defaults
        raw_recipients = getattr(doc, "notification_recipients", None)
        if raw_recipients:
            recipients = [r.strip() for r in raw_recipients.split(",") if r.strip()]
        else:
            recipients = ["mithun@khanalfoods.com", "yogesha@khanalfoods.com"]
            logger.warning(
                "notification_recipients not set in DSR Settings. "
                "Using hardcoded fallback — please configure this field."
            )

        settings = {
            "email":                   email_address,
            "password":                password,
            "notification_recipients": recipients,
        }
        frappe.cache().set_value(cache_key, settings, expires_in_sec=600)
        return settings

    except frappe.DoesNotExistError:
        raise DSRProcessingError("DSR Settings doctype not found. Please configure it.")
    except DSRProcessingError:
        raise
    except Exception as e:
        logger.error(f"Failed to load DSR settings: {e}", exc_info=True)
        raise DSRProcessingError(f"Failed to load DSR settings: {e}")


# ---------------------------------------------------------------------------
# IMAP context manager
# ---------------------------------------------------------------------------

@contextmanager
def email_connection():
    """
    Context manager that opens an IMAP4_SSL connection and guarantees logout.

    Yields:
        imaplib.IMAP4_SSL

    Raises:
        EmailConnectionError
    """
    mail = None
    try:
        settings = get_dsr_settings()

        # timeout kwarg was added in Python 3.9.
        # Use a try/except so the module still works on 3.8.
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=30)
        except TypeError:
            mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)

        mail.login(settings["email"], settings["password"])
        logger.info(f"Connected to email: {settings['email']}")
        yield mail

    except imaplib.IMAP4.error as e:
        raise EmailConnectionError(f"Email login failed: {e}") from e
    except EmailConnectionError:
        raise
    except Exception as e:
        raise EmailConnectionError(f"Email connection error: {e}") from e
    finally:
        if mail:
            try:
                mail.logout()
                logger.debug("Email connection closed.")
            except Exception as e:
                logger.warning(f"Error closing email connection: {e}")


# ---------------------------------------------------------------------------
# Retry decorator  (fixed: functools.wraps, correct return on exhaustion)
# ---------------------------------------------------------------------------

def retry_on_failure(max_retries: int = MAX_RETRIES, delay: int = RETRY_DELAY):
    """
    Decorator that retries the wrapped function on transient errors.

    Only retries on ClientError, BotoCoreError, and requests network errors.
    All other exceptions propagate immediately (fail-fast for logic errors).

    Args:
        max_retries: Maximum number of attempts (first attempt + N-1 retries).
        delay:       Base delay in seconds; actual wait = delay × attempt (linear back-off).
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            transient = (ClientError, BotoCoreError, requests.exceptions.RequestException)
            last_exc: Optional[Exception] = None

            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except transient as exc:
                    last_exc = exc
                    if attempt < max_retries:
                        wait = delay * attempt
                        logger.warning(
                            f"[{func.__name__}] attempt {attempt}/{max_retries} failed: {exc}. "
                            f"Retrying in {wait}s…"
                        )
                        time.sleep(wait)
                    else:
                        logger.error(
                            f"[{func.__name__}] all {max_retries} attempts failed: {exc}"
                        )
                except Exception:
                    # Non-transient — do not retry
                    raise

            # All retries exhausted — re-raise the last transient exception
            raise last_exc  # type: ignore[misc]

        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def process_dsr_emails(reprocess: bool = False) -> Dict[str, Any]:
    """
    Process DSR emails and update invoice records.

    Args:
        reprocess: When False (default) only UNSEEN emails are processed.
                   When True ALL emails are processed; invoices already marked
                   Completed are skipped automatically inside create_invoice_record.

    Returns:
        Dict with processing statistics.
    """
    stats: Dict[str, Any] = {
        "processed":             0,
        "failed":                0,
        "skipped":               0,
        "attachments_processed": 0,
        "invoices_updated":      0,
        "start_time":            datetime.now().isoformat(),
    }

    search_criteria = "ALL" if reprocess else "UNSEEN"
    mode_label      = "REPROCESS (ALL)" if reprocess else "NORMAL (UNSEEN)"

    logger.info("=" * 60)
    logger.info(f"Starting DSR email processing — mode: {mode_label}")
    logger.info("=" * 60)

    try:
        with email_connection() as mail:
            mail.select("inbox")
            status, messages = mail.search(None, search_criteria)

            if status != "OK":
                logger.error(f"Failed to search emails. Status: {status}")
                return stats

            email_ids   = messages[0].split() if messages[0] else []
            total_emails = len(email_ids)
            logger.info(f"Found {total_emails} email(s) to process.")

            if not total_emails:
                return stats

            for idx, email_id in enumerate(email_ids, 1):
                eid_str = email_id.decode() if isinstance(email_id, bytes) else str(email_id)
                logger.info(f"[{idx}/{total_emails}] Processing email ID: {eid_str}")

                try:
                    result = _process_single_email(mail, email_id)
                    if result["success"]:
                        stats["processed"]             += 1
                        stats["attachments_processed"] += result.get("attachments", 0)
                        stats["invoices_updated"]      += result.get("invoices", 0)
                        _mark_email(mail, email_id, "Processed")
                    else:
                        stats["skipped"] += 1
                        _mark_email(mail, email_id, result.get("label", "No_Attachments"))

                except Exception as exc:
                    stats["failed"] += 1
                    error_msg = f"Error processing email {eid_str}: {exc}"
                    logger.error(error_msg, exc_info=True)
                    frappe.log_error(error_msg, "DSR POD Processing")
                    notify_manual_intervention(
                        subject="DSR POD Processing Failed",
                        body=(
                            f"<b>Email ID:</b> {eid_str}<br>"
                            f"<b>Error:</b> {exc}<br>"
                            f"<b>Time:</b> {datetime.now():%Y-%m-%d %H:%M:%S}<br>"
                            "Please check and handle manually."
                        ),
                    )
                    _mark_email(mail, email_id, "Error")

        stats["end_time"] = datetime.now().isoformat()
        stats["duration_seconds"] = (
            datetime.fromisoformat(stats["end_time"])
            - datetime.fromisoformat(stats["start_time"])
        ).total_seconds()

        logger.info("DSR email processing completed.")
        logger.info(f"Statistics: {json.dumps(stats, indent=2)}")
        return stats

    except EmailConnectionError as exc:
        frappe.log_error(f"DSR Email Connection Failed: {exc}", "DSR POD Processing")
        raise
    except Exception as exc:
        error_msg = f"Unexpected error in process_dsr_emails: {exc}"
        logger.error(error_msg, exc_info=True)
        frappe.log_error(error_msg, "DSR POD Processing")
        raise


def reprocess_dsr_emails() -> Dict[str, Any]:
    """
    Convenience wrapper: reprocess ALL emails in the inbox.

    Invoices already marked Completed are skipped automatically.

    Usage:
        bench --site <site_name> execute \
            khanal_tech_integrations.utils.DSR_Logistics.Dsr_Pod.reprocess_dsr_emails
    """
    return process_dsr_emails(reprocess=True)


# ---------------------------------------------------------------------------
# Single-email processor
# ---------------------------------------------------------------------------

def _process_single_email(
    mail: imaplib.IMAP4_SSL,
    email_id: bytes,
) -> Dict[str, Any]:
    """
    Fetch, parse, and process one email.

    Returns:
        Dict with keys: success (bool), attachments (int), invoices (int), label (str).
    """
    result: Dict[str, Any] = {
        "success":     False,
        "attachments": 0,
        "invoices":    0,
        "label":       "Error",
    }

    status, data = mail.fetch(email_id, "(RFC822)")
    if status != "OK" or not data or not isinstance(data[0], tuple):
        eid_str = email_id.decode() if isinstance(email_id, bytes) else str(email_id)
        logger.warning(f"Could not fetch email content for ID {eid_str}.")
        return result

    raw_email = data[0][1]
    parsed_results, attachments = _parse_email_attachments(raw_email)

    if not parsed_results:
        logger.info("No valid POD attachments found in this email.")
        result["label"] = "No_Attachments"
        return result

    logger.info(f"Found {len(parsed_results)} valid attachment(s).")

    for parsed_data in parsed_results:
        try:
            logger.info(f"Processing attachment: {parsed_data['filename']}")
            s3_result = _upload_attachment_to_s3(
                parsed_data["filename"],
                attachments[parsed_data["filename"]],
            )

            if s3_result and s3_result.get("pod_url"):
                parsed_data.update(s3_result)
                logger.info(f"S3 upload successful: {parsed_data['pod_url']}")

                if create_invoice_record(parsed_data):
                    result["invoices"]    += 1
                    result["attachments"] += 1
                else:
                    logger.warning(
                        f"Invoice update skipped/failed for {parsed_data['invoice_number']}."
                    )
            else:
                logger.error(f"S3 upload returned no URL for {parsed_data['filename']}.")

        except Exception as exc:
            error_msg = (
                f"Error processing attachment "
                f"{parsed_data.get('filename', 'unknown')}: {exc}"
            )
            logger.error(error_msg, exc_info=True)
            frappe.log_error(error_msg, "DSR POD Attachment Processing")
            # Continue with remaining attachments

    result["success"] = result["invoices"] > 0
    result["label"] = "Processed" if result["success"] else "No_Attachments"
    return result


# ---------------------------------------------------------------------------
# Email parsing
# ---------------------------------------------------------------------------

def _parse_email_attachments(
    email_bytes: bytes,
) -> Tuple[List[Dict[str, str]], Dict[str, bytes]]:
    """
    Walk a raw email and extract attachments whose filenames match the
    expected DSR naming convention:

        {waybill}_{series}_{invoice}_{DDMMYYYY}.{ext}

    Returns:
        (parsed_results, attachments)
        parsed_results — list of dicts with waybill_number, series_name,
                         invoice_number, pod_date, filename
        attachments    — dict mapping filename → raw bytes
    """
    msg         = email.message_from_bytes(email_bytes, policy=policy.default)
    results:     List[Dict[str, str]]  = []
    attachments: Dict[str, bytes]      = {}

    for part in msg.walk():
        disposition = part.get_content_disposition()
        if disposition not in ("attachment", "inline"):
            continue

        filename = part.get_filename()
        if not filename:
            continue

        # Decode encoded filenames
        if isinstance(filename, bytes):
            filename = filename.decode("utf-8", errors="ignore")

        # Validate naming convention: 4 underscore-separated parts
        stem  = os.path.splitext(filename)[0]
        parts = stem.split("_")

        if len(parts) != 4:
            logger.debug(f"Skipping '{filename}': expected 4 filename parts, got {len(parts)}.")
            continue

        waybill_number, series_name, invoice_number, date_str = parts

        if not waybill_number.isdigit():
            logger.debug(f"Skipping '{filename}': waybill is not numeric.")
            continue

        if not invoice_number.isdigit():
            logger.debug(f"Skipping '{filename}': invoice number is not numeric.")
            continue

        if len(date_str) != 8 or not date_str.isdigit():
            logger.debug(f"Skipping '{filename}': date must be 8 digits (DDMMYYYY).")
            continue

        try:
            date_obj       = datetime.strptime(date_str, "%d%m%Y")
            formatted_date = date_obj.strftime("%Y-%m-%d")
        except ValueError as exc:
            logger.debug(f"Skipping '{filename}': invalid date — {exc}.")
            continue

        # Use the new-style API (policy.default) to retrieve bytes
        try:
            attachment_data: Optional[bytes] = part.get_payload(decode=True)
        except Exception as exc:
            logger.warning(f"Could not extract payload for '{filename}': {exc}.")
            continue

        if not attachment_data:
            logger.warning(f"Empty payload for '{filename}'. Skipping.")
            continue

        results.append(
            {
                "waybill_number":  waybill_number,
                "series_name":     series_name,
                "invoice_number":  invoice_number,
                "pod_date":        formatted_date,
                "filename":        filename,
            }
        )
        attachments[filename] = attachment_data
        logger.debug(
            f"Parsed: waybill={waybill_number}, invoice={invoice_number}, date={formatted_date}"
        )

    return results, attachments


# ---------------------------------------------------------------------------
# S3 upload
# ---------------------------------------------------------------------------

@retry_on_failure(max_retries=MAX_RETRIES, delay=RETRY_DELAY)
def _upload_attachment_to_s3(
    filename: str,
    attachment_data: bytes,
) -> Optional[Dict[str, str]]:
    """
    Upload *attachment_data* to S3 and return the public URL.

    Uses virtual-hosted URL format (works for all regions including us-east-1).

    Returns:
        Dict with pod_url and s3_key, or raises on failure.
    """
    settings  = get_s3_settings()
    timestamp = str(int(time.time()))

    safe_name = filename.replace(" ", "_").replace("/", "_")
    name, ext = os.path.splitext(safe_name)
    keyed_name = f"{name}_{timestamp}{ext}"
    s3_key     = f"{settings['prefix']}/{keyed_name}"

    # Guard against absurdly large files (50 MB)
    max_size = 50 * 1024 * 1024
    if len(attachment_data) > max_size:
        raise ValueError(
            f"File size {len(attachment_data):,} bytes exceeds 50 MB limit."
        )

    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings["access_key"],
        aws_secret_access_key=settings["secret_key"],
        region_name=settings["region"],
    )

    content_type = mimetypes.guess_type(keyed_name)[0] or "application/octet-stream"

    s3_client.upload_fileobj(
        Fileobj=io.BytesIO(attachment_data),
        Bucket=settings["bucket"],
        Key=s3_key,
        ExtraArgs={
            "ContentType": content_type,
            "Metadata": {
                "original_filename": filename,
                "uploaded_at":       datetime.now().isoformat(),
                "source":            "DSR_Logistics_POD",
            },
        },
    )

    # Virtual-hosted URL — correct for every AWS region
    pod_url = (
        f"https://{settings['bucket']}.s3.{settings['region']}.amazonaws.com/{s3_key}"
    )

    logger.info(f"Uploaded '{filename}' → {pod_url}")
    return {"pod_url": pod_url, "s3_key": s3_key}


# ---------------------------------------------------------------------------
# SAP B1 on-demand invoice fetch
# ---------------------------------------------------------------------------

def _fetch_invoice_from_sap(invoice_number: str) -> bool:
    """
    Fetch an AR Invoice from SAP B1 by DocNum and create the corresponding
    SAP AR Invoice Detail record in Frappe.

    Called as a fallback inside create_invoice_record when a DSR POD arrives
    for an invoice that hasn't been synced to Frappe yet (e.g. 247xxx range).

    Returns True if the Frappe record was created, False on any failure.
    """
    try:
        from khanal_tech_integrations.utils.safexpress.automated_invoice_attach import Saved_InvDoc

        session      = AuthenticateSAPB1()
        doc_settings = frappe.get_doc("SAP Settings")
        if not doc_settings.sap_b1_url:
            logger.error("SAP B1 URL not configured — cannot auto-fetch invoice.")
            return False

        url = (
            f"{doc_settings.sap_b1_url}Invoices"
            f"?$filter=DocNum eq {invoice_number}"
            f"&$expand=DocumentLines,AddressExtension,EWayBillDetails"
        )
        response = session.request(
            "GET", url, headers=SAP_HEADERS, data="",
            verify=False, timeout=SAP_REQUEST_TIMEOUT,
        )
        if response.status_code != 200:
            logger.error(
                f"SAP B1 fetch for DocNum {invoice_number} returned "
                f"HTTP {response.status_code}: {response.text[:300]}"
            )
            return False

        invoices = response.json().get("value", [])
        if not invoices:
            logger.warning(f"SAP B1 has no invoice with DocNum {invoice_number}.")
            return False

        logger.info(
            f"Auto-fetched SAP invoice DocNum={invoice_number}, "
            f"DocEntry={invoices[0].get('DocEntry')}. Creating Frappe record…"
        )
        Saved_InvDoc(invoices[0])
        logger.info(f"SAP AR Invoice Detail created for DocNum {invoice_number}.")
        return True

    except Exception as exc:
        logger.error(
            f"Auto-fetch from SAP failed for DocNum {invoice_number}: {exc}",
            exc_info=True,
        )
        frappe.log_error(
            f"Failed to fetch DocNum {invoice_number} from SAP B1: {exc}",
            "DSR POD Invoice Auto-Fetch",
        )
        return False


# ---------------------------------------------------------------------------
# Invoice record update  (two-phase commit)
# ---------------------------------------------------------------------------

def create_invoice_record(parsed_data: Dict[str, str]) -> bool:
    """
    Update the SAP AR Invoice Detail record with POD information using a
    two-phase commit:

    Phase 1 — Write to Frappe DB with pod_status = "Pending_SAP".
              This is an idempotent write; if SAP later fails the record
              is still retryable.

    Phase 2 — PATCH SAP B1. On success, update pod_status to "Completed".
              On failure, leave the record in "Pending_SAP" so the next
              run can pick it up.

    Args:
        parsed_data: Must include invoice_number, waybill_number, pod_url, pod_date.

    Returns:
        True if both phases succeeded, False otherwise.
    """
    invoice_number = parsed_data.get("invoice_number")
    if not invoice_number:
        logger.error("invoice_number missing in parsed_data.")
        return False

    logger.info(f"Updating SAP AR Invoice Detail for invoice {invoice_number}…")

    # ------------------------------------------------------------------
    # Look up the Frappe record
    # ------------------------------------------------------------------
    try:
        records = frappe.get_all(
            "SAP AR Invoice Detail",
            filters={"docnum": invoice_number},
            fields=["name", "docentry", "docnum", "pod_url", "pod_status"],
        )
    except Exception as exc:
        logger.error(f"DB lookup failed for invoice {invoice_number}: {exc}", exc_info=True)
        frappe.log_error(str(exc), "DSR POD Invoice Lookup")
        return False

    if not records:
        logger.warning(
            f"No SAP AR Invoice Detail found for invoice {invoice_number}. "
            "Attempting auto-fetch from SAP B1…"
        )
        if _fetch_invoice_from_sap(invoice_number):
            # Retry lookup after the record was auto-created
            try:
                records = frappe.get_all(
                    "SAP AR Invoice Detail",
                    filters={"docnum": invoice_number},
                    fields=["name", "docentry", "docnum", "pod_url", "pod_status"],
                )
            except Exception as exc:
                logger.error(f"Retry lookup failed for {invoice_number}: {exc}", exc_info=True)
                records = []

    if not records:
        logger.warning(f"Invoice {invoice_number} not found in Frappe even after auto-fetch attempt.")
        notify_manual_intervention(
            subject="DSR POD: Invoice Not Found",
            body=(
                f"<b>Invoice Number:</b> {invoice_number}<br>"
                f"<b>Waybill Number:</b> {parsed_data.get('waybill_number', 'N/A')}<br>"
                f"<b>POD URL:</b> {parsed_data.get('pod_url', 'N/A')}<br>"
                f"<b>Time:</b> {datetime.now():%Y-%m-%d %H:%M:%S}<br>"
                "The invoice was not found in SAP B1 either. "
                "Please create or link the invoice manually."
            ),
        )
        return False

    record      = records[0]
    record_name = record["name"]
    docentry    = record["docentry"]

    # Skip if already fully completed
    if record.get("pod_status") == POD_STATUS_COMPLETED and record.get("pod_url"):
        logger.info(f"Invoice {invoice_number} already completed. Skipping.")
        return False

    # ------------------------------------------------------------------
    # Phase 1: write to Frappe DB (status = Pending_SAP)
    # ------------------------------------------------------------------
    phase1_data = {
        "way_bill_number":  parsed_data["waybill_number"],
        "pod_url":          parsed_data["pod_url"],
        "transporter_type": "DSR Logistics",
        "shipping_status":  POD_STATUS_COMPLETED,
        "pod_status":       POD_STATUS_PENDING_SAP,
        "pod_date":         parsed_data["pod_date"],
    }

    try:
        frappe.db.set_value("SAP AR Invoice Detail", record_name, phase1_data)
        frappe.db.commit()
        logger.info(f"Phase 1 complete: DB updated to {POD_STATUS_PENDING_SAP} for {record_name}.")
    except Exception as exc:
        # Nothing was committed — safe to leave as-is
        frappe.db.rollback()
        error_msg = f"Phase 1 DB write failed for invoice {invoice_number}: {exc}"
        logger.error(error_msg, exc_info=True)
        frappe.log_error(error_msg, "DSR POD Phase1")
        notify_manual_intervention(
            subject="SAP AR Invoice DB Write Failed",
            body=(
                f"<b>Invoice:</b> {invoice_number}<br>"
                f"<b>Error:</b> {exc}<br>"
                f"<b>Time:</b> {datetime.now():%Y-%m-%d %H:%M:%S}<br>"
                "Please update the record manually."
            ),
        )
        return False

    # ------------------------------------------------------------------
    # Phase 2: PATCH SAP B1, then mark Completed
    # ------------------------------------------------------------------
    try:
        patch_result = _patch_sap_invoice(docentry)
        if patch_result:
            logger.info(f"Phase 2 complete: SAP B1 updated for docentry {docentry}.")
        else:
            logger.warning(
                f"SAP B1 PATCH returned no result for docentry {docentry}. "
                f"Record left in {POD_STATUS_PENDING_SAP}."
            )
            return False

        # Both phases succeeded — mark Completed
        frappe.db.set_value(
            "SAP AR Invoice Detail",
            record_name,
            {"pod_status": POD_STATUS_COMPLETED},
        )
        frappe.db.commit()
        logger.info(f"Invoice {invoice_number} fully completed.")
        return True

    except Exception as exc:
        # Phase 2 failed — leave pod_status = Pending_SAP for retry
        error_msg = (
            f"Phase 2 SAP PATCH failed for docentry {docentry} "
            f"(invoice {invoice_number}): {exc}"
        )
        logger.error(error_msg, exc_info=True)
        frappe.log_error(error_msg, "DSR POD Phase2")
        notify_manual_intervention(
            subject="SAP B1 POD Patch Failed",
            body=(
                f"<b>Invoice:</b> {invoice_number}<br>"
                f"<b>DocEntry:</b> {docentry}<br>"
                f"<b>Error:</b> {exc}<br>"
                f"<b>Time:</b> {datetime.now():%Y-%m-%d %H:%M:%S}<br>"
                f"The Frappe record is in status '{POD_STATUS_PENDING_SAP}'. "
                "Re-run the job or patch SAP manually."
            ),
        )
        return False


# ---------------------------------------------------------------------------
# SAP B1 PATCH
# ---------------------------------------------------------------------------

@retry_on_failure(max_retries=MAX_RETRIES, delay=RETRY_DELAY)
def _patch_sap_invoice(docentry: str) -> Optional[Any]:
    """
    PATCH the SAP B1 invoice identified by *docentry* with POD fields.

    Looks up the Frappe record by docentry (not by Frappe name) to get the
    latest field values.

    Args:
        docentry: SAP document entry number (integer stored as str/int).

    Returns:
        requests.Response on success.

    Raises:
        DSRProcessingError / requests exception on failure (triggering retry).
    """
    # Correct lookup: filter by docentry field, not by Frappe document name
    records = frappe.get_all(
        "SAP AR Invoice Detail",
        filters={"docentry": docentry},
        fields=["name", "pod_url", "pod_date", "way_bill_number", "docentry"],
        limit=1,
    )

    if not records:
        raise DSRProcessingError(
            f"No SAP AR Invoice Detail found with docentry={docentry}."
        )

    doc_data    = records[0]
    record_name = doc_data["name"]

    if not doc_data.get("pod_url"):
        logger.warning(
            f"POD URL not present for docentry {docentry}. "
            "Resetting to Pending."
        )
        frappe.db.set_value(
            "SAP AR Invoice Detail",
            record_name,
            {"way_bill_number": "", "pod_status": POD_STATUS_PENDING},
        )
        frappe.db.commit()
        return None

    session      = AuthenticateSAPB1()
    doc_settings = frappe.get_doc("SAP Settings")

    if not doc_settings.sap_b1_url:
        raise DSRProcessingError("SAP B1 URL is not configured in SAP Settings.")

    url = f"{doc_settings.sap_b1_url}Invoices({docentry})"

    # Normalise pod_date to string — must be present; reset to Pending if missing
    pod_date_val = doc_data.get("pod_date")
    if isinstance(pod_date_val, (date, datetime)):
        pod_date_str = pod_date_val.strftime("%Y-%m-%d")
    elif pod_date_val:
        pod_date_str = str(pod_date_val)
    else:
        logger.warning(
            f"pod_date missing for docentry {docentry}. "
            "Cannot PATCH SAP with an unknown delivery date — resetting to Pending."
        )
        frappe.db.set_value(
            "SAP AR Invoice Detail",
            record_name,
            {"pod_status": POD_STATUS_PENDING},
        )
        frappe.db.commit()
        return None

    payload = json.dumps(
        {
            "U_TN":               "DSR Logistics",
            "TransportationCode": 7,
            "U_TrackingNo":       doc_data.get("way_bill_number") or "",
            "U_Pod_Link":         doc_data["pod_url"],
            "U_POD_DATE":         pod_date_str,
            "U_FrappeGRNKey":     "1",
        }
    )

    response = session.request(
        "PATCH",
        url,
        headers=SAP_HEADERS,
        data=payload,
        verify=False,
        timeout=SAP_REQUEST_TIMEOUT,
    )

    if response.status_code in (200, 204):
        logger.info(
            f"SAP B1 PATCH successful for docentry {docentry}. "
            f"Status: {response.status_code}"
        )
        return response

    error_msg = (
        f"SAP B1 PATCH failed for docentry {docentry}. "
        f"HTTP {response.status_code}: {response.text}"
    )
    logger.error(error_msg)
    raise DSRProcessingError(error_msg)


# ---------------------------------------------------------------------------
# Email flag helper
# ---------------------------------------------------------------------------

def _mark_email(
    mail: imaplib.IMAP4_SSL,
    email_id: bytes,
    label: str,
) -> None:
    """
    Apply IMAP flags and a Gmail label to *email_id*.

    Failures are logged as errors rather than swallowed silently so that
    an inability to mark emails surfaces clearly in the error log.
    """
    if label not in EMAIL_LABELS:
        logger.warning(f"Unknown email label '{label}'. Skipping mark.")
        return

    eid_str = email_id.decode() if isinstance(email_id, bytes) else str(email_id)
    try:
        mail.store(email_id, "+FLAGS",       EMAIL_LABELS[label])
        mail.store(email_id, "+X-GM-LABELS", label)
        logger.debug(f"Email {eid_str} marked as '{label}'.")
    except Exception as exc:
        # Log at ERROR level — if marking consistently fails, duplicate
        # processing will occur on the next run.
        logger.error(
            f"Failed to mark email {eid_str} as '{label}': {exc}. "
            "This email may be processed again on the next run.",
            exc_info=True,
        )
        frappe.log_error(
            f"Failed to mark email {eid_str} as '{label}': {exc}",
            "DSR POD Email Marking",
        )


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def notify_manual_intervention(subject: str, body: str) -> None:
    """
    Send an HTML email requesting manual intervention.

    Recipients are read from DSR Settings (notification_recipients field).
    """
    try:
        settings   = get_dsr_settings()
        recipients = settings.get("notification_recipients", [])

        if not recipients:
            logger.error("No notification recipients configured. Cannot send alert.")
            return

        frappe.sendmail(
            recipients=recipients,
            subject=f"[DSR POD] {subject}",
            message=body,
            now=True,
        )
        logger.info(f"Notification sent to {', '.join(recipients)}: {subject}")

    except Exception as exc:
        logger.error(f"Failed to send notification email: {exc}", exc_info=True)
        frappe.log_error(f"DSR POD Notification Failed: {exc}", "DSR POD Notifications")


# ---------------------------------------------------------------------------
# Pending-SAP recovery helper
# ---------------------------------------------------------------------------

def retry_pending_sap_invoices() -> Dict[str, Any]:
    """
    Find DSR Logistics SAP AR Invoice Detail records stuck in 'Pending_SAP' status
    and attempt to re-run Phase 2 (SAP PATCH) for each.

    Only touches transporter_type = 'DSR Logistics' records — SafeExpress Pending_SAP
    records are recovered by safexpress2.pod_service via its own fast-path.

    Run this as a scheduled job (e.g. every 6 hours) to self-heal any
    records where the SAP connection was temporarily unavailable.

    Usage:
        bench --site <site_name> execute \
            khanal_tech_integrations.utils.DSR_Logisticss.DSR_POD_INTEGRATION.retry_pending_sap_invoices
    """
    stats = {"attempted": 0, "succeeded": 0, "failed": 0}
    logger.info("Starting DSR Pending_SAP recovery run…")

    pending = frappe.get_all(
        "SAP AR Invoice Detail",
        filters={
            "pod_status":       POD_STATUS_PENDING_SAP,
            "transporter_type": "DSR Logistics",
        },
        fields=["name", "docentry", "docnum"],
    )

    logger.info(f"Found {len(pending)} record(s) in Pending_SAP status.")

    for rec in pending:
        stats["attempted"] += 1
        try:
            patch_result = _patch_sap_invoice(rec["docentry"])
            if patch_result:
                frappe.db.set_value(
                    "SAP AR Invoice Detail",
                    rec["name"],
                    {"pod_status": POD_STATUS_COMPLETED},
                )
                frappe.db.commit()
                logger.info(f"Recovered invoice {rec['docnum']} (docentry {rec['docentry']}).")
                stats["succeeded"] += 1
            else:
                stats["failed"] += 1
        except Exception as exc:
            stats["failed"] += 1
            logger.error(
                f"Recovery failed for invoice {rec['docnum']}: {exc}", exc_info=True
            )
            frappe.log_error(str(exc), "DSR POD Pending_SAP Recovery")

    logger.info(f"Pending_SAP recovery complete: {stats}")
    return stats


# ---------------------------------------------------------------------------
# CLI aliases (bench execute …)
# ---------------------------------------------------------------------------
# bench --site khanaltech.com execute khanal_tech_integrations.utils.DSR_Logisticss.DSR_POD_INTEGRATION.process_dsr_emails
# bench --site khanaltech.com execute khanal_tech_integrations.utils.DSR_Logisticss.DSR_POD_INTEGRATION.reprocess_dsr_emails
# bench --site khanaltech.com execute khanal_tech_integrations.utils.DSR_Logisticss.DSR_POD_INTEGRATION.retry_pending_sap_invoices