"""
Unicommerce Dashboard API
Provides endpoints for the Unicommerce dashboard in kiosk-frontend
"""

import frappe
from frappe import _
from datetime import datetime, timedelta
from frappe.utils import get_datetime, now_datetime, add_to_date, flt, cint
import json
import os

from khanal_tech_integrations.unicommerce.validators.batches import (
    validate_batch_quantities_from_unicommerce_orders,
    _export_batch_validation_to_excel,
)
from khanal_tech_integrations.unicommerce.workers.fetch import fetch_orders, fetch_returns
from khanal_tech_integrations.unicommerce.workers.invoice import post_invoices
from khanal_tech_integrations.unicommerce.workers.credit_note import post_credit_notes

try:
    from khanal_tech_integrations.utils.DN_Creation_Unicommerce import (
        Channel_post_delivery_note1
    )
except ImportError:
    Channel_post_delivery_note1 = None

# Legacy delivery note function removed with Unicommerce_Automation cleanup — always None
Channel_delivery_Creation_Dispatched2 = None

from khanal_tech_integrations.unicommerce.validators.pre_check import comprehensive_pre_posting_validation


@frappe.whitelist()
def test_endpoint():
    """Test endpoint to verify module is loaded"""
    return {
        'status': 'success',
        'message': 'Unicommerce dashboard API module is loaded and working'
    }


@frappe.whitelist()
def download_batch_validation_excel(file_name):
    """
    Serve batch validation Excel file from private folder.
    Private files return 403 when linked directly; this whitelisted method
    returns the file with proper auth.
    """
    if not file_name or not isinstance(file_name, str):
        frappe.throw(_("file_name is required"))
    # Allow only safe filenames: batch_validation_*.xlsx, no path traversal
    base = os.path.basename(file_name).strip()
    if not base.endswith(".xlsx") or not base.startswith("batch_validation_"):
        frappe.throw(_("Invalid file name"))
    site_path = frappe.get_site_path("private", "files", "batch_validation_reports", base)
    if not os.path.isfile(site_path):
        frappe.throw(_("File not found"))
    with open(site_path, "rb") as f:
        content = f.read()
    frappe.response["type"] = "binary"
    frappe.response["filecontent"] = content
    frappe.response["filename"] = base


@frappe.whitelist()
def send_batch_validation_excel_email(file_name, email):
    """
    Send the batch validation Excel file to the given email address.
    file_name: basename of the Excel file (e.g. batch_validation_...xlsx).
    email: recipient email address.
    """
    if not file_name or not isinstance(file_name, str):
        frappe.throw(_("file_name is required"))
    base = os.path.basename(file_name).strip()
    if not base.endswith(".xlsx") or not base.startswith("batch_validation_"):
        frappe.throw(_("Invalid file name"))
    site_path = frappe.get_site_path("private", "files", "batch_validation_reports", base)
    if not os.path.isfile(site_path):
        frappe.throw(_("File not found"))
    if not email or not isinstance(email, str):
        frappe.throw(_("Email address is required"))
    email = email.strip().lower()
    frappe.utils.validate_email_address(email, throw=True)
    # Always include default recipients (order preserved, no duplicates)
    default_batch_validation_recipients = ["sourav@khanalfoods.com", "yogesha@khanalfoods.com"]
    recipients = list(dict.fromkeys([email] + default_batch_validation_recipients))
    try:
        with open(site_path, "rb") as f:
            file_content = f.read()
        subject = _("Batch Validation Report")
        message = _("<p>Please find the batch validation Excel report attached.</p>")
        frappe.sendmail(
            recipients=recipients,
            subject=subject,
            message=message,
            attachments=[{"fname": base, "fcontent": file_content}],
        )
        return {"ok": True, "message": _("Report sent to {0}").format(", ".join(recipients))}
    except Exception as e:
        frappe.log_error("Unicommerce Dashboard Batch Validation Email", f"send_batch_validation_excel_email: {str(e)}")
        frappe.throw(_("Failed to send email: {0}").format(str(e)))


def _normalize_filters(filters):
    """Normalize and validate filters from frontend"""
    if not filters:
        return {}
    
    normalized = {}
    
    # Search filter
    if filters.get('search'):
        search_term = filters['search'].strip()
        if search_term:
            normalized['search'] = search_term
    
    # Date filters
    if filters.get('start_date'):
        try:
            normalized['start_date'] = get_datetime(filters['start_date']).date() if isinstance(filters['start_date'], str) else filters['start_date']
        except:
            normalized['start_date'] = None
    else:
        normalized['start_date'] = None
    
    if filters.get('end_date'):
        try:
            end_dt = get_datetime(filters['end_date'])
            if isinstance(end_dt, datetime):
                normalized['end_date'] = end_dt.replace(hour=23, minute=59, second=59).date()
            else:
                normalized['end_date'] = filters['end_date']
        except:
            normalized['end_date'] = None
    else:
        normalized['end_date'] = None
    
    # Channel filter: accept both channel_name (snake_case) and channelName (camelCase)
    # Normalize to uppercase so DB/filter comparisons are case-insensitive
    channel_raw = filters.get('channel_name') or filters.get('channelName')
    if channel_raw and str(channel_raw).strip():
        normalized['channel_name'] = str(channel_raw).strip().upper()
    else:
        normalized['channel_name'] = None
    
    # Status filter
    if filters.get('status'):
        normalized['status'] = filters['status']
    
    # State filter
    if filters.get('state'):
        normalized['state'] = filters['state']
    
    return normalized


def _get_synced_facilities():
    """Return list of facility codes used when syncing orders from Unicommerce.
    Only orders from these facilities are fetched; if an export (e.g. Excel) has more
    orders/revenue, ensure that facility is in Unicommerce Settings > Facility."""
    try:
        facility_str = frappe.db.get_single_value('Unicommerce Settings', 'facility') or ''
        return [f.strip() for f in facility_str.split(',') if f.strip()]
    except Exception:
        return []


def _build_order_filters(normalized_filters):
    """Build frappe filters from normalized filters"""
    order_filters = {}
    
    if normalized_filters.get('channel_name'):
        order_filters['channel_name'] = normalized_filters['channel_name']
    
    if normalized_filters.get('status'):
        if isinstance(normalized_filters['status'], list):
            order_filters['status'] = ('in', normalized_filters['status'])
        else:
            order_filters['status'] = normalized_filters['status']
    
    if normalized_filters.get('state'):
        order_filters['state'] = normalized_filters['state']
    
    # Date range filter
    if normalized_filters.get('start_date') or normalized_filters.get('end_date'):
        start_date = normalized_filters.get('start_date')
        end_date = normalized_filters.get('end_date')
        
        if start_date and end_date:
            order_filters['displayorderdatetime'] = ('between', [start_date, end_date])
        elif start_date:
            order_filters['displayorderdatetime'] = ('>=', start_date)
        elif end_date:
            order_filters['displayorderdatetime'] = ('<=', end_date)
    
    return order_filters


@frappe.whitelist()
def get_dashboard_summary(filters=None):
    """Get overall dashboard summary metrics"""
    try:
        if isinstance(filters, str):
            filters = json.loads(filters)
        
        normalized = _normalize_filters(filters)
        
        # Get date ranges
        today = now_datetime().date()
        current_month_start = today.replace(day=1)
        last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
        last_month_end = current_month_start - timedelta(days=1)
        last_30_days = today - timedelta(days=30)
        
        # If no date range is provided, default to last month
        if not normalized.get('start_date') and not normalized.get('end_date'):
            normalized['start_date'] = last_month_start
            normalized['end_date'] = last_month_end
        
        order_filters = _build_order_filters(normalized)
        
        # Total orders in the selected date range (or last month by default)
        total_orders_in_range = frappe.db.count('Unicommerce Orders', filters=order_filters)
        
        # Orders in last 30 days (for reference)
        filters_30d = {}
        if normalized.get('channel_name'):
            filters_30d['channel_name'] = normalized['channel_name']
        if normalized.get('status'):
            filters_30d['status'] = normalized['status']
        filters_30d['displayorderdatetime'] = ('>=', last_30_days)
        total_orders_30d = frappe.db.count('Unicommerce Orders', filters=filters_30d)
        
        # Orders today (for reference)
        filters_today = {}
        if normalized.get('channel_name'):
            filters_today['channel_name'] = normalized['channel_name']
        if normalized.get('status'):
            filters_today['status'] = normalized['status']
        filters_today['displayorderdatetime'] = ('>=', today)
        total_orders_today = frappe.db.count('Unicommerce Orders', filters=filters_today)
        
        # Status breakdown (within the selected date range)
        status_breakdown = {}
        statuses = ['COMPLETE', 'PROCESSING', 'PENDING', 'CANCELLED']
        for status in statuses:
            status_filters = order_filters.copy()
            status_filters['status'] = status
            status_breakdown[status.lower()] = frappe.db.count('Unicommerce Orders', filters=status_filters)
        
        # Channel breakdown (within the selected date range)
        channel_breakdown = {}
        channels = frappe.db.get_all('Unicommerce Orders', 
                                    filters=order_filters,
                                    fields=['channel_name'],
                                    distinct=True)
        for channel in channels:
            if channel.channel_name:
                channel_filters = order_filters.copy()
                channel_filters['channel_name'] = channel.channel_name
                channel_breakdown[channel.channel_name] = frappe.db.count('Unicommerce Orders', filters=channel_filters)
        
        # SAP Integration Status (within the selected date range)
        sap_synced_filters = order_filters.copy()
        sap_synced_filters['sap_delivery_docnum'] = ('!=', '')
        sap_synced = frappe.db.count('Unicommerce Orders', filters=sap_synced_filters)
        
        sap_pending_filters = order_filters.copy()
        sap_pending_filters['sap_delivery_docnum'] = ''
        sap_pending = frappe.db.count('Unicommerce Orders', filters=sap_pending_filters)
        
        sap_invoiced_filters = order_filters.copy()
        sap_invoiced_filters['sap_ar_invoice_docnum'] = ('!=', '')
        sap_invoiced = frappe.db.count('Unicommerce Orders', filters=sap_invoiced_filters)
        
        # Calculate success rate (orders with SAP delivery)
        success_rate = 0
        if total_orders_in_range > 0:
            success_rate = round((sap_synced / total_orders_in_range) * 100, 2)
        
        # Determine date range label
        if normalized.get('start_date') and normalized.get('end_date'):
            date_range_label = f"{normalized['start_date']} to {normalized['end_date']}"
        elif normalized.get('start_date'):
            date_range_label = f"From {normalized['start_date']}"
        elif normalized.get('end_date'):
            date_range_label = f"Until {normalized['end_date']}"
        else:
            date_range_label = f"Last Month ({last_month_start} to {last_month_end})"
        
        # Facilities used by Sync Orders (only these are fetched from Unicommerce API)
        synced_facilities = _get_synced_facilities()

        return {
            'metrics': {
                'total_orders': {
                    'in_range': total_orders_in_range,
                    'date_range_label': date_range_label,
                    'start_date': str(normalized.get('start_date', last_month_start)),
                    'end_date': str(normalized.get('end_date', last_month_end)),
                    'last_30_days': total_orders_30d,
                    'today': total_orders_today
                },
                'status_breakdown': status_breakdown,
                'channel_breakdown': channel_breakdown,
                'sap_integration': {
                    'synced': sap_synced,
                    'pending': sap_pending,
                    'invoiced': sap_invoiced
                },
                'success_rate': success_rate
            },
            'synced_facilities': synced_facilities
        }
    except Exception as e:
        error_msg = f"Error in get_dashboard_summary: {str(e)}"
        frappe.log_error("Unicommerce Dashboard", error_msg + "\n" + frappe.get_traceback())
        # Return error in a format that frappeRequest can handle
        frappe.response.message = {'error': error_msg, 'exc_type': type(e).__name__}
        frappe.response.http_status_code = 500
        return {'error': error_msg, 'exc_type': type(e).__name__}


@frappe.whitelist()
def get_orders_data(filters=None, page=1, page_size=50):
    """Get paginated orders data"""
    try:
        # Handle filters - can be dict, string, or None
        if filters is None:
            filters = {}
        elif isinstance(filters, str):
            try:
                filters = json.loads(filters)
            except:
                # If JSON parsing fails, try to parse as dict string
                try:
                    filters = eval(filters) if isinstance(filters, str) else filters
                except:
                    filters = {}
        
        # Ensure filters is a dict
        if not isinstance(filters, dict):
            filters = {}
        
        # Debug logging
        frappe.log_error("Unicommerce Dashboard Debug", f"get_orders_data - Received filters: {filters}, type: {type(filters)}")
        
        normalized = _normalize_filters(filters)
        
        # Debug normalized filters
        frappe.log_error("Unicommerce Dashboard Debug", f"get_orders_data - Normalized filters: {normalized}")
        
        # Debug: Check if channel_name is in normalized
        if normalized.get('channel_name'):
            frappe.log_error("Unicommerce Dashboard Debug", f"get_orders_data - Channel filter found: {normalized['channel_name']}")
        
        # Only apply default date range if no filters are provided at all
        # If user has selected channel/status but no dates, don't restrict by date
        has_any_filter = normalized.get('channel_name') or normalized.get('status') or normalized.get('search')
        
        # If no date range is provided AND no other filters, default to last month
        if not normalized.get('start_date') and not normalized.get('end_date') and not has_any_filter:
            today = now_datetime().date()
            current_month_start = today.replace(day=1)
            last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
            last_month_end = current_month_start - timedelta(days=1)
            normalized['start_date'] = last_month_start
            normalized['end_date'] = last_month_end
        
        order_filters = _build_order_filters(normalized)
        
        # Handle search filter - use SQL for OR conditions across multiple fields
        search_term = normalized.get('search')
        if search_term:
            # Use SQL query for search across multiple fields (OR condition)
            search_pattern = f'%{search_term}%'
            
            # Build WHERE conditions with proper parameter binding
            where_conditions = ["(uniware_id LIKE %s OR customer_name LIKE %s OR name LIKE %s)"]
            query_params = [search_pattern, search_pattern, search_pattern]
            
            # Add other filters
            if order_filters.get('channel_name'):
                where_conditions.append("channel_name = %s")
                query_params.append(order_filters['channel_name'])
            if order_filters.get('status'):
                where_conditions.append("status = %s")
                query_params.append(order_filters['status'])
            if order_filters.get('state'):
                where_conditions.append("state = %s")
                query_params.append(order_filters['state'])
            if order_filters.get('displayorderdatetime'):
                date_filter = order_filters['displayorderdatetime']
                if isinstance(date_filter, tuple):
                    if date_filter[0] == 'between':
                        where_conditions.append("displayorderdatetime BETWEEN %s AND %s")
                        query_params.extend([date_filter[1][0], date_filter[1][1]])
                    elif date_filter[0] == '>=':
                        where_conditions.append("displayorderdatetime >= %s")
                        query_params.append(date_filter[1])
                    elif date_filter[0] == '<=':
                        where_conditions.append("displayorderdatetime <= %s")
                        query_params.append(date_filter[1])
            
            where_clause = " AND ".join(where_conditions)
            
            # Get orders with search
            start = (int(page) - 1) * int(page_size)
            orders_query = f"""
                SELECT name, uniware_id, channel_name, status, 
                       displayorderdatetime, customer_name, state, city,
                       sap_delivery_docnum, sap_ar_invoice_docnum,
                       sap_delivery_docentry, sap_ar_invoice_docentry,
                       created, updated
                FROM `tabUnicommerce Orders`
                WHERE {where_clause}
                ORDER BY displayorderdatetime DESC
                LIMIT %s OFFSET %s
            """
            query_params.extend([int(page_size), start])
            orders = frappe.db.sql(orders_query, tuple(query_params), as_dict=True)
            
            # Get total count
            count_params = query_params[:-2]  # Remove limit and offset
            count_query = f"SELECT COUNT(*) as total FROM `tabUnicommerce Orders` WHERE {where_clause}"
            total_count = frappe.db.sql(count_query, tuple(count_params), as_dict=True)[0]['total']
        else:
            # No search - use regular frappe.db.get_list
            # Calculate pagination
            start = (int(page) - 1) * int(page_size)
            
            # Debug: Log filters being applied
            if order_filters.get('channel_name'):
                frappe.log_error("Unicommerce Dashboard Filter Debug", f"Applying channel filter: {order_filters['channel_name']}")
            
            # Get orders
            orders = frappe.db.get_list(
                'Unicommerce Orders',
                filters=order_filters,
                fields=[
                    'name', 'uniware_id', 'channel_name', 'status', 
                    'displayorderdatetime', 'customer_name', 'state', 'city',
                    'sap_delivery_docnum', 'sap_ar_invoice_docnum',
                    'sap_delivery_docentry', 'sap_ar_invoice_docentry',
                    'created', 'updated'
                ],
                order_by='displayorderdatetime desc',
                start=start,
                page_length=int(page_size)
            )
            
            # Get total count
            total_count = frappe.db.count('Unicommerce Orders', filters=order_filters)
            
            # Debug: Verify channel filter worked
            if order_filters.get('channel_name'):
                channels_in_results = set([o.get('channel_name') for o in orders if o.get('channel_name')])
                if len(channels_in_results) > 1 or (len(channels_in_results) == 1 and list(channels_in_results)[0] != order_filters['channel_name']):
                    frappe.log_error("Unicommerce Dashboard Filter Debug", f"Channel filter issue! Filtered for '{order_filters['channel_name']}' but got channels: {channels_in_results}")
        
        # Format dates
        for order in orders:
            if order.get('displayorderdatetime'):
                order['displayorderdatetime'] = str(order['displayorderdatetime'])
            if order.get('created'):
                order['created'] = str(order['created'])
            if order.get('updated'):
                order['updated'] = str(order['updated'])
        
        return {
            'orders': orders,
            'total_count': total_count,
            'page': int(page),
            'page_size': int(page_size),
            'has_more': start + len(orders) < total_count
        }
    except Exception as e:
        error_msg = f"Error in get_orders_data: {str(e)}"
        frappe.log_error("Unicommerce Dashboard", error_msg + "\n" + frappe.get_traceback())
        frappe.response.http_status_code = 500
        return {'error': error_msg, 'status': 'error'}


