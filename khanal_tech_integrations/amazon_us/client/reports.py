"""SP-API Reports API client: create → poll → download."""
import gzip
import time

import frappe
import requests

from khanal_tech_integrations.amazon_us import SP_API_BASE
from khanal_tech_integrations.amazon_us.client.sp_api import _get, _post

_REPORTS_BASE = "/reports/2021-06-30"


def list_reports(report_type, marketplace_id=None, processing_status="DONE", page_size=10):
    """
    List auto-generated reports of a given type (e.g. settlement reports).
    marketplace_id filters to a specific marketplace (e.g. ATVPDKIKX0DER for US).
    Returns list of report dicts with reportId, reportDocumentId, dataStartTime, dataEndTime.
    """
    params = {
        "reportTypes": report_type,
        "processingStatuses": processing_status,
        "pageSize": page_size,
    }
    if marketplace_id:
        params["marketplaceIds"] = marketplace_id
    resp = _get(f"{_REPORTS_BASE}/reports", params=params)
    if resp.status_code != 200:
        raise Exception(f"list_reports failed: {resp.status_code} {resp.text[:200]}")
    return resp.json().get("reports", [])


def create_report(report_type, marketplace_id, data_start_time, data_end_time):
    """
    Request a new SP-API report. Returns reportId string.
    data_start_time / data_end_time must be UTC ISO 8601 strings.
    """
    body = {
        "reportType": report_type,
        "marketplaceIds": [marketplace_id],
        "dataStartTime": data_start_time,
        "dataEndTime": data_end_time,
    }
    resp = _post(f"{_REPORTS_BASE}/reports", body=body)
    if resp.status_code not in (200, 202):
        raise Exception(
            f"create_report failed: {resp.status_code} {resp.text[:300]}"
        )
    return resp.json().get("reportId")


def poll_report(report_id, poll_interval=30, max_wait=600):
    """
    Poll until report processingStatus=DONE. Returns reportDocumentId.
    Raises if status=FATAL/CANCELLED or max_wait exceeded.
    """
    deadline = time.time() + max_wait
    while time.time() < deadline:
        resp = _get(f"{_REPORTS_BASE}/reports/{report_id}")
        if resp.status_code != 200:
            raise Exception(
                f"poll_report failed: {resp.status_code} {resp.text[:200]}"
            )
        data = resp.json()
        status = data.get("processingStatus", "")
        frappe.logger().info(f"[reports] {report_id} status={status}")
        if status == "DONE":
            return data.get("reportDocumentId")
        if status in ("FATAL", "CANCELLED"):
            raise Exception(f"Report {report_id} ended with status={status}")
        time.sleep(poll_interval)
    raise Exception(f"Report {report_id} not ready after {max_wait}s")


def download_report(report_document_id):
    """
    Get presigned download URL for a report document and return content as string.
    Auto-decompresses GZIP if compressionAlgorithm=GZIP.
    """
    resp = _get(f"{_REPORTS_BASE}/documents/{report_document_id}")
    if resp.status_code != 200:
        raise Exception(
            f"download_report metadata failed: {resp.status_code} {resp.text[:200]}"
        )
    doc_info = resp.json()
    url = doc_info.get("url")
    if not url:
        raise ValueError(f"No download URL returned for report document {report_document_id}")
    compression = doc_info.get("compressionAlgorithm", "")

    content_resp = requests.get(url, timeout=120)
    content_resp.raise_for_status()

    if compression.upper() == "GZIP":
        return gzip.decompress(content_resp.content).decode("utf-8", errors="replace")
    return content_resp.text
