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
- Transaction management for data consistency

Usage:
    bench --site <site_name> execute khanal_tech_integrations.utils.DSR_Logistics.Dsr_Pod.process_dsr_emails
"""

import imaplib
import logging
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

# Constants
SAP_HEADERS = {
    "Accept": "*/*",
    "User-Agent": "Khanal Tech",
    "Content-Type": "application/json"
}

EMAIL_LABELS = {
    "Processed": "\\Seen",
    "Error": "\\Flagged",
    "No_Attachments": "\\Seen"
}

MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
EMAIL_FETCH_TIMEOUT = 30  # seconds
S3_UPLOAD_TIMEOUT = 60  # seconds


class DSRProcessingError(Exception):
    """Custom exception for DSR processing errors"""
    pass


class EmailConnectionError(Exception):
    """Custom exception for email connection errors"""
    pass


def get_s3_settings() -> Dict[str, str]:
    """
    Retrieve S3 settings from AWS doctype.
    
    Returns:
        Dict containing S3 configuration (access_key, secret_key, region, bucket, prefix)
        
    Raises:
        DSRProcessingError: If settings cannot be loaded
    """
    try:
        s3_settings = frappe.get_single("AWS")
        if not s3_settings.access_key_id or not s3_settings.secret_access_key:
            raise DSRProcessingError("S3 credentials are not configured")
        
        return {
            "access_key": s3_settings.access_key_id,
            "secret_key": s3_settings.secret_access_key,
            "region": s3_settings.region or "us-east-1",
            "bucket": s3_settings.bucket_name_dsr,
            "prefix": s3_settings.folder_prefix or "DSR_Logistics_POD"
        }
    except frappe.DoesNotExistError:
        raise DSRProcessingError("AWS Settings not found. Please configure AWS Settings doctype.")
    except Exception as e:
        logger.error(f"Failed to load S3 Settings: {str(e)}", exc_info=True)
        raise DSRProcessingError(f"Failed to load S3 Settings: {str(e)}")


def get_dsr_settings() -> Dict[str, str]:
    """
    Retrieve DSR email settings.
    
    Returns:
        Dict containing email and password/app_password
        
    Raises:
        DSRProcessingError: If settings cannot be loaded
    """
    try:
        dsr_settings = frappe.get_doc("DSR Settings")
        email_address = dsr_settings.email
        # Prefer app_password over password for better security
        password = dsr_settings.app_password or dsr_settings.password
        
        if not email_address or not password:
            raise DSRProcessingError("DSR email credentials are not configured")
        
        return {
            "email": email_address,
            "password": password
        }
    except frappe.DoesNotExistError:
        raise DSRProcessingError("DSR Settings not found. Please configure DSR Settings doctype.")
    except Exception as e:
        logger.error(f"Failed to load DSR Settings: {str(e)}", exc_info=True)
        raise DSRProcessingError(f"Failed to load DSR Settings: {str(e)}")


@contextmanager
def email_connection():
    """
    Context manager for IMAP email connection.
    
    Yields:
        IMAP4_SSL connection object
        
    Raises:
        EmailConnectionError: If connection or login fails
    """
    mail = None
    try:
        settings = get_dsr_settings()
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=EMAIL_FETCH_TIMEOUT)
        mail.login(settings["email"], settings["password"])
        logger.info(f"Successfully connected to email: {settings['email']}")
        yield mail
    except imaplib.IMAP4.error as e:
        error_msg = f"Email login failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise EmailConnectionError(error_msg)
    except Exception as e:
        error_msg = f"Email connection error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise EmailConnectionError(error_msg)
    finally:
        if mail:
            try:
                mail.logout()
                logger.debug("Email connection closed")
            except Exception as e:
                logger.warning(f"Error closing email connection: {str(e)}")


def retry_on_failure(max_retries: int = MAX_RETRIES, delay: int = RETRY_DELAY):
    """
    Decorator for retrying functions on failure.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Delay between retries in seconds
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (ClientError, BotoCoreError, requests.exceptions.RequestException) as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (attempt + 1)  # Exponential backoff
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {str(e)}. "
                            f"Retrying in {wait_time} seconds..."
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(f"All {max_retries} attempts failed for {func.__name__}: {str(e)}")
                except Exception as e:
                    # Don't retry on non-transient errors
                    logger.error(f"Non-retryable error in {func.__name__}: {str(e)}")
                    raise
            if last_exception:
                raise last_exception
        return wrapper
    return decorator