@frappe.whitelist()
def get_channel_analytics(filters=None):
    """Get comprehensive channel-wise analytics with revenue, orders, and top items"""
    try:
        if isinstance(filters, str):
            filters = json.loads(filters)
        
        normalized = _normalize_filters(filters)
        
        # If no date range is provided, default to last month
        if not normalized.get('start_date') and not normalized.get('end_date'):
            today = now_datetime().date()
            current_month_start = today.replace(day=1)
            last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
            last_month_end = current_month_start - timedelta(days=1)
            normalized['start_date'] = last_month_start
            normalized['end_date'] = last_month_end
        
        # Get date ranges
        today = now_datetime().date()
        current_month_start = today.replace(day=1)
        last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
        last_month_end = current_month_start - timedelta(days=1)
        last_month_to_present_start = last_month_start
        
        # Get all channels
        base_filters = {}
        if normalized.get('channel_name'):
            base_filters['channel_name'] = normalized['channel_name']
        
        channels = frappe.db.get_all(
            'Unicommerce Orders',
            filters=base_filters,
            fields=['channel_name'],
            distinct=True
        )
        
        channel_analytics = []
        all_items_data = {}  # For top items across all channels
        
        for channel in channels:
            if not channel.channel_name:
                continue
            
            channel_name = channel.channel_name
            channel_filters = base_filters.copy()
            channel_filters['channel_name'] = channel_name
            
            # Total orders (from start to present)
            total_orders = frappe.db.count('Unicommerce Orders', filters=channel_filters)
            
            # Current month orders
            current_month_filters = channel_filters.copy()
            current_month_filters['displayorderdatetime'] = ('>=', current_month_start)
            current_month_orders = frappe.db.count('Unicommerce Orders', filters=current_month_filters)
            
            # Last month orders
            last_month_filters = channel_filters.copy()
            last_month_filters['displayorderdatetime'] = ('between', [last_month_start, last_month_end])
            last_month_orders = frappe.db.count('Unicommerce Orders', filters=last_month_filters)
            
            # Complete orders
            complete_filters = channel_filters.copy()
            complete_filters['status'] = 'COMPLETE'
            complete_orders = frappe.db.count('Unicommerce Orders', filters=complete_filters)
            
            # SAP synced orders
            sap_filters = channel_filters.copy()
            sap_filters['sap_delivery_docnum'] = ('!=', '')
            sap_synced = frappe.db.count('Unicommerce Orders', filters=sap_filters)
            
            # Calculate revenue from last month to present
            revenue_filters = channel_filters.copy()
            revenue_filters['displayorderdatetime'] = ('>=', last_month_to_present_start)
            revenue_filters['status'] = ('!=', 'CANCELLED')
            
            orders_for_revenue = frappe.db.get_list(
                'Unicommerce Orders',
                filters=revenue_filters,
                fields=['name']
            )
            
            # Calculate revenue from line items
            total_revenue = 0.0
            item_quantities = {}  # For top items per channel
            
            for order in orders_for_revenue:
                order_doc = frappe.get_doc('Unicommerce Orders', order.name)
                if hasattr(order_doc, 'line_items') and order_doc.line_items:
                    for line_item in order_doc.line_items:
                        # Revenue = selling_price * quantity (excluding GST)
                        selling_price = flt(line_item.selling_price) if line_item.selling_price else 0
                        quantity = flt(line_item.quantity) if line_item.quantity else 1
                        total_integrated_gst = flt(line_item.totalintegratedgst) if line_item.totalintegratedgst else 0
                        
                        # Revenue per line item (selling price - GST)
                        line_revenue = (selling_price - total_integrated_gst) * quantity
                        total_revenue += line_revenue
                        
                        # Track items for top items
                        item_code = line_item.itemsku or 'Unknown'
                        if item_code not in item_quantities:
                            item_quantities[item_code] = {
                                'quantity': 0,
                                'revenue': 0
                            }
                        item_quantities[item_code]['quantity'] += quantity
                        item_quantities[item_code]['revenue'] += line_revenue
                        
                        # Track for all channels
                        item_key = f"{channel_name}-{item_code}"
                        if item_key not in all_items_data:
                            all_items_data[item_key] = {
                                'channel': channel_name,
                                'item_code': item_code,
                                'quantity': 0,
                                'revenue': 0
                            }
                        all_items_data[item_key]['quantity'] += quantity
                        all_items_data[item_key]['revenue'] += line_revenue
            
            # Get top 5 items for this channel
            top_items = sorted(
                item_quantities.items(),
                key=lambda x: x[1]['quantity'],
                reverse=True
            )[:5]
            
            top_items_list = [
                {
                    'item_code': item_code,
                    'quantity': data['quantity'],
                    'revenue': round(data['revenue'], 2)
                }
                for item_code, data in top_items
            ]
            
            # Calculate success rate
            success_rate = 0
            if total_orders > 0:
                success_rate = round((sap_synced / total_orders) * 100, 2)
            
            channel_analytics.append({
                'channel_name': channel_name,
                'total_orders': total_orders,
                'current_month_orders': current_month_orders,
                'last_month_orders': last_month_orders,
                'complete_orders': complete_orders,
                'sap_synced': sap_synced,
                'success_rate': success_rate,
                'revenue_from_last_month': round(total_revenue, 2),
                'top_items': top_items_list
            })
        
        # Sort by total orders descending
        channel_analytics.sort(key=lambda x: x['total_orders'], reverse=True)
        
        # Get best performing channel for last month (by revenue)
        best_channel_last_month = max(
            channel_analytics,
            key=lambda x: x['revenue_from_last_month']
        ) if channel_analytics else None
        
        # Get top 5 items across all channels
        top_items_all_channels = sorted(
            all_items_data.values(),
            key=lambda x: x['quantity'],
            reverse=True
        )[:5]
        
        return {
            'channels': channel_analytics,
            'best_channel_last_month': {
                'channel_name': best_channel_last_month['channel_name'] if best_channel_last_month else None,
                'revenue': best_channel_last_month['revenue_from_last_month'] if best_channel_last_month else 0,
                'orders': best_channel_last_month['last_month_orders'] if best_channel_last_month else 0
            } if best_channel_last_month else None,
            'top_items_all_channels': [
                {
                    'channel': item['channel'],
                    'item_code': item['item_code'],
                    'quantity': item['quantity'],
                    'revenue': round(item['revenue'], 2)
                }
                for item in top_items_all_channels
            ]
        }
    except Exception as e:
        error_msg = f"Error in get_channel_analytics: {str(e)}"
        frappe.log_error("Unicommerce Dashboard", error_msg + "\n" + frappe.get_traceback())
        frappe.response.http_status_code = 500
        return {'error': error_msg, 'status': 'error'}


