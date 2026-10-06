import frappe
import json
import decimal
from khanal_tech_integrations.utils.hana_connection_pool import HANAConnectionPool

def convert_decimals(obj):
    if isinstance(obj, list):
        return [convert_decimals(item) for item in obj]
    elif isinstance(obj, dict):
        return {
            key: str(value) if isinstance(value, decimal.Decimal) else convert_decimals(value)
            for key, value in obj.items()
        }
    else:
        return obj

def bulk_insert_customers(sap_data):
    """
    Inserts multiple customer records into the `order_report_data` DocType using bulk_insert for efficiency.
    :param sap_data: List of dictionaries containing customer data to insert.
    """
    # Prepare data for bulk insert
    insert_data = []
    frappe.db.truncate("orders_report_data")

    cleaned_data = convert_decimals(sap_data)

    # print(f"\n\n==========       cleaned_data::: {cleaned_data}      ==========       \n\n")    

    # Wrap each row in the `data` field (the only field in the table)
    for row in cleaned_data:
        # print(f"\n============= row::: {row}")  # Print each row to verify its content
        doc = frappe.get_doc({
            "doctype": "orders_report_data",
            "data": row
        })
        doc.insert(ignore_permissions=True)

    # Perform bulk insert: first argument is DocType name, second is the list of records (values)
    try:
        # print(f"Inserting {len(insert_data)} records into order_report_data...")
        # frappe.db.bulk_insert("order_report_data", insert_data, ignore_duplicates=True)
        # frappe.db.bulk_insert(
        #         "orders_report_data", ["data"], [json.dumps(item) for item in sap_data], ignore_duplicates=True)
        frappe.db.commit()  # Commit the transaction
        print(f"{len(sap_data)} records inserted successfully.")
    except Exception as e:
        frappe.log_error("Bulk Insert Error", str(e))
        print(f"Error during bulk insert: {str(e)}")
        raise

@frappe.whitelist()
def fetch_orders_report_data():
    try:
        # Create an instance of the connection pool

        orders_report_sql_row = frappe.get_all(
            "custom_report_queries",
            fields=["sql_statement"],
            filters={"report_name": "Orders_Summary_per _Month"},

        )
        conn = HANAConnectionPool().get_connection()
        print("Connection successful!")

        # Create a cursor to execute queries
        cursor = conn.cursor()

        # Example: query from B1 table
        cursor.execute(orders_report_sql_row[0]['sql_statement']) 

        # Fetch the column names
        columns = [desc[0] for desc in cursor.description]

        # Fetch the rows (tuples)
        rows = cursor.fetchall()

        # Convert rows to a list of dictionaries (mapping column names to row values)
        result_array = [dict(zip(columns, row)) for row in rows]

        # Print the result (as a list of dictionaries)
        print(result_array)

        # Perform bulk insert
        bulk_insert_customers(sap_data=result_array)

        # Close connection
        cursor.close()
        conn.close()

        frappe.log(f"Inserted records into order_report_data.")
        return f"Data fetched and inserted successfully. Total records: {len(result_array)}"

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
            fields=["sap_data_row"],
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


