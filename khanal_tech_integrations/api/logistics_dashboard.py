"""
Logistics Dashboard API
Provides endpoints for the Logistics dashboard in kiosk-frontend
Uses SAP HANA database for read operations
"""

import frappe
from frappe import _
from datetime import datetime, timedelta
from frappe.utils import get_datetime, now_datetime, add_to_date, flt
import json
import os
import ssl
import urllib3
from khanal_tech_integrations.api.common.sap_connector import SAPConnector


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

    # Normalize invalid ranges
    if normalized.get('start_date') and normalized.get('end_date'):
        if normalized['start_date'] > normalized['end_date']:
            normalized['start_date'], normalized['end_date'] = normalized['end_date'], normalized['start_date']
    
    # Transporter filter
    if filters.get('transporter_name'):
        normalized['transporter_name'] = filters['transporter_name']
    
    # Channel filter
    if filters.get('channel'):
        normalized['channel'] = filters['channel']
    
    # Status filter
    if filters.get('delivery_status'):
        normalized['delivery_status'] = filters['delivery_status']
    
    # POD status filter
    if filters.get('pod_status'):
        normalized['pod_status'] = filters['pod_status']
    
    # POD link filter
    if filters.get('pod_link_status'):
        normalized['pod_link_status'] = filters['pod_link_status']
    
    # POD date filter
    if filters.get('pod_date_status'):
        normalized['pod_date_status'] = filters['pod_date_status']
    
    return normalized


def _get_fiscal_year_range(reference_date=None):
    """Return fiscal year range (Apr 1 to Mar 31) for a given date."""
    if not reference_date:
        reference_date = now_datetime().date()
    year = reference_date.year
    if reference_date.month < 4:
        start_date = datetime(year - 1, 4, 1).date()
        end_date = datetime(year, 3, 31).date()
    else:
        start_date = datetime(year, 4, 1).date()
        end_date = datetime(year + 1, 3, 31).date()
    return start_date, end_date


POD_LINK_EXPR = 'IFNULL(NULLIF(TRIM(CAST(a."U_Pod_Link" AS NVARCHAR)), \'NA\'), \'\')'
POD_DATE_EXPR = 'IFNULL(TO_VARCHAR(a."U_POD_DATE"), \'\')'
TRACKING_EXPR = 'IFNULL(TRIM(CAST(a."U_TrackingNo" AS NVARCHAR)), \'\')'

# Channels where POD link/date is not applicable — excluded from "missing" counts
POD_NA_CHANNEL_COND = (
    'T1."CardCode" IN (\'C00623\',\'C01026\',\'C02574\',\'C03121\',\'C03358\',\'C03412\',\'C03494\',\'C03564\','
    '\'C03575\',\'C03579\',\'C03586\',\'C03596\')'
    ' OR T2."GroupName" LIKE \'%Export%\''
    ' OR T2."GroupName" LIKE \'%Others%\''
)


def _append_channel_filter(where_conditions, channel):
    """Append channel filter conditions to the WHERE clause list."""
    if not channel:
        return where_conditions

    if channel == 'E-com B2C':
        where_conditions.append(
            'T1."CardCode" IN (\'C00623\',\'C01026\',\'C02574\',\'C03121\',\'C03358\',\'C03412\',\'C03494\',\'C03564\','
            '\'C03575\',\'C03579\',\'C03586\',\'C03596\')'
        )
    elif channel == 'E-com B2B':
        where_conditions.append('''
            T1."CardCode" NOT IN ('C00623','C01026','C02574','C03121','C03358','C03412','C03494','C03564',
                                   'C03575','C03579','C03586','C03596','C01186','C03326','C03324','C03327','C01072','C01183','C03177')
            AND T2."GroupName" NOT LIKE '%Domestic HN%'
            AND T2."GroupName" NOT LIKE '%Export%'
            AND T2."GroupName" NOT LIKE '%Others%'
            AND T2."GroupName" NOT LIKE '%Domestic Dogsee%'
        ''')
    elif channel == 'Offline HN':
        where_conditions.append('T2."GroupName" LIKE \'%Domestic HN%\'')
    elif channel == 'Offline Dogsee':
        where_conditions.append('T2."GroupName" LIKE \'%Domestic Dogsee%\'')
    elif channel == 'Export':
        where_conditions.append('T2."GroupName" LIKE \'%Export%\'')
    elif channel == 'Inter Transfer':
        where_conditions.append(
            'T1."CardCode" IN (\'C01186\', \'C03326\', \'C03324\',\'C03327\',\'C01072\',\'C01183\',\'C03177\')'
        )
    elif channel == 'Others':
        where_conditions.append('T2."GroupName" LIKE \'%Others%\'')
    return where_conditions