@frappe.whitelist(allow_guest=False, methods=['GET', 'POST'])
def get_batch_validation_summary(filters=None, limit_orders=0):
    """
    Get batch validation summary by comparing with SAP HANA inventory (OIBT table)
    
    Args:
        filters: Filter dictionary for orders (IGNORED - we get from form_dict instead)
        limit_orders: Max orders to process; 0 = no limit (check all). Non-zero limits window for deterministic re-runs.
    """
    try:
        # Use the actual batch validation function that queries SAP HANA directly
        if not validate_batch_quantities_from_unicommerce_orders:
            frappe.log_error("Unicommerce Dashboard", "validate_batch_quantities_from_unicommerce_orders function not available")
            return {
                'total_valid': 0,
                'total_invalid': 0,
                'total_items': 0,
                'success_rate': 0,
                'channel_breakdown': {},
                'insufficient_inventory': [],
                'errors': ['Batch validation function not available. Please check imports.'],
                'warnings': []
            }
        
        # Get filters from function parameter (Frappe passes it for POST requests)
        if filters is None:
            filters = {}
        elif isinstance(filters, str):
            try:
                filters = json.loads(filters)
            except (json.JSONDecodeError, TypeError):
                filters = {}
        
        if not isinstance(filters, dict):
            filters = {}
        
        # Normalize channel key: accept both channel_name (snake_case) and channelName (camelCase)
        # and normalize value to uppercase for case-insensitive matching
        _channel_raw = filters.get('channel_name') or filters.get('channelName')
        if _channel_raw and str(_channel_raw).strip():
            filters['channel_name'] = str(_channel_raw).strip().upper()
        if filters.get('channelName'):
            filters.pop('channelName', None)  # avoid duplicate keys
        
        # Store original filters for applied_filters response (before any modifications)
        original_filters = filters.copy()
        
        # Log what we received BEFORE any modifications
        frappe.log_error(title="Unicommerce Dashboard Batch Validation", message=f"🔍 RAW FILTERS RECEIVED: {filters}, channel_name: {filters.get('channel_name')}")
        
        # Extract and preserve channel filter FIRST (before any modifications)
        filtered_channel = None
        if filters and filters.get('channel_name'):
            filtered_channel = str(filters['channel_name']).strip().upper() or None
            if not filtered_channel:
                filtered_channel = None
                frappe.log_error("Unicommerce Dashboard Batch Validation", f"⚠️ Channel filter was empty after strip")
            else:
                # Keep it in filters dict - don't delete it!
                # The validator will extract it and filter in Python
                frappe.log_error("Unicommerce Dashboard Batch Validation", f"✅ Channel filter extracted: '{filtered_channel}'")
        else:
            frappe.log_error("Unicommerce Dashboard Batch Validation", f"❌ NO CHANNEL FILTER IN FILTERS! Filters keys: {list(filters.keys()) if filters else 'No filters'}")
        
        # CRITICAL: If channel filter is missing, stop batch validation immediately
        # This prevents processing all channels when a specific channel was requested
        if not filtered_channel:
            error_msg = "Channel filter is required for batch validation. Please select a channel before validating."
            print(f"❌ {error_msg}")  # Print to terminal
            frappe.log_error("Unicommerce Dashboard Batch Validation", f"❌ {error_msg}. Filters received: {filters}")
            frappe.response.http_status_code = 400
            return {
                'error': error_msg,
                'status': 'error',
                'total_valid': 0,
                'total_invalid': 0,
                'total_items': 0,
                'success_rate': 0,
                'channel_breakdown': {},
                'errors': [error_msg],
                'warnings': ['Channel filter is required to prevent processing all channels']
            }
        
        # Store original dates before modification
        original_start_date = filters.get('start_date')
        original_end_date = filters.get('end_date')
        
        # Log the filters being applied for debugging
        frappe.log_error("Unicommerce Dashboard Batch Validation", f"Batch validation filters received: {filters}, channel_name: {filtered_channel}, start_date: {original_start_date}, end_date: {original_end_date}")
        
        # Limit orders to prevent timeout - add date filter if none provided
        if not filters.get('start_date') and not filters.get('end_date'):
            # Set default date range to last 30 days
            end_date = now_datetime().date()
            start_date = end_date - timedelta(days=30)
            filters['start_date'] = start_date.strftime('%Y-%m-%d')
            filters['end_date'] = end_date.strftime('%Y-%m-%d')
            frappe.log_error("Unicommerce Dashboard", f"Limited batch validation to last 30 days (no date filter provided) to prevent timeout")
        
        # CRITICAL: Ensure channel filter is ALWAYS in filters dict if it was provided
        if filtered_channel:
            filters['channel_name'] = filtered_channel  # Set it explicitly
            frappe.log_error("Unicommerce Dashboard Batch Validation", f"✅ Channel filter PRESERVED in filters dict: '{filtered_channel}'. Full filters: {filters}")
        else:
            # Remove channel_name if it's empty/None to avoid confusion
            if 'channel_name' in filters:
                del filters['channel_name']
            frappe.log_error("Unicommerce Dashboard Batch Validation", f"⚠️ No channel filter - will process ALL channels. Filters dict: {filters}")
        
        # Pass limit_orders so validator uses same window of orders each run (deterministic)
        filters['limit_orders'] = cint(limit_orders) or 0
        
        # Call the actual validation function that uses HANA database
        # Note: This can take time for large datasets - consider using background job for large validations
        try:
            # Log exactly what we're passing to the validator
            frappe.log_error("Unicommerce Dashboard Batch Validation", f"Calling validate_batch_quantities_from_unicommerce_orders with filters: {filters}, channel_name key exists: {'channel_name' in filters}, channel_name value: {filters.get('channel_name')}")
            validation_result = validate_batch_quantities_from_unicommerce_orders(
                filters=filters,
                export_to_excel=False
            )
            # Log what we got back
            frappe.log_error("Unicommerce Dashboard Batch Validation", f"Validation result - total_orders: {validation_result.get('total_orders')}, valid_batches: {len(validation_result.get('valid_batches', []))}, invalid_batches: {len(validation_result.get('invalid_batches', []))}")
        except Exception as e:
            error_msg = f"Error during batch validation: {str(e)}"
            frappe.log_error("Unicommerce Dashboard Batch Validation", error_msg)
            return {
                'total_valid': 0,
                'total_invalid': 0,
                'total_items': 0,
                'success_rate': 0,
                'channel_breakdown': {},
                'insufficient_inventory': [],
                'errors': [error_msg],
                'warnings': ['Validation may have timed out. Try using a smaller date range.'],
                'processed_orders': 0,
                'total_orders': 0,
                'skipped_orders': 0
            }
        
        # Extract and filter batches (for grouping and export)
        valid_batches = validation_result.get('valid_batches', [])
        invalid_batches = validation_result.get('invalid_batches', [])
        if filtered_channel:
            filtered_channel_upper = filtered_channel.upper()
            valid_batches = [b for b in valid_batches if b.get('channel_name', '').upper() == filtered_channel_upper]
            invalid_batches = [b for b in invalid_batches if b.get('channel_name', '').upper() == filtered_channel_upper]
        
        # Group by item code + batch number only (ignore order) - same as frontend
        # When merging rows we SUM required_qty but keep one available_qty (same batch).
        # After grouping, total required can exceed available, so reclassify those as insufficient.
        def _group_batches_by_item_batch(batch_list):
            grouped = {}
            for b in batch_list:
                key = (
                    b.get('channel_name', ''),
                    b.get('item_code', ''),
                    b.get('batch_number', ''),
                    b.get('warehouse_code', '')
                )
                if key not in grouped:
                    grouped[key] = {
                        'order': b.get('order', ''),
                        'channel_name': b.get('channel_name', ''),
                        'item_code': b.get('item_code', ''),
                        'batch_number': b.get('batch_number', ''),
                        'warehouse_code': b.get('warehouse_code', ''),
                        'required_qty': flt(b.get('required_qty', 0)),
                        'available_qty': flt(b.get('available_qty', 0)),
                        'status': b.get('status', ''),
                        'order_count': 1
                    }
                else:
                    grouped[key]['required_qty'] += flt(b.get('required_qty', 0))
                    grouped[key]['order_count'] += 1
                    grouped[key]['order'] = _("Multiple ({0} orders)").format(grouped[key]['order_count'])
                    # Keep max available (same batch; may differ if reported at different times)
                    grouped[key]['available_qty'] = max(flt(grouped[key]['available_qty']), flt(b.get('available_qty', 0)))
            return list(grouped.values())
        
        matching_batches_grouped = _group_batches_by_item_batch(valid_batches)
        non_matching_batches_grouped = _group_batches_by_item_batch(invalid_batches)
        
        # Reclassify: if grouped row has total required > available, move to non_matching (was sufficient per-order but insufficient when summed)
        still_matching = []
        for row in matching_batches_grouped:
            if flt(row.get('available_qty', 0)) >= flt(row.get('required_qty', 0)):
                still_matching.append(row)
            else:
                row['status'] = 'INSUFFICIENT_STOCK'
                non_matching_batches_grouped.append(row)
        matching_batches_grouped = still_matching
        
        # Export to Excel with grouped data (same as frontend - clean sheet)
        excel_url = None
        email_sent = False
        excel_path = None
        file_name = None
        if _export_batch_validation_to_excel:
            try:
                results_for_excel = dict(validation_result)
                results_for_excel['valid_batches'] = matching_batches_grouped
                results_for_excel['invalid_batches'] = non_matching_batches_grouped
                excel_path = _export_batch_validation_to_excel(results_for_excel, filters)
                file_name = os.path.basename(excel_path)
                # Use whitelisted download method so private file is served with auth (avoids 403)
                excel_url = frappe.utils.get_url(
                    f"/api/method/khanal_tech_integrations.api.unicommerce_dashboard.download_batch_validation_excel?file_name={file_name}"
                )
            except Exception as e:
                frappe.log_error("Unicommerce Dashboard Batch Validation", f"Error exporting to Excel: {str(e)}")
        
        total_line_items = validation_result.get('total_line_items', 0)
        
        # Build channel breakdown
        channel_breakdown = {}
        filtered_channel_upper = filtered_channel.upper() if filtered_channel else None
        
        # Process valid batches
        for batch in valid_batches:
            # If channel filter is applied, ALWAYS use the filter value, ignore batch channel_name
            # This ensures channel breakdown only shows the filtered channel
            if filtered_channel:
                channel = filtered_channel  # FORCE use filter value
            else:
                channel = batch.get('channel_name', 'Unknown')
            
            if channel not in channel_breakdown:
                channel_breakdown[channel] = {
                    'valid': 0,
                    'invalid': 0,
                    'total': 0
                }
            channel_breakdown[channel]['valid'] += 1
            channel_breakdown[channel]['total'] += 1
        
        # Process invalid batches - Group by item_code and batch_code
        # When channel filter is applied, only group batches from that channel
        insufficient_items_dict = {}
        filtered_channel_upper = filtered_channel.upper() if filtered_channel else None
        
        for batch in invalid_batches:
            # If channel filter is applied, ALWAYS use the filter value, ignore batch channel_name
            if filtered_channel:
                channel = filtered_channel  # FORCE use filter value
            else:
                channel = batch.get('channel_name', 'Unknown')
                
            if channel not in channel_breakdown:
                channel_breakdown[channel] = {
                    'valid': 0,
                    'invalid': 0,
                    'total': 0
                }
            channel_breakdown[channel]['invalid'] += 1
            channel_breakdown[channel]['total'] += 1
            
            # Build key for grouping: item_code + batch_code + warehouse_code
            # When channel filter is applied, we still group by item+batch+warehouse
            # but ensure all batches are from the same channel
            item_code = batch.get('item_code', '')
            batch_code = batch.get('batch_number', '')
            warehouse_code = batch.get('warehouse_code', '')
            
            # Create a unique key for grouping
            # When channel filter is applied, all batches should be from same channel, so we don't need channel in key
            group_key = f"{item_code}|{batch_code}|{warehouse_code}"
            
            if group_key not in insufficient_items_dict:
                # Initialize grouped item
                required_qty = batch.get('required_qty', 0)
                available_qty = batch.get('available_qty', 0)
                shortage = max(0, required_qty - available_qty)
                
                # If channel filter is applied, ALWAYS use the filter value for channels
                if filtered_channel:
                    channels_set = set([filtered_channel])  # FORCE use filter value
                else:
                    channels_set = set([channel])
                
                insufficient_items_dict[group_key] = {
                    'item_code': item_code,
                    'batch_code': batch_code,
                    'warehouse_code': warehouse_code,
                    'channels': channels_set,  # When filtering, this will only contain the filtered channel
                    'total_quantity_needed': required_qty,
                    'quantity_available': available_qty,
                    'total_shortage': shortage,
                    'status': batch.get('status', 'UNKNOWN'),
                    'affected_orders': [batch.get('order', 'Unknown')],
                    'order_count': 1
                }
            else:
                # Aggregate quantities for the same item+batch combination
                required_qty = batch.get('required_qty', 0)
                insufficient_items_dict[group_key]['total_quantity_needed'] += required_qty
                insufficient_items_dict[group_key]['total_shortage'] = max(0, 
                    insufficient_items_dict[group_key]['total_quantity_needed'] - 
                    insufficient_items_dict[group_key]['quantity_available']
                )
                # If channel filter is applied, ALWAYS use the filter value, never add other channels
                if filtered_channel:
                    # FORCE use filter value - clear and set to only filtered channel
                    insufficient_items_dict[group_key]['channels'] = set([filtered_channel])
                else:
                    # No filter, add channel normally
                    insufficient_items_dict[group_key]['channels'].add(channel)
                insufficient_items_dict[group_key]['affected_orders'].append(batch.get('order', 'Unknown'))
                insufficient_items_dict[group_key]['order_count'] += 1
                # Update status if this one is more critical
                current_status = insufficient_items_dict[group_key]['status']
                new_status = batch.get('status', 'UNKNOWN')
                # Prioritize: BATCH_NOT_FOUND > INSUFFICIENT_STOCK > others
                if new_status == 'BATCH_NOT_FOUND' or (current_status != 'BATCH_NOT_FOUND' and new_status == 'INSUFFICIENT_STOCK'):
                    insufficient_items_dict[group_key]['status'] = new_status
        
        # Convert grouped dict to list and format for frontend
        # REMOVED: insufficient_items section as per user request
        insufficient_items = []
        
        total_valid = len(valid_batches)
        total_invalid = len(invalid_batches)
        total_items = total_valid + total_invalid
        
        # Calculate success rate
        success_rate = round((total_valid / total_items * 100), 2) if total_items > 0 else 0
        
        # Send email with Excel attachment if export was successful
        if excel_url and not email_sent:
            try:
                user_email = frappe.session.user
                if user_email and '@' in user_email:
                    channel_name = filtered_channel or 'All Channels'
                    start_date = applied_start_date or filters.get('start_date', 'N/A')
                    end_date = applied_end_date or filters.get('end_date', 'N/A')
                    
                    subject = f"Batch Validation Report - {channel_name} ({start_date} to {end_date})"
                    message = f"""
                    <p>Batch validation has been completed successfully.</p>
                    
                    <p><strong>Summary:</strong></p>
                    <ul>
                        <li>Total Items: {total_items}</li>
                        <li>Valid Batches: {total_valid}</li>
                        <li>Invalid Batches: {total_invalid}</li>
                        <li>Success Rate: {success_rate}%</li>
                    </ul>
                    
                    <p><strong>Filters Applied:</strong></p>
                    <ul>
                        <li>Channel: {channel_name}</li>
                        <li>Date Range: {start_date} to {end_date}</li>
                    </ul>
                    
                    <p>Please find the detailed Excel report attached.</p>
                    """
                    
                    frappe.sendmail(
                        recipients=[user_email],
                        subject=subject,
                        message=message,
                        attachments=[{
                            'fname': os.path.basename(excel_path),
                            'fcontent': open(excel_path, 'rb').read()
                        }]
                    )
                    email_sent = True
            except Exception as email_error:
                frappe.log_error("Unicommerce Dashboard Batch Validation Email", f"Error sending email: {str(email_error)}")
        
        # If channel filter is applied, only show that channel in breakdown
        # CRITICAL: This is a final safety check - channel_breakdown should already only have the filtered channel
        if filtered_channel:
            # Filter channel breakdown to only show the filtered channel (case-insensitive)
            filtered_channel_upper = filtered_channel.upper()
            filtered_breakdown = {}
            
            # Check what channels are actually in the breakdown
            all_channels_in_breakdown = list(channel_breakdown.keys())
            frappe.log_error("Unicommerce Dashboard Batch Validation", f"Channel breakdown before final filter - Channels found: {all_channels_in_breakdown}, Filter: '{filtered_channel}'")
            
            for channel, data in channel_breakdown.items():
                if channel.upper() == filtered_channel_upper:
                    # Use the exact filter value as the key
                    filtered_breakdown[filtered_channel] = data
                    break
            
            if filtered_breakdown:
                channel_breakdown = filtered_breakdown
                frappe.log_error("Unicommerce Dashboard Batch Validation", f"Channel breakdown filtered to only show '{filtered_channel}': {channel_breakdown}")
            else:
                # Channel filter was applied but no data found for that channel
                # This should not happen if filtering worked correctly
                channel_breakdown = {}
                frappe.log_error("Unicommerce Dashboard Batch Validation", f"ERROR: Channel filter '{filtered_channel}' applied but no matching channel found in breakdown. Available channels: {all_channels_in_breakdown}. This indicates a filtering problem!")
        
        # Format dates for applied_filters - use original dates if available, otherwise use current filters
        applied_start_date = None
        applied_end_date = None
        if original_start_date:
            applied_start_date = str(original_start_date) if isinstance(original_start_date, str) else original_start_date.strftime('%Y-%m-%d') if hasattr(original_start_date, 'strftime') else str(original_start_date)
        elif filters and filters.get('start_date'):
            applied_start_date = str(filters.get('start_date'))
        
        if original_end_date:
            applied_end_date = str(original_end_date) if isinstance(original_end_date, str) else original_end_date.strftime('%Y-%m-%d') if hasattr(original_end_date, 'strftime') else str(original_end_date)
        elif filters and filters.get('end_date'):
            applied_end_date = str(filters.get('end_date'))
        
        return {
            'total_valid': total_valid,
            'total_invalid': total_invalid,
            'total_items': total_items,
            'success_rate': success_rate,
            'channel_breakdown': channel_breakdown,
            'matching_batches': matching_batches_grouped[:500],
            'non_matching_batches': non_matching_batches_grouped[:500],
            'excel_url': excel_url,
            'excel_file_name': file_name if excel_path else None,
            'email_sent': email_sent,
            'errors': validation_result.get('errors', []),
            'warnings': validation_result.get('warnings', []),
            'processed_orders': validation_result.get('processed_orders', 0),
            'total_orders': validation_result.get('total_orders', 0),
            'skipped_orders': validation_result.get('skipped_orders', 0),
            'applied_filters': {
                'channel_name': filtered_channel if filtered_channel else None,
                'start_date': applied_start_date,
                'end_date': applied_end_date
            }
        }
    except Exception as e:
        error_msg = f"Error in get_batch_validation_summary: {str(e)}"
        frappe.log_error("Unicommerce Dashboard", error_msg)
        return {
            'error': error_msg,
            'total_valid': 0,
            'total_invalid': 0,
            'total_items': 0,
            'success_rate': 0,
            'channel_breakdown': {},
            'insufficient_inventory': [],
            'errors': [error_msg],
            'warnings': []
        }


def _run_batch_validation_job(progress_key, filters):
    """Background job: run batch validation and write progress to cache for UI polling."""
    cache_key = f"batch_validation_progress:{progress_key}"
    CACHE_EXPIRY = 3600  # 1 hour

    def progress_callback(step=None, message="", detail=""):
        frappe.cache().set_value(
            cache_key,
            {"status": "running", "step": step or "", "message": message, "detail": detail},
            expires_in_sec=CACHE_EXPIRY
        )

    try:
        frappe.cache().set_value(
            cache_key,
            {"status": "running", "step": "started", "message": "Starting batch validation...", "detail": ""},
            expires_in_sec=CACHE_EXPIRY
        )
        result = validate_batch_quantities_from_unicommerce_orders(
            filters=filters,
            export_to_excel=False,
            progress_callback=progress_callback
        )
        applied_filters = {
            "channel_name": filters.get("channel_name"),
            "start_date": filters.get("start_date"),
            "end_date": filters.get("end_date"),
        }
        frappe.cache().set_value(
            cache_key,
            {
                "status": "completed",
                "step": "done",
                "message": "Validation complete.",
                "detail": "",
                "result": result,
                "applied_filters": applied_filters,
            },
            expires_in_sec=CACHE_EXPIRY
        )
    except Exception as e:
        frappe.log_error("Batch Validation Job", str(e))
        frappe.cache().set_value(
            cache_key,
            {
                "status": "failed",
                "step": "error",
                "message": "Validation failed.",
                "detail": str(e),
                "error": str(e)
            },
            expires_in_sec=CACHE_EXPIRY
        )


@frappe.whitelist(allow_guest=False, methods=['GET', 'POST'])
def start_batch_validation(filters=None, limit_orders=0):
    """
    Start batch validation in the background and return a progress_key for polling.
    Frontend should poll get_batch_validation_progress(progress_key) to show live progress.
    """
    if not validate_batch_quantities_from_unicommerce_orders:
        frappe.response.http_status_code = 400
        return {"error": "Batch validation function not available.", "progress_key": None}

    if filters is None:
        filters = {}
    elif isinstance(filters, str):
        try:
            filters = json.loads(filters)
        except (json.JSONDecodeError, TypeError):
            filters = {}
    if not isinstance(filters, dict):
        filters = {}

    _channel_raw = filters.get("channel_name") or filters.get("channelName")
    if _channel_raw and str(_channel_raw).strip():
        filters["channel_name"] = str(_channel_raw).strip().upper()
    if filters.get("channelName"):
        filters.pop("channelName", None)

    filtered_channel = None
    if filters and filters.get("channel_name"):
        filtered_channel = str(filters["channel_name"]).strip().upper() or None
    if not filtered_channel:
        frappe.response.http_status_code = 400
        return {
            "error": "Channel filter is required for batch validation. Please select a channel.",
            "progress_key": None
        }

    if not filters.get("start_date") and not filters.get("end_date"):
        end_date = now_datetime().date()
        start_date = end_date - timedelta(days=30)
        filters["start_date"] = start_date.strftime("%Y-%m-%d")
        filters["end_date"] = end_date.strftime("%Y-%m-%d")

    filters["channel_name"] = filtered_channel
    filters["limit_orders"] = cint(limit_orders) or 0

    progress_key = frappe.generate_hash(length=16)
    cache_key = f"batch_validation_progress:{progress_key}"
    frappe.cache().set_value(
        cache_key,
        {"status": "started", "step": "enqueue", "message": "Starting validation...", "detail": ""},
        expires_in_sec=3600
    )

    frappe.enqueue(
        method=_run_batch_validation_job,
        queue="long",
        timeout=3600,
        progress_key=progress_key,
        filters=filters
    )

    return {"progress_key": progress_key, "status": "started"}