def process_dsr_emails() -> Dict[str, Any]:
    """
    Main function to process DSR emails and update invoice records.
    
    Processes unread emails from DSR Logistics inbox, extracts POD attachments,
    uploads them to S3, and updates SAP AR Invoice Detail records.
    
    Returns:
        Dict with processing statistics (processed, failed, skipped)
    """
    stats = {
        "processed": 0,
        "failed": 0,
        "skipped": 0,
        "attachments_processed": 0,
        "invoices_updated": 0,
        "start_time": datetime.now().isoformat()
    }
    
    logger.info("=" * 60)
    logger.info("Starting DSR email processing...")
    logger.info("=" * 60)
    
    try:
        with email_connection() as mail:
            mail.select("inbox")
            status, messages = mail.search(None, "UNSEEN")
            
            if status != "OK":
                logger.error(f"Failed to search emails. Status: {status}")
                return stats
            
            email_ids = messages[0].split() if messages[0] else []
            total_emails = len(email_ids)
            logger.info(f"Found {total_emails} unread email(s)")
            
            if total_emails == 0:
                logger.info("No unread emails to process")
                return stats
            
            for idx, email_id in enumerate(email_ids, 1):
                email_id_str = email_id.decode() if isinstance(email_id, bytes) else str(email_id)
                logger.info(f"[{idx}/{total_emails}] Processing email ID: {email_id_str}")
                
                try:
                    result = process_single_email(mail, email_id, stats)
                    if result["success"]:
                        stats["processed"] += 1
                        stats["attachments_processed"] += result.get("attachments", 0)
                        stats["invoices_updated"] += result.get("invoices", 0)
                        mark_email(mail, email_id, "Processed")
                    else:
                        stats["skipped"] += 1
                        mark_email(mail, email_id, result.get("label", "Error"))
                except Exception as e:
                    stats["failed"] += 1
                    error_msg = f"Error processing email {email_id_str}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    frappe.log_error(error_msg, "DSR POD Processing")
                    notify_manual_intervention(
                        subject="DSR POD Processing Failed",
                        body=(
                            f"<b>Email ID:</b> {email_id_str}<br>"
                            f"<b>Error:</b> {str(e)}<br>"
                            f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>"
                            f"Please check and handle it manually."
                        )
                    )
                    mark_email(mail, email_id, "Error")
        
        stats["end_time"] = datetime.now().isoformat()
        duration = (datetime.fromisoformat(stats["end_time"]) - 
                   datetime.fromisoformat(stats["start_time"])).total_seconds()
        stats["duration_seconds"] = duration
        
        logger.info("=" * 60)
        logger.info("DSR email processing completed")
        logger.info(f"Statistics: {json.dumps(stats, indent=2)}")
        logger.info("=" * 60)
        
        return stats
        
    except EmailConnectionError as e:
        logger.error(f"Email connection failed: {str(e)}")
        frappe.log_error(f"DSR Email Connection Failed: {str(e)}", "DSR POD Processing")
        raise
    except Exception as e:
        error_msg = f"Unexpected error in process_dsr_emails: {str(e)}"
        logger.error(error_msg, exc_info=True)
        frappe.log_error(error_msg, "DSR POD Processing")
        raise


