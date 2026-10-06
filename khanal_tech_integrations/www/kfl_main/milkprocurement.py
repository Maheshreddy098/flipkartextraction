import frappe
from frappe import _
import datetime

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
        Milk_Procurement_data = frappe.get_all(
            "Milk_Procurement",
            fields=["plant_id", "doc_num", "vendor_name","vendor_id", "supplied_date", "qty_ltr","snf","fat", "unit_price", "ts_value"],
            order_by="creation desc",
            start=start,  # Start index for pagination
            page_length=page_size  # Number of records to fetch
        )

        # Check if there are more records
        total_records = frappe.db.count("Milk_Procurement")  # Get total record count
        has_more = (start + page_size) < total_records

        # Log the query results for debugging
        frappe.log(f"Fetched {len(Milk_Procurement_data)} records from Milk_Procurement.")

        # If called via API, return the data as JSON
        if frappe.form_dict.get("is_api_call"):
            return {
                "Milk_Procurement_data": Milk_Procurement_data,
                "has_more": has_more,
                "total_records": total_records  # Include total record count in the response
            }

        # If called as a context function, set the data in the context
        if context is not None:
            context.Milk_Procurement_data = Milk_Procurement_data
            context.has_more = has_more
        return context

    except Exception as e:
        frappe.log_error(f"Error fetching Milk Procurement data: {str(e)}")
        if frappe.form_dict.get("is_api_call"):
            return {"error": str(e)}
        raise



##########################################################################################################


# This function fetches the total count of Milk Procurement records
@frappe.whitelist()
def fetch_milk_procurement_report_total_count():
        return frappe.db.count("Milk_Procurement")  # Get total record count

@frappe.whitelist()
def fetch_total_milk_vendors():
    try:
        result = frappe.db.sql("""
            SELECT COUNT(DISTINCT vendor_id) AS milk_vendors_count
            FROM tabMilk_Procurement
        """, as_dict=True)

        count = result[0].milk_vendors_count if result and result[0].milk_vendors_count else 0

        return count

    except Exception as e:
        frappe.log_error(message=str(e), title="Fetch Milk Vendors Count Error")
        return {"milk_vendors_count": 0}

##########################################################################################################

# This function fetches MIlk Procurement reports based on the provided filters by harsha
@frappe.whitelist()
def fetch_Milk_Procurement_reports(filters=None):
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
        Milk_Procurement_data = frappe.get_all(
            "Milk_Procurement",
            fields=["plant_id", "doc_num", "vendor_name","vendor_id", "supplied_date", "qty_ltr","snf","fat", "unit_price", "ts_value"],                
            filters=filters
        )

         # Convert date to string
        for row in Milk_Procurement_data:
            if isinstance(row.get("supplied_date"), (datetime.date, datetime.datetime)):
                row["supplied_date"] = row["supplied_date"].strftime("%Y-%m-%d")

        return Milk_Procurement_data
    except Exception as e:
        frappe.log_error(message=str(e), title="Fetch Milk Procurement Reports Error")
        return []
    
##########################################################################################################

# This function fetches the total milk quantity based on filters
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

def fetch_total_milk_quantity():
    try:
        result = frappe.db.sql("""
            SELECT SUM(qty_ltr) AS total_qty
            FROM `tabMilk_Procurement`
        """, as_dict=True)

        total = result[0].total_qty if result and result[0].total_qty else 0
        
        # Format the total with Indian currency style
        formatted_total = format_in_indian_currency(total)

        return {"total_qty": formatted_total+ " Ltr"}

    except Exception as e:
        frappe.log_error(message=str(e), title="Fetch Total Milk Quantity Error")
        return {"total_qty": 0}
    



##########################################################################################################

# This function formats a total cost in Indian currency style
@frappe.whitelist()
def format_in_indian_currency(number):
    number_str = str(int(number))  # Ensure integer string
    if len(number_str) <= 3:
        return number_str

    # Last 3 digits
    last_three = number_str[-3:]
    remaining = number_str[:-3]

    # Reverse the remaining part to process from right to left
    reversed_remaining = remaining[::-1]

    # Group in twos
    grouped = [reversed_remaining[i:i+2][::-1] for i in range(0, len(reversed_remaining), 2)]

    # Re-reverse to correct order and join with commas
    formatted_remaining = ",".join(grouped[::-1])

    return formatted_remaining + "," + last_three


def fetch_total_cost():
    try:
        result = frappe.db.sql("""
            SELECT SUM(qty_ltr * unit_price) AS total_milk_cost
            FROM `tabMilk_Procurement`
        """, as_dict=True)

        total = result[0].total_milk_cost if result and result[0].total_milk_cost else 0
        
        # Format the total with Indian currency style
        formatted_total1 = format_in_indian_currency(total)

        return {"total_milk_cost": "₹  " + formatted_total1}

    except Exception as e:
        frappe.log_error(message=str(e), title="Fetch Total Milk Quantity Error")
        return {"total_milk_cost": "₹0"}