@frappe.whitelist()
def get_dashboard_summary(filters=None):
    """Get overall dashboard summary metrics from SAP HANA OINV table"""
    try:
        if isinstance(filters, str):
            filters = json.loads(filters)
        
        normalized = _normalize_filters(filters)
        
        # Get date ranges
        today = now_datetime().date()
        last_30_days = today - timedelta(days=30)
        
        # If no date range is provided, default to fiscal year
        if not normalized.get('start_date') and not normalized.get('end_date'):
            fy_start, fy_end = _get_fiscal_year_range(today)
            normalized['start_date'] = fy_start
            normalized['end_date'] = fy_end
        
        # Connect to SAP HANA
        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        
        try:
            # Build WHERE clause
            where_conditions = ['a."CANCELED" = \'N\'']
            params = []
            
            # Date filter
            if normalized.get('start_date') and normalized.get('end_date'):
                where_conditions.append('a."DocDate" BETWEEN ? AND ?')
                params.extend([normalized['start_date'], normalized['end_date']])
            elif normalized.get('start_date'):
                where_conditions.append('a."DocDate" >= ?')
                params.append(normalized['start_date'])
            elif normalized.get('end_date'):
                where_conditions.append('a."DocDate" <= ?')
                params.append(normalized['end_date'])
            
            # Transporter filter
            if normalized.get('transporter_name'):
                where_conditions.append('UPPER(TRIM(b."TrnspName")) = UPPER(?)')
                params.append(normalized['transporter_name'].strip())

            # Channel filter
            where_conditions = _append_channel_filter(where_conditions, normalized.get('channel'))
            
            where_clause = ' AND '.join(where_conditions)
            
            # Query for total invoices and POD metrics
            query = f"""
                SELECT
                    COUNT(DISTINCT a."DocEntry") as total_invoices,
                    COUNT(DISTINCT CASE WHEN b."TrnspName" IS NOT NULL AND b."TrnspName" != '' THEN a."DocEntry" END) as shipments_with_transporter,
                    COUNT(DISTINCT CASE WHEN {TRACKING_EXPR} != '' THEN a."DocEntry" END) as shipments_with_tracking,
                    COUNT(DISTINCT CASE WHEN {POD_LINK_EXPR} != '' THEN a."DocEntry" END) as with_pod_link,
                    COUNT(DISTINCT CASE WHEN {POD_LINK_EXPR} = '' AND NOT ({POD_NA_CHANNEL_COND}) THEN a."DocEntry" END) as without_pod_link,
                    COUNT(DISTINCT CASE WHEN {POD_DATE_EXPR} != '' THEN a."DocEntry" END) as with_pod_date,
                    COUNT(DISTINCT CASE WHEN {POD_DATE_EXPR} = '' AND NOT ({POD_NA_CHANNEL_COND}) THEN a."DocEntry" END) as without_pod_date
                FROM {schema}."OINV" a
                INNER JOIN {schema}."OCRD" T1 ON a."CardCode" = T1."CardCode"
                INNER JOIN {schema}."OCRG" T2 ON T2."GroupCode" = T1."GroupCode"
                INNER JOIN {schema}."OSHP" b ON a."TrnspCode" = b."TrnspCode"
                WHERE {where_clause}
            """
            
            cursor.execute(query, params)
            result = cursor.fetchone()
            
            total_invoices = result[0] or 0
            shipments_with_transporter = result[1] or 0
            shipments_with_tracking = result[2] or 0
            with_pod_link = result[3] or 0
            without_pod_link = result[4] or 0
            with_pod_date = result[5] or 0
            without_pod_date = result[6] or 0
            
            # Coverage rates use applicable totals (exclude non-POD channels from denominator)
            applicable_link_total = with_pod_link + without_pod_link
            applicable_date_total = with_pod_date + without_pod_date
            pod_link_rate = round((with_pod_link / applicable_link_total) * 100, 2) if applicable_link_total > 0 else 0
            pod_date_rate = round((with_pod_date / applicable_date_total) * 100, 2) if applicable_date_total > 0 else 0
            
            # Get transporter breakdown
            transporter_query = f"""
                SELECT 
                    b."TrnspName" as transporter_name,
                    COUNT(DISTINCT a."DocEntry") as shipment_count
                FROM {schema}."OINV" a
                INNER JOIN {schema}."OCRD" T1 ON a."CardCode" = T1."CardCode"
                INNER JOIN {schema}."OCRG" T2 ON T2."GroupCode" = T1."GroupCode"
                INNER JOIN {schema}."OSHP" b ON a."TrnspCode" = b."TrnspCode"
                WHERE {where_clause}
                    AND b."TrnspName" IS NOT NULL 
                    AND b."TrnspName" != ''
                GROUP BY b."TrnspName"
                ORDER BY shipment_count DESC
            """
            
            cursor.execute(transporter_query, params)
            transporter_results = cursor.fetchall()
            
            transporter_breakdown = {}
            for row in transporter_results:
                transporter_breakdown[row[0]] = row[1]

            # Get missing POD link counts by transporter (exclude non-applicable channels)
            missing_pod_link_query = f"""
                SELECT
                    b."TrnspName" as transporter_name,
                    COUNT(DISTINCT a."DocEntry") as without_pod_link
                FROM {schema}."OINV" a
                INNER JOIN {schema}."OCRD" T1 ON a."CardCode" = T1."CardCode"
                INNER JOIN {schema}."OCRG" T2 ON T2."GroupCode" = T1."GroupCode"
                INNER JOIN {schema}."OSHP" b ON a."TrnspCode" = b."TrnspCode"
                WHERE {where_clause}
                    AND {POD_LINK_EXPR} = ''
                    AND NOT ({POD_NA_CHANNEL_COND})
                GROUP BY b."TrnspName"
                ORDER BY without_pod_link DESC
            """

            cursor.execute(missing_pod_link_query, params)
            missing_pod_link_results = cursor.fetchall()

            missing_pod_link_by_transporter = {}
            for row in missing_pod_link_results:
                missing_pod_link_by_transporter[row[0]] = row[1]
            
            # Get shipments for last 30 days
            filters_30d = where_conditions.copy()
            filters_30d.append('a."DocDate" >= ?')
            params_30d = params.copy()
            params_30d.append(last_30_days)
            where_clause_30d = ' AND '.join(filters_30d)
            
            query_30d = f"""
                SELECT COUNT(DISTINCT a."DocEntry") as total_invoices
                FROM {schema}."OINV" a
                INNER JOIN {schema}."OCRD" T1 ON a."CardCode" = T1."CardCode"
                INNER JOIN {schema}."OCRG" T2 ON T2."GroupCode" = T1."GroupCode"
                INNER JOIN {schema}."OSHP" b ON a."TrnspCode" = b."TrnspCode"
                WHERE {where_clause_30d}
            """
            
            cursor.execute(query_30d, params_30d)
            result_30d = cursor.fetchone()
            total_invoices_30d = result_30d[0] or 0
            
            # Get shipments today
            filters_today = where_conditions.copy()
            filters_today.append('a."DocDate" >= ?')
            params_today = params.copy()
            params_today.append(today)
            where_clause_today = ' AND '.join(filters_today)
            
            query_today = f"""
                SELECT COUNT(DISTINCT a."DocEntry") as total_invoices
                FROM {schema}."OINV" a
                INNER JOIN {schema}."OCRD" T1 ON a."CardCode" = T1."CardCode"
                INNER JOIN {schema}."OCRG" T2 ON T2."GroupCode" = T1."GroupCode"
                INNER JOIN {schema}."OSHP" b ON a."TrnspCode" = b."TrnspCode"
                WHERE {where_clause_today}
            """
            
            cursor.execute(query_today, params_today)
            result_today = cursor.fetchone()
            total_invoices_today = result_today[0] or 0
            
            # Determine date range label
            if normalized.get('start_date') and normalized.get('end_date'):
                date_range_label = f"{normalized['start_date']} to {normalized['end_date']}"
            elif normalized.get('start_date'):
                date_range_label = f"From {normalized['start_date']}"
            elif normalized.get('end_date'):
                date_range_label = f"Until {normalized['end_date']}"
            else:
                date_range_label = f"Fiscal Year ({normalized.get('start_date')} to {normalized.get('end_date')})"
            
            return {
                'metrics': {
                    'total_invoices': {
                        'in_range': total_invoices,
                        'date_range_label': date_range_label,
                        'start_date': str(normalized.get('start_date')),
                        'end_date': str(normalized.get('end_date')),
                        'last_30_days': total_invoices_30d,
                        'today': total_invoices_today
                    },
                    'pod_link': {
                        'with_link': with_pod_link,
                        'without_link': without_pod_link,
                        'coverage_rate': pod_link_rate
                    },
                    'pod_date': {
                        'with_date': with_pod_date,
                        'without_date': without_pod_date,
                        'coverage_rate': pod_date_rate
                    },
                    'transporter_breakdown': transporter_breakdown,
                    'missing_pod_link_by_transporter': missing_pod_link_by_transporter,
                    'tracking_coverage': {
                        'with_tracking': shipments_with_tracking,
                        'without_tracking': total_invoices - shipments_with_tracking,
                        'coverage_rate': round((shipments_with_tracking / total_invoices * 100), 2) if total_invoices > 0 else 0
                    }
                }
            }
        finally:
            connector.close_hana_connection(connection, cursor)
            
    except Exception as e:
        frappe.log_error(f"Error in get_dashboard_summary: {str(e)}", "Logistics Dashboard")
        import traceback
        frappe.log_error(traceback.format_exc(), "Logistics Dashboard Traceback")
        return {'error': str(e)}


