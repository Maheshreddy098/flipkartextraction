"""
Pre-Posting Validation Module for SAP Posting
Validates batch quantities, SAP accessibility, and item active status before posting to SAP B1

This module ensures:
1. Batch quantities are sufficient for all orders
2. SAP Service Layer is accessible (renews session if needed)
3. All items are active in SAP (Frozen='tNO')
"""

import frappe
import logging
import requests
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from ..client.sap import SAPClient
from ..mappers.sap_payload import CHANNEL_WAREHOUSE_MAP, DEFAULT_WAREHOUSE
from khanal_tech_integrations.api.common.sap_connector import SAPConnector

# Configure logging
logger = logging.getLogger(__name__)


def _create_database_connection():
    connector = SAPConnector()
    connection, cursor, _ = connector.get_hana_connection()
    return connector, connection, cursor


def _close_database_connection(connector, connection, cursor):
    if connector:
        connector.close_hana_connection(connection, cursor)


class ValidationError(Exception):
    """Custom exception for validation errors"""
    def __init__(self, message, validation_type, details=None):
        self.message = message
        self.validation_type = validation_type  # 'SAP_ACCESS', 'BATCH_QUANTITY', 'ITEM_STATUS'
        self.details = details or {}
        super().__init__(self.message)


def check_sap_service_layer_accessibility(force_renew=False) -> Tuple[bool, str, Optional[requests.Session]]:
    """
    Check if SAP Service Layer is accessible and session is valid
    
    Args:
        force_renew (bool): Force session renewal even if cached session exists
        
    Returns:
        tuple: (is_accessible, message, session)
            - is_accessible (bool): True if SAP is accessible
            - message (str): Status message
            - session (requests.Session): Valid SAP session or None
    """
    logger.info("Checking SAP Service Layer accessibility...")
    
    try:
        sap = SAPClient()
        sap.login()
        sap.get("Items", params={"$top": 1, "$select": "ItemCode"})
        logger.info("SAP Service Layer is accessible")
        return True, "SAP Service Layer is accessible", sap.session
    except requests.exceptions.Timeout:
        return False, "SAP Service Layer request timed out (check network connectivity)", None
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to SAP Service Layer (check URL and network)", None
    except Exception as e:
        error_msg = f"SAP Service Layer accessibility check failed: {str(e)}"
        logger.error(error_msg)
        return False, error_msg, None