@frappe.whitelist(allow_guest=False, methods=['GET', 'POST'])
def get_batch_validation_progress(progress_key):
    """
    Return current progress for a batch validation started with start_batch_validation.
    Response: { status, step, message, detail, result? (if completed), error? (if failed) }
    """
    if not progress_key or not str(progress_key).strip():
        return {"status": "unknown", "message": "Missing progress_key"}
    cache_key = f"batch_validation_progress:{progress_key}"
    data = frappe.cache().get_value(cache_key)
    if data is None:
        return {"status": "unknown", "message": "No progress found or expired."}
    return data


def _shipping_charge_taxable_value(shipping_charge, tax_percentage):
    """Compute taxable value (exclusive of tax) for a shipping charge. Matches build_freight_line_item logic."""
    try:
        sc = flt(shipping_charge, 4)
        if sc <= 0:
            return 0
        tp = flt(tax_percentage, 2)
        allowed = {0, 5, 12, 18, 24}
        tp = int(tp) if tp in allowed else 0
        if tp > 0:
            return round(sc * (100 / (100 + tp)), 3)
        return round(sc, 3)
    except (TypeError, ValueError):
        return 0


@frappe.whitelist()
def get_shipping_charges_taxable_summary(channel_name, year=None, month=None):
    """
    Return total taxable value of shipping charges only for a channel and month.
    Taxable value = shipping amount excluding GST (same as sent to SAP in freight line).
    """
    try:
        channel_name = (channel_name or "").strip().upper()
        if not channel_name:
            return {"error": "channel_name is required", "total_taxable_value": None}
        from datetime import date
        today = now_datetime().date()
        year = cint(year) or today.year
        month = cint(month) or today.month
        start = date(year, month, 1)
        if month == 12:
            end = date(year, 12, 31)
        else:
            from calendar import monthrange
            _, last = monthrange(year, month)
            end = date(year, month, last)
        start_str = start.isoformat()
        end_str = end.isoformat()

        rows = frappe.db.sql("""
            SELECT li.shippingcharges AS shippingcharges,
                   li.shippingchargetaxpercentage AS shippingchargetaxpercentage
            FROM `tabOrder Line Items` li
            INNER JOIN `tabUnicommerce Orders` o ON o.name = li.parent AND li.parenttype = 'Unicommerce Orders'
            WHERE o.channel_name = %s
              AND o.displayorderdatetime >= %s AND o.displayorderdatetime <= %s
              AND (li.cancellationreason IS NULL OR li.cancellationreason = '')
              AND li.shippingcharges IS NOT NULL AND CAST(li.shippingcharges AS DECIMAL(18,4)) > 0
        """, (channel_name, start_str, end_str), as_dict=True)

        total_taxable = 0
        for r in rows:
            total_taxable += _shipping_charge_taxable_value(r.get("shippingcharges"), r.get("shippingchargetaxpercentage"))

        return {
            "channel_name": channel_name,
            "year": year,
            "month": month,
            "month_label": f"{year}-{month:02d}",
            "total_taxable_value": round(total_taxable, 2),
            "line_count": len(rows),
        }
    except Exception as e:
        frappe.log_error("get_shipping_charges_taxable_summary: " + str(e) + "\n" + frappe.get_traceback(), "Shipping charges summary")
        return {"error": str(e), "total_taxable_value": None}


@frappe.whitelist()
def get_sap_integration_status(filters=None):
    """Get SAP integration status"""
    try:
        if isinstance(filters, str):
            filters = json.loads(filters)
        
        normalized = _normalize_filters(filters)
        order_filters = _build_order_filters(normalized)
        
        # Orders with delivery documents
        delivery_filters = order_filters.copy()
        delivery_filters['sap_delivery_docnum'] = ('!=', '')
        orders_with_delivery = frappe.db.count('Unicommerce Orders', filters=delivery_filters)
        
        # Orders without delivery documents
        no_delivery_filters = order_filters.copy()
        no_delivery_filters['sap_delivery_docnum'] = ''
        orders_without_delivery = frappe.db.count('Unicommerce Orders', filters=no_delivery_filters)
        
        # Orders with AR invoices
        invoice_filters = order_filters.copy()
        invoice_filters['sap_ar_invoice_docnum'] = ('!=', '')
        orders_with_invoice = frappe.db.count('Unicommerce Orders', filters=invoice_filters)
        
        # Orders without AR invoices
        no_invoice_filters = order_filters.copy()
        no_invoice_filters['sap_ar_invoice_docnum'] = ''
        orders_without_invoice = frappe.db.count('Unicommerce Orders', filters=no_invoice_filters)
        
        # Orders requiring attention (complete but no SAP docs)
        attention_filters = order_filters.copy()
        attention_filters['status'] = 'COMPLETE'
        attention_filters['sap_delivery_docnum'] = ''
        orders_requiring_attention = frappe.db.count('Unicommerce Orders', filters=attention_filters)
        
        return {
            'delivery_status': {
                'with_delivery': orders_with_delivery,
                'without_delivery': orders_without_delivery
            },
            'invoice_status': {
                'with_invoice': orders_with_invoice,
                'without_invoice': orders_without_invoice
            },
            'orders_requiring_attention': orders_requiring_attention
        }
    except Exception as e:
        error_msg = f"Error in get_sap_integration_status: {str(e)}"
        frappe.log_error("Unicommerce Dashboard", error_msg + "\n" + frappe.get_traceback())
        frappe.response.http_status_code = 500
        return {'error': error_msg, 'status': 'error'}


@frappe.whitelist()
def get_returns_summary(filters=None):
    """Get returns summary with current month and last month breakdown"""
    try:
        if isinstance(filters, str):
            filters = json.loads(filters)
        
        normalized = _normalize_filters(filters)
        
        # Get date ranges
        today = now_datetime().date()
        current_month_start = today.replace(day=1)
        last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
        last_month_end = current_month_start - timedelta(days=1)
        
        # Get orders with returns (all time)
        returns_filters_all = {}
        returns_filters_all['return_code'] = ('!=', '')
        if normalized.get('channel_name'):
            returns_filters_all['channel_name'] = normalized['channel_name']
        
        orders_with_returns_all = frappe.db.get_list(
            'Unicommerce Orders',
            filters=returns_filters_all,
            fields=[
                'name', 'uniware_id', 'return_code', 'statuscode', 'channel_name', 
                'returncompleteddate', 'inventoryreceiveddate', 'displayorderdatetime',
                'trackingnumber', 'shippingprovider', 'returninvoicecode', 'putawaycode',
                'type', 'actioncode', 'returnfacilitycode', 'sap_ar_creditnote_docentry'
            ],
            order_by='displayorderdatetime desc'
        )
        
        # Filter for current month returns
        current_month_returns = [
            order for order in orders_with_returns_all
            if order.get('displayorderdatetime') and 
            get_datetime(order['displayorderdatetime']).date() >= current_month_start
        ]
        
        # Filter for last month returns
        last_month_returns = [
            order for order in orders_with_returns_all
            if order.get('displayorderdatetime') and 
            get_datetime(order['displayorderdatetime']).date() >= last_month_start and
            get_datetime(order['displayorderdatetime']).date() <= last_month_end
        ]
        
        # Total returns
        total_returns = len(orders_with_returns_all)
        current_month_total = len(current_month_returns)
        last_month_total = len(last_month_returns)
        
        # Returns by status
        returns_by_status = {}
        for order in orders_with_returns_all:
            status = order.get('statuscode', 'Unknown') or 'Unknown'
            returns_by_status[status] = returns_by_status.get(status, 0) + 1
        
        # Returns by channel (all time)
        returns_by_channel_all = {}
        for order in orders_with_returns_all:
            channel = order.get('channel_name', 'Unknown') or 'Unknown'
            returns_by_channel_all[channel] = returns_by_channel_all.get(channel, 0) + 1
        
        # Returns by channel (current month)
        returns_by_channel_current = {}
        for order in current_month_returns:
            channel = order.get('channel_name', 'Unknown') or 'Unknown'
            returns_by_channel_current[channel] = returns_by_channel_current.get(channel, 0) + 1
        
        # Returns by channel (last month)
        returns_by_channel_last = {}
        for order in last_month_returns:
            channel = order.get('channel_name', 'Unknown') or 'Unknown'
            returns_by_channel_last[channel] = returns_by_channel_last.get(channel, 0) + 1
        
        return {
            'total_returns': total_returns,
            'current_month': {
                'total': current_month_total,
                'by_channel': returns_by_channel_current
            },
            'last_month': {
                'total': last_month_total,
                'by_channel': returns_by_channel_last
            },
            'returns_by_status': returns_by_status,
            'returns_by_channel': returns_by_channel_all
        }
    except Exception as e:
        error_msg = f"Error in get_returns_summary: {str(e)}"
        frappe.log_error("Unicommerce Dashboard", error_msg + "\n" + frappe.get_traceback())
        frappe.response.http_status_code = 500
        return {'error': error_msg, 'status': 'error'}


@frappe.whitelist()
def get_returns_data(filters=None, page=1, page_size=50):
    """Get detailed returns list with pagination"""
    try:
        if isinstance(filters, str):
            filters = json.loads(filters)
        
        normalized = _normalize_filters(filters)
        
        # Build filters for returns
        returns_filters = {}
        returns_filters['return_code'] = ('!=', '')
        
        if normalized.get('channel_name'):
            returns_filters['channel_name'] = normalized['channel_name']
        
        if normalized.get('status'):
            # Map status filter to statuscode for returns
            returns_filters['statuscode'] = normalized['status']
        
        # Date range filter
        if normalized.get('start_date') or normalized.get('end_date'):
            start_date = normalized.get('start_date')
            end_date = normalized.get('end_date')
            
            if start_date and end_date:
                returns_filters['displayorderdatetime'] = ('between', [start_date, end_date])
            elif start_date:
                returns_filters['displayorderdatetime'] = ('>=', start_date)
            elif end_date:
                returns_filters['displayorderdatetime'] = ('<=', end_date)
        
        # Calculate pagination
        start = (int(page) - 1) * int(page_size)
        
        # Get returns with all details
        returns = frappe.db.get_list(
            'Unicommerce Orders',
            filters=returns_filters,
            fields=[
                'name', 'uniware_id', 'return_code', 'statuscode', 'channel_name',
                'returncompleteddate', 'inventoryreceiveddate', 'displayorderdatetime',
                'trackingnumber', 'shippingprovider', 'returninvoicecode', 'putawaycode',
                'type', 'actioncode', 'returnfacilitycode', 'sap_ar_creditnote_docentry',
                'customer_name', 'state', 'city'
            ],
            order_by='displayorderdatetime desc',
            start=start,
            page_length=int(page_size)
        )
        
        # Get total count
        total_count = frappe.db.count('Unicommerce Orders', filters=returns_filters)
        
        # Format dates
        for ret in returns:
            if ret.get('displayorderdatetime'):
                ret['displayorderdatetime'] = str(ret['displayorderdatetime'])
            if ret.get('returncompleteddate'):
                ret['returncompleteddate'] = str(ret['returncompleteddate'])
            if ret.get('inventoryreceiveddate'):
                ret['inventoryreceiveddate'] = str(ret['inventoryreceiveddate'])
        
        return {
            'returns': returns,
            'total_count': total_count,
            'page': int(page),
            'page_size': int(page_size),
            'has_more': start + len(returns) < total_count
        }
    except Exception as e:
        frappe.log_error("Unicommerce Dashboard", f"Error in get_returns_data: {str(e)}")
        return {'error': str(e)}


@frappe.whitelist()
def get_chart_data(filters=None, chart_type='orders', days=30):
    """Get chart data for visualization"""
    try:
        if isinstance(filters, str):
            filters = json.loads(filters)
        
        normalized = _normalize_filters(filters)
        
        # Default to last N days if no date range specified
        if not normalized.get('end_date'):
            normalized['end_date'] = now_datetime().date()
        if not normalized.get('start_date'):
            normalized['start_date'] = normalized['end_date'] - timedelta(days=int(days))
        
        order_filters = _build_order_filters(normalized)
        
        if chart_type == 'orders':
            # Order volume over time
            labels = []
            successful = []
            failed = []
            total = []
            
            current_date = normalized['start_date']
            end_date = normalized['end_date']
            
            while current_date <= end_date:
                labels.append(current_date.strftime('%Y-%m-%d'))
                
                day_filters = order_filters.copy()
                day_filters['displayorderdatetime'] = ('between', [
                    datetime.combine(current_date, datetime.min.time()),
                    datetime.combine(current_date, datetime.max.time())
                ])
                
                # Total orders
                day_total = frappe.db.count('Unicommerce Orders', filters=day_filters)
                total.append(day_total)
                
                # Successful (with SAP delivery)
                success_filters = day_filters.copy()
                success_filters['sap_delivery_docnum'] = ('!=', '')
                day_success = frappe.db.count('Unicommerce Orders', filters=success_filters)
                successful.append(day_success)
                
                # Failed (without SAP delivery but complete)
                failed_filters = day_filters.copy()
                failed_filters['status'] = 'COMPLETE'
                failed_filters['sap_delivery_docnum'] = ''
                day_failed = frappe.db.count('Unicommerce Orders', filters=failed_filters)
                failed.append(day_failed)
                
                current_date += timedelta(days=1)
            
            return {
                'labels': labels,
                'datasets': {
                    'total': total,
                    'successful': successful,
                    'failed': failed
                }
            }
        
        elif chart_type == 'channels':
            # Channel performance
            channel_data = get_channel_analytics(filters)
            channels = channel_data.get('channels', [])
            
            labels = [ch['channel_name'] for ch in channels]
            orders = [ch['total_orders'] for ch in channels]
            success_rates = [ch['success_rate'] for ch in channels]
            
            return {
                'labels': labels,
                'datasets': {
                    'orders': orders,
                    'success_rates': success_rates
                }
            }
        
        elif chart_type == 'status':
            # Status distribution
            status_breakdown = {}
            statuses = ['COMPLETE', 'PROCESSING', 'PENDING', 'CANCELLED']
            for status in statuses:
                status_filters = order_filters.copy()
                status_filters['status'] = status
                status_breakdown[status] = frappe.db.count('Unicommerce Orders', filters=status_filters)
            
            return {
                'labels': list(status_breakdown.keys()),
                'values': list(status_breakdown.values())
            }
        
        else:
            return {'error': f'Unknown chart type: {chart_type}'}
    
    except Exception as e:
        frappe.log_error("Unicommerce Dashboard", f"Error in get_chart_data: {str(e)}")
        return {'error': str(e)}


