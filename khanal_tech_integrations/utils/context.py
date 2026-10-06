import frappe
import khanal_tech_integrations.utils.Dashboard_Reports.dashboard_custom_report_queries as dashboard_custom_report_queries

def get_session_custom_reports():
    # Always fetch fresh data instead of using cached session data
    data = dashboard_custom_report_queries.fetch_custom_reports_queries()
    return data