def process_single_email(mail: imaplib.IMAP4_SSL, email_id: bytes, stats: Dict) -> Dict[str, Any]:
    """
    Process a single email and its attachments.
    
    Args:
        mail: IMAP connection object
        email_id: Email ID to process
        stats: Statistics dictionary to update
        
    Returns:
        Dict with success status and processing details
    """
    result = {
        "success": False,
        "attachments": 0,
        "invoices": 0,
        "label": "Error"
    }
    
    try:
        status, data = mail.fetch(email_id, "(RFC822)")
        if status != "OK" or not data or not isinstance(data[0], tuple):
            logger.warning(f"Error fetching email content for {email_id.decode()}")
            result["label"] = "Error"
            return result
        
        raw_email = data[0][1]
        parsed_results, attachments = parse_email_attachments(raw_email)
        
        if not parsed_results or not attachments:
            logger.info(f"No valid POD attachments found in email {email_id.decode()}")
            result["label"] = "No_Attachments"
            return result
        
        logger.info(f"Found {len(parsed_results)} valid attachment(s) in email")
        
        for parsed_data in parsed_results:
            try:
                logger.info(f"Processing attachment: {parsed_data['filename']}")
                s3_result = process_and_upload_attachment(
                    parsed_data["filename"],
                    attachments[parsed_data["filename"]]
                )
                
                if s3_result and s3_result.get("pod_url"):
                    parsed_data.update(s3_result)
                    logger.info(f"Successfully uploaded to S3: {parsed_data['pod_url']}")
                    
                    if create_invoice_record(parsed_data):
                        result["invoices"] += 1
                        result["attachments"] += 1
                    else:
                        logger.warning(f"Failed to update invoice for {parsed_data['invoice_number']}")
                else:
                    logger.error(f"Upload to S3 failed for {parsed_data['filename']}")
                    
            except Exception as e:
                error_msg = f"Error processing attachment {parsed_data.get('filename', 'unknown')}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                frappe.log_error(error_msg, "DSR POD Attachment Processing")
                # Continue processing other attachments
                continue
        
        result["success"] = result["invoices"] > 0
        # Mark as Seen even on partial failure so the email isn't reprocessed indefinitely.
        # Attachments were found and attempted — "Error" (Flagged/UNSEEN) would loop forever.
        result["label"] = "Processed" if result["success"] else "No_Attachments"
        return result

    except Exception as e:
        logger.error(f"Error in process_single_email: {str(e)}", exc_info=True)
        result["label"] = "Error"
        return result


def parse_email_attachments(email_bytes: bytes) -> Tuple[List[Dict[str, str]], Dict[str, bytes]]:
    """
    Parse email attachments and extract POD information from filenames.
    
    Expected filename format: {waybill_number}_{series_name}_{invoice_number}_{date}.{ext}
    Date format: DDMMYYYY
    
    Args:
        email_bytes: Raw email bytes
        
    Returns:
        Tuple of (parsed_results list, attachments dict)
    """
    msg = email.message_from_bytes(email_bytes, policy=policy.default)
    results = []
    attachments = {}
    
    for part in msg.walk():
        content_disposition = part.get_content_disposition()
        if content_disposition not in ('attachment', 'inline'):
            continue
        
        filename = part.get_filename()
        if not filename:
            continue
        
        # Decode filename if it's encoded
        try:
            if isinstance(filename, bytes):
                filename = filename.decode('utf-8', errors='ignore')
        except Exception as e:
            logger.warning(f"Error decoding filename: {str(e)}")
            continue
        
        # Parse filename: waybill_series_invoice_date.ext
        filename_without_ext = os.path.splitext(filename)[0]
        parts = filename_without_ext.split('_')
        
        # Validate filename structure
        if len(parts) != 4:
            logger.debug(f"Skipping attachment '{filename}': Invalid format (expected 4 parts)")
            continue
        
        waybill_number, series_name, invoice_number, date_str = parts
        
        # Validate parts
        if not waybill_number.isdigit():
            logger.debug(f"Skipping attachment '{filename}': Waybill number is not numeric")
            continue
        
        if not invoice_number.isdigit():
            logger.debug(f"Skipping attachment '{filename}': Invoice number is not numeric")
            continue
        
        if len(date_str) != 8:
            logger.debug(f"Skipping attachment '{filename}': Date format invalid (expected DDMMYYYY)")
            continue
        
        # Parse date
        try:
            date_obj = datetime.strptime(date_str, "%d%m%Y")
            formatted_date = date_obj.strftime("%Y-%m-%d")
        except ValueError as e:
            logger.debug(f"Skipping attachment '{filename}': Invalid date format - {str(e)}")
            continue
        
        # Extract attachment data
        try:
            attachment_data = part.get_payload(decode=True)
            if not attachment_data:
                logger.warning(f"Empty attachment data for '{filename}'")
                continue
        except Exception as e:
            logger.warning(f"Error extracting attachment data for '{filename}': {str(e)}")
            continue
        
        results.append({
            'waybill_number': waybill_number,
            'series_name': series_name,
            'invoice_number': invoice_number,
            'pod_date': formatted_date,
            'filename': filename
        })
        attachments[filename] = attachment_data
        
        logger.debug(
            f"Parsed attachment: waybill={waybill_number}, "
            f"invoice={invoice_number}, date={formatted_date}"
        )
    
    return results, attachments


