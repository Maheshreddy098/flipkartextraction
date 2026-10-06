import frappe
from frappe import _
import datetime

@frappe.whitelist()
def get_context(context=None):
    """
    Fetch paginated data from the Vendor Supply Report doctype and pass it to the frontend.
    If called via API, return the data as JSON.
    """
    print("Fetching Vendor Supply Report data...")
    try:
        # Get pagination parameters
        page = int(frappe.form_dict.get("page", 1))
        page_size = int(frappe.form_dict.get("page_size", 10))  # Default to 10 records per page
        start = (page - 1) * page_size

        # Fetch paginated data from the Vendor Supply Report doctype
        vendor_reports = frappe.get_all(
            "Vendor Supply Report",
            fields=["card_code","card_name","vendor_mobile_no","vendor_email","registered_date","days_supplied","total_quantity_supplied"],
            order_by="creation desc",
            start=start,  # Start index for pagination
            page_length=page_size  # Number of records to fetch
        )

        # Check if there are more records. 
        total_records = frappe.db.count("Vendor Supply Report")  # Get total record count
        has_more = (start + page_size) < total_records

        # Log the query results for debugging
        frappe.log(f"Fetched {len(vendor_reports)} records from Vendor Supply Report.")

        # If called via API, return the data as JSON
        if frappe.form_dict.get("is_api_call"):
            return {
                "vendor_reports": vendor_reports,
                "has_more": has_more,
                "total_records": total_records  # Include total record count in the response
            }

        print("Vendor Supply Report data fetched successfully.")
        print("Vendor Reports:", vendor_reports)
        # If called as a context function, set the data in the context
        if context is not None:
            context.vendor_reports = vendor_reports
            context.has_more = has_more
        return context

    except Exception as e:
        frappe.log_error(f"Error fetching Vendor Supply Report data: {str(e)}")
        if frappe.form_dict.get("is_api_call"):
            return {"error": str(e)}
        raise



# This function fetches vendor reports based on the provided filters by harsha
@frappe.whitelist()
def fetch_vendor_report_total_count():
        return frappe.db.count("Vendor Supply Report")  # Get total record count

# This function fetches vendor reports based on the provided filters by harsha
@frappe.whitelist()
def fetch_vendor_reports(filters=None):
    try:
        # Check if the user has the 'Vendor Manager' role
        user_roles = frappe.get_roles(frappe.session.user)
        if "Vendor Manager" not in user_roles:
            frappe.throw(_("You do not have permission to access this page."))

        # Parse filters if provided
        filters = filters or {}
        if isinstance(filters, str):
            filters = frappe.parse_json(filters)

        # Fetch filtered vendor reports
        vendor_reports = frappe.get_all(
            "Vendor Supply Report",
            fields=[
                "card_code", 
                "card_name", 
                "vendor_mobile_no", 
                "vendor_email", 
                "registered_date", 
                "days_supplied", 
                "total_quantity_supplied"
            ],
            filters=filters
        )
        # Convert date to string
        for row in vendor_reports:
            if isinstance(row.get("registered_date"), (datetime.date, datetime.datetime)):
                row["registered_date"] = row["registered_date"].strftime("%Y-%m-%d")
        return vendor_reports
    except Exception as e:
        frappe.log_error(message=str(e), title="Fetch Vendor Reports Error")
        return []

