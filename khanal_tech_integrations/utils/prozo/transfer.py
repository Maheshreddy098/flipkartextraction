import requests
import json
import frappe
from frappe.utils import add_to_date, get_datetime, now_datetime, today
from frappe.utils import now

import datetime
from frappe.query_builder.functions import Sum

headersList = {"Accept": "*/*",
                "User-Agent": "KhanalTech",
                "Content-Type": "application/json" 
                }

#import time

import urllib3
urllib3.disable_warnings()


#

def transferdetails(id):
        doc = frappe.get_doc("Prozo Inventory Transfers",id)
        #LineItems = get_single_inventory_transfer(transfer_request['DocEntry'])
        print(doc.get_title(),doc)

    

        #new=frappe.db.get_list('Prozo Inventory Transfers', filters={  'towarehouse': ['like', '%PZ%'] })
        #print(new)

#
# %%

#   Authentication for PROZO

import requests
import json
#import urlib3


def Authentication():
        prozo_url = "https://staging.prozo.com/wms/v1/auth"

        headersList = {
         "Accept": "*/*",'tenant': 'tenant_28','source': '2',
         "User-Agent": "Thunder Client (https://www.thunderclient.com)",
         "Content-Type": "application/json" }

        payload = {
            "username": "9087654321",
            "password": "dummy@123"
        }

        response = requests.request("POST", prozo_url, data=json.dumps(payload),  headers=headersList)

        return response

#%%
df=Authentication()
token=df.json()['token']
#print([i for i in df.json()])





# GET GRN FROM PROZO

def getgrn(token):
        import requests

        url = "https://staging.prozo.com/wms/v1/grn"

        payload={}
        headers ={
                'id': '1',
                'source': '2',
                'tenant': 'tenant_28',
                'Authorization':token
                        }

        response = requests.request("GET", url, headers=headers, data=payload)

        print(response.text)

        return response

#


total=getgrn(token).json()


#Get GRN ID LIST

GRNlist=[]   
for i in total: 
        GRNlist.append({
            
            'id':i['id'],
            'code':i['warehouse']['code'],
            'Warehouse':i['warehouse']['name'],
            'PONumber':i['po']['poNumber'],
            'Quantity':i['po']['quantity'],
            'Status':i['qcStatus'],
            'Accepted Qty':i['po']['grnAcceptedQuantity'],
            'GRN_Date':['createdDate'],
            'Total_Quantity':i['totalQuantity']     
        })


print(GRNlist)        
#%%

#  View Single GRN Based on id

def getsinglegrn(token,id):
        
        url = "https://staging.prozo.com/wms/v1/grn/"+str(id)

        payload={}
        headers = {  
           'id': '1',
            'source': '2',
            'tenant': 'tenant_28',
            'Authorization':token
        }

        response = requests.request("GET", url, headers=headers, data=payload)

        #print(response.text)

        return response



getsinglegrn(token,8)

grndetails=[]
        
for i in range(len(data['po']['poDetails'])):  
    
    grndetails.append({
                        
                        'id':data['id'],
                        'PO Number':data['po']['poNumber'],
                        'GRN Number':data['grnNumber'],
                        'GRN Status':data['qcStatus'],
                        'GRN_Quantity':data['acceptedQuantity'],
                        'Wareshouse':data['warehouse']['code'],
                        'Wareshouse':data['createdDate'],   
                        'Item Code':data['po']['poDetails'][i]['product']['barCode'],
                        'Item Description':data['po']['poDetails'][i]['product']['title'],
                        'Item Price':data['po']['poDetails'][i]['product']['mrp'],
                        'Batch Name':data['po']['poDetails'][i]['product']['batch']['batchName'],
                        'Batch Code':data['po']['poDetails'][i]['product']['batch']['barCode']
                })