@retry_on_failure(max_retries=MAX_RETRIES, delay=RETRY_DELAY)
def process_and_upload_attachment(filename: str, attachment_data: bytes) -> Optional[Dict[str, str]]:
    """
    Process and upload attachment to S3.
    
    Args:
        filename: Original filename
        attachment_data: Binary attachment data
        
    Returns:
        Dict with pod_url if successful, None otherwise
    """
    try:
        settings = get_s3_settings()
        timestamp = str(int(time.time()))
        base_filename = filename.replace(' ', '_').replace('/', '_')
        name, ext = os.path.splitext(base_filename)
        sanitized_filename = f"{name}_{timestamp}{ext}"
        s3_key = f"{settings['prefix']}/{sanitized_filename}"
        
        # Validate file size (e.g., max 50MB)
        max_size = 50 * 1024 * 1024  # 50MB
        if len(attachment_data) > max_size:
            raise ValueError(f"File size {len(attachment_data)} exceeds maximum {max_size} bytes")
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings["access_key"],
            aws_secret_access_key=settings["secret_key"],
            region_name=settings["region"]
        )
        
        file_stream = io.BytesIO(attachment_data)
        content_type = mimetypes.guess_type(sanitized_filename)[0] or "application/octet-stream"
        
        # Upload with metadata
        s3_client.upload_fileobj(
            Fileobj=file_stream,
            Bucket=settings["bucket"],
            Key=s3_key,
            ExtraArgs={
                "ContentType": content_type,
                "Metadata": {
                    "original_filename": filename,
                    "uploaded_at": datetime.now().isoformat(),
                    "source": "DSR_Logistics_POD"
                }
            }
        )
        
        # Generate URL (use proper S3 URL format based on region)
        if settings["region"] == "us-east-1":
            pod_url = f"https://{settings['bucket']}.s3.amazonaws.com/{s3_key}"
        else:
            pod_url = f"https://{settings['bucket']}.s3.{settings['region']}.amazonaws.com/{s3_key}"
        
        logger.info(f"Successfully uploaded {filename} to S3: {s3_key}")
        return {"pod_url": pod_url, "s3_key": s3_key}
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_msg = f"AWS S3 error uploading {filename}: {error_code} - {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise
    except Exception as e:
        error_msg = f"Error processing {filename}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        notify_manual_intervention(
            subject="DSR POD Upload Failed",
            body=(
                f"<b>Filename:</b> {filename}<br>"
                f"<b>Error:</b> {str(e)}<br>"
                f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>"
                f"Please upload and link it manually."
            )
        )
        raise


