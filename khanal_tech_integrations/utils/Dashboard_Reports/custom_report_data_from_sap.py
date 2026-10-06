import frappe
import json
import decimal
from khanal_tech_integrations.utils.hana_connection_pool import HANAConnectionPool
import khanal_tech_integrations.utils.Dashboard_Reports.dashboard_custom_report_queries as dashboard_custom_report_queries

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

def bulk_insert_customers(sap_data, data_table_name="all_custom_reports_data", report_name=None):
    """
    Inserts multiple customer records into the `order_report_data` DocType using bulk_insert for efficiency.
    :param sap_data: List of dictionaries containing customer data to insert.
    """
    # Prepare data for bulk insert
    insert_data = []
    if data_table_name == "all_custom_reports_data":
        frappe.db.delete("all_custom_reports_data", {"report_name": report_name})
    else:
        frappe.db.truncate(data_table_name)

    cleaned_data = convert_decimals(sap_data)

    # print(f"\n\n==========       cleaned_data::: {cleaned_data}      ==========       \n\n")    

    # Wrap each row in the `data` field (the only field in the table)
    for row in cleaned_data:
        # print(f"\n============= row::: {row}")  # Print each row to verify its content
        if data_table_name == "all_custom_reports_data":
            doc = frappe.get_doc({
                "doctype": data_table_name,
                "report_name": report_name,
                "sap_data_row": row
            })
        else:
            doc = frappe.get_doc({
                "doctype": data_table_name,
                "sap_data_row": row
            })
        doc.insert(ignore_permissions=True)

    #TODO:: Perform bulk insert: first argument is DocType name, second is the list of records (values)
    try:
        frappe.db.commit()  # Commit the transaction
        print(f"{len(sap_data)} records inserted successfully.")
    except Exception as e:
        frappe.log_error("Bulk Insert Error", str(e))
        print(f"Error during bulk insert: {str(e)}")
        raise

def fetch_custom_report_data_from_sap(report_name):
    try:
        # Create an instance of the connection pool

        custom_report_queries_sql_row = frappe.get_all(
            "custom_report_queries",
            fields=["sql_statement", "data_table_name"],
            filters={"report_name": report_name},

        )
        conn = HANAConnectionPool().get_connection()
        print("Connection successful!")

        # Create a cursor to execute queries
        cursor = conn.cursor()

        # Example: query from B1 table
        cursor.execute(custom_report_queries_sql_row[0]['sql_statement']) 

        # Fetch the column names
        columns = [desc[0] for desc in cursor.description]

        # Fetch the rows (tuples)
        rows = cursor.fetchall()

        # Convert rows to a list of dictionaries (mapping column names to row values)
        result_array = [dict(zip(columns, row)) for row in rows]

        # Print the result (as a list of dictionaries)
        print(result_array)

        # Perform bulk insert
        bulk_insert_customers(sap_data=result_array, data_table_name=custom_report_queries_sql_row[0]['data_table_name'], report_name=report_name)

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
    try:
        selected_report_name = frappe.form_dict.get("report_name").strip()
        # Fetch fresh report queries instead of using cached session data
        allowed_reports = dashboard_custom_report_queries.fetch_custom_reports_queries()
        matched_report_name = next((r['report_name'] for r in allowed_reports if r['name'] == selected_report_name), None)
        if not matched_report_name:
            matched_report_name = next((r['report_name'] for r in allowed_reports if r['report_name'] == selected_report_name), None)   

        if not matched_report_name:
            return "You do not have permission to access this report or it does not exist."

        fetch_message = fetch_custom_report_data_from_sap(matched_report_name)
        response_json_data = {"message": fetch_message}
        # If called via API, context will be None
        if context is None:
            return response_json_data
        # If called for page rendering, context is a dict
        context.response_json = response_json_data
        return context
    except Exception as e:
        frappe.log_error(f"Error fetching orders_report_data data: {str(e)}")
        if context is None or frappe.form_dict.get("is_api_call"):
            return {"error": str(e)}
        raise


