"""
Batch Quantity Validator for Unicommerce Orders
Validates batch quantities in HANA warehouse against Unicommerce order requirements
"""

import frappe
import pandas as pd
import os
import logging
import traceback
from datetime import datetime
from frappe import _
from frappe.utils import get_datetime, cint

# Canonical channel→warehouse map (mirrors mappers/sap_payload.py).
# FBA fulfilment-centre channels have dedicated warehouses; everything else → EC-FG.
from khanal_tech_integrations.unicommerce.mappers.sap_payload import (
    CHANNEL_WAREHOUSE_MAP,
    DEFAULT_WAREHOUSE,
)
from khanal_tech_integrations.api.common.sap_connector import SAPConnector


def _resolve_warehouse_for_channel(channel_name: str) -> str:
    """Return the SAP warehouse code for a given Unicommerce channel name."""
    return CHANNEL_WAREHOUSE_MAP.get((channel_name or "").strip().upper(), DEFAULT_WAREHOUSE)


def create_database_connection():
    connector = SAPConnector()
    connection, cursor, _ = connector.get_hana_connection()
    return connector, connection, cursor


def close_database_connection(connector, connection, cursor):
    if connector:
        connector.close_hana_connection(connection, cursor)

# Configure logging
logger = logging.getLogger(__name__)


def _normalize_date(date_value):
    """
    Normalize date input to datetime object with proper handling.
    
    Args:
        date_value: String date, datetime object, or None
        
    Returns:
        datetime object or None
        
    Raises:
        ValueError: If date cannot be parsed
    """
    if not date_value:
        return None
    
    if isinstance(date_value, datetime):
        return date_value
    
    if not isinstance(date_value, str):
        try:
            return get_datetime(date_value)
        except Exception:
            raise ValueError(f"Unable to parse date: {date_value}")
    
    # Try YYYY-MM-DD format first
    if len(date_value) == 10 and date_value.count('-') == 2:
        if date_value[4] == '-' and date_value[7] == '-':
            try:
                dt = datetime.strptime(date_value, "%Y-%m-%d")
                return dt.replace(hour=0, minute=0, second=0, microsecond=0)
            except ValueError:
                pass
    
    # Try DD-MM-YYYY format
    if len(date_value) == 10 and date_value.count('-') == 2:
        try:
            dt = datetime.strptime(date_value, "%d-%m-%Y")
            return dt.replace(hour=0, minute=0, second=0, microsecond=0)
        except ValueError:
            pass
    
    # Fallback to frappe's get_datetime
    try:
        dt = get_datetime(date_value)
        if isinstance(dt, datetime):
            # If time is at midnight, ensure it's properly set
            if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
                dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
            return dt
        return dt
    except Exception as e:
        raise ValueError(f"Unable to parse date '{date_value}': {str(e)}")


