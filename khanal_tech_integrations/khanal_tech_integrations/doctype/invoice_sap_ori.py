#%%
import requests
import json
import frappe
#import time
import datetime

import urllib3
urllib3.disable_warnings()
doc_settings = frappe.get_doc('SAP Settings')
b1_url = doc_settings.sap_b1_url
manager_data_TEST_DB = {"CompanyDB": "KHANAL","Password": "F@3ac8#b","UserName": "manager"}
manager_data_LIVE_DB = {"CompanyDB": "KFL_LIVE","Password": "F@3ac8#b","UserName": "manager"}

#Function to authenticate SAP B1
def AuthenticateSAPB1(b1_url):
    reqUrl = b1_url + "Login"
    b1_session = requests.Session()
    #b1_session.verify = False

    headersList = {
                    "Accept": "*/*",
                    "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                    "Content-Type": "application/json" 
                }
    payload = json.dumps(manager_data_TEST_DB)
    response = b1_session.request("POST", reqUrl, data=payload,  headers=headersList,verify=False)

    return b1_session
inv_payload ={
    "CardCode": "C03186",
    "DocumentLines": [
                       ]
}

# %%
def create_invoice():
    session =  AuthenticateSAPB1(b1_url)
    headersList = {
                "Accept": "*/*",
                "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                "Content-Type": "application/json" 
            }
    doc_settings = frappe.get_doc('SAP Settings')
    invoice_Url = doc_settings.sap_b1_url+"Invoices"
    response = session.request("POST", invoice_Url, data=json.dumps(inv_payload),  headers=headersList,verify=False)
    response.json()
    return response.json()
# %%
@frappe.whitelist()
def generate_invoice_from_order():
    orderr = 'SLP3817458722'
    order_doc = frappe.get_doc('Orders', orderr)
    lineitemss = order_doc.line_items
    print(lineitemss[0].itemsku)
    inv_payload["DocumentLines"][0]['ItemCode'] = lineitemss[0].itemsku
    print('pass2')
    inv_payload["DocumentLines"][0]['PriceAfterVAT'] = lineitemss[0].total_price
    print('pass3')
    inv_payload["DocumentLines"][0]['U_BuyerName'] = order_doc.customer_name
    inv_payload["DocumentLines"][0]['U_Order'] = order_doc.uniware_id
    inv_payload["DocumentLines"][0]['U_City'] = order_doc.city
    inv_payload["DocumentLines"][0]['U_State'] = order_doc.state
    inv_payload["DocumentLines"][0]['U_PINCode'] = order_doc.pin_code
    inv_payload["DocumentLines"][0]['U_Country'] = 'India'
    print('pass5')
    session =  AuthenticateSAPB1(b1_url)
    headersList = {
                "Accept": "*/*",
                "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                "Content-Type": "application/json" 
            }
    doc_settings = frappe.get_doc('SAP Settings')
    invoice_Url = doc_settings.sap_b1_url+"Invoices"
    response = session.request("POST", invoice_Url, data=json.dumps(inv_payload),  headers=headersList,verify=False)
    print(response.json())
    return response.json()