def create_invoice_record(parsed_data: Dict[str, str]) -> bool:
    """
    Update SAP AR Invoice Detail record with POD information.
    
    Args:
        parsed_data: Dict containing invoice_number, waybill_number, pod_url, pod_date
        
    Returns:
        True if successful, False otherwise
    """
    invoice_number = parsed_data.get("invoice_number")
    if not invoice_number:
        logger.error("Invoice number missing in parsed_data")
        return False
    
    logger.info(f"Updating SAP AR Invoice Detail for Invoice {invoice_number}...")
    
    try:
        # Find invoice record
        ar_invoice_records = frappe.get_all(
            "SAP AR Invoice Detail",
            filters={"docnum": invoice_number},
            fields=["name", "docentry", "docnum", "way_bill_number", "pod_url", "pod_status"]
        )
        
        if not ar_invoice_records:
            logger.warning(f"No matching SAP AR Invoice Detail found for Invoice {invoice_number}")
            notify_manual_intervention(
                subject="DSR POD: Invoice Not Found",
                body=(
                    f"<b>Invoice Number:</b> {invoice_number}<br>"
                    f"<b>Waybill Number:</b> {parsed_data.get('waybill_number', 'N/A')}<br>"
                    f"<b>POD URL:</b> {parsed_data.get('pod_url', 'N/A')}<br>"
                    f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>"
                    f"Please create or link the invoice manually."
                )
            )
            return False
        
        record = ar_invoice_records[0]
        record_name = record["name"]
        docentry = record["docentry"]
        
        # Check if already processed
        if record.get("pod_status") == "Completed" and record.get("pod_url"):
            logger.info(f"Invoice {invoice_number} already has POD. Skipping update.")
            return False
        
        # Phase 1: write to Frappe with Pending_SAP so a partial failure is retryable
        update_data = {
            "way_bill_number": parsed_data["waybill_number"],
            "pod_url": parsed_data["pod_url"],
            "transporter_type": "DSR Logistics",
            "shipping_status": "Completed",
            "pod_status": "Pending_SAP",
            "pod_date": parsed_data["pod_date"]
        }

        frappe.db.set_value("SAP AR Invoice Detail", record_name, update_data)
        frappe.db.commit()

        logger.info(f"Successfully updated SAP AR Invoice Detail {record_name}")

        # Phase 2: PATCH SAP B1, then mark Completed only on success
        try:
            patch_result = patch_pod_ar_invoice(docentry)
            if patch_result and patch_result.status_code in (200, 204):
                logger.info(f"Successfully updated SAP B1 for docentry {docentry}")
                frappe.db.set_value("SAP AR Invoice Detail", record_name, {"pod_status": "Completed"})
                frappe.db.commit()
            else:
                status = patch_result.status_code if patch_result else "no response"
                logger.warning(f"SAP B1 update failed for docentry {docentry} (status {status}) — left as Pending_SAP")
                frappe.log_error(
                    f"SAP B1 PATCH failed for docentry {docentry} (status {status}). Record left as Pending_SAP.",
                    "DSR POD SAP Update"
                )
        except Exception as e:
            logger.error(f"Error updating SAP B1 for docentry {docentry}: {str(e)}", exc_info=True)
            frappe.log_error(
                f"SAP B1 Update Error for docentry {docentry}: {str(e)}",
                "DSR POD SAP Update"
            )

        return True
        
    except Exception as e:
        error_msg = f"Error updating SAP AR Invoice Detail for {invoice_number}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        frappe.log_error(error_msg, "DSR POD Invoice Update")
        frappe.db.rollback()
        
        notify_manual_intervention(
            subject="SAP AR Invoice Update Failed",
            body=(
                f"<b>Invoice Number:</b> {invoice_number}<br>"
                f"<b>Waybill Number:</b> {parsed_data.get('waybill_number', 'N/A')}<br>"
                f"<b>Error:</b> {str(e)}<br>"
                f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>"
                f"Please update SAP manually."
            )
        )
        return False


def mark_email(mail: imaplib.IMAP4_SSL, email_id: bytes, label: str) -> None:
    """
    Mark email with appropriate flags and labels.
    
    Args:
        mail: IMAP connection object
        email_id: Email ID to mark
        label: Label to apply (Processed, Error, No_Attachments)
    """
    try:
        if label in EMAIL_LABELS:
            mail.store(email_id, "+FLAGS", EMAIL_LABELS[label])
            mail.store(email_id, "+X-GM-LABELS", label)
            logger.debug(f"Marked email {email_id.decode()} as {label}")
    except Exception as e:
        logger.error(
            f"Failed to mark email {email_id.decode()} as '{label}': {str(e)}. "
            "This email may be reprocessed on the next run.",
            exc_info=True,
        )
        frappe.log_error(
            f"Failed to mark email {email_id.decode()} as '{label}': {str(e)}",
            "DSR POD Email Marking",
        )