@frappe.whitelist()
def get_shipments_data(filters=None, page=1, page_size=50):
    """Get paginated shipments data from SAP HANA OINV table"""
    try:
        if filters is None:
            filters = {}
        elif isinstance(filters, str):
            try:
                filters = json.loads(filters)
            except:
                filters = {}
        
        if not isinstance(filters, dict):
            filters = {}
        
        normalized = _normalize_filters(filters)
        
        # If no date range is provided, default to fiscal year
        if not normalized.get('start_date') and not normalized.get('end_date'):
            today = now_datetime().date()
            fy_start, fy_end = _get_fiscal_year_range(today)
            normalized['start_date'] = fy_start
            normalized['end_date'] = fy_end
        
        # Connect to SAP HANA
        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        
        try:
            # Build WHERE clause
            where_conditions = ['a."CANCELED" = \'N\'']
            params = []
            
            # Date filter
            if normalized.get('start_date') and normalized.get('end_date'):
                where_conditions.append('a."DocDate" BETWEEN ? AND ?')
                params.extend([normalized['start_date'], normalized['end_date']])
            elif normalized.get('start_date'):
                where_conditions.append('a."DocDate" >= ?')
                params.append(normalized['start_date'])
            elif normalized.get('end_date'):
                where_conditions.append('a."DocDate" <= ?')
                params.append(normalized['end_date'])
            
            # Transporter filter
            if normalized.get('transporter_name'):
                where_conditions.append('UPPER(TRIM(b."TrnspName")) = UPPER(?)')
                params.append(normalized['transporter_name'].strip())
            
            # Channel filter
            where_conditions = _append_channel_filter(where_conditions, normalized.get('channel'))
            
            # POD status filter
            if normalized.get('pod_status'):
                if normalized['pod_status'] == 'Completed':
                    where_conditions.append(f'{POD_DATE_EXPR} != \'\'')
                elif normalized['pod_status'] == 'Pending':
                    where_conditions.append(f'{POD_DATE_EXPR} = \'\' AND NOT ({POD_NA_CHANNEL_COND})')

            # POD link filter
            if normalized.get('pod_link_status'):
                if normalized['pod_link_status'] == 'Available':
                    where_conditions.append(f'{POD_LINK_EXPR} != \'\'')
                elif normalized['pod_link_status'] == 'Missing':
                    where_conditions.append(f'{POD_LINK_EXPR} = \'\' AND NOT ({POD_NA_CHANNEL_COND})')

            # POD date filter (explicit)
            if normalized.get('pod_date_status'):
                if normalized['pod_date_status'] == 'Available':
                    where_conditions.append(f'{POD_DATE_EXPR} != \'\'')
                elif normalized['pod_date_status'] == 'Missing':
                    where_conditions.append(f'{POD_DATE_EXPR} = \'\' AND NOT ({POD_NA_CHANNEL_COND})')
            
            # Search filter
            search_term = normalized.get('search')
            if search_term:
                where_conditions.append('(a."DocNum" LIKE ? OR a."U_TrackingNo" LIKE ? OR a."CardCode" LIKE ? OR T1."CardName" LIKE ?)')
                search_pattern = f'%{search_term}%'
                params.extend([search_pattern, search_pattern, search_pattern, search_pattern])
            
            where_clause = ' AND '.join(where_conditions)
            
            # Calculate pagination
            start = (int(page) - 1) * int(page_size)
            
            # Query shipments with channel classification
            query = f"""
                SELECT 
                    a."DocEntry",
                    a."DocNum",
                    a."DocDate",
                    b."TrnspName" as transporter_name,
                    a."U_TrackingNo" as tracking_id,
                    a."CardCode" as customer_code,
                    T1."CardName" as customer_name,
                    CASE 
                        WHEN T1."CardCode" IN ('C00623','C01026','C02574','C03121','C03358','C03412','C03494','C03564',
                                               'C03575','C03579','C03586','C03596') THEN 'E-com B2C'
                        WHEN T2."GroupName" LIKE '%Domestic HN%' THEN 'Offline HN'
                        WHEN T2."GroupName" LIKE '%Export%' THEN 'Export'
                        WHEN T2."GroupName" LIKE '%Others' THEN 'Others'
                        WHEN T2."GroupName" LIKE '%Domestic Dogsee%' THEN 'Offline Dogsee'
                        WHEN T1."CardCode" IN ('C01186', 'C03326', 'C03324','C03327','C01072','C01183','C03177') THEN 'Inter Transfer'
                        ELSE 'E-com B2B' 
                    END AS channel,
                    CASE 
                        WHEN T1."CardCode" IN ('C00623','C01026','C02574','C03121','C03358','C03412','C03494','C03564',
                                               'C03575','C03579','C03586','C03596') THEN 'NA'
                        WHEN T2."GroupName" LIKE '%Export%' THEN 'NA'
                        WHEN T2."GroupName" LIKE '%Others' THEN 'NA'
                        ELSE a."U_Pod_Link"
                    END AS pod_link,
                    a."U_POD_DATE" as pod_date,
                    a."AtcEntry"
                FROM {schema}."OINV" a
                INNER JOIN {schema}."OCRD" T1 ON a."CardCode" = T1."CardCode"
                INNER JOIN {schema}."OCRG" T2 ON T2."GroupCode" = T1."GroupCode"
                INNER JOIN {schema}."OSHP" b ON a."TrnspCode" = b."TrnspCode"
                WHERE {where_clause}
                ORDER BY a."DocDate" DESC, a."DocNum" DESC
                LIMIT ? OFFSET ?
            """
            
            params.extend([int(page_size), start])
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            # Format results
            shipments = []
            for row in results:
                pod_status = 'Completed' if row[9] and str(row[9]).strip() != '' else 'Pending'
                shipments.append({
                    'docentry': row[0],
                    'docnum': row[1],
                    'docdate': str(row[2]) if row[2] else None,
                    'transporter_name': row[3] or '',
                    'tracking_id': row[4] or '',
                    'customer_code': row[5] or '',
                    'customer_name': row[6] or '',
                    'channel': row[7] or '',
                    'pod_link': row[8] or '',
                    'pod_date': str(row[9]) if row[9] else None,
                    'pod_status': pod_status,
                    'atcentry': row[10] or ''
                })
            
            # Get total count
            count_query = f"""
                SELECT COUNT(DISTINCT a."DocEntry")
                FROM {schema}."OINV" a
                INNER JOIN {schema}."OCRD" T1 ON a."CardCode" = T1."CardCode"
                INNER JOIN {schema}."OCRG" T2 ON T2."GroupCode" = T1."GroupCode"
                INNER JOIN {schema}."OSHP" b ON a."TrnspCode" = b."TrnspCode"
                WHERE {where_clause}
            """
            
            # Remove LIMIT and OFFSET from params for count
            count_params = params[:-2]
            cursor.execute(count_query, count_params)
            total_count = cursor.fetchone()[0] or 0
            
            return {
                'shipments': shipments,
                'total_count': total_count,
                'page': int(page),
                'page_size': int(page_size),
                'has_more': start + len(shipments) < total_count
            }
        finally:
            connector.close_hana_connection(connection, cursor)
            
    except Exception as e:
        frappe.log_error(f"Error in get_shipments_data: {str(e)}", "Logistics Dashboard")
        import traceback
        frappe.log_error(traceback.format_exc(), "Logistics Dashboard Traceback")
        return {'error': str(e)}


