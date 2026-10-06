"""
Configuration constants for Safexpress integration.

This module contains all configuration constants, API endpoints, and default values
used throughout the Safexpress integration.
"""

from typing import List

# API Endpoints
SAFEXPRESS_TRACKING_API_URL = "https://webs.safexpress.com:8443/SafexWaybillTracking/webresources/tracking/all"

# Invoice Series Prefixes
INVOICE_SERIES_PREFIXES: List[str] = [
    "KAIN24",
    "KAIN25",
    "AR2024",
    "AR2025",
    "HRIN24",
    "HRIN25",
    "MHIN24",
    "MHIN25",
    "KAIN23",
    "AR2023",
    "HRIN23",
    "MHIN23",
    "Manual",
]

# Default Values
DEFAULT_LOOKBACK_DAYS: int = 4
MAX_LOOKBACK_DAYS: int = 500
DEFAULT_BATCH_SIZE: int = 50
DEFAULT_TIMEOUT_SECONDS: int = 30
DEFAULT_POD_FETCH_TIMEOUT_SECONDS: int = 60  # Longer timeout for POD API (can be slow)
DEFAULT_UPLOAD_TIMEOUT_SECONDS: int = 60

# Retry Configuration
MAX_RETRY_ATTEMPTS: int = 3
RETRY_DELAY_SECONDS: int = 2
RETRY_BACKOFF_MULTIPLIER: float = 2.0

# HTTP Status Codes
HTTP_SUCCESS_CODES: List[int] = [200, 201, 204]
HTTP_NOT_FOUND: int = 404

# Date Formats (in order of preference)
DATE_FORMATS: List[str] = [
    "%d-%b-%Y",  # 25-Nov-2024
    "%d/%m/%Y",  # 25/11/2024
    "%Y-%m-%d",  # 2024-11-25
    "%d-%m-%Y",  # 25-11-2024
]

# SAP Field Names
SAP_FIELD_TRANSPORTER_NAME = "U_TN"
SAP_FIELD_TRACKING_NUMBER = "U_TrackingNo"
SAP_FIELD_POD_LINK = "U_Pod_Link"
SAP_FIELD_POD_DATE = "U_POD_DATE"
SAP_FIELD_TRANSPORTATION_CODE = "TransportationCode"

# Document Types
DOC_TYPE_INVOICE = "INV"
DOC_TYPE_WAYBILL = "WB"

# POD Status Values
POD_STATUS_COMPLETED = "Completed"
POD_STATUS_PENDING = "Pending"

# Transporter Name
TRANSPORTER_NAME_SAFEXPRESS = "Safexpress"

# S3 Configuration
S3_UPLOAD_URL = "https://tg31l9q380.execute-api.us-west-1.amazonaws.com/dev/khanalfoods-fileupload-bucket/"
S3_BUCKET_URL = "https://khanalfoods-fileupload-bucket.s3.us-west-1.amazonaws.com/"

