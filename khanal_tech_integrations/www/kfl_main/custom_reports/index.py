import frappe
from frappe import _
import khanal_tech_integrations.utils.Dashboard_Reports.dashboard_custom_report_queries as dashboard_custom_report_queries
import json

def get_context(context):
    context.no_cache = True  # Prevent browser caching
    selected_report_name = frappe.form_dict.get("report_name")
    # Your report data logic here
    context.report_name = selected_report_name
    context.title = f"Report: {selected_report_name}"
    context.timestamp = frappe.utils.now()  # Add timestamp to prevent caching


    print(f"Report Name from form_dict: {selected_report_name}")
    # Fetch fresh report queries instead of using cached session data
    allowed_reports = dashboard_custom_report_queries.fetch_custom_reports_queries()
    print(f"Allowed Reports from fresh query: {allowed_reports}")
    names = [report['name'] for report in allowed_reports]
    report_names = [report['report_name'] for report in allowed_reports]
    print(f"Allowed Report Names: {names}")

    if selected_report_name not in names and selected_report_name not in report_names:
        frappe.throw(_("You do not have permission to access this report."), frappe.PermissionError)

    selected_report_display_name = next((r['report_display_name'] for r in allowed_reports if r['name'] == selected_report_name), None)
    if not selected_report_display_name:
        selected_report_display_name = next((r['report_display_name'] for r in allowed_reports if r['report_name'] == selected_report_name), None)
    context.report_display_name = selected_report_display_name or "Custom Report"
    # Select the template to render based on selected_report_name
    if selected_report_name == "sales_summary_report":
        context.template = "khanal_tech_integrations/www/kfl_main/custom_reports/sales_summary_report.html"
    else:
        context.template = "khanal_tech_integrations/www/kfl_main/custom_reports/generic_custom_report.html"

    print(f"Rendering template: {context.template}")
    # Render the selected template and return HTML
    html = frappe.render_template(context.template, context)

    # Write directly to response
    frappe.response["type"] = "page"
    frappe.response["response"] = html

    # Returning context won't matter — we're overriding rendering
    return context

def current_month_orders_data():
    print("Fetching current month orders count...")
    try:
        result = frappe.db.sql("""
            SELECT 
                COUNT(*) AS 'Total_Orders',
                COUNT(DISTINCT JSON_EXTRACT(sap_data_row, '$.CardName')) AS 'Num_Of_Customers',
                SUM(JSON_EXTRACT(sap_data_row, '$.PO_DocTotal')) AS 'Total_Amount',
                SUM(CASE
                    WHEN JSON_EXTRACT(sap_data_row, '$.Status') = 'Closed' THEN 1
                END) AS 'Closed_Orders',
                (COUNT(*) - SUM(CASE
                    WHEN JSON_EXTRACT(sap_data_row, '$.Status') = 'Closed' THEN 1
                END)) AS 'Open_Orders'
            FROM
                taball_custom_reports_data
            WHERE
                report_name = 'New_Orders_Last_30_Days'
            ;
        """, as_dict=True)

        data = result[0] if result else {}
        return data

    except Exception as e:
        print(f"Error fetching current month orders count: {e}")
        frappe.log_error(message=str(e), title="current_month_orders_count Error")
        return {"current_month_orders_count": 0}
    

def current_month_processed_milk_data():
    try:
        result = frappe.db.sql("""
            SELECT 
            JSON_UNQUOTE(JSON_EXTRACT(sap_data_row, '$.Plant Name')) AS 'Plant_Name',
            COUNT(DISTINCT JSON_EXTRACT(sap_data_row, '$.PostDate')) AS 'Num_Of_Days',
            ROUND(SUM(JSON_EXTRACT(sap_data_row, '$.Raw_Milk_Processed'))) AS 'Total_Milk_Processed'
        FROM
            taball_custom_reports_data
        WHERE
            report_name = 'Milk_Procured_last_30Days'
        GROUP BY JSON_EXTRACT(sap_data_row, '$.Plant Name');
        """, as_dict=True)
        return result if result else {}

    except Exception as e:
        frappe.log_error(message=str(e), title="current_month_processed_milk_data Error")
        return {"current_month_processed_milk_data": 0}
    