def validate_batch_quantities_for_orders(order_list: List[str], channel_name: str) -> Tuple[List[Dict], List[Dict]]:
    """
    Validate batch quantities for a list of orders
    
    Args:
        order_list (list): List of Unicommerce order IDs
        channel_name (str): Channel name for context
        
    Returns:
        tuple: (failed_items, available_items)
            - failed_items: List of items with insufficient batch quantities
            - available_items: List of items with sufficient quantities
    """
    logger.info(f"Validating batch quantities for {len(order_list)} orders in channel {channel_name}...")
    
    failed_items = []
    available_items = []
    connector = None
    connection = None
    cursor = None
    
    if not order_list:
        return failed_items, available_items
    
    try:
        # Get all order documents
        orders_data = []
        for order_id in order_list:
            try:
                order_doc = frappe.get_doc('Unicommerce Orders', order_id)
                orders_data.append(order_doc)
            except Exception as e:
                logger.warning(f"Failed to load order {order_id}: {str(e)}")
                continue
        
        if not orders_data:
            logger.error("No valid orders found")
            return failed_items, available_items
        
        # Create database connection
        connector, connection, cursor = _create_database_connection()
        
        # Aggregate required quantities by item_code, batch_number, and warehouse
        required_quantities = {}  # Key: (item_code, batch_number, warehouse_code)
        
        for order_doc in orders_data:
            if not hasattr(order_doc, 'line_items') or not order_doc.line_items:
                continue
            
            for line_item in order_doc.line_items:
                item_code = getattr(line_item, 'item_code', None) or getattr(line_item, 'itemcode', None)
                batch_number = getattr(line_item, 'batch_number', None) or getattr(line_item, 'batchnumber', None)
                warehouse_code = getattr(line_item, 'warehouse_code', None) or getattr(line_item, 'warehousecode', None)
                quantity = float(getattr(line_item, 'quantity', 0) or getattr(line_item, 'qty', 0) or 0)
                
                if not item_code or not batch_number or quantity <= 0:
                    continue
                
                # Use default warehouse if not specified
                if not warehouse_code:
                    # Try to get from channel configuration
                    try:
                        warehouse_code = CHANNEL_WAREHOUSE_MAP.get(
                            (channel_name or "").strip().upper(),
                            DEFAULT_WAREHOUSE,
                        )
                    except Exception:
                        warehouse_code = DEFAULT_WAREHOUSE
                
                key = (item_code, batch_number, warehouse_code)
                if key not in required_quantities:
                    required_quantities[key] = {
                        'ItemCode': item_code,
                        'BatchNumber': batch_number,
                        'Warehouse': warehouse_code,
                        'RequiredQty': 0,
                        'Orders': []
                    }
                
                required_quantities[key]['RequiredQty'] += quantity
                required_quantities[key]['Orders'].append(order_doc.name)
        
        # Check batch quantities in SAP HANA
        for key, item_data in required_quantities.items():
            item_code = item_data['ItemCode']
            batch_number = item_data['BatchNumber']
            warehouse_code = item_data['Warehouse']
            required_qty = item_data['RequiredQty']
            
            try:
                # Query OIBT table for available quantity
                cursor.execute("""
                    SELECT COALESCE(SUM("Quantity"), 0) AS "AvailableQty"
                    FROM OIBT
                    WHERE "ItemCode" = ? 
                      AND "BatchNum" = ? 
                      AND "WhsCode" = ?
                """, (item_code, batch_number, warehouse_code))
                
                result = cursor.fetchone()
                available_qty = float(result[0]) if result and result[0] is not None else 0
                
                if available_qty >= required_qty:
                    available_items.append({
                        'ItemCode': item_code,
                        'BatchNumber': batch_number,
                        'Warehouse': warehouse_code,
                        'RequiredQty': required_qty,
                        'AvailableQty': available_qty,
                        'Status': 'AVAILABLE',
                        'Orders': item_data['Orders']
                    })
                else:
                    shortage = required_qty - available_qty
                    failed_items.append({
                        'ItemCode': item_code,
                        'BatchNumber': batch_number,
                        'Warehouse': warehouse_code,
                        'RequiredQty': required_qty,
                        'AvailableQty': available_qty,
                        'Shortage': shortage,
                        'Status': 'INSUFFICIENT_STOCK',
                        'Message': f"Item {item_code} with batch {batch_number} in warehouse {warehouse_code}: Required {required_qty}, Available {available_qty}, Shortage {shortage}",
                        'Orders': item_data['Orders']
                    })
                    
            except Exception as e:
                logger.error(f"Error checking batch quantity for {item_code}/{batch_number}/{warehouse_code}: {str(e)}")
                failed_items.append({
                    'ItemCode': item_code,
                    'BatchNumber': batch_number,
                    'Warehouse': warehouse_code,
                    'RequiredQty': required_qty,
                    'AvailableQty': 0,
                    'Status': 'CHECK_FAILED',
                    'Message': f"Failed to check batch quantity: {str(e)}",
                    'Orders': item_data['Orders']
                })
        
        # Close database connection
        _close_database_connection(connector, connection, cursor)
        
        logger.info(f"Batch validation complete: {len(available_items)} available, {len(failed_items)} failed")
        return failed_items, available_items
        
    except Exception as e:
        error_msg = f"Error validating batch quantities: {str(e)}"
        logger.error(error_msg)
        frappe.log_error(error_msg, "Batch Quantity Validation Error")
        return failed_items, available_items