# %%
@frappe.whitelist()
def invoice_from_order():
    orderr = 'SLP3817458722'
    order_doc = frappe.get_doc('Orders', orderr)
    lineitemss = order_doc.line_items
    print(len(lineitemss))
    print("procesing is on /n /n *** ** *")
    for index_no in range(len(lineitemss)):
        lineitem_invoice = {
            "LineNum": 0,
            "ItemCode": "FGHN0005",
            "AccountCode": "41102000",
            'WarehouseCode': 'EC-FG',
            "Quantity": "1",
            "TaxCode": "IGST@12",
            'TaxType': 'tt_Yes',
            'TaxLiable': 'tYES',
            'TaxTotal': 0.0,
            'PriceAfterVAT': 700,
         'U_BuyerName': None, #channel
         'U_Order': None, #Order code 
         'U_OrderID': None, #order Display code 
         'U_OrderedOn': None,
         'U_City': None,
         'U_State': None,
         'U_PINCode': None,
         'U_Country': 'India',
         'BatchNumbers': [{
             'BatchNumber': 'G3H102F04G',
             "Quantity": 1 
             }]}
        lineitem_invoice["LineNum"] = index_no
        lineitem_invoice['ItemCode'] = lineitemss[index_no].itemsku
        print('pass2')
        lineitem_invoice['PriceAfterVAT'] = lineitemss[index_no].total_price
        print('pass3')
        lineitem_invoice['U_BuyerName'] = order_doc.customer_name
        lineitem_invoice['U_Order'] = order_doc.uniware_id
        lineitem_invoice['U_City'] = order_doc.city
        lineitem_invoice['U_State'] = order_doc.state
        lineitem_invoice['U_PINCode'] = order_doc.pin_code
        lineitem_invoice['U_Country'] = 'India'
        print('pass5')
        inv_payload["DocumentLines"].append(lineitem_invoice)
    session =  AuthenticateSAPB1(b1_url)
    headersList = {
                "Accept": "*/*",
                "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                "Content-Type": "application/json" 
            }
    doc_settings = frappe.get_doc('SAP Settings')
    invoice_Url = doc_settings.sap_b1_url+"Invoices"
    response = session.request("POST", invoice_Url, data=json.dumps(inv_payload),  headers=headersList,verify=False)
    print(response.json())
    return response.json()

####################
lineitem_invoice = {
            "LineNum": 0,
            "ItemCode": "FGHN0005",
            "AccountCode": "41102000",
            'WarehouseCode': 'EC-FG',
            "Quantity": "1",
            "TaxCode": "IGST@12",
            'TaxType': 'tt_Yes',
            'TaxLiable': 'tYES',
            'TaxTotal': 0.0,
            'PriceAfterVAT': 700,
         'U_BuyerName': None, #channel
         'U_Order': None, #Order code 
         'U_OrderID': None, #order Display code 
         'U_OrderedOn': None,
         'U_City': None,
         'U_State': None,
         'U_PINCode': None,
         'U_Country': 'India',
         'BatchNumbers': [{
             'BatchNumber': 'G3H102F04G',
             "Quantity": 1 
             }]}
#################################################3

# %%
@frappe.whitelist()
def invoice_from_orderlist():
    orderrlist = ['SLP3817458722','SLP3781522492']
    initial_count = 0
    for single in orderrlist:
        order_doc = frappe.get_doc('Orders', single)
        lineitemss = order_doc.line_items
        print("Procesing is on /n /n *** ** *")
        for itemss in lineitemss:
            lineitem_invoice["LineNum"] = initial_count
            initial_count += 1
            print('Initialcount is = '+ str(initial_count))
            lineitem_invoice['ItemCode'] = itemss.itemsku
            print('pass2')
            lineitem_invoice['PriceAfterVAT'] = itemss.total_price
            print('pass3')
            lineitem_invoice['U_BuyerName'] = order_doc.customer_name
            lineitem_invoice['U_Order'] = order_doc.uniware_id
            lineitem_invoice['U_City'] = order_doc.city
            lineitem_invoice['U_State'] = order_doc.state
            lineitem_invoice['U_PINCode'] = order_doc.pin_code
            lineitem_invoice['U_Country'] = 'India'
            print('pass5')
            inv_payload["DocumentLines"].append(lineitem_invoice) #appending as a lineitems inside inv_payload dictionary
    session =  AuthenticateSAPB1(b1_url)
    headersList = {
                "Accept": "*/*",
                "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                "Content-Type": "application/json" 
            }
    doc_settings = frappe.get_doc('SAP Settings')
    invoice_Url = doc_settings.sap_b1_url+"Invoices"
    response = session.request("POST", invoice_Url, data=json.dumps(inv_payload),  headers=headersList,verify=False)
    print(response.json())
    #code to be inserted 
    ####response docNum to be collected and pushed into the data point of the order-
    # DocType using a loop in the list - open doctype and writing data  ####
    return response.json()