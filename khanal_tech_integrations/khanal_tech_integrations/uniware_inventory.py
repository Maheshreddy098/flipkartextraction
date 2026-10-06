#%%

import requests
import json
import frappe
#import time
import datetime

import urllib3
urllib3.disable_warnings()
doc_settings = frappe.get_doc('SAP Settings')
# doc_settings.sap_b1_url
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

#Function to Authenticate Unicommerce - Uniware
def AuthenticateUniware():
    reqUrl = "https://khanalfoods.unicommerce.com/oauth/token?grant_type=password&client_id=my-trusted-client&username=buddhiraj@khanalfoods.com&password=Pihu@1729"
    headersList1 = {
        "Accept": "*/*",
        "User-Agent": "Thunder Client (https://www.thunderclient.com)",
        "Content-Type": "application/json" }
    headersList1["facility"] = 'khanalfoods'
    payload = ""
    response = requests.request("GET", reqUrl, data=json.dumps(payload),  headers=headersList1)

    return response.json()
# %%
@frappe.whitelist()
def EC_inventory_transfers():
    session = AuthenticateSAPB1(b1_url)
    payload = ''
    headersList = {
                "Accept": "*/*",
                "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                "Content-Type": "application/json" 
            }
    i = 1
    while True:
        doc_settings = frappe.get_doc('SAP Settings')
        # doc_settings.sap_b1_url
        reqUrl = doc_settings.sap_b1_url+"StockTransfers?$skip=" + str(20*i)
        try:
            #print ('going into TRY')
            response = session.request("GET", reqUrl, data=payload,  headers=headersList)
        except:
            print ('going into EXCEPT')
            #Renew session in case of expiry
            session = AuthenticateSAPB1(b1_url)
            response = session.request("GET", reqUrl, data=payload,  headers=headersList)
        transfer_requests = dict(response.json())

        print ('Working on : ',i)
        #print (len(transfer_requests['value']))
        #if i % 10 == 0:
        #    break

        if len(transfer_requests['value'])>1:#'value' in transfer_requests:
            if transfer_requests['value'] is not None:
                for transfer_request in transfer_requests['value']:
                    if transfer_request['FromWarehouse'] == 'EC-FG':
                        doc = frappe.new_doc('Stock_Transfer_EC')
                        doc.docentry = transfer_request['DocEntry']
                        doc.docdate = transfer_request['DocDate']
                        doc.docnum = transfer_request['DocNum']
                        doc.fromwarehouse = transfer_request['FromWarehouse']
                        doc.towarehouse = transfer_request['ToWarehouse']
                        try:     #try saving, skip if already exist
                            doc.save()
                        except frappe.DuplicateEntryError:
                            pass
                else:
                    pass
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
        

    frappe.msgprint(msg='Data Inserted successfully',title='Success')
#%%
def get_single_inventory_transfer(DocEntry):
    session = AuthenticateSAPB1(b1_url)
    doc_settings = frappe.get_doc('SAP Settings')
    # doc_settings.sap_b1_url
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

#%%
PO_payload = {"vendorCode": "EC-DIS",
   "purchaseOrderItems": [

   ]
}
PO_lineitem = {
         "itemSKU": "FGHN0025",
         "quantity": 3045,
         "unitPrice": 0,
         "taxTypeCode": None
      }
#%%
@frappe.whitelist()
def create_PO_uniware(docnum):
    #new create 
    U_session =  AuthenticateUniware()
    SAP_session = AuthenticateSAPB1()
    original_inv_transfer = get_single_inventory_transfer(docnum)
    for item in original_inv_transfer:
        PO_lineitem['itemSKU'] = item['itemcode']
        PO_lineitem['quantity'] = item['quantity']
        PO_payload["purchaseOrderItems"].append(PO_lineitem)
    PO_posting_url = "https://khanalfoods.unicommerce.com/services/rest/v1/purchase/purchaseOrder/create"
    


    