@frappe.whitelist()
def get_channel_subtotal(channel_name=None, start_date=None, end_date=None, date_field='displayorderdatetime'):
    """
    Get total subtotal (sum of line item total_price) for a channel in a date range.
    Dates in DD-MM-YYYY or YYYY-MM-DD. date_field: 'displayorderdatetime' (order date) or 'created'.
    """
    try:
        if not channel_name:
            return {'error': 'channel_name is required', 'total_subtotal': None}
        start_d = _parse_date_for_subtotal(start_date)
        end_d = _parse_date_for_subtotal(end_date)
        if not start_d or not end_d:
            return {'error': 'start_date and end_date required (DD-MM-YYYY or YYYY-MM-DD)', 'total_subtotal': None}
        if start_d > end_d:
            return {'error': 'start_date must be before or equal to end_date', 'total_subtotal': None}
        # End of day for end_date
        from datetime import time
        end_dt = datetime.combine(end_d, time(23, 59, 59))
        channel_upper = str(channel_name).strip().upper()
        allowed_date_fields = ('displayorderdatetime', 'created')
        col = date_field if date_field in allowed_date_fields else 'displayorderdatetime'
        # Sum total_price from Order Line Items for orders matching channel and date
        result = frappe.db.sql("""
            SELECT COALESCE(SUM(oli.total_price), 0) AS total_subtotal,
                   COUNT(DISTINCT o.name) AS order_count
            FROM `tabUnicommerce Orders` o
            INNER JOIN `tabOrder Line Items` oli ON oli.parent = o.name AND oli.parenttype = 'Unicommerce Orders'
            WHERE o.channel_name = %(channel)s
            AND o.{0} BETWEEN %(start)s AND %(end)s
        """.format(col), {'channel': channel_upper, 'start': start_d, 'end': end_dt}, as_dict=True)
        row = result[0] if result else None
        total_subtotal = flt(row.get('total_subtotal'), 2) if row else 0
        order_count = cint(row.get('order_count'), 0) if row else 0
        return {
            'channel_name': channel_upper,
            'start_date': str(start_d),
            'end_date': str(end_d),
            'date_field': date_field,
            'total_subtotal': total_subtotal,
            'order_count': order_count
        }
    except Exception as e:
        frappe.log_error("Unicommerce Dashboard", f"get_channel_subtotal: {str(e)}")
        return {'error': str(e), 'total_subtotal': None}