@retry_on_failure(max_retries=MAX_RETRIES, delay=RETRY_DELAY)
def patch_pod_ar_invoice(docentry: str) -> Optional[Any]:
    """
    Update SAP B1 invoice with POD information via PATCH request.
    
    Args:
        docentry: SAP document entry number
        
    Returns:
        Response object if successful, None otherwise
    """
    try:
        doc = frappe.get_doc('SAP AR Invoice Detail', docentry)
        
        if not doc.pod_url:
            logger.warning(f"POD URL not present for docentry {docentry}. Clearing waybill.")
            doc.way_bill_number = ''
            doc.pod_status = 'Pending'
            doc.save(ignore_permissions=True)
            frappe.db.commit()
            return None
        
        session = AuthenticateSAPB1()
        doc_settings = frappe.get_doc('SAP Settings')
        
        if not doc_settings.sap_b1_url:
            raise ValueError("SAP B1 URL not configured")
        
        url = f"{doc_settings.sap_b1_url}Invoices({doc.docentry})"
        
        # Format POD date
        if doc.pod_date:
            if isinstance(doc.pod_date, date):
                pod_date_str = doc.pod_date.strftime("%Y-%m-%d")
            elif isinstance(doc.pod_date, datetime):
                pod_date_str = doc.pod_date.strftime("%Y-%m-%d")
            else:
                pod_date_str = str(doc.pod_date)
        else:
            pod_date_str = datetime.now().strftime("%Y-%m-%d")
        
        payload = json.dumps({
            "U_TN": "DSR Logistics",
            "TransportationCode": 7,
            "U_TrackingNo": doc.way_bill_number or "",
            "U_Pod_Link": doc.pod_url,
            "U_POD_DATE": pod_date_str
        })
        
        response = session.request(
            "PATCH",
            url,
            headers=SAP_HEADERS,
            data=payload,
            verify=False,
            timeout=30
        )
        
        if response.status_code in (200, 204):
            logger.info(f"SAP B1 update successful for docentry {docentry}. Status: {response.status_code}")
            return response
        else:
            error_msg = (
                f"SAP B1 update failed for docentry {docentry}. "
                f"Status: {response.status_code}, Response: {response.text}"
            )
            logger.error(error_msg)
            raise Exception(error_msg)
            
    except Exception as e:
        error_msg = f"Error patching SAP POD for docentry {docentry}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        frappe.log_error(error_msg, "DSR POD SAP Patch")
        notify_manual_intervention(
            subject="SAP POD Patch Failed",
            body=(
                f"<b>DocEntry:</b> {docentry}<br>"
                f"<b>Error:</b> {str(e)}<br>"
                f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>"
                f"Please patch manually in SAP."
            )
        )
        raise


def notify_manual_intervention(subject: str, body: str) -> None:
    """
    Send notification email for manual intervention.
    
    Args:
        subject: Email subject
        body: Email body (HTML supported)
    """
    try:
        # Get recipients from DSR Settings or use defaults
        recipients = ["mithun@khanalfoods.com", "yogesha@khanalfoods.com"]
        
        # Try to get from settings if available
        try:
            dsr_settings = frappe.get_doc("DSR Settings")
            if hasattr(dsr_settings, 'notification_recipients') and dsr_settings.notification_recipients:
                recipients = [r.strip() for r in dsr_settings.notification_recipients.split(',')]
        except Exception:
            pass  # Use default recipients
        
        frappe.sendmail(
            recipients=recipients,
            subject=f"[DSR POD] {subject}",
            message=body,
            now=True
        )
        logger.info(f"Notification sent to {', '.join(recipients)}: {subject}")
    except Exception as e:
        logger.error(f"Failed to send notification email: {str(e)}", exc_info=True)
        frappe.log_error(f"DSR POD Notification Failed: {str(e)}", "DSR POD Notifications")


# Command line execution
# bench --site <site_name> execute khanal_tech_integrations.utils.DSR_Logistics.Dsr_Pod.process_dsr_emails


# ============================================================================
# SIMPLE REPROCESS FUNCTION - Only updates if SAP B1 POD fields are empty
# ============================================================================

