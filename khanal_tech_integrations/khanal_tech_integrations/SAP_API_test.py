#%%
from urllib import response
import requests
import json
#import frappe
#import time
import datetime
import frappe

import urllib3
urllib3.disable_warnings()
doc_settings = frappe.get_doc('SAP Settings')
# doc_settings.sap_b1_url
b1_url = doc_settings.sap_b1_url
manager_data_TEST_DB = {"CompanyDB": "KHANAL_080922","Password": "F@3ac8#b","UserName": "manager"}
manager_data_LIVE_DB = {"CompanyDB": "KFL_LIVE","Password": "F@3ac8#b","UserName": "manager"}
headersList = {
                    "Accept": "*/*",
                    "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                    "Content-Type": "application/json" 
                }

#Function to authenticate SAP B1
def AuthenticateSAPB1():
    reqUrl = b1_url + "Login"
    b1_session = requests.Session()
    #b1_session.verify = False

    
    payload = json.dumps(manager_data_TEST_DB)
    response = b1_session.request("POST", reqUrl, data=payload,  headers=headersList,verify=False)

    return b1_session

# %%
session = AuthenticateSAPB1()
payload = ''

#CHECK THE LAST MAX UPDATED INV. TRANSFERS
start_page = 6700


#for i in range(int(start_page),2):
i = int(start_page)
doc_settings = frappe.get_doc('SAP Settings')
# doc_settings.sap_b1_url
reqUrl = doc_settings.sap_b1_url+"StockTransfers?$skip=" + str(20*i)
session = AuthenticateSAPB1()
response = session.request("GET", reqUrl, data=payload,  headers=headersList)
    
transfer_requests = dict(response.json())
print (transfer_requests)

next_page = transfer_requests.get("odata.nextLink",None)
print (next_page)

# while next_page is not None:
    
#     print ('Working on : ',next_page)
#     #print (transfer_requests['value'])
#     #if i % 10 == 0:
#     #    break

#     if len(transfer_requests['value'])>1: #'value' in transfer_requests:
#         if transfer_requests['value'] is not None:
#             for transfer_request in transfer_requests['value']:
#                 print ('data')
#                 #print (transfer_request)
    
#     i +=1
    
#     reqUrl = doc_settings.sap_b1_url+"StockTransfers?$skip=" + str(20*i)
    
#     session = AuthenticateSAPB1()
#     response = session.request("GET", reqUrl, data=payload,  headers=headersList)
    
#     transfer_requests = dict(response.json())
#     next_page = transfer_requests.get("odata.nextLink",None)
    
   
   
# %%
headersList = {
                    "Accept": "*/*",
                    "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                    "Content-Type": "application/json" 
                }
B1SESSION='e566700c-38c4-11ed-8000-005056b25c9b' 
ROUTEID='.node4'

reqUrl = doc_settings.sap_b1_url+"StockTransfers?$skip=" + str(20)

b1_session = requests.Session()
b1_session.cookies.set("B1SESSION", B1SESSION)
b1_session.cookies.set("ROUTEID", ROUTEID)
resp = b1_session.request("GET", reqUrl,  headers=headersList,verify=False)
# %%

A = [{'Item':'ABC','Batch':'B1'},]

#%%

x = 'abc'

x.split(',')

# %%
def get_GST(origin_state,dest_state,tax_rate):
    doc_settings = frappe.get_doc('SAP Settings')
    # doc_settings.sap_b1_url
    reqUrl = doc_settings.sap_b1_url+"States?$select=Code&$filter=startswith(Country,'IN') and startswith(Name,"+ origin_state +")"
    session = AuthenticateSAPB1()
    response = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
    state_code = dict(response.json())['value']['Code']

    if state_code == 'KT':
        state_code = 'KA'

    if origin_state==dest_state:
        tax_type = 'CS'
    else:
        tax_type = 'IG'

    gst_code = state_code + tax_type + tax_rate
    return gst_code
# %%
