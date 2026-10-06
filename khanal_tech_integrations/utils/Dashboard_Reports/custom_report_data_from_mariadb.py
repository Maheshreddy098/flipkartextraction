import frappe
from khanal_tech_integrations.utils import *
import khanal_tech_integrations.utils.Dashboard_Reports.dashboard_custom_report_queries as dashboard_custom_report_queries
from khanal_tech_integrations.utils.Dashboard_Reports.custom_report_data_from_sap import fetch_custom_report_data_from_sap

@frappe.whitelist()
def get_context(context=None):
    """
    Fetch paginated data from the Ware House Report doctype and pass it to the frontend.
    If called via API, return the data as JSON.
    """
    try:
        # Get pagination parameters
        selected_report_name = frappe.form_dict.get("report_name")
        # Fetch fresh report queries instead of using cached session data
        allowed_reports = dashboard_custom_report_queries.fetch_custom_reports_queries()
        matched_report_name = next((r['report_name'] for r in allowed_reports if r['name'] == selected_report_name), None)
        if not matched_report_name:
            matched_report_name = next((r['report_name'] for r in allowed_reports if r['report_name'] == selected_report_name), None)   
        
        if not matched_report_name:
            return "You do not have permission to access this report or it does not exist."
        
        data_table_name = frappe.db.get_value(
            "custom_report_queries",
            fieldname="data_table_name",
            filters={"report_name": matched_report_name},
            order_by="creation desc")

        if not data_table_name:
            raise ValueError(f"No data table found for report name: {selected_report_name}")

        if frappe.db.exists("DocType", {"name": data_table_name}):
            # Fetch paginated data from the ware house supply Report doctype
            if data_table_name == "all_custom_reports_data":
                custom_report_data_rows = frappe.get_all(
                    data_table_name,
                    fields=["sap_data_row", "creation"],
                    filters={"report_name": matched_report_name},
                    order_by="creation desc",
                )
                if len(custom_report_data_rows) == 0:
                    fetch_custom_report_data_from_sap(matched_report_name)
                    custom_report_data_rows = frappe.get_all(
                        data_table_name,
                        fields=["sap_data_row", "creation"],
                        filters={"report_name": matched_report_name},
                        order_by="creation desc",
                    )
            else:
                custom_report_data_rows = frappe.get_all(
                    data_table_name,
                    fields=["sap_data_row", "creation"],
                    order_by="creation desc"               
                    )
                if len(custom_report_data_rows) == 0:
                    print("\n\n ================ No DATA found, fetching from SAP...================= \n\n")
                    fetch_custom_report_data_from_sap(matched_report_name)
                    custom_report_data_rows = frappe.get_all(
                        data_table_name,
                        fields=["sap_data_row", "creation"],
                        order_by="creation desc"               
                        )
            
        else:
            frappe.log_error(f"DocType {data_table_name} does not exist")

        # If called as a context function, set the data in the context
        if frappe.form_dict.get("is_api_call"):
            last_fetched_time_from_sap = None
            if len(custom_report_data_rows) > 0:
                last_fetched_time_from_sap = custom_report_data_rows[0].get("creation")
            return {
                "custom_report_data_rows": custom_report_data_rows,
                "last_fetched_time_from_sap": last_fetched_time_from_sap
            }

        return context

    except Exception as e:
        frappe.log_error(f"Error fetching orders_report_data data: {str(e)}")
        if frappe.form_dict.get("is_api_call"):
            return {"error": str(e)}
        raise

