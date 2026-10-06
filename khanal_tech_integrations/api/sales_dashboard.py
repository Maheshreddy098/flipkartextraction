from datetime import datetime
import frappe
from frappe import _

from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
from khanal_tech_integrations.utils.Report.Ar_invoice import invoice_total
from khanal_tech_integrations.utils.Report.Ar_CreditNote import credit_note_total
from khanal_tech_integrations.utils.Finance.AgeingReport import (
    ttReceipt_List,
    ttJournalEntry_List,
    ttBalance_Report,
)

headersList = {
        "Accept": "*/*",
        "User-Agent": "Khanal Tech",
        "Content-Type": "application/json",
        "Prefer": "odata.maxpagesize=100",
    }

# khanal_tech_integrations.api.sales_dashboard.sales_order_count
@frappe.whitelist()
# def sales_order_count(from_date=None, to_date=None):
def sales_order_count(from_date=None, to_date=None):
    session = AuthenticateSAPB1()
    
    payload = ''
    if from_date:
        from_date = datetime.strptime(from_date, '%Y-%m-%d')
    else:
        from_date = datetime.now().replace(day=1)
    
    if to_date:
        to_date = datetime.strptime(to_date, '%Y-%m-%d')
    else:
        to_date = datetime.now()
        
    reqUrl = frappe.get_doc('SAP Settings').sap_b1_url + f"Orders/$count?$filter=DocDate ge '{from_date}' and DocDate le '{to_date}' and Cancelled eq 'tNO'"
    response = session.request("GET", reqUrl, data=payload, headers=headersList, verify=False)
    sales_order_count = response.json()
    print(sales_order_count)
    return {
	        "value": sales_order_count,
	        "fieldtype": "Float",
	        # "route_options": {"from_date": "2023-05-23"},
	        # "route": ["query-report", "Permitted Documents For User"]
            }

@frappe.whitelist()
def open_sales_order(from_date=None, to_date=None):
    session = AuthenticateSAPB1()
    payload = ''
    if from_date:
        from_date = datetime.strptime(from_date, '%Y-%m-%d')
    else:
        from_date = datetime.now().replace(day=1)
    
    if to_date:
        to_date = datetime.strptime(to_date, '%Y-%m-%d')
    else:
        to_date = datetime.now()

    payload = ''
    
    reqUrl = frappe.get_doc('SAP Settings').sap_b1_url + f"Orders/$count?$filter=DocDate ge '{from_date}' and DocDate le '{to_date}' and Cancelled eq 'tNO' and DocumentStatus eq 'bost_Open'"
    response = session.request("GET", reqUrl, data=payload, headers=headersList, verify=False)
    open_sales_order = response.json()
    # print(open_sales_order)
    return {
            "value": open_sales_order,
            "fieldtype": "Float",
            # "route_options": {"from_date": "2023-05-23"},
            # "route": ["query-report", "Permitted Documents For User"]
            }

@frappe.whitelist()
def total_sales_order(from_date=None, to_date=None):
    session = AuthenticateSAPB1()
    if from_date:
        from_date = datetime.strptime(from_date, '%Y-%m-%d')
    else:
        from_date = datetime.now().replace(day=1)
    
    if to_date:
        to_date = datetime.strptime(to_date, '%Y-%m-%d')
    else:
        to_date = datetime.now()

    headersList["Prefer"] = "odata.maxpagesize=3000"

    payload = ''
    reqUrl = frappe.get_doc('SAP Settings').sap_b1_url + f"Orders?$select=DocTotal&$filter=DocDate ge '{from_date}' and DocDate le '{to_date}' and Cancelled eq 'tNO'"
    
    response = session.request("GET", reqUrl, data=payload, headers=headersList, verify=False)
    total_sales_order = response.json()
    # print(total_sales_order)
    # total = [ total_sales_order['value'][i]['DocTotal'] for i in range(len(total_sales_order['value']))]
    total = sum(item["DocTotal"] for item in total_sales_order["value"])
    # print (total)
    return {
            "value": total,
            "fieldtype": "Currency",
            # "route_options": {"from_date": "2023-05-23"},
            # "route": ["query-report", "Permitted Documents For User"]
            }