def _parse_date_for_subtotal(value):
    """Parse DD-MM-YYYY or YYYY-MM-DD to date."""
    if not value:
        return None
    s = str(value).strip()
    for fmt in ('%d-%m-%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


@frappe.whitelist()
def get_sap_docnum_order_report(doc_numbers=None, channel_name=None, start_date=None, end_date=None):
    """
    For given SAP AR DocNums (e.g. 66378, 66379), return which order IDs (U_Order) are in each doc,
    and which orders in the same channel/date range are NOT in those docs and why.
    We only send order id (uniware_id) to SAP as U_Order; order name in Frappe = uniware_id.
    """
    try:
        if not doc_numbers:
            return {'error': 'doc_numbers is required (e.g. "66378,66379" or list)'}
        if isinstance(doc_numbers, str):
            doc_list = [d.strip() for d in doc_numbers.split(',') if d.strip()]
        else:
            doc_list = [str(d).strip() for d in doc_numbers if str(d).strip()]
        if not doc_list:
            return {'error': 'doc_numbers is required (e.g. "66378,66379")'}

        # Normalise to string for comparison (DB may store as string or int)
        doc_set = set(doc_list)

        # Orders in each doc (sap_ar_invoice_docnum stored on order when we post)
        doc_details = {}
        for doc in doc_list:
            orders_in_doc = frappe.db.get_all(
                'Unicommerce Orders',
                filters={'sap_ar_invoice_docnum': doc},
                fields=['name', 'channel_name', 'status', 'displayorderdatetime', 'state']
            )
            order_ids = [r['name'] for r in orders_in_doc]
            doc_details[doc] = {
                'order_ids': order_ids,
                'order_count': len(order_ids),
                'sample_orders': order_ids[:20],
            }

        all_orders_in_docs = set()
        for doc in doc_list:
            all_orders_in_docs.update(doc_details[doc]['order_ids'])

        # If channel + date range provided: list orders NOT in these docs and why
        orders_not_in_docs = []
        not_in_summary = {'no_docnum': 0, 'other_docnum': 0, 'not_complete': 0}
        if channel_name and start_date and end_date:
            start_d = _parse_date_for_subtotal(start_date)
            end_d = _parse_date_for_subtotal(end_date)
            if start_d and end_d:
                from datetime import time
                end_dt = datetime.combine(end_d, time(23, 59, 59))
                channel_upper = str(channel_name).strip().upper()
                # All orders in range for this channel
                range_orders = frappe.db.get_all(
                    'Unicommerce Orders',
                    filters={
                        'channel_name': channel_upper,
                        'displayorderdatetime': ('between', [start_d, end_dt]),
                    },
                    fields=['name', 'status', 'sap_ar_invoice_docnum', 'displayorderdatetime', 'state']
                )
                for r in range_orders:
                    order_id = r['name']
                    if order_id in all_orders_in_docs:
                        continue
                    docnum = (r.get('sap_ar_invoice_docnum') or '') if r.get('sap_ar_invoice_docnum') is not None else ''
                    status = (r.get('status') or '')
                    if status != 'COMPLETE':
                        reason = 'not_complete'
                        not_in_summary['not_complete'] += 1
                    elif not docnum or str(docnum).strip() == '':
                        reason = 'no_docnum'
                        not_in_summary['no_docnum'] += 1
                    else:
                        reason = 'other_docnum'
                        not_in_summary['other_docnum'] += 1
                    orders_not_in_docs.append({
                        'order_id': order_id,
                        'status': status,
                        'sap_ar_invoice_docnum': docnum or None,
                        'reason': reason,
                        'displayorderdatetime': str(r.get('displayorderdatetime')) if r.get('displayorderdatetime') else None,
                        'state': r.get('state'),
                    })
                orders_not_in_docs.sort(key=lambda x: (x['reason'], x['order_id']))

        return {
            'doc_numbers': doc_list,
            'doc_details': doc_details,
            'total_orders_in_docs': len(all_orders_in_docs),
            'orders_not_in_docs': orders_not_in_docs,
            'orders_not_in_docs_count': len(orders_not_in_docs),
            'not_in_summary': not_in_summary,
            'channel_name': channel_name,
            'start_date': str(start_d) if channel_name and start_date and end_date and start_d else None,
            'end_date': str(end_d) if channel_name and start_date and end_date and end_d else None,
            'note': 'Order ID = uniware_id = U_Order sent to SAP. doc_details lists which orders are in each DocNum.',
        }
    except Exception as e:
        frappe.log_error("Unicommerce Dashboard", f"get_sap_docnum_order_report: {str(e)}")
        return {'error': str(e)}


@frappe.whitelist()
def get_channel_sap_value_breakdown(channel_name=None, start_date=None, end_date=None):
    """
    Explain why SAP posted amount can differ from dashboard subtotal.
    Returns:
    - total_subtotal: sum of total_price (what dashboard shows)
    - total_taxable_value: sum of (sellingpricewithouttaxesanddiscount - discount) * quantity — this is what SAP posts per line
    - posted_to_sap: count and taxable value for orders that have sap_ar_invoice_docentry (already posted)
    - not_posted: count and taxable value for COMPLETE orders not yet posted
    - only_complete: orders considered for SAP are status=COMPLETE; cancelled/pending are excluded
    """
    try:
        if not channel_name:
            return {'error': 'channel_name is required'}
        start_d = _parse_date_for_subtotal(start_date)
        end_d = _parse_date_for_subtotal(end_date)
        if not start_d or not end_d:
            return {'error': 'start_date and end_date required (DD-MM-YYYY or YYYY-MM-DD)'}
        from datetime import time
        end_dt = datetime.combine(end_d, time(23, 59, 59))
        channel_upper = str(channel_name).strip().upper()

        # All line items in range: subtotal (total_price) vs taxable (sellingpricewithouttaxesanddiscount - discount) * qty
        agg = frappe.db.sql("""
            SELECT
                COALESCE(SUM(oli.total_price), 0) AS total_subtotal,
                COALESCE(SUM((COALESCE(oli.sellingpricewithouttaxesanddiscount, 0) - COALESCE(oli.discount, 0)) * NULLIF(COALESCE(oli.quantity, 0), 0)), 0) AS total_taxable_value,
                COUNT(DISTINCT o.name) AS order_count
            FROM `tabUnicommerce Orders` o
            INNER JOIN `tabOrder Line Items` oli ON oli.parent = o.name AND oli.parenttype = 'Unicommerce Orders'
            WHERE o.channel_name = %(channel)s
            AND o.displayorderdatetime BETWEEN %(start)s AND %(end)s
        """, {'channel': channel_upper, 'start': start_d, 'end': end_dt}, as_dict=True)
        row_all = agg[0] if agg else {}

        # Only COMPLETE orders (same as SAP posting logic)
        complete = frappe.db.sql("""
            SELECT
                COALESCE(SUM(oli.total_price), 0) AS total_subtotal,
                COALESCE(SUM((COALESCE(oli.sellingpricewithouttaxesanddiscount, 0) - COALESCE(oli.discount, 0)) * NULLIF(COALESCE(oli.quantity, 0), 0)), 0) AS total_taxable_value,
                COUNT(DISTINCT o.name) AS order_count
            FROM `tabUnicommerce Orders` o
            INNER JOIN `tabOrder Line Items` oli ON oli.parent = o.name AND oli.parenttype = 'Unicommerce Orders'
            WHERE o.channel_name = %(channel)s
            AND o.displayorderdatetime BETWEEN %(start)s AND %(end)s
            AND o.status = 'COMPLETE'
        """, {'channel': channel_upper, 'start': start_d, 'end': end_dt}, as_dict=True)
        row_complete = complete[0] if complete else {}

        # Already posted to SAP (have sap_ar_invoice_docentry)
        posted = frappe.db.sql("""
            SELECT
                COALESCE(SUM((COALESCE(oli.sellingpricewithouttaxesanddiscount, 0) - COALESCE(oli.discount, 0)) * NULLIF(COALESCE(oli.quantity, 0), 0)), 0) AS total_taxable_value,
                COUNT(DISTINCT o.name) AS order_count
            FROM `tabUnicommerce Orders` o
            INNER JOIN `tabOrder Line Items` oli ON oli.parent = o.name AND oli.parenttype = 'Unicommerce Orders'
            WHERE o.channel_name = %(channel)s
            AND o.displayorderdatetime BETWEEN %(start)s AND %(end)s
            AND o.status = 'COMPLETE'
            AND o.sap_ar_invoice_docentry IS NOT NULL AND o.sap_ar_invoice_docentry != ''
        """, {'channel': channel_upper, 'start': start_d, 'end': end_dt}, as_dict=True)
        row_posted = posted[0] if posted else {}

        # Not posted (COMPLETE but no sap_ar_invoice_docentry)
        not_posted = frappe.db.sql("""
            SELECT
                COALESCE(SUM((COALESCE(oli.sellingpricewithouttaxesanddiscount, 0) - COALESCE(oli.discount, 0)) * NULLIF(COALESCE(oli.quantity, 0), 0)), 0) AS total_taxable_value,
                COUNT(DISTINCT o.name) AS order_count
            FROM `tabUnicommerce Orders` o
            INNER JOIN `tabOrder Line Items` oli ON oli.parent = o.name AND oli.parenttype = 'Unicommerce Orders'
            WHERE o.channel_name = %(channel)s
            AND o.displayorderdatetime BETWEEN %(start)s AND %(end)s
            AND o.status = 'COMPLETE'
            AND (o.sap_ar_invoice_docentry IS NULL OR o.sap_ar_invoice_docentry = '')
        """, {'channel': channel_upper, 'start': start_d, 'end': end_dt}, as_dict=True)
        row_not_posted = not_posted[0] if not_posted else {}

        return {
            'channel_name': channel_upper,
            'start_date': str(start_d),
            'end_date': str(end_d),
            'all_orders': {
                'order_count': cint(row_all.get('order_count'), 0),
                'total_subtotal': flt(row_all.get('total_subtotal'), 2),
                'total_taxable_value': flt(row_all.get('total_taxable_value'), 2),
            },
            'complete_orders_only': {
                'order_count': cint(row_complete.get('order_count'), 0),
                'total_subtotal': flt(row_complete.get('total_subtotal'), 2),
                'total_taxable_value': flt(row_complete.get('total_taxable_value'), 2),
            },
            'posted_to_sap': {
                'order_count': cint(row_posted.get('order_count'), 0),
                'taxable_value_posted': flt(row_posted.get('total_taxable_value'), 2),
            },
            'not_posted_to_sap': {
                'order_count': cint(row_not_posted.get('order_count'), 0),
                'taxable_value_not_posted': flt(row_not_posted.get('total_taxable_value'), 2),
            },
            'note': 'SAP posts taxable value (sellingpricewithouttaxesanddiscount - discount) per line, not total_price. Only COMPLETE orders are posted. Flipkart is split into SGST and IGST invoices; check both DocNums for total posted.',
        }
    except Exception as e:
        frappe.log_error("Unicommerce Dashboard", f"get_channel_sap_value_breakdown: {str(e)}")
        return {'error': str(e)}


@frappe.whitelist()
def get_channel_shipping_breakdown(channel_name=None, start_date=None, end_date=None, complete_only=True):
    """
    Shipping charges breakdown for a channel/date range.
    - line_count_with_shipping: number of Order Line Items rows where shippingcharges > 0
    - sum_shipping_gross: sum of shippingcharges (including tax), in ₹
    - sum_shipping_taxable: sum of taxable value (shippingcharges * 100/(100+tax%)), what we post to SAP
    - total_line_count: total Order Line Items in range (for comparison with pivot "Count of Shipping Method")
    """
    try:
        if not channel_name:
            return {'error': 'channel_name is required'}
        start_d = _parse_date_for_subtotal(start_date)
        end_d = _parse_date_for_subtotal(end_date)
        if not start_d or not end_d:
            return {'error': 'start_date and end_date required (DD-MM-YYYY or YYYY-MM-DD)'}
        from datetime import time
        end_dt = datetime.combine(end_d, time(23, 59, 59))
        channel_upper = str(channel_name).strip().upper()

        status_filter = "AND o.status = 'COMPLETE'" if complete_only else ""

        # Total line items in range
        total_lines = frappe.db.sql("""
            SELECT COUNT(*) AS cnt
            FROM `tabUnicommerce Orders` o
            INNER JOIN `tabOrder Line Items` oli ON oli.parent = o.name AND oli.parenttype = 'Unicommerce Orders'
            WHERE o.channel_name = %(channel)s AND o.displayorderdatetime BETWEEN %(start)s AND %(end)s
            """ + status_filter,
            {'channel': channel_upper, 'start': start_d, 'end': end_dt}, as_dict=True)
        total_line_count = (total_lines[0]['cnt'] if total_lines else 0) or 0

        # Lines with shipping > 0: count, sum(gross), sum(taxable)
        shipping = frappe.db.sql("""
            SELECT
                COUNT(*) AS line_count_with_shipping,
                COALESCE(SUM(oli.shippingcharges), 0) AS sum_shipping_gross,
                COALESCE(SUM(
                    CASE WHEN COALESCE(oli.shippingchargetaxpercentage, 0) > 0
                    THEN (COALESCE(oli.shippingcharges, 0) * 100.0 / (100 + COALESCE(oli.shippingchargetaxpercentage, 0)))
                    ELSE COALESCE(oli.shippingcharges, 0) END
                ), 0) AS sum_shipping_taxable
            FROM `tabUnicommerce Orders` o
            INNER JOIN `tabOrder Line Items` oli ON oli.parent = o.name AND oli.parenttype = 'Unicommerce Orders'
            WHERE o.channel_name = %(channel)s AND o.displayorderdatetime BETWEEN %(start)s AND %(end)s
            AND COALESCE(oli.shippingcharges, 0) > 0
            """ + status_filter,
            {'channel': channel_upper, 'start': start_d, 'end': end_dt}, as_dict=True)
        row = shipping[0] if shipping else {}
        return {
            'channel_name': channel_upper,
            'start_date': str(start_d),
            'end_date': str(end_d),
            'complete_orders_only': complete_only,
            'total_line_count': total_line_count,
            'line_count_with_shipping': cint(row.get('line_count_with_shipping'), 0),
            'sum_shipping_gross': flt(row.get('sum_shipping_gross'), 2),
            'sum_shipping_taxable': flt(row.get('sum_shipping_taxable'), 2),
            'note': 'sum_shipping_gross = shipping charges including tax. sum_shipping_taxable = value posted to SAP (ex-tax). total_line_count may match Excel "Count of Shipping Method" if that column counts line items.',
        }
    except Exception as e:
        frappe.log_error("Unicommerce Dashboard", f"get_channel_shipping_breakdown: {str(e)}")
        return {'error': str(e)}


@frappe.whitelist()
def export_channel_taxable_details(channel_name=None, start_date=None, end_date=None, complete_only=True, limit=None):
    """
    Export per-line taxable details (items + shipping) for a channel/date range.
    This is meant for reconciliation against SAP invoice exports.

    For each Order Line Item, returns:
      - order_id
      - line_id (Order Line Items.name)
      - status (order status)
      - displayorderdatetime
      - quantity
      - item_taxable = (sellingpricewithouttaxesanddiscount - discount) * quantity
      - shippingcharges (gross, incl. tax)
      - shippingchargetaxpercentage
      - shipping_taxable (ex-tax, same formula used for SAP freight)
      - total_taxable_including_shipping = item_taxable + shipping_taxable
      - has_sap_docentry (bool)
      - sap_ar_invoice_docnum
    """
    try:
        if not channel_name:
            return {'error': 'channel_name is required'}
        start_d = _parse_date_for_subtotal(start_date)
        end_d = _parse_date_for_subtotal(end_date)
        if not start_d or not end_d:
            return {'error': 'start_date and end_date required (DD-MM-YYYY or YYYY-MM-DD)'}
        from datetime import time
        end_dt = datetime.combine(end_d, time(23, 59, 59))
        channel_upper = str(channel_name).strip().upper()

        status_clause = "AND o.status = 'COMPLETE'" if complete_only else ""
        limit_clause = ""
        if limit and cint(limit) > 0:
            limit_clause = f"LIMIT {cint(limit)}"

        rows = frappe.db.sql(
            f"""
            SELECT
                o.name AS order_id,
                o.status,
                o.displayorderdatetime,
                o.sap_ar_invoice_docentry,
                o.sap_ar_invoice_docnum,
                oli.name AS line_id,
                COALESCE(oli.quantity, 0) AS quantity,
                COALESCE(oli.sellingpricewithouttaxesanddiscount, 0) AS sellingpricewithouttaxesanddiscount,
                COALESCE(oli.discount, 0) AS discount,
                COALESCE(oli.shippingcharges, 0) AS shippingcharges,
                COALESCE(oli.shippingchargetaxpercentage, 0) AS shippingchargetaxpercentage,
                (COALESCE(oli.sellingpricewithouttaxesanddiscount, 0) - COALESCE(oli.discount, 0))
                    * NULLIF(COALESCE(oli.quantity, 0), 0) AS item_taxable,
                CASE
                    WHEN COALESCE(oli.shippingchargetaxpercentage, 0) > 0
                        THEN (COALESCE(oli.shippingcharges, 0) * 100.0
                              / (100 + COALESCE(oli.shippingchargetaxpercentage, 0)))
                    ELSE COALESCE(oli.shippingcharges, 0)
                END AS shipping_taxable
            FROM `tabUnicommerce Orders` o
            INNER JOIN `tabOrder Line Items` oli
                ON oli.parent = o.name AND oli.parenttype = 'Unicommerce Orders'
            WHERE o.channel_name = %(channel)s
              AND o.displayorderdatetime BETWEEN %(start)s AND %(end)s
              {status_clause}
            ORDER BY o.displayorderdatetime, o.name, oli.name
            {limit_clause}
            """,
            {'channel': channel_upper, 'start': start_d, 'end': end_dt},
            as_dict=True,
        )

        # Build response rows with derived totals and flags
        result_rows = []
        sum_item_taxable = 0.0
        sum_shipping_taxable = 0.0
        sum_total_taxable = 0.0

        for r in rows:
            item_taxable = float(r.get('item_taxable') or 0)
            shipping_taxable = float(r.get('shipping_taxable') or 0)
            total_taxable = item_taxable + shipping_taxable
            has_sap_docentry = bool(r.get('sap_ar_invoice_docentry'))

            sum_item_taxable += item_taxable
            sum_shipping_taxable += shipping_taxable
            sum_total_taxable += total_taxable

            result_rows.append({
                'order_id': r.get('order_id'),
                'status': r.get('status'),
                'displayorderdatetime': r.get('displayorderdatetime'),
                'sap_ar_invoice_docentry': r.get('sap_ar_invoice_docentry'),
                'sap_ar_invoice_docnum': r.get('sap_ar_invoice_docnum'),
                'has_sap_docentry': has_sap_docentry,
                'line_id': r.get('line_id'),
                'quantity': r.get('quantity'),
                'sellingpricewithouttaxesanddiscount': r.get('sellingpricewithouttaxesanddiscount'),
                'discount': r.get('discount'),
                'item_taxable': item_taxable,
                'shippingcharges': r.get('shippingcharges'),
                'shippingchargetaxpercentage': r.get('shippingchargetaxpercentage'),
                'shipping_taxable': shipping_taxable,
                'total_taxable_including_shipping': total_taxable,
            })

        return {
            'channel_name': channel_upper,
            'start_date': str(start_d),
            'end_date': str(end_d),
            'complete_orders_only': complete_only,
            'row_count': len(result_rows),
            'sum_item_taxable': flt(sum_item_taxable, 2),
            'sum_shipping_taxable': flt(sum_shipping_taxable, 2),
            'sum_total_taxable_including_shipping': flt(sum_total_taxable, 2),
            'rows': result_rows,
            'note': 'Use rows to reconcile line-by-line against SAP invoice export (match on DocNum + line taxable).',
        }
    except Exception as e:
        frappe.log_error("Unicommerce Dashboard", f"export_channel_taxable_details: {str(e)}")
        return {'error': str(e)}


@frappe.whitelist()
def sync_orders_from_unicommerce(from_date=None, to_date=None, channel_name=None):
    """Sync orders from Unicommerce API.
    Only facilities listed in Unicommerce Settings > Facility are fetched.
    If an external report (e.g. Excel) shows more orders/revenue, add the missing
    facility code there and re-run sync for the same date range."""
    try:
        from_d = _parse_date_for_subtotal(from_date)
        to_d = _parse_date_for_subtotal(to_date)
        from_dt = from_d.isoformat() if from_d else None
        to_dt = to_d.isoformat() if to_d else None
        result = fetch_orders(
            from_date=from_dt,
            to_date=to_dt,
            max_orders=None,
            channel_name=(channel_name or None),
        )

        return {
            'status': 'success',
            'message': f'Synced {result.get("new", 0) + result.get("updated", 0)} orders',
            'total_fetched': result.get('fetched', 0),
            'total_processed': result.get('new', 0) + result.get('updated', 0),
            'total_skipped': result.get('skipped_posted', 0),
            'total_failed': result.get('detail_failed', 0)
        }
    except Exception as e:
        frappe.log_error("Unicommerce Dashboard", f"Error in sync_orders_from_unicommerce: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }


@frappe.whitelist()
def trigger_batch_validation(filters=None, export_to_excel=False):
    """Trigger batch validation"""
    try:
        if not validate_batch_quantities_from_unicommerce_orders:
            return {
                'status': 'error',
                'error': 'validate_batch_quantities_from_unicommerce_orders function not available. Please check imports.'
            }
        if isinstance(filters, str):
            filters = json.loads(filters)
        
        # Use existing batch validation function
        result = validate_batch_quantities_from_unicommerce_orders(
            filters=filters,
            export_to_excel=export_to_excel
        )
        
        return {
            'status': 'success',
            'result': result
        }
    except Exception as e:
        frappe.log_error("Unicommerce Dashboard", f"Error in trigger_batch_validation: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }


@frappe.whitelist()
def export_dashboard_data(filters=None, format='csv', export_type='orders'):
    """Export dashboard data"""
    try:
        if isinstance(filters, str):
            filters = json.loads(filters)
        
        normalized = _normalize_filters(filters)
        order_filters = _build_order_filters(normalized)
        
        if export_type == 'orders':
            # Export orders
            orders = frappe.db.get_list(
                'Unicommerce Orders',
                filters=order_filters,
                fields=[
                    'uniware_id', 'channel_name', 'status', 'displayorderdatetime',
                    'customer_name', 'state', 'city', 'sap_delivery_docnum',
                    'sap_ar_invoice_docnum'
                ],
                limit_page_length=0
            )
            
            # Convert to CSV format
            if format == 'csv':
                import csv
                import io
                
                output = io.StringIO()
                if orders:
                    writer = csv.DictWriter(output, fieldnames=orders[0].keys())
                    writer.writeheader()
                    for order in orders:
                        # Convert datetime to string
                        row = {}
                        for k, v in order.items():
                            if isinstance(v, datetime):
                                row[k] = str(v)
                            else:
                                row[k] = v
                        writer.writerow(row)
                
                csv_content = output.getvalue()
                output.close()
                
                # Save to file
                import os
                from frappe.utils import get_site_path
                
                file_path = os.path.join(
                    get_site_path('private', 'files'),
                    f'unicommerce_orders_export_{now_datetime().strftime("%Y%m%d_%H%M%S")}.csv'
                )
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                with open(file_path, 'w') as f:
                    f.write(csv_content)
                
                return {
                    'status': 'success',
                    'file_url': f'/private/files/{os.path.basename(file_path)}',
                    'file_path': file_path
                }
        
        elif export_type == 'batch_validation':
            # Export batch validation results
            result = trigger_batch_validation(filters=filters, export_to_excel=True)
            if result.get('status') == 'success' and result.get('result', {}).get('excel_file'):
                return {
                    'status': 'success',
                    'file_url': result['result']['excel_file'].get('path', ''),
                    'file_path': result['result']['excel_file'].get('absolute_path', '')
                }
            else:
                return {
                    'status': 'error',
                    'error': 'Failed to generate batch validation export'
                }
        
        elif export_type == 'returns':
            # Export returns (orders with a return_code) with optional filters
            returns_filters = {'return_code': ('!=', '')}
            if normalized.get('channel_name'):
                returns_filters['channel_name'] = normalized['channel_name']
            if normalized.get('status'):
                # Map status filter to statuscode for returns, mirroring get_returns_data
                returns_filters['statuscode'] = normalized['status']
            if normalized.get('start_date') or normalized.get('end_date'):
                start_date = normalized.get('start_date')
                end_date = normalized.get('end_date')
                if start_date and end_date:
                    returns_filters['displayorderdatetime'] = ('between', [start_date, end_date])
                elif start_date:
                    returns_filters['displayorderdatetime'] = ('>=', start_date)
                elif end_date:
                    returns_filters['displayorderdatetime'] = ('<=', end_date)

            returns = frappe.db.get_list(
                'Unicommerce Orders',
                filters=returns_filters,
                fields=[
                    'uniware_id', 'channel_name', 'statuscode', 'displayorderdatetime',
                    'return_code', 'returncompleteddate', 'inventoryreceiveddate',
                    'customer_name', 'state', 'city',
                    'sap_ar_creditnote_docentry'
                ],
                limit_page_length=0
            )

            if format == 'csv':
                import csv
                import io

                output = io.StringIO()
                if returns:
                    writer = csv.DictWriter(output, fieldnames=returns[0].keys())
                    writer.writeheader()
                    for row_in in returns:
                        row = {}
                        for k, v in row_in.items():
                            if isinstance(v, datetime):
                                row[k] = str(v)
                            else:
                                row[k] = v
                        writer.writerow(row)

                csv_content = output.getvalue()
                output.close()

                import os
                from frappe.utils import get_site_path

                file_path = os.path.join(
                    get_site_path('private', 'files'),
                    f'unicommerce_returns_export_{now_datetime().strftime("%Y%m%d_%H%M%S")}.csv'
                )
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                with open(file_path, 'w') as f:
                    f.write(csv_content)

                return {
                    'status': 'success',
                    'file_url': f'/private/files/{os.path.basename(file_path)}',
                    'file_path': file_path
                }
        
        else:
            return {
                'status': 'error',
                'error': f'Unknown export type: {export_type}'
            }
    
    except Exception as e:
        frappe.log_error("Unicommerce Dashboard", f"Error in export_dashboard_data: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }


@frappe.whitelist()
def post_delivery_note_to_sap(channel_name=None, start_date=None, end_date=None, skip_validation=False):
    """
    Post Delivery Notes to SAP B1 for Unicommerce orders with pre-posting validation
    
    Args:
        channel_name (str): Channel name (e.g., 'Amazon_IN_API', 'FLIPKART')
        start_date (str): Start date in DD-MM-YYYY format
        end_date (str): End date in DD-MM-YYYY format
        skip_validation (bool): Skip pre-posting validation (not recommended)
        
    Returns:
        dict: Summary of delivery note creation results
    """
    try:
        if not Channel_delivery_Creation_Dispatched2:
            return {
                'status': 'error',
                'error': 'Delivery note creation function not available. Please check imports.'
            }
        
        if not channel_name:
            return {
                'status': 'error',
                'error': 'Channel name is required'
            }
        
        if not start_date or not end_date:
            return {
                'status': 'error',
                'error': 'Start date and end date are required (format: DD-MM-YYYY)'
            }
        
        frappe.log_error("Unicommerce Dashboard", f"Posting delivery notes to SAP - Channel: {channel_name}, Dates: {start_date} to {end_date}")
        
        # Pre-posting validation (unless skipped)
        if not skip_validation and comprehensive_pre_posting_validation:
            frappe.log_error("Unicommerce Dashboard", f"Running pre-posting validation for {channel_name}...")
            validation_result = comprehensive_pre_posting_validation(
                channel_name=channel_name,
                start_date=start_date,
                end_date=end_date,
                order_list=None
            )
            
            if not validation_result.get('is_valid', False):
                # Build detailed error message
                error_details = []
                
                if not validation_result.get('sap_accessible', False):
                    error_details.append(f"SAP Service Layer: {validation_result.get('sap_message', 'Not accessible')}")
                
                batch_validation = validation_result.get('batch_validation', {})
                if not batch_validation.get('passed', False):
                    failed_items = batch_validation.get('failed_items', [])
                    error_details.append(f"Batch Quantity: {len(failed_items)} items have insufficient stock")
                    # Add first few failed items as examples
                    for item in failed_items[:5]:
                        fallback = f"{item.get('ItemCode', '')} - {item.get('Status', '')}"
                        error_details.append(f"  - {item.get('Message') or fallback}")
                    if len(failed_items) > 5:
                        error_details.append(f"  ... and {len(failed_items) - 5} more items")
                
                item_validation = validation_result.get('item_status_validation', {})
                inactive_items = item_validation.get('inactive_items') or []
                if not item_validation.get('passed', False) and len(inactive_items) > 0:
                    error_details.append(f"Item Status: {len(inactive_items)} items are inactive or not found in SAP")
                    for item in inactive_items[:5]:
                        fallback = f"{item.get('ItemCode', '')} - {item.get('Status', '')}"
                        error_details.append(f"  - {item.get('Message') or fallback}")
                    if len(inactive_items) > 5:
                        error_details.append(f"  ... and {len(inactive_items) - 5} more items")
                
                error_message = "Pre-posting validation failed:\n" + "\n".join(error_details)
                
                return {
                    'status': 'validation_failed',
                    'error': error_message,
                    'validation_result': validation_result,
                    'message': 'Cannot post to SAP due to validation failures. Please resolve the issues and try again.'
                }
            else:
                frappe.log_error("Unicommerce Dashboard", f"Pre-posting validation passed for {channel_name}")
        
        # Call the delivery note creation function
        result = Channel_delivery_Creation_Dispatched2(
            Channel_Name=channel_name,
            startDate=start_date,
            endDate=end_date
        )
        
        return {
            'status': 'success',
            'result': result,
            'message': f'Delivery notes posted successfully for {channel_name}'
        }
        
    except Exception as e:
        error_msg = f"Error posting delivery notes to SAP: {str(e)}"
        frappe.log_error("Unicommerce Dashboard", error_msg)
        return {
            'status': 'error',
            'error': error_msg
        }


@frappe.whitelist()
def clear_ar_invoice_docnum_for_range(channel_name=None, start_date=None, end_date=None):
    """
    Clear sap_ar_invoice_docnum and sap_ar_invoice_docentry for all orders in the given
    channel and displayorderdatetime range. Use this to "reset" before re-posting so that
    only the orders from your next "Post to SAP" run get docnum/docentry (no orders will
    have them without an actual SAP post).
    Dates: DD-MM-YYYY or YYYY-MM-DD.
    """
    try:
        if not channel_name or not start_date or not end_date:
            return {'error': 'channel_name, start_date and end_date are required'}
        start_d = _parse_date_for_subtotal(start_date)
        end_d = _parse_date_for_subtotal(end_date)
        if not start_d or not end_d:
            return {'error': 'Invalid start_date or end_date (use DD-MM-YYYY or YYYY-MM-DD)'}
        from datetime import time
        end_dt = datetime.combine(end_d, time(23, 59, 59))
        channel_upper = str(channel_name).strip().upper()
        total_in_range = frappe.db.count('Unicommerce Orders', filters={
            'channel_name': channel_upper,
            'displayorderdatetime': ('between', [start_d, end_dt]),
        })
        # Count how many had docnum/docentry before clear
        had_doc = frappe.db.sql("""
            SELECT COUNT(*) FROM `tabUnicommerce Orders`
            WHERE channel_name = %(channel)s
            AND displayorderdatetime BETWEEN %(start)s AND %(end)s
            AND (COALESCE(sap_ar_invoice_docnum,'') != '' OR sap_ar_invoice_docentry IS NOT NULL)
        """, {'channel': channel_upper, 'start': start_d, 'end': end_dt}, as_dict=False)
        orders_cleared = (had_doc[0][0] if had_doc else 0)
        # Bulk update to avoid "modified after you have opened it" and to be fast
        frappe.db.sql("""
            UPDATE `tabUnicommerce Orders`
            SET sap_ar_invoice_docnum = '', sap_ar_invoice_docentry = NULL
            WHERE channel_name = %(channel)s
            AND displayorderdatetime BETWEEN %(start)s AND %(end)s
            AND (COALESCE(sap_ar_invoice_docnum,'') != '' OR sap_ar_invoice_docentry IS NOT NULL)
        """, {'channel': channel_upper, 'start': start_d, 'end': end_dt})
        frappe.db.commit()
        return {
            'message': f'Cleared sap_ar_invoice_docnum/docentry for {orders_cleared} orders',
            'channel_name': channel_upper,
            'start_date': str(start_d),
            'end_date': str(end_d),
            'orders_cleared': orders_cleared,
            'total_in_range': total_in_range,
        }
    except Exception as e:
        frappe.log_error("Unicommerce Dashboard", f"clear_ar_invoice_docnum_for_range: {str(e)}")
        return {'error': str(e)}


@frappe.whitelist()
def backfill_sap_docnum_for_range(channel_name=None, start_date=None, end_date=None, docnum=None, docentry=None):
    """
    Backfill sap_ar_invoice_docnum and sap_ar_invoice_docentry for COMPLETE orders in the given
    channel and displayorderdatetime range that currently have no docnum/docentry.
    This is intended for cases where SAP posting succeeded for a batch, but some orders in the
    batch did not get updated in Frappe (e.g. save() failures during update_order_records).

    Args:
        channel_name (str): Channel name (e.g. 'FLIPKART')
        start_date (str): Start date (DD-MM-YYYY or YYYY-MM-DD)
        end_date (str): End date (DD-MM-YYYY or YYYY-MM-DD)
        docnum (str): SAP AR Invoice DocNum to set
        docentry (int/str, optional): SAP AR Invoice DocEntry. If not provided, will be
            looked up from any existing order for this channel/date range that already
            has the given docnum and a non-null docentry.
    """
    try:
        if not channel_name or not start_date or not end_date or not docnum:
            return {'error': 'channel_name, start_date, end_date and docnum are required'}

        start_d = _parse_date_for_subtotal(start_date)
        end_d = _parse_date_for_subtotal(end_date)
        if not start_d or not end_d:
            return {'error': 'Invalid start_date or end_date (use DD-MM-YYYY or YYYY-MM-DD)'}

        from datetime import time
        end_dt = datetime.combine(end_d, time(23, 59, 59))
        channel_upper = str(channel_name).strip().upper()

        # If docentry not provided, try to infer it from any existing order that already has this docnum
        if not docentry:
            existing = frappe.db.sql(
                """
                SELECT sap_ar_invoice_docentry
                FROM `tabUnicommerce Orders`
                WHERE channel_name = %(channel)s
                  AND displayorderdatetime BETWEEN %(start)s AND %(end)s
                  AND sap_ar_invoice_docnum = %(docnum)s
                  AND sap_ar_invoice_docentry IS NOT NULL
                LIMIT 1
                """,
                {'channel': channel_upper, 'start': start_d, 'end': end_dt, 'docnum': str(docnum)},
                as_dict=True,
            )
            if not existing:
                return {'error': f'Could not infer docentry for docnum {docnum}. Please provide docentry explicitly.'}
            docentry = existing[0]['sap_ar_invoice_docentry']

        # Count how many COMPLETE orders in range are missing docnum/docentry
        missing_count = frappe.db.sql(
            """
            SELECT COUNT(*)
            FROM `tabUnicommerce Orders`
            WHERE channel_name = %(channel)s
              AND status = 'COMPLETE'
              AND displayorderdatetime BETWEEN %(start)s AND %(end)s
              AND (COALESCE(sap_ar_invoice_docnum,'') = '' OR sap_ar_invoice_docentry IS NULL)
            """,
            {'channel': channel_upper, 'start': start_d, 'end': end_dt},
            as_dict=False,
        )
        to_update = missing_count[0][0] if missing_count else 0

        if to_update == 0:
            return {
                'message': 'No COMPLETE orders without docnum/docentry found in range; nothing to backfill.',
                'channel_name': channel_upper,
                'start_date': str(start_d),
                'end_date': str(end_d),
                'docnum': str(docnum),
                'docentry': docentry,
                'orders_updated': 0,
            }

        # Bulk update missing docnum/docentry
        frappe.db.sql(
            """
            UPDATE `tabUnicommerce Orders`
            SET sap_ar_invoice_docnum = %(docnum)s,
                sap_ar_invoice_docentry = %(docentry)s
            WHERE channel_name = %(channel)s
              AND status = 'COMPLETE'
              AND displayorderdatetime BETWEEN %(start)s AND %(end)s
              AND (COALESCE(sap_ar_invoice_docnum,'') = '' OR sap_ar_invoice_docentry IS NULL)
            """,
            {
                'channel': channel_upper,
                'start': start_d,
                'end': end_dt,
                'docnum': str(docnum),
                'docentry': docentry,
            },
        )
        frappe.db.commit()

        return {
            'message': f'Backfilled sap_ar_invoice_docnum/docentry for {to_update} COMPLETE orders',
            'channel_name': channel_upper,
            'start_date': str(start_d),
            'end_date': str(end_d),
            'docnum': str(docnum),
            'docentry': docentry,
            'orders_updated': to_update,
        }
    except Exception as e:
        frappe.log_error("Unicommerce Dashboard", f"backfill_sap_docnum_for_range: {str(e)}")
        return {'error': str(e)}


@frappe.whitelist()
def post_ar_invoice_to_sap(channel_name=None, start_date=None, end_date=None, skip_validation=False, preview_payload=False):
    """
    Post AR Invoices to SAP B1 for Unicommerce orders with pre-posting validation.
    Docnum/docentry are set on orders only after a successful SAP POST (no other code path sets them).
    Batch validation is not run here; run it from Batch Validation before posting.

    Args:
        channel_name (str): Channel name (e.g., 'Amazon_IN_API', 'FLIPKART')
        start_date (str): Start date in DD-MM-YYYY format
        end_date (str): End date in DD-MM-YYYY format
        skip_validation (bool): Skip pre-posting validation (not recommended)
        preview_payload (bool): If True, only build and return JSON payloads without posting

    Returns:
        dict: Summary and payloads (preview or sent)
    """
    try:
        if not channel_name:
            return {
                'status': 'error',
                'error': 'Channel name is required'
            }
        
        if not start_date or not end_date:
            return {
                'status': 'error',
                'error': 'Start date and end date are required (format: DD-MM-YYYY)'
            }
        if preview_payload:
            return {
                'status': 'error',
                'error': 'Preview payload is not supported in the modern worker pipeline.'
            }
        canonical_channel = channel_name
        frappe.log_error("Unicommerce Dashboard", f"Posting AR invoices to SAP - Channel: {canonical_channel}, Dates: {start_date} to {end_date}")
        
        # Pre-posting validation (unless skipped)
        if not skip_validation and comprehensive_pre_posting_validation:
            frappe.log_error("Unicommerce Dashboard", f"Running pre-posting validation for {canonical_channel}...")
            validation_result = comprehensive_pre_posting_validation(
                channel_name=canonical_channel,
                start_date=start_date,
                end_date=end_date,
                order_list=None
            )
            
            if not validation_result.get('is_valid', False):
                # Build detailed error message
                error_details = []
                
                if not validation_result.get('sap_accessible', False):
                    error_details.append(f"SAP Service Layer: {validation_result.get('sap_message', 'Not accessible')}")
                
                batch_validation = validation_result.get('batch_validation', {})
                if not batch_validation.get('passed', False):
                    failed_items = batch_validation.get('failed_items', [])
                    error_details.append(f"Batch Quantity: {len(failed_items)} items have insufficient stock")
                    # Add first few failed items as examples
                    for item in failed_items[:5]:
                        fallback = f"{item.get('ItemCode', '')} - {item.get('Status', '')}"
                        error_details.append(f"  - {item.get('Message') or fallback}")
                    if len(failed_items) > 5:
                        error_details.append(f"  ... and {len(failed_items) - 5} more items")
                
                item_validation = validation_result.get('item_status_validation', {})
                inactive_items = item_validation.get('inactive_items') or []
                if not item_validation.get('passed', False) and len(inactive_items) > 0:
                    error_details.append(f"Item Status: {len(inactive_items)} items are inactive or not found in SAP")
                    for item in inactive_items[:5]:
                        fallback = f"{item.get('ItemCode', '')} - {item.get('Status', '')}"
                        error_details.append(f"  - {item.get('Message') or fallback}")
                    if len(inactive_items) > 5:
                        error_details.append(f"  ... and {len(inactive_items) - 5} more items")
                
                error_message = "Pre-posting validation failed:\n" + "\n".join(error_details)
                
                return {
                    'status': 'validation_failed',
                    'error': error_message,
                    'validation_result': validation_result,
                    'message': 'Cannot post to SAP due to validation failures. Please resolve the issues and try again.'
                }
            else:
                frappe.log_error("Unicommerce Dashboard", f"Pre-posting validation passed for {canonical_channel}")
        
        start_d = _parse_date_for_subtotal(start_date)
        end_d = _parse_date_for_subtotal(end_date)
        if not start_d or not end_d:
            return {'status': 'error', 'error': 'Invalid start_date or end_date (use DD-MM-YYYY or YYYY-MM-DD)'}
        result = post_invoices(
            limit=500,
            start_date=start_d.isoformat(),
            end_date=end_d.isoformat(),
            channel_name=canonical_channel,
        )
        summary = result if isinstance(result, dict) else {"result": result}
        payloads_sent = {}
        
        return {
            'status': 'success',
            'result': summary,
            'payloads_sent': payloads_sent,
            'message': f'AR invoices posted successfully for {canonical_channel}'
        }
        
    except Exception as e:
        error_msg = f"Error posting AR invoices to SAP: {str(e)}"
        frappe.log_error("Unicommerce Dashboard", error_msg)
        return {
            'status': 'error',
            'error': error_msg
        }


@frappe.whitelist()
def post_credit_note_to_sap(channel_name=None, start_date=None, end_date=None, skip_validation=False):
    """
    Post Credit Notes to SAP B1 for Unicommerce returns with pre-posting validation
    
    Note: Credit notes are for returns, so batch validation may not be applicable.
    However, we still validate SAP accessibility and item status.
    
    Args:
        channel_name (str): Channel name (e.g., 'Amazon_IN_API', 'FLIPKART')
        start_date (str): Start date in DD-MM-YYYY format
        end_date (str): End date in DD-MM-YYYY format
        skip_validation (bool): Skip pre-posting validation (not recommended)
        
    Returns:
        dict: Summary of credit note creation results
    """
    try:
        if not channel_name:
            return {
                'status': 'error',
                'error': 'Channel name is required'
            }
        
        if not start_date or not end_date:
            return {
                'status': 'error',
                'error': 'Start date and end date are required (format: DD-MM-YYYY)'
            }
        
        frappe.log_error("Unicommerce Dashboard", f"Posting credit notes to SAP - Channel: {channel_name}, Dates: {start_date} to {end_date}")
        
        # Pre-posting validation (SAP accessibility and item status only, batch validation skipped for returns)
        if not skip_validation and comprehensive_pre_posting_validation:
            frappe.log_error("Unicommerce Dashboard", f"Running pre-posting validation for credit notes ({channel_name})...")
            # For credit notes, we only check SAP accessibility and item status
            # Batch validation is not applicable for returns
            validation_result = comprehensive_pre_posting_validation(
                channel_name=channel_name,
                start_date=start_date,
                end_date=end_date,
                order_list=None
            )
            
            # For credit notes, we only care about SAP accessibility and item status
            if not validation_result.get('sap_accessible', False):
                return {
                    'status': 'validation_failed',
                    'error': f"SAP Service Layer not accessible: {validation_result.get('sap_message', 'Not accessible')}",
                    'validation_result': validation_result,
                    'message': 'Cannot post credit notes to SAP. Please check SAP connectivity.'
                }
            
            # Check item status (but don't fail on batch validation for returns)
            item_validation = validation_result.get('item_status_validation', {})
            inactive_items = item_validation.get('inactive_items') or []
            if not item_validation.get('passed', False) and len(inactive_items) > 0:
                error_details = [f"Item Status: {len(inactive_items)} items are inactive or not found in SAP"]
                for item in inactive_items[:5]:
                    fallback = f"{item.get('ItemCode', '')} - {item.get('Status', '')}"
                    error_details.append(f"  - {item.get('Message') or fallback}")
                if len(inactive_items) > 5:
                    error_details.append(f"  ... and {len(inactive_items) - 5} more items")

                error_message = "Pre-posting validation failed:\n" + "\n".join(error_details)

                return {
                    'status': 'validation_failed',
                    'error': error_message,
                    'validation_result': validation_result,
                    'message': 'Cannot post credit notes to SAP due to inactive items. Please resolve the issues and try again.'
                }
        
        start_d = _parse_date_for_subtotal(start_date)
        end_d = _parse_date_for_subtotal(end_date)
        if not start_d or not end_d:
            return {'status': 'error', 'error': 'Invalid start_date or end_date (use DD-MM-YYYY or YYYY-MM-DD)'}
        summary = post_credit_notes(
            limit=500,
            start_date=start_d.isoformat(),
            end_date=end_d.isoformat(),
            channel_name=channel_name,
        )
        if isinstance(summary, dict):
            msg = f"Credit note worker run completed for {channel_name}."
            return {
                'status': 'success',
                'message': msg,
                'summary': summary,
            }
        return {
            'status': 'success',
            'message': f'Credit notes posted successfully for {channel_name}'
        }
        
    except Exception as e:
        error_msg = f"Error posting credit notes to SAP: {str(e)}"
        frappe.log_error("Unicommerce Dashboard", error_msg)
        return {
            'status': 'error',
            'error': error_msg
        }


@frappe.whitelist()
def post_delivery_note_legacy(channel_name=None, start_date=None, end_date=None, skip_validation=False):
    """
    Post Delivery Notes to SAP B1 using legacy function (Channel_post_delivery_note1) with pre-posting validation
    
    Args:
        channel_name (str): Channel name (e.g., 'Amazon_IN_API', 'FLIPKART')
        start_date (str): Start date in DD-MM-YYYY format
        end_date (str): End date in DD-MM-YYYY format
        skip_validation (bool): Skip pre-posting validation (not recommended)
        
    Returns:
        dict: Summary of delivery note creation results
    """
    try:
        if not Channel_post_delivery_note1:
            return {
                'status': 'error',
                'error': 'Legacy delivery note creation function not available. Please check imports.'
            }
        
        if not channel_name:
            return {
                'status': 'error',
                'error': 'Channel name is required'
            }
        
        if not start_date or not end_date:
            return {
                'status': 'error',
                'error': 'Start date and end date are required (format: DD-MM-YYYY)'
            }
        
        frappe.log_error("Unicommerce Dashboard", f"Posting delivery notes to SAP (Legacy) - Channel: {channel_name}, Dates: {start_date} to {end_date}")
        
        # Pre-posting validation (unless skipped)
        if not skip_validation and comprehensive_pre_posting_validation:
            frappe.log_error("Unicommerce Dashboard", f"Running pre-posting validation for {channel_name} (Legacy)...")
            validation_result = comprehensive_pre_posting_validation(
                channel_name=channel_name,
                start_date=start_date,
                end_date=end_date,
                order_list=None
            )
            
            if not validation_result.get('is_valid', False):
                # Build detailed error message
                error_details = []
                
                if not validation_result.get('sap_accessible', False):
                    error_details.append(f"SAP Service Layer: {validation_result.get('sap_message', 'Not accessible')}")
                
                batch_validation = validation_result.get('batch_validation', {})
                if not batch_validation.get('passed', False):
                    failed_items = batch_validation.get('failed_items', [])
                    error_details.append(f"Batch Quantity: {len(failed_items)} items have insufficient stock")
                    for item in failed_items[:5]:
                        fallback = f"{item.get('ItemCode', '')} - {item.get('Status', '')}"
                        error_details.append(f"  - {item.get('Message') or fallback}")
                    if len(failed_items) > 5:
                        error_details.append(f"  ... and {len(failed_items) - 5} more items")
                
                item_validation = validation_result.get('item_status_validation', {})
                inactive_items = item_validation.get('inactive_items') or []
                if not item_validation.get('passed', False) and len(inactive_items) > 0:
                    error_details.append(f"Item Status: {len(inactive_items)} items are inactive or not found in SAP")
                    for item in inactive_items[:5]:
                        fallback = f"{item.get('ItemCode', '')} - {item.get('Status', '')}"
                        error_details.append(f"  - {item.get('Message') or fallback}")
                    if len(inactive_items) > 5:
                        error_details.append(f"  ... and {len(inactive_items) - 5} more items")

                error_message = "Pre-posting validation failed:\n" + "\n".join(error_details)

                return {
                    'status': 'validation_failed',
                    'error': error_message,
                    'validation_result': validation_result,
                    'message': 'Cannot post to SAP due to validation failures. Please resolve the issues and try again.'
                }
            else:
                frappe.log_error("Unicommerce Dashboard", f"Pre-posting validation passed for {channel_name} (Legacy)")
        
        # Call the legacy delivery note creation function
        result = Channel_post_delivery_note1(
            Channel_Name=channel_name,
            startDate=start_date,
            endDate=end_date
        )
        
        return {
            'status': 'success',
            'result': result,
            'message': f'Delivery notes posted successfully (Legacy) for {channel_name}'
        }
        
    except Exception as e:
        error_msg = f"Error posting delivery notes to SAP (Legacy): {str(e)}"
        frappe.log_error("Unicommerce Dashboard", error_msg)
        return {
            'status': 'error',
            'error': error_msg
        }


@frappe.whitelist()
def validate_before_posting(channel_name=None, start_date=None, end_date=None):
    """
    Standalone validation endpoint to check before posting
    
    Args:
        channel_name (str): Channel name
        start_date (str): Start date in DD-MM-YYYY format
        end_date (str): End date in DD-MM-YYYY format
        
    Returns:
        dict: Validation results
    """
    try:
        if not comprehensive_pre_posting_validation:
            return {
                'status': 'error',
                'error': 'Validation function not available'
            }
        
        if not channel_name or not start_date or not end_date:
            return {
                'status': 'error',
                'error': 'Channel name, start date, and end date are required'
            }
        
        validation_result = comprehensive_pre_posting_validation(
            channel_name=channel_name,
            start_date=start_date,
            end_date=end_date,
            order_list=None
        )
        
        return {
            'status': 'success',
            'validation_result': validation_result
        }
        
    except Exception as e:
        error_msg = f"Validation error: {str(e)}"
        frappe.log_error("Unicommerce Dashboard Validation", error_msg)
        return {
            'status': 'error',
            'error': error_msg
        }


# =============================================================================
# MANUAL CRON JOB TRIGGERS
# =============================================================================

def _run_fill_orders_job(from_date, to_date):
    """Background job: run fetch_orders and store result in cache for status endpoint."""
    try:
        # Caller may pass ISO datetime (2026-04-28T00:00:00Z), bare date
        # (YYYY-MM-DD), or operator format (DD-MM-YYYY). Strip any time
        # suffix first, then parse to canonical YYYY-MM-DD for fetch_orders.
        from_head = str(from_date).strip()[:10] if from_date else None
        to_head = str(to_date).strip()[:10] if to_date else None
        from_d = _parse_date_for_subtotal(from_head)
        to_d = _parse_date_for_subtotal(to_head)
        from_dt = from_d.isoformat() if from_d else None
        to_dt = to_d.isoformat() if to_d else None
        result = fetch_orders(from_date=from_dt, to_date=to_dt, max_orders=None)
        frappe.cache().set_value(
            "unicommerce_fill_orders_last_result",
            {"status": "completed", "result": result, "from_date": from_date, "to_date": to_date},
            expires_in_sec=86400,
        )
        return result
    except Exception as e:
        frappe.cache().set_value(
            "unicommerce_fill_orders_last_result",
            {"status": "error", "error": str(e), "from_date": from_date, "to_date": to_date},
            expires_in_sec=86400,
        )
        raise


@frappe.whitelist()
def trigger_fill_orders(from_date=None, to_date=None):
    """Manually trigger fill_orders with custom date range. Runs in background to avoid broken pipe on long runs."""
    try:
        # If no dates provided, default to last 1 day
        if not from_date or not to_date:
            now = datetime.now()
            to_date = now.strftime('%Y-%m-%dT%H:%M:%SZ')
            from_date = (now - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        else:
            # Convert to ISO format; accept DD-MM-YYYY (from dashboard) or YYYY-MM-DD (from date input)
            try:
                from_dt = datetime.strptime(from_date, '%d-%m-%Y')
                to_dt = datetime.strptime(to_date, '%d-%m-%Y')
                from_date = from_dt.strftime('%Y-%m-%dT00:00:00Z')
                to_date = to_dt.strftime('%Y-%m-%dT23:59:59Z')
            except ValueError:
                try:
                    from_dt = datetime.strptime(from_date, '%Y-%m-%d')
                    to_dt = datetime.strptime(to_date, '%Y-%m-%d')
                    from_date = from_dt.strftime('%Y-%m-%dT00:00:00Z')
                    to_date = to_dt.strftime('%Y-%m-%dT23:59:59Z')
                except ValueError:
                    pass  # use as-is if already ISO

        frappe.enqueue(
            method=_run_fill_orders_job,
            queue="long",
            timeout=7200,
            job_name="unicommerce_fill_orders",
            from_date=from_date,
            to_date=to_date,
        )
        return {
            "status": "started",
            "message": "Fill orders started in the background. This may take several minutes for large date ranges. Refresh the dashboard later to see updated orders, or use 'Check last result' to see the outcome.",
        }
    except Exception as e:
        error_msg = f"Error triggering fill_orders: {str(e)}"
        frappe.log_error("Unicommerce Dashboard", error_msg + "\n" + frappe.get_traceback())
        return {"status": "error", "error": error_msg, "exc_type": type(e).__name__}


@frappe.whitelist()
def get_fill_orders_last_result():
    """Return the result of the most recent fill_orders background job, if any."""
    data = frappe.cache().get_value("unicommerce_fill_orders_last_result")
    if data is None:
        return {"status": "unknown", "message": "No fill orders result found. Run Fill Orders first."}
    return data


@frappe.whitelist()
def trigger_monthly_export_with_download(start_date=None, end_date=None, email=None):
    """Create master sheet for date range and send to email. Runs immediately (no queue).
    start_date, end_date: DD-MM-YYYY or YYYY-MM-DD (required). email: where to send the report (required)."""
    try:
        email = (email or "").strip()
        if not email:
            return {"status": "error", "error": "Email address is required"}
        frappe.utils.validate_email_address(email, throw=True)
        return {
            "status": "error",
            "error": "Monthly export from legacy automation is deprecated. Use unicommerce reporting export APIs."
        }
    except Exception as e:
        error_msg = str(e)
        frappe.log_error("Unicommerce Dashboard", error_msg + "\n" + frappe.get_traceback())
        return {"status": "error", "error": error_msg, "exc_type": type(e).__name__}


@frappe.whitelist()
def get_monthly_export_status(job_id):
    """Return status of a monthly export job started with trigger_monthly_export_with_download.
    Returns { status: 'queued'|'running'|'success'|'error', ... }."""
    if not job_id:
        return {"status": "unknown", "error": "job_id required"}
    cache_key = f"monthly_export_result:{job_id}"
    data = frappe.cache().get_value(cache_key)
    if data is None:
        return {"status": "unknown", "error": "Job not found or expired"}
    return data


@frappe.whitelist()
def send_monthly_export_email(file_name, email):
    """
    Send the monthly Unicommerce export Excel file to the given email address.
    file_name: basename of the Excel file (e.g. unicommerce_export_...xlsx).
    email: recipient email address.
    """
    if not file_name or not isinstance(file_name, str):
        frappe.throw(_("file_name is required"))
    base = os.path.basename(file_name).strip()
    if not base.endswith(".xlsx") or not base.startswith("unicommerce_export_"):
        frappe.throw(_("Invalid file name"))
    site_path = frappe.get_site_path("private", "files", "unicommerce_exports", base)
    if not os.path.isfile(site_path):
        frappe.throw(_("File not found"))
    if not email or not isinstance(email, str):
        frappe.throw(_("Email address is required"))
    email = email.strip().lower()
    frappe.utils.validate_email_address(email, throw=True)
    try:
        with open(site_path, "rb") as f:
            file_content = f.read()
        subject = _("Monthly Unicommerce Export Report")
        message = _("<p>Please find the monthly Unicommerce export Excel report attached.</p>")
        frappe.sendmail(
            recipients=[email],
            subject=subject,
            message=message,
            attachments=[{"fname": base, "fcontent": file_content}],
        )
        return {"ok": True, "message": _("Report sent to {0}").format(email)}
    except Exception as e:
        frappe.log_error("Unicommerce Dashboard Monthly Export Email", f"send_monthly_export_email: {str(e)}")
        frappe.throw(_("Failed to send email: {0}").format(str(e)))


@frappe.whitelist()
def trigger_update_latest_orders():
    """Manually trigger update_latest_orders cron job"""
    try:
        result = fetch_orders(max_orders=None)
        return {
            'status': 'success',
            'message': 'Successfully updated latest orders',
            'result': result
        }
    except Exception as e:
        error_msg = f"Error triggering update_latest_orders: {str(e)}"
        frappe.log_error("Unicommerce Dashboard", error_msg + "\n" + frappe.get_traceback())
        return {'status': 'error', 'error': error_msg, 'exc_type': type(e).__name__}


@frappe.whitelist()
def trigger_update_uniware_po_status(days=None):
    """Manually trigger Update_Uniware_PO_Status cron job"""
    try:
        return {
            'status': 'error',
            'error': 'PO status sync via legacy automation has been deprecated.'
        }
    except Exception as e:
        error_msg = f"Error triggering Update_Uniware_PO_Status: {str(e)}"
        frappe.log_error("Unicommerce Dashboard", error_msg + "\n" + frappe.get_traceback())
        return {'status': 'error', 'error': error_msg, 'exc_type': type(e).__name__}


@frappe.whitelist()
def trigger_po_grn_completion(days=None):
    """Manually trigger PO_GRN_Completion cron job"""
    try:
        return {
            'status': 'error',
            'error': 'PO GRN completion via legacy automation has been deprecated.'
        }
    except Exception as e:
        error_msg = f"Error triggering PO_GRN_Completion: {str(e)}"
        frappe.log_error("Unicommerce Dashboard", error_msg + "\n" + frappe.get_traceback())
        return {'status': 'error', 'error': error_msg, 'exc_type': type(e).__name__}


@frappe.whitelist()
def trigger_unicommerce_dispatch_dn():
    """Manually trigger Unicommerce_Dispatch_DN cron job (Delivery Notes)"""
    return {
        'status': 'error',
        'error': 'DN_Creation_Unicommerce has been removed. Delivery Notes dispatch is no longer available via this trigger.'
    }


@frappe.whitelist()
def trigger_unicommerce_dispatch_inv():
    """Manually trigger Unicommerce_Dispatch_INV cron job (AR Invoices)"""
    return {
        'status': 'error',
        'error': 'Legacy dispatch trigger has been removed. Use post_ar_invoice_to_sap instead.'
    }


@frappe.whitelist()
def trigger_dn_creation_from_upload():
    """Manually trigger DN_Creation_from_Upload cron job"""
    return {
        'status': 'error',
        'error': 'DN_Creation_Unicommerce has been removed. DN creation from upload is no longer available.'
    }


@frappe.whitelist()
def trigger_create_channel_invoices(channel_name=None, start_date=None, end_date=None):
    """Manually trigger create_channel_invoices for AR invoice creation"""
    try:
        return post_ar_invoice_to_sap(
            channel_name=channel_name,
            start_date=start_date,
            end_date=end_date,
            skip_validation=False,
            preview_payload=False,
        )
    except Exception as e:
        error_msg = f"Error triggering create_channel_invoices: {str(e)}"
        frappe.log_error("Unicommerce Dashboard", error_msg + "\n" + frappe.get_traceback())
        return {'status': 'error', 'error': error_msg, 'exc_type': type(e).__name__}