def _build_order_filters(filters):
    """
    Build order filters from input filters dictionary with validation.
    
    Args:
        filters (dict): Input filters
        
    Returns:
        dict: Validated order filters for frappe.db.get_list
    """
    order_filters = {}
    
    if not filters:
        return order_filters
    
    # Status filter
    if filters.get("status"):
        status = str(filters["status"]).strip()
        if status:
            order_filters["status"] = status
    
    # Channel name filter - DO NOT add to order_filters
    # We'll filter by channel in Python after fetching to avoid case-sensitivity issues
    # This ensures we catch all case variations (FLIPKART, Flipkart, flipkart, etc.)
    # Just log it, don't add to order_filters
    channel_name = filters.get("channel_name")
    if channel_name:
        logger.info(f"Channel filter will be applied in Python after fetching: '{channel_name}'")
    else:
        logger.info("No channel filter provided in filters")
    
    # Date filters
    start_date = filters.get("start_date")
    end_date = filters.get("end_date")
    
    if start_date or end_date:
        try:
            start_dt = None
            end_dt = None
            
            if start_date:
                start_dt = _normalize_date(start_date)
            
            if end_date:
                end_dt = _normalize_date(end_date)
                # Set to end of day if only date provided
                if isinstance(end_dt, datetime):
                    if end_dt.hour == 0 and end_dt.minute == 0 and end_dt.second == 0:
                        end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=0)
            
            # Build date filter
            if start_dt and end_dt:
                if start_dt > end_dt:
                    raise ValueError(f"Start date ({start_dt}) cannot be after end date ({end_dt})")
                order_filters["displayorderdatetime"] = ("between", [start_dt, end_dt])
                logger.info(f"Date filter: {start_dt.strftime('%Y-%m-%d %H:%M:%S')} to {end_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            elif start_dt:
                order_filters["displayorderdatetime"] = (">=", start_dt)
                logger.info(f"Date filter: From {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            elif end_dt:
                order_filters["displayorderdatetime"] = ("<=", end_dt)
                logger.info(f"Date filter: Until {end_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                
        except Exception as e:
            error_msg = f"Error processing date filters: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    return order_filters


def _validate_line_item_data(line_item, uniware_id):
    """
    Validate and extract data from line item with error handling.
    
    Args:
        line_item: Line item dict from order
        uniware_id: Order ID for error context
        
    Returns:
        dict: Validated data or None if validation fails
    """
    try:
        item_code = line_item.get('itemsku')
        batch_number = line_item.get('vendorbatchnumber')  # SAP Batch Code
        quantity = line_item.get('quantity')
        
        # Validate required fields
        if not item_code:
            return {
                "valid": False,
                "error": "Item code (itemsku) is missing",
                "item_code": None
            }
        
        if not batch_number:
            return {
                "valid": False,
                "error": "Batch number (vendorbatchnumber) is missing",
                "item_code": item_code
            }
        
        if quantity is None:
            return {
                "valid": False,
                "error": "Quantity is missing",
                "item_code": item_code,
                "batch_number": batch_number
            }
        
        # Validate and convert quantity
        try:
            required_qty = float(quantity)
            if required_qty <= 0:
                return {
                    "valid": False,
                    "error": f"Quantity must be positive, got: {quantity}",
                    "item_code": item_code,
                    "batch_number": batch_number
                }
        except (ValueError, TypeError) as e:
            return {
                "valid": False,
                "error": f"Invalid quantity format: {quantity} ({str(e)})",
                "item_code": item_code,
                "batch_number": batch_number
            }
        
        # Clean and validate strings
        item_code = str(item_code).strip()
        batch_number = str(batch_number).strip()
        
        if not item_code:
            return {
                "valid": False,
                "error": "Item code is empty after cleaning",
                "item_code": None
            }
        
        if not batch_number:
            return {
                "valid": False,
                "error": "Batch number is empty after cleaning",
                "item_code": item_code
            }
        
        return {
            "valid": True,
            "item_code": item_code,
            "batch_number": batch_number,
            "required_qty": required_qty
        }
        
    except Exception as e:
        return {
            "valid": False,
            "error": f"Unexpected error validating line item: {str(e)}",
            "item_code": None
        }


def _get_total_ec_fg_qty_in_hana(cursor, item_code: str) -> dict:
    """Return total available quantity for an item across ALL batches in EC-FG."""
    try:
        cursor.execute(
            """
            SELECT SUM(T0."Quantity")
            FROM OBTQ T0
            WHERE T0."ItemCode" = ?
              AND T0."WhsCode" = 'EC-FG'
              AND T0."Quantity" > 0
            """,
            (item_code,),
        )
        result = cursor.fetchone()
        total = float(result[0]) if result and result[0] else 0.0
        return {"available_qty": total}
    except Exception as exc:
        logger.error("_get_total_ec_fg_qty_in_hana failed for %s: %s", item_code, exc)
        return {"available_qty": 0.0, "error": str(exc)}


def _check_batch_quantity_in_hana(cursor, item_code, warehouse_code, batch_number):
    """
    Check batch quantity in HANA database using OBTQ (Batch Quantity) table.
    This EXACTLY matches the user's SAP B1 query structure.
    
    User's query structure:
    SELECT T0."ItemCode", T0."WhsCode", T1."DistNumber", T0."Quantity"
    FROM OBTQ T0  
    LEFT JOIN OBTN T1 ON T1."ItemCode" = T0."ItemCode" AND T0."SysNumber" = T1."SysNumber"
    INNER JOIN OITM T2 ON T1."ItemCode" = T2."ItemCode"
    WHERE T0."Quantity" <> 0 AND T2."validFor" = 'Y'
    
    Args:
        cursor: HANA database cursor
        item_code: Item code to check
        warehouse_code: Warehouse code
        batch_number: Batch number (DistNumber in OBTN)
        
    Returns:
        dict: Result with available quantity and status
    """
    try:
        # EXACT match to user's SAP B1 query structure
        # Use LEFT JOIN for OBTN (as in user's query) and INNER JOIN for OITM
        # Try with validFor first
        query = """
            SELECT 
                T0."Quantity"
            FROM OBTQ T0
            LEFT JOIN OBTN T1 ON T1."ItemCode" = T0."ItemCode" 
                              AND T0."SysNumber" = T1."SysNumber"
            INNER JOIN OITM T2 ON T1."ItemCode" = T2."ItemCode"
            WHERE T0."ItemCode" = ? 
              AND T0."WhsCode" = ? 
              AND T1."DistNumber" = ?
              AND T0."Quantity" <> 0
              AND T2."validFor" = 'Y'
        """
        
        logger.debug(f"Querying HANA for batch: Item={item_code}, Warehouse={warehouse_code}, Batch={batch_number}")
        cursor.execute(query, (item_code, warehouse_code, batch_number))
        result = cursor.fetchone()
        
        if result is None:
            # Try without validFor filter (some items might be valid but flag is different)
            query_fallback = """
                SELECT 
                    T0."Quantity"
                FROM OBTQ T0
                LEFT JOIN OBTN T1 ON T1."ItemCode" = T0."ItemCode" 
                                  AND T0."SysNumber" = T1."SysNumber"
                WHERE T0."ItemCode" = ? 
                  AND T0."WhsCode" = ? 
                  AND T1."DistNumber" = ?
                  AND T0."Quantity" <> 0
            """
            logger.debug(f"Trying fallback query (without validFor filter)")
            cursor.execute(query_fallback, (item_code, warehouse_code, batch_number))
            result = cursor.fetchone()
        
        if result is None:
            # Try simplest query - just OBTQ with basic filters
            query_simple = """
                SELECT 
                    T0."Quantity"
                FROM OBTQ T0
                LEFT JOIN OBTN T1 ON T1."ItemCode" = T0."ItemCode" 
                                  AND T0."SysNumber" = T1."SysNumber"
                WHERE T0."ItemCode" = ? 
                  AND T0."WhsCode" = ? 
                  AND T1."DistNumber" = ?
            """
            logger.debug(f"Trying simple query (without quantity filter)")
            cursor.execute(query_simple, (item_code, warehouse_code, batch_number))
            result = cursor.fetchone()
        
        if result is None:
            available_qty = 0.0
            status = "BATCH_NOT_FOUND"
            logger.warning(f"No batch quantity found in OBTQ: Item={item_code}, Warehouse={warehouse_code}, Batch={batch_number}")
        else:
            qty = result[0]
            if qty is None:
                available_qty = 0.0
                status = "NO_DATA"
            else:
                try:
                    available_qty = float(qty)
                    if available_qty <= 0:
                        # Quantity is 0 or negative, treat as not available
                        available_qty = 0.0
                        status = "NO_DATA"
                        logger.debug(f"Batch quantity is 0 or negative: {qty}")
                    else:
                        status = "SUCCESS"
                        logger.info(f"✅ Found batch quantity: {available_qty} for {item_code}/{batch_number} in {warehouse_code}")
                except (ValueError, TypeError) as e:
                    logger.error(f"Invalid quantity value in HANA: {qty} (type: {type(qty)}) for {item_code}/{batch_number}: {str(e)}")
                    available_qty = 0.0
                    status = "INVALID_DATA"
        
        return {
            "available_qty": available_qty,
            "status": status,
            "error": None
        }
        
    except Exception as e:
        error_msg = f"Database error checking batch quantity: {str(e)}"
        logger.error(f"{error_msg}\nTraceback: {traceback.format_exc()}")
        return {
            "available_qty": 0.0,
            "status": "ERROR",
            "error": error_msg
        }


def _emit_progress(progress_callback, step, message, detail=""):
    """Call progress_callback if provided (for UI progress reporting)."""
    if progress_callback and callable(progress_callback):
        try:
            progress_callback(step=step, message=message, detail=detail or "")
        except Exception:
            pass


@frappe.whitelist()
def validate_batch_quantities_from_unicommerce_orders(filters=None, export_to_excel=False, progress_callback=None):
    """
    REBUILT: Clean batch validation with proper OBTQ query and channel filtering.
    
    This function:
    1. Fetches filtered unicommerce orders (with channel filter applied at DB level)
    2. Extracts item_code, batch_number, quantity from line items
    3. Checks batch quantity in HANA using OBTQ table (matching user's SAP B1 query)
    4. Returns validation results with proper channel filtering
    
    If progress_callback is provided (e.g. from background job), it is called with
    (step, message, detail) so the frontend can show live progress.
    """
    results = {
        "total_orders": 0,
        "total_line_items": 0,
        "valid_batches": [],
        "invalid_batches": [],
        "errors": [],
        "warnings": []
    }
    
    connector = None
    connection = None
    cursor = None
    
    try:
        # Normalize filter keys: accept both channel_name (snake_case) and channelName (camelCase)
        # and normalize channel value to UPPERCASE for case-insensitive matching
        if filters:
            _ch = filters.get("channel_name") or filters.get("channelName")
            if _ch and str(_ch).strip():
                filters["channel_name"] = str(_ch).strip().upper()
            if "channelName" in filters:
                filters.pop("channelName", None)
        
        # Log what we received - use both logger and frappe.log_error for visibility
        logger.info(f"📥 Received filters: {filters}")
        logger.info(f"📥 Channel in filters: {filters.get('channel_name') if filters else 'No filters dict'}")
        frappe.log_error(title="Batch Validator", message=f"📥 VALIDATOR RECEIVED filters: {filters}, channel_name: {filters.get('channel_name') if filters else 'None'}")
        
        # Extract channel filter FIRST before building order_filters (already uppercase from normalization)
        expected_channel = None
        if filters and filters.get("channel_name"):
            expected_channel = str(filters["channel_name"]).strip().upper()
            if expected_channel:
                logger.info(f"🔍 Channel filter extracted: '{expected_channel}'")
                frappe.log_error(title="Batch Validator", message=f"🔍 VALIDATOR: Channel filter extracted: '{expected_channel}'")
            else:
                expected_channel = None
                logger.warning("Channel filter was empty after strip")
                frappe.log_error(title="Batch Validator", message="⚠️ VALIDATOR: Channel filter was empty after strip")
        else:
            logger.warning("⚠️ NO CHANNEL FILTER IN FILTERS DICT - Will process ALL channels!")
            frappe.log_error(title="Batch Validator", message=f"❌ VALIDATOR: NO CHANNEL FILTER! Filters keys: {list(filters.keys()) if filters else 'None'}")
        
        # Build filters (without channel - we filter in Python)
        order_filters = _build_order_filters(filters)
        
        _emit_progress(progress_callback, "fetching_orders", "Fetching orders from database...", "")
        
        # Limit orders for deterministic validation window (e.g. 500 from dashboard)
        limit_orders = cint(filters.get("limit_orders")) if filters else 0
        
        # Fetch orders with filters (date/status only, no channel)
        # order_by ensures same order every run so re-runs show consistent missing batches
        logger.info(f"📋 Fetching orders with filters: {order_filters}, order_by=displayorderdatetime desc, limit_orders={limit_orders}")
        orders = frappe.db.get_list(
            'Unicommerce Orders',
            filters=order_filters,
            fields=['name', 'uniware_id', 'channel_name', 'status'],
            order_by='displayorderdatetime desc',
            limit_page_length=0
        )
        
        logger.info(f"📦 Fetched {len(orders)} orders from database")
        _emit_progress(progress_callback, "filtering_channel", f"Fetched {len(orders)} orders. Filtering by channel...", "")
        
        # CRITICAL: Filter by channel in Python (case-insensitive)
        if expected_channel:
            original_count = len(orders)
            # Get unique channels before filtering
            channels_before = set([o.get('channel_name') for o in orders if o.get('channel_name')])
            logger.info(f"📊 Channels in fetched orders: {channels_before}")
            
            # Filter orders - explicit loop for better logging and debugging
            filtered_orders = []
            skipped_count = 0
            for o in orders:
                order_channel = o.get('channel_name', '')
                order_channel_upper = order_channel.upper() if order_channel else ''
                if order_channel_upper == expected_channel:
                    filtered_orders.append(o)
                else:
                    skipped_count += 1
                    if skipped_count <= 5:  # Log first 5 skipped orders for debugging
                        logger.debug(f"Skipping order {o.get('uniware_id')} - channel '{order_channel}' (upper: '{order_channel_upper}') != '{expected_channel}'")
            
            orders = filtered_orders
            logger.info(f"Filtered orders: {len(filtered_orders)} kept, {skipped_count} skipped")
            
            # Get unique channels after filtering
            channels_after = set([o.get('channel_name') for o in orders if o.get('channel_name')])
            logger.info(f"✅ Channel filter '{expected_channel}': {original_count} -> {len(orders)} orders")
            logger.info(f"📊 Channels after filter: {channels_after}")
            frappe.log_error(title="Batch Validator", message=f"✅ VALIDATOR: Filtered to '{expected_channel}': {original_count} -> {len(orders)} orders. Remaining channels: {channels_after}")
            
            if len(orders) == 0:
                logger.warning(f"No orders found for channel '{expected_channel}'")
                return results
        else:
            channels_all = set([o.get('channel_name') for o in orders if o.get('channel_name')])
            logger.warning(f"⚠️ No channel filter - processing ALL {len(channels_all)} channels: {channels_all}")
        
        # Apply order limit so same window is validated every run (deterministic re-runs)
        if limit_orders and limit_orders > 0:
            orders = orders[:limit_orders]
            logger.info(f"📌 Limited to first {limit_orders} orders (newest first by displayorderdatetime)")
        
        results["total_orders"] = len(orders)
        
        if not orders:
            _emit_progress(progress_callback, "done", "No orders to validate.", "")
            return results
        
        _emit_progress(progress_callback, "connecting_hana", f"Connecting to SAP HANA for {len(orders)} orders...", "")
        
        # Connect to HANA
        connector, connection, cursor = create_database_connection()
        logger.info("✅ Connected to HANA")
        
        _emit_progress(progress_callback, "validating", "Validating batch quantities...", f"0 / {len(orders)} orders")
        
        # Process each order
        total_orders = len(orders)
        for idx, order in enumerate(orders):
            channel_name = order.get('channel_name', '')
            uniware_id = order.get('uniware_id')
            
            # CRITICAL: Final channel check - skip if doesn't match filter
            # This is a safety check - orders should already be filtered above
            if expected_channel:
                channel_upper = channel_name.upper() if channel_name else ''
                if channel_upper != expected_channel:
                    # Log this as a warning since it shouldn't happen if filtering worked
                    logger.warning(f"⚠️ Skipping order {uniware_id} - channel '{channel_name}' (upper: '{channel_upper}') doesn't match filter '{expected_channel}'")
                    frappe.log_error(title="Batch Validator", message=f"⚠️ VALIDATOR: Skipping order {uniware_id} - channel '{channel_name}' doesn't match filter '{expected_channel}'")
                    continue
            
            try:
                order_doc = frappe.get_doc('Unicommerce Orders', order.get('name'))
                line_items = order_doc.get('line_items', [])
                
                if not line_items:
                    continue
                
                # Resolve warehouse using canonical map (FBA→own FC warehouse, others→EC-FG).
                warehouse_code = _resolve_warehouse_for_channel(channel_name)
                
                # Process line items
                for line_item in line_items:
                    item_code = line_item.get('itemsku', '').strip()
                    batch_number = line_item.get('vendorbatchnumber', '').strip()
                    required_qty = float(line_item.get('quantity', 0))
                    
                    if not item_code or not batch_number or required_qty <= 0:
                        continue
                    
                    results["total_line_items"] += 1
                    
                    # Check batch quantity using OBTQ
                    batch_check = _check_batch_quantity_in_hana(cursor, item_code, warehouse_code, batch_number)
                    available_qty = batch_check.get("available_qty", 0)
                    
                    batch_info = {
                        "order": uniware_id,
                        "channel_name": channel_name,
                        "warehouse_code": warehouse_code,
                        "item_code": item_code,
                        "batch_number": batch_number,
                        "required_qty": required_qty,
                        "available_qty": available_qty
                    }
                    
                    if available_qty >= required_qty:
                        batch_info["status"] = "AVAILABLE"
                        results["valid_batches"].append(batch_info)
                    else:
                        batch_info["status"] = "INSUFFICIENT_STOCK" if available_qty > 0 else "BATCH_NOT_FOUND"
                        # For EC-FG channels: check if FEFO across all EC-FG batches can cover qty.
                        # Only report AVAILABLE_VIA_FEFO when the setting is enabled so
                        # pre-validation matches what the posting worker will actually do.
                        if warehouse_code == DEFAULT_WAREHOUSE:
                            try:
                                _fefo_enabled = bool(getattr(
                                    frappe.get_cached_doc("Unicommerce Settings"),
                                    "ec_fg_fefo_fallback", False,
                                ))
                            except Exception:
                                _fefo_enabled = False
                            if _fefo_enabled:
                                total_check = _get_total_ec_fg_qty_in_hana(cursor, item_code)
                                ec_fg_total = total_check.get("available_qty", 0)
                                batch_info["ec_fg_total_qty"] = ec_fg_total
                                if ec_fg_total >= required_qty:
                                    batch_info["status"] = "AVAILABLE_VIA_FEFO"
                                    results["valid_batches"].append(batch_info)
                                    continue
                        results["invalid_batches"].append(batch_info)
                        
            except Exception as e:
                logger.error(f"Error processing order {uniware_id}: {str(e)}")
                results["errors"].append({"order": uniware_id, "error": str(e)})
            
            # Emit progress every 50 orders so UI can show backend progress
            current = idx + 1
            if current % 50 == 0 or current == total_orders:
                _emit_progress(progress_callback, "validating", "Validating batch quantities...", f"{current} / {total_orders} orders")
        
        close_database_connection(connector, connection, cursor)
        _emit_progress(progress_callback, "done", "Validation complete.", f"{len(results['valid_batches'])} valid, {len(results['invalid_batches'])} invalid")
        logger.info(f"✅ Validation complete: {len(results['valid_batches'])} valid, {len(results['invalid_batches'])} invalid")
        return results
        
    except Exception as e:
        logger.error(f"Critical error: {str(e)}\n{traceback.format_exc()}")
        if connection and cursor:
            close_database_connection(connector, connection, cursor)
        results["errors"].append({"error": str(e)})
        return results


def _export_batch_validation_to_excel(results, filters=None):
    """
    Export batch validation results to Excel file with all line-level details.
    
    Args:
        results (dict): Results from validate_batch_quantities_from_unicommerce_orders
        filters (dict, optional): Filters used for the query (for filename)
    
    Returns:
        str: Path to the created Excel file
    """
    try:
        # Create output directory
        output_dir = frappe.get_site_path('private', 'files', 'batch_validation_reports')
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Add filter info to filename
        filter_parts = []
        if filters:
            if filters.get("channel_name"):
                filter_parts.append(str(filters["channel_name"]).replace(" ", "_").replace("/", "_"))
            if filters.get("start_date"):
                start_str = str(filters["start_date"]).replace("-", "")[:8]
                filter_parts.append(f"from_{start_str}")
            if filters.get("end_date"):
                end_str = str(filters["end_date"]).replace("-", "")[:8]
                filter_parts.append(f"to_{end_str}")
        
        filter_suffix = "_".join(filter_parts) if filter_parts else "all"
        excel_filename = f"batch_validation_{filter_suffix}_{timestamp}.xlsx"
        excel_path = os.path.join(output_dir, excel_filename)
        
        # Ensure file doesn't already exist
        counter = 1
        while os.path.exists(excel_path):
            excel_filename = f"batch_validation_{filter_suffix}_{timestamp}_{counter}.xlsx"
            excel_path = os.path.join(output_dir, excel_filename)
            counter += 1
        
        logger.info(f"Creating Excel file: {excel_path}")
        
        # Create DataFrames for each sheet
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            # Sheet 1: Summary
            total_valid = len(results.get("valid_batches", []))
            total_invalid = len(results.get("invalid_batches", []))
            total_items = results.get("total_line_items", 0)
            success_rate = round((total_valid / max(total_items, 1)) * 100, 2) if total_items > 0 else 0
            
            summary_data = {
                "Metric": [
                    "Total Orders Processed",
                    "Processed Orders",
                    "Skipped Orders",
                    "Total Line Items Checked",
                    "Valid Batches (Sufficient Stock)",
                    "Invalid Batches (Insufficient/Missing Stock)",
                    "Errors Encountered",
                    "Warnings",
                    "Success Rate (%)"
                ],
                "Value": [
                    results.get("total_orders", 0),
                    results.get("processed_orders", 0),
                    results.get("skipped_orders", 0),
                    total_items,
                    total_valid,
                    total_invalid,
                    len(results.get("errors", [])),
                    len(results.get("warnings", [])),
                    success_rate
                ]
            }
            df_summary = pd.DataFrame(summary_data)
            df_summary.to_excel(writer, sheet_name="Summary", index=False)
            
            # Sheet 2: Valid Batches (grouped by item + batch, same as frontend)
            if results.get("valid_batches"):
                df_valid = pd.DataFrame(results["valid_batches"])
                column_order = ["order", "order_count", "channel_name", "warehouse_code", "item_code", "batch_number",
                              "required_qty", "available_qty", "status"]
                existing_columns = [col for col in column_order if col in df_valid.columns]
                remaining_columns = [col for col in df_valid.columns if col not in column_order]
                df_valid = df_valid[existing_columns + remaining_columns]
                df_valid.to_excel(writer, sheet_name="Valid Batches", index=False)
            else:
                pd.DataFrame({"Message": ["No valid batches found"]}).to_excel(writer, sheet_name="Valid Batches", index=False)
            
            # Sheet 3: Invalid Batches (grouped by item + batch, same as frontend)
            if results.get("invalid_batches"):
                df_invalid = pd.DataFrame(results["invalid_batches"])
                df_invalid["shortage_qty"] = df_invalid.apply(
                    lambda row: max(0, (row.get("required_qty", 0) or 0) - (row.get("available_qty", 0) or 0)),
                    axis=1
                )
                column_order = ["order", "order_count", "channel_name", "warehouse_code", "item_code", "batch_number",
                              "required_qty", "available_qty", "shortage_qty", "status"]
                existing_columns = [col for col in column_order if col in df_invalid.columns]
                remaining_columns = [col for col in df_invalid.columns if col not in column_order]
                df_invalid = df_invalid[existing_columns + remaining_columns]
                df_invalid.to_excel(writer, sheet_name="Invalid Batches", index=False)
            else:
                pd.DataFrame({"Message": ["No invalid batches found"]}).to_excel(writer, sheet_name="Invalid Batches", index=False)
            
            # Sheet 4: Errors
            if results.get("errors"):
                df_errors = pd.DataFrame(results["errors"])
                df_errors.to_excel(writer, sheet_name="Errors", index=False)
            else:
                pd.DataFrame({"Message": ["No errors encountered"]}).to_excel(writer, sheet_name="Errors", index=False)
            
            # Sheet 5: Warnings
            if results.get("warnings"):
                df_warnings = pd.DataFrame(results["warnings"])
                df_warnings.to_excel(writer, sheet_name="Warnings", index=False)
            else:
                pd.DataFrame({"Message": ["No warnings"]}).to_excel(writer, sheet_name="Warnings", index=False)
            
            # Sheet 6: All (Grouped) - same grouped item+batch view as frontend
            all_items = results.get("valid_batches", []) + results.get("invalid_batches", [])
            if all_items:
                df_all = pd.DataFrame(all_items)
                df_all["shortage_qty"] = df_all.apply(
                    lambda row: 0 if row.get("status") == "AVAILABLE"
                    else max(0, (row.get("required_qty", 0) or 0) - (row.get("available_qty", 0) or 0)),
                    axis=1
                )
                df_all["status_priority"] = df_all["status"].map({
                    "BATCH_NOT_FOUND": 1,
                    "INSUFFICIENT_STOCK": 2,
                    "AVAILABLE": 3
                })
                df_all = df_all.sort_values(["status_priority", "item_code", "batch_number"])
                df_all = df_all.drop(columns=["status_priority"])
                column_order = ["status", "order", "order_count", "channel_name", "warehouse_code", "item_code", "batch_number",
                              "required_qty", "available_qty", "shortage_qty"]
                existing_columns = [col for col in column_order if col in df_all.columns]
                remaining_columns = [col for col in df_all.columns if col not in column_order]
                df_all = df_all[existing_columns + remaining_columns]
                df_all.to_excel(writer, sheet_name="All (Grouped)", index=False)
            else:
                pd.DataFrame({"Message": ["No line items to display"]}).to_excel(writer, sheet_name="All (Grouped)", index=False)
            
            # Sheet 7: Channel Summary
            channel_summary = {}
            all_batch_items = results.get("valid_batches", []) + results.get("invalid_batches", [])
            
            for item in all_batch_items:
                channel = item.get("channel_name", "Unknown")
                if channel not in channel_summary:
                    channel_summary[channel] = {
                        "total_items": 0,
                        "valid_items": 0,
                        "invalid_items": 0,
                        "total_required_qty": 0,
                        "total_available_qty": 0,
                        "total_shortage_qty": 0
                    }
                
                channel_summary[channel]["total_items"] += 1
                channel_summary[channel]["total_required_qty"] += item.get("required_qty", 0)
                channel_summary[channel]["total_available_qty"] += item.get("available_qty", 0)
                
                if item.get("status") == "AVAILABLE":
                    channel_summary[channel]["valid_items"] += 1
                else:
                    channel_summary[channel]["invalid_items"] += 1
                    channel_summary[channel]["total_shortage_qty"] += max(0, (
                        item.get("required_qty", 0) - item.get("available_qty", 0)
                    ))
            
            if channel_summary:
                channel_data = []
                for channel, stats in channel_summary.items():
                    channel_data.append({
                        "Channel Name": channel,
                        "Total Items": stats["total_items"],
                        "Valid Items": stats["valid_items"],
                        "Invalid Items": stats["invalid_items"],
                        "Success Rate (%)": round((stats["valid_items"] / max(stats["total_items"], 1)) * 100, 2),
                        "Total Required Qty": stats["total_required_qty"],
                        "Total Available Qty": stats["total_available_qty"],
                        "Total Shortage Qty": stats["total_shortage_qty"]
                    })
                df_channel = pd.DataFrame(channel_data)
                df_channel = df_channel.sort_values("Invalid Items", ascending=False)
                df_channel.to_excel(writer, sheet_name="Channel Summary", index=False)
            else:
                pd.DataFrame({"Message": ["No channel data available"]}).to_excel(writer, sheet_name="Channel Summary", index=False)
        
        logger.info(f"Excel file created successfully: {excel_path}")
        return excel_path
        
    except Exception as e:
        error_msg = f"Error exporting to Excel: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        raise