@frappe.whitelist()
def total_sales_order_open(from_date=None, to_date=None):
    session = AuthenticateSAPB1()
    if from_date:
        from_date = datetime.strptime(from_date, '%Y-%m-%d')
    else:
        from_date = datetime.now().replace(day=1)

    if to_date:
        to_date = datetime.strptime(to_date, '%Y-%m-%d')
    else:
        to_date = datetime.now()

    headersList["Prefer"] = "odata.maxpagesize=3000"

    payload = ''
    reqUrl = frappe.get_doc('SAP Settings').sap_b1_url + f"Orders?$select=DocTotal&$filter=DocDate ge '{from_date}' and DocDate le '{to_date}' and Cancelled eq 'tNO' and DocumentStatus eq 'bost_Open'"

    response = session.request("GET", reqUrl, data=payload, headers=headersList, verify=False)
    total_sales_order = response.json()
    # print(total_sales_order)
    # total = [ total_sales_order['value'][i]['DocTotal'] for i in range(len(total_sales_order['value']))]
    total = sum(item["DocTotal"] for item in total_sales_order["value"])
    # print (total)
    return {
            "value": total,
            "fieldtype": "Currency",
            }



# bench --site dev.localhost execute  khanal_tech_integrations.api.sales_dashboard.prepare_sales_table
# Domestic E-com Customer
@frappe.whitelist()
def prepare_sales_table(cust_group="Export HN Customer", from_date="2024-01-01", to_date="2024-01-31"):
    # session = AuthenticateSAPB1()
    # headersList["Prefer"] = "odata.maxpagesize=3000"
    # payload = ''
    if from_date:
        from_date = datetime.strptime(from_date, "%Y-%m-%d")
    else:
        from_date = datetime.now().replace(day=1)

    if to_date:
        to_date = datetime.strptime(to_date, "%Y-%m-%d")
    else:
        to_date = datetime.now()

    customers_data = []
    customers = frappe.get_all(
        "Customer",
        filters={"customer_group": cust_group, "disabled": 0},
        # fields=["name", "custom_sap_customer_code", "custom_foreign_name","image"],
        fields=["name", "custom_sap_customer_code","image"],
    )
    print(len(customers),'customers')

    for customer in customers:
        customer_data = {}
        total_invoice = invoice_total(
            customer["custom_sap_customer_code"], from_date, to_date, "None"
        )
        # print(total_invoice,'total_invoice')

        customer_data["customer"] = customer["name"]
        customer_data["sap_customer_code"] = customer["custom_sap_customer_code"]
        # customer_data["foreign_name"] = customer["custom_foreign_name"]
        customer_data["foreign_name"] = ''
        customer_data["image"] = customer["image"]
        
        customer_data["total_invoice"] = total_invoice
        customer_data["opening_balance"] = ttBalance_Report(
            '2022-01-01', from_date, customer["custom_sap_customer_code"]
        )['TotalLC']

        customer_data["total_credit_note"] = credit_note_total(
            customer["custom_sap_customer_code"], from_date, to_date, "None"
        )
        customer_data["collections"] = ttReceipt_List(
            from_date, to_date, customer["custom_sap_customer_code"]
        )['TotalLC']
        customer_data["deductions"] = ttJournalEntry_List(
            from_date, to_date, customer["custom_sap_customer_code"]
        )['TotalLC']
        customer_data["closing_balance"] = ttBalance_Report(
            '2022-01-01', to_date, customer["custom_sap_customer_code"]
        )['TotalLC']
        customers_data.append(customer_data)

    # print(customers_data)

    # customers_data = sorted(customers_data, key=lambda x: float(x['closing_balance'] or 0))
    customers_data = sorted(customers_data, key=lambda x: float(x['closing_balance'] or 0), reverse=True)


    print(customers_data,'customers_data','\n\n')
  
    
    customers_with_zero_values = []
    customers_with_non_zero_values = []

    for customer in customers_data:
            # Check if all relevant fields have a value of '0'
            if all(float(customer[key]) == 0 for key in customer if key not in ['customer', 'sap_customer_code', 'foreign_name', 'image']):
                customers_with_zero_values.append(customer)
            else:
                customers_with_non_zero_values.append(customer)

        # Combine non-zero customers first and zero-value customers at the bottom
    sorted_customer_data = customers_with_non_zero_values + customers_with_zero_values

    
    print(sorted_customer_data,'sorted_customer_data','\n\n')
    return sorted_customer_data
