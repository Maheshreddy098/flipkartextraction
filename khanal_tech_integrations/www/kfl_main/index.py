import frappe
import frappe.utils
from frappe.utils.dateutils import add_to_date
import khanal_tech_integrations.www.kfl_main.vendor as vendor
import khanal_tech_integrations.www.kfl_main.milkprocurement as milkprocurement
import khanal_tech_integrations.www.kfl_main.warehouse as warehouse
import khanal_tech_integrations.utils.Dashboard_Reports.dashboard_custom_report_queries as dashboard_custom_report_queries
import khanal_tech_integrations.www.kfl_main.custom_reports.index as custom_reports

# Set up logger
logger = frappe.logger("kfl_main")

def get_context(context):
    context.no_cache = True

    endDate = frappe.local.form_dict.get("endDate") or frappe.utils.nowdate()
    if endDate == "null?":
        endDate = frappe.utils.nowdate()

    startDate = frappe.local.form_dict.get("startDate") or add_to_date(endDate, days=-15)
    if startDate == "null":
        startDate = add_to_date(endDate, days=-15)

    default_query_result = get_data_userwise(startDate=startDate, endDate=endDate)

    # Set context variables
    context.my_variable = {
        "fetch_vendor_report_total_count": vendor.fetch_vendor_report_total_count()
    }
    context.vendor_data = vendor.fetch_vendor_reports()
    

    context.milk_procurement_count = {
        "fetch_milk_procurement_report_total_count": milkprocurement.fetch_milk_procurement_report_total_count()
    }
    context.milk_vendors_count = milkprocurement.fetch_total_milk_vendors()
    context.milk_procurement_data = milkprocurement.fetch_Milk_Procurement_reports()    
    context.milk_procurement_sum = milkprocurement.fetch_total_milk_quantity()    
    context.total_cost = milkprocurement.fetch_total_cost()
    context.current_month_orders_data = custom_reports.current_month_orders_data()
    context.current_month_processed_milk_data = custom_reports.current_month_processed_milk_data()
    context.current_month_not_delivered_data = custom_reports.current_month_not_delivered_data()
    context.due_amount_data = custom_reports.due_amount_data()
    context.ordered_items_366_days_data = custom_reports.ordered_items_366_days_data()
    context.procured_milk_per_warehouse_366_days_data = custom_reports.procured_milk_per_warehouse_366_days_data()
    context.orders_summary_per_month_data = custom_reports.orders_summary_per_month_data()
    context.top_inventory_items_data = custom_reports.top_inventory_items_data()

    context.warehouse_count = {
        "fetch_warehouse_report_total_count": warehouse.fetch_warehouse_report_total_count()
    }
    context.warehouse_data = warehouse.fetch_warehouse_reports()
    context.warehouse_sort = warehouse.fetch_warehouse_reports_top_21()
    context.warehouse_sort1 = warehouse.fetch_warehouse_reports_least_20()

    context.total_bread = warehouse.fetch_warehouse_grand_total()
   
  
     
    context.startDate = startDate
    context.endDate = endDate

    logger.info(f"Default Query Result: {default_query_result}")
    return context

def get_data_userwise(startDate=None, endDate=None):
    try:
        user_doc = frappe.get_doc("User", frappe.session.user)
        user_roles = [role.role for role in user_doc.roles]

        test_members = frappe.db.get_list(
            'Test_members',
            filters={"emp_email": user_doc.email},
            fields=['employee', 'emp_email']
        )

        # Safe debug logs
        logger = frappe.logger("kfl_main")
        logger.info(f"User: {user_doc.name}, Email: {user_doc.email}")
        logger.info(f"User Roles: {user_roles}")
        logger.info(f"Test Members: {test_members}")
        logger.info(f"Start Date: {startDate}, End Date: {endDate}")

        return []

    except Exception as e:
        frappe.logger("kfl_main").error(f"Error in get_data_userwise: {e}")
        return []
