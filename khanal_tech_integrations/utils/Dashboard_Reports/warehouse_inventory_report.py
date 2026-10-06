import requests
import frappe
from frappe.model.document import Document
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1

headersList = {
    "Accept": "*/*",
    "Content-Type": "application/json",
    "User-Agent": "KhanalTech",
}

@frappe.whitelist()
def fetch_santa_monica_data():
    try:
        # Check user permissions
        if not frappe.has_permission("santa_monica", "write"):
            frappe.throw("Not permitted")

        # Authenticate with SAP
        session = AuthenticateSAPB1()
        doc_settings = frappe.get_doc('SAP Settings')
        base_url = doc_settings.sap_b1_url + "SQLQueries('SantaMaria_PCH1')/List"

        all_data = []
        skip = 0
        page_size = 20  # Can be 100, 200, depending on SAP limits

        while skip < 1000:  # Adjust the limit as needed
            req_url = f"{base_url}?$skip={skip}&$top={page_size}"
            response = session.request("POST", req_url, headers=headersList, verify=False)

            if response.status_code != 200:
                frappe.log_error("SAP API Failed", response.text)
                return f"Failed to fetch data from SAP. Status Code: {response.status_code}"
            page_data = response.json().get("value", [])
            if not page_data:
                break  # No more data

            all_data.extend(page_data)
            skip += page_size

        # Log fetched record count
        frappe.log(f"Fetched {len(all_data)} records from SAP API.")

        if not all_data:
            frappe.log_error("No data returned from SAP API", "santa_monica")
            return "No data available from SAP."

        # Truncate the existing table
        frappe.db.truncate("santa_monica")

        # Insert records
        successful_inserts = 0
        for item in all_data:
            try:
                doc = frappe.get_doc({
                    "doctype": "santa_monica",
                    "item_code": item.get("ItemCode"),
                    "open_qty": item.get("OpenQty"),
                    "line_total": item.get("LineTotal"),
                    "whse_code": item.get("WhsCode"),
                    "base_card": item.get("BaseCard")                        
                })
                doc.insert(ignore_permissions=True)
                successful_inserts += 1
            except Exception as insert_error:
                frappe.log_error(f"Insert Error for Item: {item.get('ItemCode')}", str(insert_error))

        frappe.db.commit()

        frappe.log(f"Inserted {successful_inserts} records into santa_monica.")
        return f"Data fetched and inserted successfully. Total records: {successful_inserts}"

    except Exception as e:
        frappe.log_error("Warehouse Report Error", str(e))
        return f"An error occurred while fetching data: {str(e)}"


        # bench --site mysite.somesh execute khanal_tech_integrations.utils.Dashboard_Reports.warehouse_inventory_report.fetch_santa_monica_data