def _disable_ssl_verification():
    """Disable SSL verification for outbound requests (per deployment needs)."""
    os.environ["PYTHONHTTPSVERIFY"] = "0"
    try:
        ssl._create_default_https_context = ssl._create_unverified_context
    except Exception:
        pass
    try:
        urllib3.disable_warnings()
    except Exception:
        pass


@frappe.whitelist()
def get_transporter_analytics(filters=None):
    """Get comprehensive transporter-wise analytics from SAP HANA"""
    try:
        if isinstance(filters, str):
            filters = json.loads(filters)
        
        normalized = _normalize_filters(filters)
        
        # If no date range is provided, default to fiscal year
        if not normalized.get('start_date') and not normalized.get('end_date'):
            today = now_datetime().date()
            fy_start, fy_end = _get_fiscal_year_range(today)
            normalized['start_date'] = fy_start
            normalized['end_date'] = fy_end
        
        # Connect to SAP HANA
        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        
        try:
            # Build WHERE clause
            where_conditions = ['a."CANCELED" = \'N\'']
            params = []
            
            # Date filter
            if normalized.get('start_date') and normalized.get('end_date'):
                where_conditions.append('a."DocDate" BETWEEN ? AND ?')
                params.extend([normalized['start_date'], normalized['end_date']])
            elif normalized.get('start_date'):
                where_conditions.append('a."DocDate" >= ?')
                params.append(normalized['start_date'])
            elif normalized.get('end_date'):
                where_conditions.append('a."DocDate" <= ?')
                params.append(normalized['end_date'])
            
            where_conditions = _append_channel_filter(where_conditions, normalized.get('channel'))
            where_clause = ' AND '.join(where_conditions)
            
            # Query transporter analytics (missing counts exclude non-applicable channels)
            query = f"""
                SELECT
                    b."TrnspName" as transporter_name,
                    COUNT(DISTINCT a."DocEntry") as total_shipments,
                    COUNT(DISTINCT CASE WHEN {POD_LINK_EXPR} != '' THEN a."DocEntry" END) as with_pod_link,
                    COUNT(DISTINCT CASE WHEN {POD_LINK_EXPR} = '' AND NOT ({POD_NA_CHANNEL_COND}) THEN a."DocEntry" END) as without_pod_link,
                    COUNT(DISTINCT CASE WHEN {POD_DATE_EXPR} != '' THEN a."DocEntry" END) as with_pod_date,
                    COUNT(DISTINCT CASE WHEN {POD_DATE_EXPR} = '' AND NOT ({POD_NA_CHANNEL_COND}) THEN a."DocEntry" END) as without_pod_date,
                    COUNT(DISTINCT CASE WHEN {TRACKING_EXPR} != '' THEN a."DocEntry" END) as with_tracking
                FROM {schema}."OINV" a
                INNER JOIN {schema}."OCRD" T1 ON a."CardCode" = T1."CardCode"
                INNER JOIN {schema}."OCRG" T2 ON T2."GroupCode" = T1."GroupCode"
                INNER JOIN {schema}."OSHP" b ON a."TrnspCode" = b."TrnspCode"
                WHERE {where_clause}
                    AND b."TrnspName" IS NOT NULL
                    AND b."TrnspName" != ''
                GROUP BY b."TrnspName"
                ORDER BY total_shipments DESC
            """
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            transporter_analytics = []
            for row in results:
                total = row[1] or 0
                with_pod_link = row[2] or 0
                without_pod_link = row[3] or 0
                with_pod_date = row[4] or 0
                without_pod_date = row[5] or 0
                with_tracking = row[6] or 0

                applicable_link = with_pod_link + without_pod_link
                applicable_date = with_pod_date + without_pod_date
                pod_link_rate = round((with_pod_link / applicable_link * 100), 2) if applicable_link > 0 else 0
                pod_date_rate = round((with_pod_date / applicable_date * 100), 2) if applicable_date > 0 else 0

                transporter_analytics.append({
                    'transporter_name': row[0],
                    'total_shipments': total,
                    'with_pod_link': with_pod_link,
                    'without_pod_link': without_pod_link,
                    'with_pod_date': with_pod_date,
                    'without_pod_date': without_pod_date,
                    'with_tracking': with_tracking,
                    'pod_link_rate': pod_link_rate,
                    'pod_date_rate': pod_date_rate
                })
            
            return {
                'transporters': transporter_analytics
            }
        finally:
            connector.close_hana_connection(connection, cursor)
            
    except Exception as e:
        frappe.log_error(f"Error in get_transporter_analytics: {str(e)}", "Logistics Dashboard")
        import traceback
        frappe.log_error(traceback.format_exc(), "Logistics Dashboard Traceback")
        return {'error': str(e)}


