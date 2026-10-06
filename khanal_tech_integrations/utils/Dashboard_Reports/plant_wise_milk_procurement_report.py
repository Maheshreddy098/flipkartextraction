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
def fetch_Milk_Procurement_data():
    try:
        # Check user permissions
        if not frappe.has_permission("Milk_Procurement", "write"):
            frappe.throw("Not permitted")

        # Authenticate with SAP
        session = AuthenticateSAPB1()
        doc_settings = frappe.get_doc('SAP Settings')
        base_url = doc_settings.sap_b1_url + "SQLQueries('Plant_wise_milk_procurement')/List"

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
            frappe.log_error("No data returned from SAP API", "Milk_Procurement")
            return "No data available from SAP."

        # Truncate the existing table
        frappe.db.truncate("Milk_Procurement")

        # Insert records
        successful_inserts = 0
        for item in all_data:
            try:
                doc = frappe.get_doc({
                     "doctype": "Milk_Procurement",
                        "plant_id": item.get("Plant ID"),
                        "doc_num": item.get("DocNum"),
                        "vendor_id": item.get("Vendor ID"),
                        "vendor_name": item.get("Vendor Name"),
                        "supplied_date": item.get("Supplied Date"),
                        "qty_ltr": item.get("Qty in Ltr"),
                        "snf": item.get("SNF"),
                        "fat": item.get("FAT"),
                        "unit_price": item.get("Unit Price"),
                        "ts_value": item.get("TS Value")                        
                    })
                doc.insert(ignore_permissions=True)
                successful_inserts += 1
            except Exception as insert_error:
                frappe.log_error(f"Insert Error for Item: {item.get('Supplied Date')}", str(insert_error))

        frappe.db.commit()

        frappe.log(f"Inserted {successful_inserts} records into Milk_Procurement.")
        return f"Data fetched and inserted successfully. Total records: {successful_inserts}"

    except Exception as e:
        frappe.log_error("Warehouse Report Error", str(e))
        return f"An error occurred while fetching data: {str(e)}"



        # bench --site mysite.somesh execute khanal_tech_integrations.utils.Dashboard_Reports.plant_wise_milk_procurement_report.fetch_Milk_Procurement_data