def current_month_not_delivered_data():    
    try:
        result = frappe.db.sql("""
            SELECT 
                COUNT(DISTINCT JSON_EXTRACT(sap_data_row, '$.Order_DocEntry')) AS 'Num_Of_Orders',
                COUNT(DISTINCT JSON_EXTRACT(sap_data_row, '$.CardName')) AS 'Num_Of_Uniq_Customers',
                COUNT(DISTINCT JSON_EXTRACT(sap_data_row, '$.ItemCode')) AS 'Num_Of_Uniq_Items',
                SUM(JSON_EXTRACT(sap_data_row, '$.Ordered_Quantity')) AS 'Total_Units'
            FROM
                taball_custom_reports_data
            WHERE
                report_name = 'Not_Delivered_Upcoming_Orders_ItemWise'
                    AND JSON_UNQUOTE(JSON_EXTRACT(sap_data_row, '$.DueDate')) < CURDATE()
        """, as_dict=True)
        data = result[0] if result else {}
        return data

    except Exception as e:
        frappe.log_error(message=str(e), title="current_month_not_delivered_data Error")
        return {"current_month_processed_milk_data": 0}    
    
def due_amount_data():    
    try:
        result = frappe.db.sql("""
            SELECT 
                COUNT(DISTINCT JSON_EXTRACT(sap_data_row, '$.DocEntry')) AS 'Num_Of_Orders',
                COUNT(DISTINCT JSON_EXTRACT(sap_data_row, '$.CardCode')) AS 'Num_Of_Uniq_Customers',
                SUM(JSON_EXTRACT(sap_data_row, '$.Due_Amount')) AS 'Total_Due_Amount'
            FROM
                taball_custom_reports_data
            WHERE
                report_name = 'Amount_Due_AR_Invoices'
        """, as_dict=True)
        data = result[0] if result else {}
        return data

    except Exception as e:
        frappe.log_error(message=str(e), title="due_amount_data Error")
        return {"due_amount_data": 0}        
    
def ordered_items_366_days_data():    
    try:
        result = frappe.db.sql("""
            SELECT 
                sap_data_row AS 'ordered_items_366_days_row'
            FROM
                taball_custom_reports_data
            WHERE
                report_name = 'Ordered_Items_Summary_366_Days'
            ;
        """, as_dict=True)
        return [json.loads(r['ordered_items_366_days_row']) for r in result]

    except Exception as e:
        frappe.log_error(message=str(e), title="ordered_items_366_days_row Error")
        return {"ordered_items_366_days_row": 0}
    
def procured_milk_per_warehouse_366_days_data():    
    try:
        result = frappe.db.sql("""
            SELECT 
                sap_data_row AS 'monthly_milk_procured_per_warehouse_last_366_days_row'
            FROM
                taball_custom_reports_data
            WHERE
                report_name = 'Monthly_Milk_Procured_per_WareHouse_per_Vendor'
                    AND STR_TO_DATE(JSON_UNQUOTE(JSON_EXTRACT(sap_data_row, '$.Procured_Month')),
                        '%Y-%d-%b') > DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
                        ;
        """, as_dict=True)
        return [json.loads(r['monthly_milk_procured_per_warehouse_last_366_days_row']) for r in result]

    except Exception as e:
        frappe.log_error(message=str(e), title="monthly_milk_procured_per_warehouse_last_366_days_row Error")
        return {"monthly_milk_procured_per_warehouse_last_366_days_row": 0}
    
def orders_summary_per_month_data():    
    try:
        result = frappe.db.sql("""
            SELECT sap_data_row AS 'orders_summary_per_month_data_row'
            FROM (SELECT 
                sap_data_row
            FROM
                taborders_report_data
            ORDER BY JSON_UNQUOTE(JSON_EXTRACT(sap_data_row, '$.Year-Month')) DESC
            LIMIT 15)sub
            ORDER BY JSON_UNQUOTE(JSON_EXTRACT(sap_data_row, '$.Year-Month')) ASC
            ;
        """, as_dict=True)
        return [json.loads(r['orders_summary_per_month_data_row']) for r in result]

    except Exception as e:
        frappe.log_error(message=str(e), title="orders_summary_per_month_data_row Error")
        return {"orders_summary_per_month_data_row": 0}    
    
def top_inventory_items_data():    
    try:
        result = frappe.db.sql("""
            SELECT 
                JSON_UNQUOTE(JSON_EXTRACT(sap_data_row, '$.ItemCode')) AS 'ItemCode',
                JSON_UNQUOTE(JSON_EXTRACT(sap_data_row, '$.ItemName')) AS 'ItemName',
                SUM(JSON_EXTRACT(sap_data_row, '$.total_onHand')) AS 'Sum_total_onHand'
            FROM
                taball_custom_reports_data
            WHERE
                report_name = 'Inventory_By_WareHouse'
            GROUP BY JSON_EXTRACT(sap_data_row, '$.ItemCode')
            ORDER BY SUM(JSON_EXTRACT(sap_data_row, '$.total_onHand')) DESC
            LIMIT 12;            ;
        """, as_dict=True)
        # return [json.loads(r) for r in result]
        return result
    

    except Exception as e:
        frappe.log_error(message=str(e), title="top_inventory_items_data Error")
        return {"top_inventory_items_data": 0}    