@frappe.whitelist()
def get_chart_data(filters=None, chart_type='shipments', days=30):
    """Get chart data for visualization from SAP HANA"""
    try:
        if isinstance(filters, str):
            filters = json.loads(filters)
        
        normalized = _normalize_filters(filters)
        
        # Default to fiscal year if no date range specified
        if not normalized.get('start_date') and not normalized.get('end_date'):
            fy_start, fy_end = _get_fiscal_year_range(now_datetime().date())
            normalized['start_date'] = fy_start
            normalized['end_date'] = fy_end
        elif not normalized.get('end_date'):
            normalized['end_date'] = now_datetime().date()
        elif not normalized.get('start_date'):
            normalized['start_date'] = normalized['end_date'] - timedelta(days=int(days))
        
        # Connect to SAP HANA
        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        
        try:
            if chart_type == 'shipments':
                # Shipment volume over time (daily for short ranges, monthly for long)
                labels = []
                pod_completed = []
                pod_pending = []
                total = []

                start_date = normalized['start_date']
                end_date = normalized['end_date']
                date_span = (end_date - start_date).days

                base_conditions = ['a."CANCELED" = \'N\'']
                base_params = []

                if normalized.get('transporter_name'):
                    base_conditions.append('UPPER(TRIM(b."TrnspName")) = UPPER(?)')
                    base_params.append(normalized['transporter_name'].strip())

                base_conditions = _append_channel_filter(base_conditions, normalized.get('channel'))

                if date_span > 60:
                    # Aggregate by month for large ranges
                    where_clause = ' AND '.join(base_conditions + ['a."DocDate" BETWEEN ? AND ?'])
                    query = f"""
                        SELECT
                            TO_VARCHAR(a."DocDate", 'YYYY-MM') as period,
                            COUNT(DISTINCT a."DocEntry") as total,
                            COUNT(DISTINCT CASE WHEN {POD_DATE_EXPR} != '' THEN a."DocEntry" END) as pod_completed,
                            COUNT(DISTINCT CASE WHEN {POD_DATE_EXPR} = '' THEN a."DocEntry" END) as pod_pending
                        FROM {schema}."OINV" a
                        INNER JOIN {schema}."OCRD" T1 ON a."CardCode" = T1."CardCode"
                        INNER JOIN {schema}."OCRG" T2 ON T2."GroupCode" = T1."GroupCode"
                        INNER JOIN {schema}."OSHP" b ON a."TrnspCode" = b."TrnspCode"
                        WHERE {where_clause}
                        GROUP BY TO_VARCHAR(a."DocDate", 'YYYY-MM')
                        ORDER BY period
                    """
                    cursor.execute(query, base_params + [start_date, end_date])
                    rows = cursor.fetchall()
                    for row in rows:
                        labels.append(row[0])
                        total.append(row[1] or 0)
                        pod_completed.append(row[2] or 0)
                        pod_pending.append(row[3] or 0)
                else:
                    # Daily aggregation for short ranges
                    current_date = start_date
                    while current_date <= end_date:
                        labels.append(current_date.strftime('%Y-%m-%d'))
                        where_clause = ' AND '.join(base_conditions + ['a."DocDate" = ?'])
                        query = f"""
                            SELECT 
                                COUNT(DISTINCT a."DocEntry") as total,
                                COUNT(DISTINCT CASE WHEN {POD_DATE_EXPR} != '' THEN a."DocEntry" END) as pod_completed,
                                COUNT(DISTINCT CASE WHEN {POD_DATE_EXPR} = '' THEN a."DocEntry" END) as pod_pending
                            FROM {schema}."OINV" a
                            INNER JOIN {schema}."OCRD" T1 ON a."CardCode" = T1."CardCode"
                            INNER JOIN {schema}."OCRG" T2 ON T2."GroupCode" = T1."GroupCode"
                            INNER JOIN {schema}."OSHP" b ON a."TrnspCode" = b."TrnspCode"
                            WHERE {where_clause}
                        """

                        cursor.execute(query, base_params + [current_date])
                        result = cursor.fetchone()

                        total.append(result[0] or 0)
                        pod_completed.append(result[1] or 0)
                        pod_pending.append(result[2] or 0)
                        current_date += timedelta(days=1)

                return {
                    'labels': labels,
                    'datasets': {
                        'total': total,
                        'pod_completed': pod_completed,
                        'pod_pending': pod_pending
                    }
                }
            
            elif chart_type == 'transporters':
                # Transporter performance
                transporter_data = get_transporter_analytics(filters)
                transporters = transporter_data.get('transporters', [])

                labels = [t['transporter_name'] for t in transporters]
                shipments = [t['total_shipments'] for t in transporters]
                pod_rates = [t['pod_link_rate'] for t in transporters]

                return {
                    'labels': labels,
                    'datasets': {
                        'shipments': shipments,
                        'pod_rates': pod_rates
                    }
                }

            elif chart_type == 'pod_status':
                # POD link distribution
                where_conditions = ['a."CANCELED" = \'N\'']
                params = []

                if normalized.get('transporter_name'):
                    where_conditions.append('UPPER(TRIM(b."TrnspName")) = UPPER(?)')
                    params.append(normalized['transporter_name'].strip())

                where_conditions = _append_channel_filter(where_conditions, normalized.get('channel'))
                where_clause = ' AND '.join(where_conditions)

                pod_case = f"""
                    CASE
                        WHEN {POD_LINK_EXPR} != '' THEN 'Link Available'
                        ELSE 'Link Missing'
                    END
                """

                query = f"""
                    SELECT
                        {pod_case} AS pod_status,
                        COUNT(DISTINCT a."DocEntry") as count
                    FROM {schema}."OINV" a
                    INNER JOIN {schema}."OCRD" T1 ON a."CardCode" = T1."CardCode"
                    INNER JOIN {schema}."OCRG" T2 ON T2."GroupCode" = T1."GroupCode"
                    INNER JOIN {schema}."OSHP" b ON a."TrnspCode" = b."TrnspCode"
                    WHERE {where_clause}
                        AND a."DocDate" BETWEEN ? AND ?
                    GROUP BY {pod_case}
                """

                params = params + [normalized['start_date'], normalized['end_date']]
                cursor.execute(query, params)
                results = cursor.fetchall()

                labels = []
                values = []
                for row in results:
                    labels.append(row[0] or 'Unknown')
                    values.append(row[1] or 0)

                return {
                    'labels': labels,
                    'values': values
                }

            else:
                return {'error': f'Unknown chart type: {chart_type}'}
        finally:
            connector.close_hana_connection(connection, cursor)
    
    except Exception as e:
        frappe.log_error(f"Error in get_chart_data: {str(e)}", "Logistics Dashboard")
        import traceback
        frappe.log_error(traceback.format_exc(), "Logistics Dashboard Traceback")
        return {'error': str(e)}