def reprocess_dsr_emails_with_sap_check():
    """
    Simple function to reprocess all DSR emails.
    Only updates invoices if SAP B1 POD fields (pod_url, pod_date) are empty.
    Uses clear print statements for visibility.
    
    Usage:
        bench --site <site_name> execute khanal_tech_integrations.utils.DSR_Logistics.Dsr_Pod.reprocess_dsr_emails_with_sap_check
    """
    print("=" * 80)
    print("DSR POD REPROCESSING - Checking SAP B1 before updating")
    print("=" * 80)
    
    # Get email settings
    try:
        dsr_settings = frappe.get_doc("DSR Settings")
        email_address = dsr_settings.email
        password = dsr_settings.app_password or dsr_settings.password
        
        if not email_address or not password:
            print("ERROR: DSR email credentials not configured")
            return
        
        print(f"✓ Connected to email: {email_address}")
    except Exception as e:
        print(f"ERROR: Failed to load DSR Settings: {str(e)}")
        return
    
    # Get S3 settings
    try:
        s3_settings = frappe.get_single("AWS")
        print(f"✓ S3 bucket configured: {s3_settings.bucket_name_dsr}")
    except Exception as e:
        print(f"ERROR: Failed to load S3 Settings: {str(e)}")
        return
    
    # Connect to email
    mail = None
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(email_address, password)
        print("✓ Successfully logged into email")
    except Exception as e:
        print(f"ERROR: Email login failed: {str(e)}")
        return
    
    try:
        # Select inbox and get ALL emails (not just unread)
        mail.select("inbox")
        status, messages = mail.search(None, "ALL")  # Get ALL emails
        
        if status != "OK":
            print(f"ERROR: Failed to search emails. Status: {status}")
            return
        
        email_ids = messages[0].split() if messages[0] else []
        total_emails = len(email_ids)
        print(f"\n📧 Found {total_emails} total email(s) to process")
        print("-" * 80)
        
        if total_emails == 0:
            print("No emails found. Exiting.")
            return
        
        # Statistics
        stats = {
            "total_emails": total_emails,
            "processed": 0,
            "skipped_empty": 0,
            "skipped_already_filled": 0,
            "errors": 0
        }
        
        # Process each email
        for idx, email_id in enumerate(email_ids, 1):
            email_id_str = email_id.decode() if isinstance(email_id, bytes) else str(email_id)
            print(f"\n[{idx}/{total_emails}] Processing Email ID: {email_id_str}")
            
            try:
                # Fetch email
                status, data = mail.fetch(email_id, "(RFC822)")
                if status != "OK" or not data or not isinstance(data[0], tuple):
                    print(f"  ⚠️  Error fetching email content")
                    stats["errors"] += 1
                    continue
                
                raw_email = data[0][1]
                parsed_results, attachments = parse_email_attachments(raw_email)
                
                if not parsed_results or not attachments:
                    print(f"  ⚠️  No valid POD attachments found")
                    stats["skipped_empty"] += 1
                    continue
                
                print(f"  ✓ Found {len(parsed_results)} valid attachment(s)")
                
                # Process each attachment
                for parsed_data in parsed_results:
                    invoice_number = parsed_data.get("invoice_number")
                    waybill_number = parsed_data.get("waybill_number")
                    
                    print(f"\n  📄 Attachment: {parsed_data['filename']}")
                    print(f"     Invoice: {invoice_number}, Waybill: {waybill_number}")
                    
                    # Check SAP B1 - Is POD already filled?
                    try:
                        ar_invoice = frappe.get_all(
                            "SAP AR Invoice Detail",
                            filters={"docnum": invoice_number},
                            fields=["name", "docentry", "docnum", "pod_url", "pod_date", "pod_status"]
                        )
                        
                        if not ar_invoice:
                            print(f"     ⚠️  Invoice {invoice_number} not found in SAP AR Invoice Detail")
                            stats["errors"] += 1
                            continue
                        
                        invoice_record = ar_invoice[0]
                        pod_url = invoice_record.get("pod_url")
                        pod_date = invoice_record.get("pod_date")
                        pod_status = invoice_record.get("pod_status", "")
                        
                        # Check if POD fields are already filled
                        if pod_url and pod_date and pod_status == "Completed":
                            print(f"     ⏭️  SKIPPED: Invoice already has POD")
                            print(f"        POD URL: {pod_url}")
                            print(f"        POD Date: {pod_date}")
                            print(f"        POD Status: {pod_status}")
                            stats["skipped_already_filled"] += 1
                            continue
                        
                        # POD is empty or incomplete - proceed with upload
                        print(f"     ✓ POD fields are empty/incomplete - Proceeding with upload")
                        
                        # Upload to S3
                        print(f"     📤 Uploading to S3...")
                        s3_result = process_and_upload_attachment(
                            parsed_data["filename"],
                            attachments[parsed_data["filename"]]
                        )
                        
                        if not s3_result or not s3_result.get("pod_url"):
                            print(f"     ❌ Upload to S3 failed")
                            stats["errors"] += 1
                            continue
                        
                        pod_url = s3_result["pod_url"]
                        print(f"     ✓ Uploaded successfully: {pod_url}")
                        
                        # Update invoice record
                        parsed_data.update(s3_result)
                        record_name = invoice_record["name"]
                        docentry = invoice_record["docentry"]
                        
                        print(f"     💾 Updating SAP AR Invoice Detail (Phase 1 — Pending_SAP)...")
                        frappe.db.set_value("SAP AR Invoice Detail", record_name, {
                            "way_bill_number": waybill_number,
                            "pod_url": pod_url,
                            "transporter_type": "DSR Logistics",
                            "shipping_status": "Completed",
                            "pod_status": "Pending_SAP",
                            "pod_date": parsed_data["pod_date"]
                        })
                        frappe.db.commit()
                        print(f"     ✓ Phase 1 database update done")

                        # Update SAP B1 — mark Completed only on success
                        print(f"     🔄 Updating SAP B1 (Phase 2)...")
                        try:
                            patch_result = patch_pod_ar_invoice(docentry)
                            if patch_result and patch_result.status_code in (200, 204):
                                frappe.db.set_value("SAP AR Invoice Detail", record_name, {"pod_status": "Completed"})
                                frappe.db.commit()
                                print(f"     ✓ SAP B1 updated successfully")
                            else:
                                status = patch_result.status_code if patch_result else "no response"
                                print(f"     ⚠️  SAP B1 PATCH returned {status} — left as Pending_SAP")
                                frappe.log_error(
                                    f"SAP PATCH failed for docentry {docentry} (status {status}). Left as Pending_SAP.",
                                    "DSR POD Reprocess SAP Update",
                                )
                        except Exception as e:
                            print(f"     ⚠️  SAP B1 update failed: {str(e)}")
                            frappe.log_error(
                                f"SAP PATCH exception for docentry {docentry}: {str(e)}",
                                "DSR POD Reprocess SAP Update",
                            )

                        stats["processed"] += 1
                        print(f"     ✅ COMPLETED: Invoice {invoice_number} processed successfully")
                        
                    except Exception as e:
                        print(f"     ❌ Error processing invoice {invoice_number}: {str(e)}")
                        stats["errors"] += 1
                        continue
                
            except Exception as e:
                print(f"  ❌ Error processing email {email_id_str}: {str(e)}")
                stats["errors"] += 1
                continue
        
        # Print final statistics
        print("\n" + "=" * 80)
        print("PROCESSING COMPLETE - Final Statistics")
        print("=" * 80)
        print(f"Total Emails Processed: {stats['total_emails']}")
        print(f"✅ Successfully Updated: {stats['processed']}")
        print(f"⏭️  Skipped (Already Filled): {stats['skipped_already_filled']}")
        print(f"⚠️  Skipped (No Attachments): {stats['skipped_empty']}")
        print(f"❌ Errors: {stats['errors']}")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        if mail:
            try:
                mail.logout()
                print("\n✓ Email connection closed")
            except:
                pass


# Command line execution for reprocess function:
# bench --site khanaltech.com execute khanal_tech_integrations.utils.DSR_Logistics.Dsr_Pod.reprocess_dsr_emails_with_sap_check
