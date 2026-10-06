"""
Safexpress2 - Production-Grade Safexpress Integration

A clean, modular, and production-ready implementation of Safexpress API integration
for SAP B1 invoice and delivery note management.

This module provides:
- Authentication with automatic token renewal
- POD (Proof of Delivery) retrieval and processing
- Tracking information updates
- SAP B1 integration for invoice and delivery note updates

Usage:
    from khanal_tech_integrations.utils.safexpress2 import (
        process_invoices_without_pod,
        get_all_pods_from_last_year,
        update_tracking_by_invoice,
    )
"""

from .pod_service import (
    process_invoices_without_pod,
    get_all_pods_from_last_year,
    process_pod_for_invoice,
)

from .tracking_service import (
    update_tracking_by_invoice,
    update_tracking_by_waybill,
)

__version__ = "2.0.0"
__all__ = [
    "process_invoices_without_pod",
    "get_all_pods_from_last_year",
    "process_pod_for_invoice",
    "update_tracking_by_invoice",
    "update_tracking_by_waybill",
]