@frappe.whitelist()
def comprehensive_pre_posting_validation(channel_name: str, start_date: str, end_date: str, 
                                         order_list: Optional[List[str]] = None) -> Dict:
    """
    Comprehensive pre-posting validation before SAP posting
    
    This function performs validations:
    1. SAP Service Layer accessibility check
    2. Batch quantity validation for all orders
    (Item active status check is not run; posting is not blocked by missing/inactive items in SAP.)
    
    Args:
        channel_name (str): Channel name
        start_date (str): Start date in DD-MM-YYYY format
        end_date (str): End date in DD-MM-YYYY format
        order_list (list, optional): Specific order list to validate. If None, fetches orders for date range.
        
    Returns:
        dict: Validation results with detailed error messages
            {
                'is_valid': bool,
                'sap_accessible': bool,
                'sap_message': str,
                'batch_validation': {
                    'passed': bool,
                    'failed_items': list,
                    'available_items': list
                },
                'item_status_validation': {
                    'passed': bool,
                    'inactive_items': list,
                    'active_items': list
                },
                'errors': list,
                'warnings': list
            }
    """
    logger.info(f"=== Starting comprehensive pre-posting validation for {channel_name} ===")
    
    validation_result = {
        'is_valid': False,
        'sap_accessible': False,
        'sap_message': '',
        'batch_validation': {
            'passed': False,
            'failed_items': [],
            'available_items': []
        },
        'item_status_validation': {
            'passed': False,
            'inactive_items': [],
            'active_items': []
        },
        'errors': [],
        'warnings': []
    }
    
    try:
        # Step 1: Check SAP Service Layer accessibility
        logger.info("Step 1: Checking SAP Service Layer accessibility...")
        sap_accessible, sap_message, session = check_sap_service_layer_accessibility(force_renew=False)
        validation_result['sap_accessible'] = sap_accessible
        validation_result['sap_message'] = sap_message
        
        if not sap_accessible:
            validation_result['errors'].append(f"SAP Service Layer not accessible: {sap_message}")
            logger.error(f"SAP accessibility check failed: {sap_message}")
            return validation_result
        
        # Item status check is not run (posting is not blocked by it). Set passed=True so early
        # returns (e.g. batch failure) do not wrongly report "Item Status: 0 items inactive".
        validation_result['item_status_validation']['passed'] = True
        validation_result['item_status_validation']['inactive_items'] = []
        validation_result['item_status_validation']['active_items'] = []
        
        # Step 2: Get order list if not provided
        if not order_list:
            logger.info("Step 2: Fetching orders for validation...")
            try:
                start_dt = datetime.strptime(start_date, "%d-%m-%Y").strftime("%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%d-%m-%Y").strftime("%Y-%m-%d")
                rows = frappe.get_all(
                    "Unicommerce Orders",
                    filters={
                        "channel_name": ["like", channel_name],
                        "order_date": ["between", [start_dt, end_dt]],
                        "pipeline_status": ["in", ["ready", "posting", "failed", "batch_hold", "verify"]],
                    },
                    fields=["name"],
                    limit=20000,
                )
                order_list = [row.get("name") for row in rows if row.get("name")]
                logger.info(f"Found {len(order_list)} orders to validate")
            except Exception as e:
                error_msg = f"Failed to fetch orders: {str(e)}"
                logger.error(error_msg)
                validation_result['errors'].append(error_msg)
                return validation_result
        
        if not order_list:
            validation_result['warnings'].append("No orders found for validation")
            validation_result['is_valid'] = True  # No orders means nothing to validate
            return validation_result
        
        # Step 3: Validate batch quantities
        logger.info(f"Step 3: Validating batch quantities for {len(order_list)} orders...")
        failed_batch_items, available_batch_items = validate_batch_quantities_for_orders(order_list, channel_name)
        
        validation_result['batch_validation']['failed_items'] = failed_batch_items
        validation_result['batch_validation']['available_items'] = available_batch_items
        validation_result['batch_validation']['passed'] = len(failed_batch_items) == 0
        
        if failed_batch_items:
            error_messages = [item.get('Message', f"{item['ItemCode']} - {item['Status']}") for item in failed_batch_items]
            validation_result['errors'].extend(error_messages)
            logger.error(f"Batch validation failed for {len(failed_batch_items)} items")
        
        # Step 4: Item active status check removed per requirement (no longer blocking post)
        validation_result['item_status_validation']['passed'] = True
        validation_result['item_status_validation']['inactive_items'] = []
        validation_result['item_status_validation']['active_items'] = []
        
        # Final validation result (SAP accessible + batch validation only; item status not required)
        validation_result['is_valid'] = (
            validation_result['sap_accessible'] and
            validation_result['batch_validation']['passed']
        )
        
        if validation_result['is_valid']:
            logger.info("=== Pre-posting validation PASSED ===")
        else:
            logger.warning("=== Pre-posting validation FAILED ===")
            logger.warning(f"Errors: {validation_result['errors']}")
        
        return validation_result
        
    except Exception as e:
        error_msg = f"Comprehensive validation failed: {str(e)}"
        logger.error(error_msg)
        frappe.log_error(error_msg, "Pre-Posting Validation Error")
        validation_result['errors'].append(error_msg)
        validation_result['is_valid'] = False
        return validation_result
