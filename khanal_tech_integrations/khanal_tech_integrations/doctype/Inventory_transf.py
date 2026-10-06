#SAP API
#%%
import requests
import json
import frappe
#import time

import urllib3
urllib3.disable_warnings()
doc_settings = frappe.get_doc('SAP Settings')
# doc_settings.sap_b1_url
b1_url = doc_settings.sap_b1_url
manager_data_TEST_DB = {"CompanyDB": "KHANAL_080922","Password": "F@3ac8#b","UserName": "manager"}
manager_data_LIVE_DB = {"CompanyDB": "KFL_LIVE","Password": "F@3ac8#b","UserName": "manager"}

def AuthenticateSAPB1(b1_url):
    reqUrl = b1_url + "Login"
    b1_session = requests.Session()
    headersList = {
                    "Accept": "*/*",
                    "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                    "Content-Type": "application/json" 
                }
    payload = json.dumps(manager_data_LIVE_DB)
    response = b1_session.request("POST", reqUrl, data=payload,  headers=headersList,verify=False)

    return b1_session
# %%
@frappe.whitelist()
def bulk_process_inventory_transfers():
    session = AuthenticateSAPB1(b1_url)
    payload = ''
    headersList = {
                "Accept": "*/*",
                "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                "Content-Type": "application/json" 
            }
    #headersList['Authorization'] = 'bearer ' + session['access_token']
    #CHECK THE LAST MAX UPDATED INV. TRANSFERS
    start_page = 0
    try:
        last_page_doc = frappe.get_last_doc('SAP Inventory Transfer Update Logs')
        start_page = last_page_doc.last_skip
        #print (start_page)
    except:
        pass


    #for i in range(int(start_page),2):
    i = 280 #int(start_page)
    if i>0:
        i = i - 1

    while True:
        doc_settings = frappe.get_doc('SAP Settings')
        reqUrl = doc_settings.sap_b1_url+"StockTransfers?$skip=" + str(20*i)
        try:
            #print ('going into TRY')
            response = session.request("GET", reqUrl, data=payload,  headers=headersList)
            print('Here is the response')
        except:
            print ('going into EXCEPT')
            #Renew session in case of expiry
            session = AuthenticateSAPB1(b1_url)
            response = session.request("GET", reqUrl, data=payload,  headers=headersList)
        transfer_requests = dict(response.json())

        print ('Working on : ',i)
        #print (len(transfer_requests['value']))
        #if i % 10 == 0:

        if len(transfer_requests['value'])>1:#'value' in transfer_requests:
            if transfer_requests['value'] is not None:
                for transfer_request in transfer_requests['value']:
                    doc = frappe.new_doc('SAP Inventory Transfers')
                    doc.docentry = transfer_request['DocEntry']
                    doc.series = transfer_request['Series']
                    doc.docdate = transfer_request['DocDate']
                    doc.docnum = transfer_request['DocNum']
                    doc.fromwarehouse = transfer_request['FromWarehouse']
                    doc.towarehouse = transfer_request['ToWarehouse']
                    doc.cardcode = transfer_request['CardCode']
                    doc.comments = transfer_request['Comments']
                    doc.delivered = transfer_request['U_Delivered']
                    #doc.save()
                    try:
                        #try saving, skip if already exist
                        doc.save()
                        print('doc_saved')
                    except frappe.DuplicateEntryError:
                        pass

                    doc = frappe.get_doc("SAP Inventory Transfers",transfer_request['DocEntry'])
                    LineItems = get_single_inventory_transfer(transfer_request['DocEntry'])
                    for LineItem in LineItems:
                        doc.append("line_items",LineItem)
                    doc.save()
                i +=1
                #increment the counter
            elif transfer_requests['value'] is None:
                break
            #session = ''
        else:
            break
            #Renew session in case of expiry
            #print ('Renewing session')
            #time.sleep(10)
            #session = AuthenticateSAPB1(b1_url)
        
    
    #Update the last page
    doc1 = frappe.new_doc('SAP Inventory Transfer Update Logs')
    doc1.last_skip = i
    doc1.save()

    frappe.msgprint(msg='Data Inserted successfully',title='Success')

# %%
def get_single_inventory_transfer(DocEntry):
    session = AuthenticateSAPB1(b1_url)
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url+"StockTransfers(" + str(DocEntry) + ")"
    payload = ""

    headersList = {
                "Accept": "*/*",
                "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                "Content-Type": "application/json" 
            }
    response = session.request("GET", reqUrl, data=payload,  headers=headersList)
    inventory_transfer = dict(response.json())

    LineItems = inventory_transfer['StockTransferLines']
    
    LineItem_list = []
    for LineItem in LineItems:
       
        for BatchDetail in LineItem['BatchNumbers']:
            #doc.line_items
            LineItem_list.append({"itemcode":LineItem['ItemCode'],"itemdescription":LineItem['ItemDescription'],
            "quantity":LineItem['Quantity'],"towarehousecode": LineItem['WarehouseCode'],
            "fromwarehousecode":LineItem['FromWarehouseCode'], "batchnumber": BatchDetail['BatchNumber'],
            "batchquantity":BatchDetail['Quantity']})#,BatchDetail['ExpiryDate'],BatchDetail['ManufacturingDate']}
            #print (LineItem['ItemCode'],LineItem['ItemDescription'],LineItem['Quantity'],LineItem['WarehouseCode'],LineItem['FromWarehouseCode'], BatchDetail['BatchNumber'],BatchDetail['Quantity'],BatchDetail['ExpiryDate'],BatchDetail['ManufacturingDate'])
    return LineItem_list

@frappe.whitelist()
def bulk_inventory_queue():
    frappe.enqueue(bulk_process_inventory_transfers, 
                    timeout=None, # pass timeout manually
                    is_async=True, # if this is True, method is run in worker
                    queue='long',job_name='Inventory Transfer Bulk Update',
                    now=True)
# %%

import requests
import json

b1_url = doc_settings.sap_b1_url
manager_data_TEST_DB = {"CompanyDB": "KHANAL","Password": "F@3ac8#b","UserName": "manager"}

reqUrl = b1_url + "Login"
b1_session = requests.Session()
b1_session.verify = False

headersList = {
                    "Accept": "*/*",
                    "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                    "Content-Type": "application/json" 
                }
#%%
payload = json.dumps(manager_data_TEST_DB)
response = b1_session.request("POST", reqUrl, data=payload,  headers=headersList,verify=False)
doc_settings = frappe.get_doc('SAP Settings')
reqUrl = doc_settings.sap_b1_url+"StockTransfers?$skip=" + str(1000)
response = b1_session.request("GET", reqUrl, data=payload,  headers=headersList)
response.json()

#/workspace/development/frappe-bench/apps/khanal_tech_integrations/khanal_tech_integrations/khanal_tech_integrations/doctype/Inventory_transf.py