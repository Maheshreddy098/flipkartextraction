


import requests
import json
import frappe
from frappe.utils import add_to_date, now, get_datetime, now_datetime
import pandas as pd
from datetime import datetime, timedelta
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1

csv_filename = '/Users/shahilkhan/Desktop/WorkSpace/MTR/'

headersList = {
                    "Accept": "*/*",
                    "User-Agent": "Khanal Tech",
                    "Content-Type": "application/json",
                    "Prefer": "odata.maxpagesize=300",
                }
payload = ''


# bench --site beta.localhost execute  --args "('2024-06-01','2024-06-23' )"  khanal_tech_integrations.utils.MTR.Get_DN.DeliveryNotes_Excel


@frappe.whitelist()
def DeliveryNotes_Excel(FromDate,ToDate):


    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')

    reqUrl = doc_settings.sap_b1_url + "DeliveryNotes?$filter=DocDate ge '{FromDate}' and DocDate le '{Today}'"
    modified_Url = reqUrl.format(FromDate=FromDate, Today=ToDate)
    print(modified_Url,'modified_Url')
    response = session.request("GET", modified_Url, headers=headersList, verify=False)
    # print(response,'response')
    DeliveryNotes_list = dict(response.json())
    # print(DeliveryNotes_list,'DeliveryNotes_list')
    
    all_data = []
    
    while DeliveryNotes_list.get('odata.nextLink', None):
        all_data.extend(update_DeliveryNotes(DeliveryNotes_list))
        print(DeliveryNotes_list['odata.nextLink'])
        next_url = doc_settings.sap_b1_url + DeliveryNotes_list['odata.nextLink']
        response = session.request("GET", next_url, headers=headersList, verify=False)
        DeliveryNotes_list = dict(response.json())

    all_data.extend(update_DeliveryNotes(DeliveryNotes_list))
    
    df = pd.DataFrame(all_data)



    
    df.to_csv(f"{csv_filename}JUNE_{FromDate}_{ToDate}.csv", index=False)
    return 'File Saved'



def update_DeliveryNotes(DeliveryNotes_data):
    temp_list = []
    if DeliveryNotes_data.get('value'):
        for Single_DN in DeliveryNotes_data['value']:
            DocEntry = Single_DN.get('DocEntry')
            DocNum = Single_DN.get('DocNum')
            CardCode = Single_DN.get('CardCode')
            CardName = Single_DN.get('CardName')
            PayToCode = Single_DN.get('PayToCode')
            ShipToCode = Single_DN.get('ShipToCode')
            DocDate = Single_DN.get('DocDate')
            DocDueDate = Single_DN.get('DocDueDate')
            U_BillingFrom = Single_DN.get('U_BillingFrom')
            U_BillTo = Single_DN.get('U_BillTo')
            
            for line in Single_DN.get('DocumentLines', []):
                LineNum = line.get('LineNum')
                ItemCode = line.get('ItemCode')
                ItemDescription = line.get('ItemDescription')
                WarehouseCode = line.get('WarehouseCode')
                Quantity = line.get('Quantity')
                TaxCode = line.get('TaxCode')
                TaxType = line.get('TaxType')
                TaxTotal = line.get('TaxTotal')
                UnitPrice = line.get('UnitPrice')
                GrossPrice = line.get('GrossPrice')
                GrossTotal = line.get('GrossTotal')
                GrossTotalSC = line.get('GrossTotalSC')

                U_BuyerName = line.get('U_BuyerName')
                U_Order = line.get('U_Order')
                U_OrderID = line.get('U_OrderID')
                U_OrderedOn = line.get('U_OrderedOn')

                
                data = {
                    'DocEntry': DocEntry,
                    'DocNum': DocNum,
                    'LineNum': LineNum,
                    'ItemCode': ItemCode,
                    'ItemDescription':ItemDescription,
                    'Quantity': Quantity,
                    'UnitPrice': UnitPrice,
                    'GrossPrice': GrossPrice,
                    'GrossTotal': GrossTotal,
                    'GrossTotalSC': GrossTotalSC,
                    'TaxCode': TaxCode,
                    'TaxType': TaxType,
                    'TaxTotal': TaxTotal,
                    'U_BuyerName': U_BuyerName,
                    'U_Order': U_Order,
                    'U_OrderID': U_OrderID,
                    'U_OrderedOn': U_OrderedOn,
                    'CardCode': CardCode,
                    'CardName': CardName,
                    'PayToCode': PayToCode,
                    'ShipToCode': ShipToCode,
                    'DocDate': DocDate,
                    'DocDueDate': DocDueDate,
                    'U_BillingFrom': U_BillingFrom,
                    'U_BillTo': U_BillTo,
                    'WarehouseCode': WarehouseCode,
                     
                }

                temp_list.append(data)
    return temp_list

