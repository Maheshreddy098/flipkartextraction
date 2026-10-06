import frappe
from frappe import _
from collections import OrderedDict

@frappe.whitelist()
def get_context(context=None):
    """
    Fetch paginated data from the Ware House Report doctype and pass it to the frontend.
    If called via API, return the data as JSON.
    """
    try:
        # Get pagination parameters
        page = int(frappe.form_dict.get("page", 1))
        page_size = int(frappe.form_dict.get("page_size", 10))  # Default to 10 records per page
        start = (page - 1) * page_size

        # Fetch paginated data from the ware house supply Report doctype
        santa_monica_data = frappe.db.sql("""
                    SELECT distinct
                    item_code, open_qty, line_total, whse_code, base_card
                    FROM `tabsanta_monica`
                    ORDER BY creation DESC
                    LIMIT %s OFFSET %s
                    """, (page_size, start), as_dict=True)

        # Check if there are more records
        total_records = frappe.db.count("santa_monica")  # Get total record count
        has_more = (start + page_size) < total_records

        # Log the query results for debugging
        frappe.log(f"Fetched {len(santa_monica_data)} records from santa_monica.")

        # If called via API, return the data as JSON
        if frappe.form_dict.get("is_api_call"):
            return {
                "santa_monica_data": santa_monica_data,
                "has_more": has_more,
                "total_records": total_records  # Include total record count in the response
            }

        # If called as a context function, set the data in the context
        if context is not None:
            context.santa_monica_data = santa_monica_data
            context.has_more = has_more
        return context

    except Exception as e:
        frappe.log_error(f"Error fetching Santa monica data: {str(e)}")
        if frappe.form_dict.get("is_api_call"):
            return {"error": str(e)}
        raise


##########################################################################################################


# This function fetches vendor reports based on the provided filters by harsha
@frappe.whitelist()
def fetch_warehouse_reports(filters=None):
    try:
        # Check if the user has the 'Vendor Manager' role
        user_roles = frappe.get_roles(frappe.session.user)
        if "Vendor Manager" not in user_roles:
            frappe.throw(_("You do not have permission to access this page."))

        # Parse filters if provided
        filters = filters or {}
        if isinstance(filters, str):
            filters = frappe.parse_json(filters)
            

        # Fetch filtered warehouse  reports
        santa_monica_data = frappe.get_all(
            "santa_monica",
            fields=["item_code", "open_qty", "line_total", "whse_code", "base_card"],        
            filters=filters
        )
        return santa_monica_data
    except Exception as e:
        frappe.log_error(message=str(e), title="Fetch Warehouse Reports Error")
        return []



##########################################################################################################


# This function fetches the total count of warehouse reports
@frappe.whitelist()
def fetch_warehouse_report_total_count():
        return frappe.db.count("santa_monica")


##########################################################################################################

# This function fetches the top 21 warehouse reports based on open quantity
@frappe.whitelist()
def fetch_warehouse_reports_top_21(filters=None):
    try:
        user_roles = frappe.get_roles(frappe.session.user)
        if "Vendor Manager" not in user_roles:
            frappe.throw(_("You do not have permission to access this page."))

        filters = filters or {}
        if isinstance(filters, str):
            filters = frappe.parse_json(filters)

        # Fetch more than needed to deduplicate later
        records = frappe.get_all(
            "santa_monica",
            fields=["item_code", "open_qty", "line_total", "whse_code", "base_card"],
            filters=filters,
            order_by="open_qty desc",
            limit_page_length=100  # Higher limit for deduplication
        )

        # Remove duplicates based on item_code
        unique_items = OrderedDict()
        for record in records:
            if record["item_code"] not in unique_items:
                unique_items[record["item_code"]] = record
            if len(unique_items) == 21:
                break

        return list(unique_items.values())

    except Exception as e:
        frappe.log_error(message=str(e), title="Fetch Warehouse Reports Error")
        return []
    


##########################################################################################################


# This function fetches the least 20 warehouse reports based on open quantity
@frappe.whitelist()
def fetch_warehouse_reports_least_20(filters=None):
    try:
        # Check if the user has the 'Vendor Manager' role
        user_roles = frappe.get_roles(frappe.session.user)
        if "Vendor Manager" not in user_roles:
            frappe.throw(_("You do not have permission to access this page."))

        # Parse filters if provided
        filters = filters or {}
        if isinstance(filters, str):
            filters = frappe.parse_json(filters)

        # Fetch filtered warehouse reports sorted by open_qty (low to high)
        santa_monica_data = frappe.get_all(
            "santa_monica",
            fields=["item_code", "open_qty", "line_total", "whse_code", "base_card"],
            filters=filters,
            order_by="open_qty asc",  # Sort in ascending order
            limit_page_length=40
        )
        return santa_monica_data

    except Exception as e:
        frappe.log_error(message=str(e), title="Fetch Warehouse Reports Error")
        return []
    

##########################################################################################################

# This function fetches a summary of warehouse reports, including per-item totals and grand totals
@frappe.whitelist()
def format_in_indian_currency(number):
    # Convert the number to a string
    number_str = str(int(number))  # Ensure it's an integer (removes decimals)
    
    # Split the number into the last 3 digits and the rest
    last_three = number_str[-3:]
    remaining = number_str[:-3]

    # Add commas after every two digits for the remaining part
    formatted_remaining = ",".join([remaining[i:i+2] for i in range(0, len(remaining), 2)])

    # Combine the parts with the last three digits
    if formatted_remaining:
        return formatted_remaining + "," + last_three
    else:
        return last_three

def fetch_warehouse_grand_total():
    try:
        result = frappe.db.sql("""            
            SELECT SUM(open_qty + line_total) as 'total'
            FROM `tabsanta_monica`;
        """, as_dict=True)

        # Get the total sum and ensure it's an integer (remove decimals)
        grand_total = result[0]["total"] if result and result[0]["total"] else 0
        
        # Format the grand total to Indian currency style
        formatted_grand_total = format_in_indian_currency(grand_total)

        return {"grand_total": formatted_grand_total+ " kg"}

    except Exception as e:
        frappe.log_error(message=str(e), title="Fetch Warehouse Grand Total Error")
        return {"grand_total": "₹0"}