@frappe.whitelist()
def export_dashboard_data(filters=None, format='csv', export_type='shipments'):
    """Export dashboard data from SAP HANA"""
    try:
        if isinstance(filters, str):
            filters = json.loads(filters)
        
        normalized = _normalize_filters(filters)
        
        # Default to fiscal year if no dates provided
        if not normalized.get('start_date') and not normalized.get('end_date'):
            fy_start, fy_end = _get_fiscal_year_range(now_datetime().date())
            normalized['start_date'] = fy_start
            normalized['end_date'] = fy_end

        # Connect to SAP HANA
        connector = SAPConnector()
        connection, cursor, schema = connector.get_hana_connection()
        
        try:
            if export_type == 'shipments':
                # Build WHERE clause
                where_conditions = ['a."CANCELED" = \'N\'']
                params = []
                
                # Date filter
                if normalized.get('start_date') and normalized.get('end_date'):
                    where_conditions.append('a."DocDate" BETWEEN ? AND ?')
                    params.extend([normalized['start_date'], normalized['end_date']])
                elif normalized.get('start_date'):
                    where_conditions.append('a."DocDate" >= ?')
                    params.append(normalized['start_date'])
                elif normalized.get('end_date'):
                    where_conditions.append('a."DocDate" <= ?')
                    params.append(normalized['end_date'])
                
                # Transporter filter
                if normalized.get('transporter_name'):
                    where_conditions.append('UPPER(TRIM(b."TrnspName")) = UPPER(?)')
                    params.append(normalized['transporter_name'].strip())

                # Channel filter
                where_conditions = _append_channel_filter(where_conditions, normalized.get('channel'))

                # POD status filter
                if normalized.get('pod_status'):
                    if normalized['pod_status'] == 'Completed':
                        where_conditions.append(f'{POD_DATE_EXPR} != \'\'')
                    elif normalized['pod_status'] == 'Pending':
                        where_conditions.append(f'{POD_DATE_EXPR} = \'\'')
                
                where_clause = ' AND '.join(where_conditions)
                
                # Query all shipments
                query = f"""
                    SELECT 
                        a."DocNum",
                        a."DocDate",
                        b."TrnspName" as transporter_name,
                        a."U_TrackingNo" as tracking_id,
                        a."CardCode" as customer_code,
                        T1."CardName" as customer_name,
                        CASE 
                            WHEN T1."CardCode" IN ('C00623','C01026','C02574','C03121','C03358','C03412','C03494','C03564',
                                                   'C03575','C03579','C03586','C03596') THEN 'E-com B2C'
                            WHEN T2."GroupName" LIKE '%Domestic HN%' THEN 'Offline HN'
                            WHEN T2."GroupName" LIKE '%Export%' THEN 'Export'
                            WHEN T2."GroupName" LIKE '%Others' THEN 'Others'
                            WHEN T2."GroupName" LIKE '%Domestic Dogsee%' THEN 'Offline Dogsee'
                            WHEN T1."CardCode" IN ('C01186', 'C03326', 'C03324','C03327','C01072','C01183','C03177') THEN 'Inter Transfer'
                            ELSE 'E-com B2B' 
                        END AS channel,
                        CASE 
                            WHEN T1."CardCode" IN ('C00623','C01026','C02574','C03121','C03358','C03412','C03494','C03564',
                                                   'C03575','C03579','C03586','C03596') THEN 'NA'
                            WHEN T2."GroupName" LIKE '%Export%' THEN 'NA'
                            WHEN T2."GroupName" LIKE '%Others' THEN 'NA'
                            ELSE a."U_Pod_Link"
                        END AS pod_link,
                        a."U_POD_DATE" as pod_date
                    FROM {schema}."OINV" a
                    INNER JOIN {schema}."OCRD" T1 ON a."CardCode" = T1."CardCode"
                    INNER JOIN {schema}."OCRG" T2 ON T2."GroupCode" = T1."GroupCode"
                    INNER JOIN {schema}."OSHP" b ON a."TrnspCode" = b."TrnspCode"
                    WHERE {where_clause}
                    ORDER BY a."DocDate" DESC, a."DocNum" DESC
                """
                
                cursor.execute(query, params)
                results = cursor.fetchall()
                
                # Convert to CSV format
                if format == 'csv':
                    import csv
                    import io
                    import os
                    from frappe.utils import get_site_path
                    
                    output = io.StringIO()
                    fieldnames = ['DocNum', 'DocDate', 'Transporter', 'Tracking ID', 'Customer Code', 
                                 'Customer Name', 'Channel', 'POD Link', 'POD Date']
                    writer = csv.DictWriter(output, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    for row in results:
                        pod_status = 'Completed' if row[8] and str(row[8]).strip() != '' else 'Pending'
                        writer.writerow({
                            'DocNum': row[0] or '',
                            'DocDate': str(row[1]) if row[1] else '',
                            'Transporter': row[2] or '',
                            'Tracking ID': row[3] or '',
                            'Customer Code': row[4] or '',
                            'Customer Name': row[5] or '',
                            'Channel': row[6] or '',
                            'POD Link': row[7] or '',
                            'POD Date': str(row[8]) if row[8] else ''
                        })
                    
                    csv_content = output.getvalue()
                    output.close()
                    
                    # Save to file
                    file_path = os.path.join(
                        get_site_path('private', 'files'),
                        f'logistics_shipments_export_{now_datetime().strftime("%Y%m%d_%H%M%S")}.csv'
                    )
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
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
        finally:
            connector.close_hana_connection(connection, cursor)
    
    except Exception as e:
        frappe.log_error(f"Error in export_dashboard_data: {str(e)}", "Logistics Dashboard")
        import traceback
        frappe.log_error(traceback.format_exc(), "Logistics Dashboard Traceback")
        return {
            'status': 'error',
            'error': str(e)
        }


def _enqueue_dashboard_job(method, **kwargs):
    """Enqueue a background job for dashboard-triggered actions."""
    job = frappe.enqueue(method, queue="long", timeout=1200, **kwargs)
    job_id = getattr(job, "id", None) or getattr(job, "job_id", None) or job
    return {"status": "queued", "job_id": job_id}


def _run_dsr_pod_sync_job():
    _disable_ssl_verification()
    from khanal_tech_integrations.utils.DSR_Logisticss.DSR_POD_INTEGRATION import process_dsr_emails
    return process_dsr_emails()


def _run_safexpress_pod_sync_job(days=20):
    _disable_ssl_verification()
    from khanal_tech_integrations.utils.safexpress2.pod_service import process_invoices_without_pod
    return process_invoices_without_pod(days=days)


def _run_pod_report_job(start_date=None, end_date=None):
    from khanal_tech_integrations.utils.repatch_pod import monthly_pod_pending_report
    return monthly_pod_pending_report(start_date=start_date, end_date=end_date)


@frappe.whitelist()
def trigger_pod_report(start_date=None, end_date=None):
    """Send the POD status report email for the selected date range as a background job."""
    try:
        return _enqueue_dashboard_job(
            "khanal_tech_integrations.api.logistics_dashboard._run_pod_report_job",
            start_date=start_date or None,
            end_date=end_date or None,
        )
    except Exception as e:
        frappe.log_error(f"Error in trigger_pod_report: {str(e)}", "Logistics Dashboard")
        return {"status": "error", "error": str(e)}


@frappe.whitelist()
def trigger_dsr_pod_sync():
    """Trigger DSR POD email processing as a background job."""
    try:
        return _enqueue_dashboard_job(
            "khanal_tech_integrations.api.logistics_dashboard._run_dsr_pod_sync_job"
        )
    except Exception as e:
        frappe.log_error(f"Error in trigger_dsr_pod_sync: {str(e)}", "Logistics Dashboard")
        return {"status": "error", "error": str(e)}


@frappe.whitelist()
def trigger_safexpress_pod_sync(days=20):
    """Trigger Safexpress POD processing for the last N days."""
    try:
        safe_days = int(days) if days is not None else 20
        safe_days = max(1, min(safe_days, 365))
        return _enqueue_dashboard_job(
            "khanal_tech_integrations.api.logistics_dashboard._run_safexpress_pod_sync_job",
            days=safe_days,
        )
    except Exception as e:
        frappe.log_error(f"Error in trigger_safexpress_pod_sync: {str(e)}", "Logistics Dashboard")
        return {"status": "error", "error": str(e)}
