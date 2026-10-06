import frappe
import json

@frappe.whitelist()
def fetch_custom_reports_queries():
    try:
        user_doc = frappe.get_doc("User", frappe.session.user)
        user_roles = [role.role for role in user_doc.roles]
        
        user_email = user_doc.email

        # Build LIKE conditions for roles
        role_conditions = []
        params = []
        admin_condition = " OR 1 = 1 " if frappe.session.user == "Administrator" else ""

        for role in user_roles:
            role_conditions.append("role_types LIKE %s")
            params.append(f"%{role}%")

        # Include email condition
        role_conditions.append("include_emails LIKE %s")
        params.append(f"%{user_email}%")

        # Combine OR conditions
        include_condition = " OR ".join(role_conditions)

        # Exclude email condition
        exclude_condition = "IFNULL(exclude_emails, '') NOT LIKE %s"
        params.append(f"%{user_email}%")

        # Final SQL query
        query = f"""
            SELECT category, COALESCE(report_display_name, report_name) AS 'report_display_name' , name, icon_color, report_name
            FROM `tabcustom_report_queries`
            WHERE ({include_condition})
            AND ({exclude_condition})
            {admin_condition}
            ORDER BY creation DESC
        """

        custom_report_data_rows = frappe.db.sql(query, params, as_dict=True)

        return custom_report_data_rows
    except Exception as e:
        frappe.log_error("Warehouse Report Error", str(e))
        return f"An error occurred while fetching data: {str(e)}"

@frappe.whitelist()
def get_context(context=None):
    """
    Fetch paginated data from the Ware House Report doctype and pass it to the frontend.
    If called via API, return the data as JSON.
    """
    try:
        # Get pagination parameters
        page = int(frappe.form_dict.get("page", 1))
        page_size = int(frappe.form_dict.get("page_size", 1000))  # Default to 1000 records per page
        start = (page - 1) * page_size

        # Fetch paginated data from the ware house supply Report doctype
        orders_report_data_rows = frappe.get_all(
            "orders_report_data",
            fields=["data"],
            order_by="creation desc",
            start=start,  # Start index for pagination
            page_length=page_size  # Number of records to fetch
        )

        # Check if there are more records
        total_records = frappe.db.count("orders_report_data")  # Get total record count
        has_more = (start + page_size) < total_records

        # Log the query results for debugging
        frappe.log(f"Fetched {len(orders_report_data_rows)} records from orders_report_data.")

        # If called via API, return the data as JSON
        if frappe.form_dict.get("is_api_call"):
            return {
                "orders_report_data_rows": orders_report_data_rows,
                "has_more": has_more,
                "total_records": total_records  # Include total record count in the response
            }

        # If called as a context function, set the data in the context
        if context is not None:
            context.orders_report_data_rows = orders_report_data_rows
            context.has_more = has_more
        return context

    except Exception as e:
        frappe.log_error(f"Error fetching orders_report_data data: {str(e)}")
        if frappe.form_dict.get("is_api_call"):
            return {"error": str(e)}
        raise


