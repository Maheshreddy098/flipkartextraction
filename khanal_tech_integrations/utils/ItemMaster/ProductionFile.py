import requests
import json
import frappe
from frappe.utils import add_to_date, now, get_datetime, now_datetime
import pandas as pd
from datetime import datetime, timedelta
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1

csv_filename = '/Users/shahilkhan/Desktop/WorkSpace/Production Orders/2024/10July.xlsx'
Issuecsv_filename= '/Users/shahilkhan/Desktop/WorkSpace/Production Orders/2024/Issue From 10July.csv'
Receiptcsv_filename= '/Users/shahilkhan/Desktop/WorkSpace/Production Orders/2024/Receipt From 10July.csv'
# BpData = pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Production Orders/GST REVENUE REPORT 22-23.xlsx','Sheet1')
headersList = {
                    "Accept": "*/*",
                    "User-Agent": "Khanal Tech",
                    "Content-Type": "application/json",
                    "Prefer": "odata.maxpagesize=300",
                }
payload = ''


@frappe.whitelist()
def ProductionOrders_Excel():


    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')

    reqUrl = doc_settings.sap_b1_url + "ProductionOrders?$filter=PostingDate ge '2022-03-31'"
   
    response = session.request("GET", reqUrl, headers=headersList, verify=False)
    # print(response,'response')
    ProductionOrders_list = dict(response.json())
    # print(ProductionOrders_list,'ProductionOrders_list')
    
    all_data = []
    
    while ProductionOrders_list.get('odata.nextLink', None):
        all_data.extend(update_ProductionOrders(ProductionOrders_list))
        print(ProductionOrders_list['odata.nextLink'])
        next_url = doc_settings.sap_b1_url + ProductionOrders_list['odata.nextLink']
        response = session.request("GET", next_url, headers=headersList, verify=False)
        ProductionOrders_list = dict(response.json())

    all_data.extend(update_ProductionOrders(ProductionOrders_list))
    
    df = pd.DataFrame(all_data)



    
    df.to_excel(csv_filename, index=False)
    return df



def update_ProductionOrders(ProductionOrders_data):
    temp_list = []
    if ProductionOrders_data.get('value'):
        for Single_Order in ProductionOrders_data['value']:
            AbsoluteEntry = Single_Order.get('AbsoluteEntry')
            DocumentNumber = Single_Order.get('DocumentNumber')
            ProductionOrderStatus = Single_Order.get('ProductionOrderStatus')
            ProductionOrderType = Single_Order.get('ProductionOrderType')
            Series = Single_Order.get('Series')
            ItemNo = Single_Order.get('ItemNo')
            PlannedQuantity = Single_Order.get('PlannedQuantity')
            CompletedQuantity = Single_Order.get('CompletedQuantity')
            RejectedQuantity = Single_Order.get('RejectedQuantity')
            PostingDate = Single_Order.get('PostingDate')
            DueDate = Single_Order.get('DueDate')
            Warehouse = Single_Order.get('Warehouse')
            RejectedQuantity = Single_Order.get('RejectedQuantity')
            ProductionOrderOrigin = Single_Order.get('ProductionOrderOrigin')
            UserSignature = Single_Order.get('UserSignature')
            Remarks = Single_Order.get('Remarks')
            ClosingDate = Single_Order.get('ClosingDate')
            ReleaseDate = Single_Order.get('ReleaseDate')
            CustomerCode = Single_Order.get('CustomerCode')
            InventoryUOM = Single_Order.get('InventoryUOM')
            JournalRemarks = Single_Order.get('JournalRemarks')
            TransactionNumber = Single_Order.get('TransactionNumber')
            CreationDate = Single_Order.get('CreationDate')
            UoMEntry = Single_Order.get('UoMEntry')
            StartDate = Single_Order.get('StartDate')
            ProductDescription = Single_Order.get('ProductDescription')
            
            for line in Single_Order.get('ProductionOrderLines', []):
                LineNumber = line.get('LineNumber')
                LineItemNo = line.get('ItemNo')
                BaseQuantity = line.get('BaseQuantity')
                LinePlannedQuantity = line.get('PlannedQuantity')
                IssuedQuantity = line.get('IssuedQuantity')
                LineWarehouse = line.get('Warehouse')
                
                data = {
                    'AbsoluteEntry': AbsoluteEntry,
                    'DocumentNumber': DocumentNumber,
                    'ItemNo': ItemNo,
                    'Series': Series,
                    'ProductionOrderStatus': ProductionOrderStatus,
                    'ProductionOrderType': ProductionOrderType,
                    'ProductionOrderOrigin': ProductionOrderOrigin,
                    'UserSignature': UserSignature,
                    'Remarks': Remarks,
                    'ClosingDate': ClosingDate,
                    'ReleaseDate': ReleaseDate,
                    'CustomerCode': CustomerCode,
                    'InventoryUOM': InventoryUOM,
                    'JournalRemarks': JournalRemarks,
                    'TransactionNumber': TransactionNumber,
                    'CreationDate': CreationDate,
                    'UoMEntry': UoMEntry,
                    'StartDate': StartDate,
                    'ProductDescription': ProductDescription,
                    'PlannedQuantity': PlannedQuantity,
                    'DueDate': DueDate,
                    'CompletedQuantity': CompletedQuantity,
                    'RejectedQuantity': RejectedQuantity,
                    'PostingDate': PostingDate,
                    'LineNumber': LineNumber,
                    'LineItemNo': LineItemNo,
                    'BaseQuantity': BaseQuantity,
                    'LinePlannedQuantity': LinePlannedQuantity,
                    'IssuedQuantity': IssuedQuantity, 
                    'Warehouse': Warehouse,      
                    'LineWarehouse': LineWarehouse,          
                }

                temp_list.append(data)
    return temp_list


@frappe.whitelist()
def IssueOrders_Excel():


    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')

    reqUrl = doc_settings.sap_b1_url + "InventoryGenExits?$filter=DocDate ge '2024-03-31'"
    response = session.request("GET", reqUrl, headers=headersList, verify=False)
    # print(response,'response')
    issueProductionOrders_list = dict(response.json())
    # print(issueProductionOrders_list,'issueProductionOrders_list')
    
    all_data = []
    
    while issueProductionOrders_list.get('odata.nextLink', None):
        all_data.extend(update_IssueProductionOrders(issueProductionOrders_list))
        print(issueProductionOrders_list['odata.nextLink'])
        next_url = doc_settings.sap_b1_url + issueProductionOrders_list['odata.nextLink']
        response = session.request("GET", next_url, headers=headersList, verify=False)
        issueProductionOrders_list = dict(response.json())

    all_data.extend(update_IssueProductionOrders(issueProductionOrders_list))
    
    df = pd.DataFrame(all_data)
    filtered_df = df[df['ProductionBaseType'] == 202]

    print(filtered_df,'\n\n')

    
    filtered_df.to_csv(Issuecsv_filename, index=False)
    return filtered_df

def update_IssueProductionOrders(IssueProductionOrders_data):
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    temp_list = []
    # Check if 'value' key exists and is not empty
    if IssueProductionOrders_data.get('value'):
        for Single_Order in IssueProductionOrders_data['value']:
            # Extract order-level details
            # print('\n\n\n','Single_Order')
            # print(Single_Order.get('DocEntry'),'Single_Order.get('')')
            reqUrl = doc_settings.sap_b1_url + "InventoryGenExits({DocEntry})"
            modified_Url = reqUrl.format(DocEntry=Single_Order.get('DocEntry'))
            response = session.request("GET", modified_Url, headers=headersList, verify=False)
            # print(response,'response')
            # print(modified_Url,'modified_Url')
            ProductionDict = dict(response.json())
            # print(ProductionDict,'ProductionDict')
            DocEntry = ProductionDict.get('DocEntry')
            DocNum = ProductionDict.get('DocNum')
            DocDate = ProductionDict.get('DocDate')
            TransNum = ProductionDict.get('TransNum')
            # if DocEntry==21146:
            #     print(ProductionDict.get("DocumentLines"))
            # print(ProductionDict.get('TransNum'),'TransNum')
            # print(DocEntry,'\n','DocEntry')
    
            # Check if 'DocumentLines' key exists and iterate over lines
            for line in ProductionDict.get('DocumentLines'):
                # print(line.get('LineNum'),'LineNum')
                # print(len(line.get('BatchNumbers')),'Lenght')
            
                if len(line['BatchNumbers'])>0:
                    # print(len(line.get('BatchNumbers')),'Lenght')
                    LineNumber = line.get('LineNum')
                    # print(LineNumber,'LineNumber')
                    ItemCode = line.get('ItemCode')
                    BaseQuantity = line.get('Quantity')
                    ProductionBaseEntry = line.get('BaseEntry')
                    ProductionBaseType = line.get('BaseType')
                    
                    for batchline in line.get('BatchNumbers'):
                        BatchNumber = batchline.get('BatchNumber')
                        LineQuantity = batchline.get('Quantity')
                        
                        data = {
                            'DocEntry': DocEntry,
                            'DocNum': DocNum,
                            'DocDate': DocDate,
                            'TransNum': TransNum,
                            'LineNumber': LineNumber,
                            'ItemCode': ItemCode,
                            'BaseQuantity': BaseQuantity,
                            'ProductionBaseEntry': ProductionBaseEntry,
                            'ProductionBaseType':ProductionBaseType,
                            'BatchNumber': BatchNumber,
                            'LineQuantity': LineQuantity,
                        }
                        
                        # Print data to verify correctness
                        # print(data)

                        temp_list.append(data)
    else:
        # Print a message if 'value' key is missing or empty
        print("No 'value' key found or it is empty")
    
    return temp_list








@frappe.whitelist()
def ReceiptOrders_Excel():


    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')

    reqUrl = doc_settings.sap_b1_url + "InventoryGenEntries?$filter=DocDate ge '2024-03-31'"
    response = session.request("GET", reqUrl, headers=headersList, verify=False)
    # print(response,'response')
    receiptProductionOrders_list = dict(response.json())
    # print(receiptProductionOrders_list,'receiptProductionOrders_list')
    
    all_data = []
    
    while receiptProductionOrders_list.get('odata.nextLink', None):
        all_data.extend(update_ReceiptProductionOrders(receiptProductionOrders_list))
        print(receiptProductionOrders_list['odata.nextLink'])
        next_url = doc_settings.sap_b1_url + receiptProductionOrders_list['odata.nextLink']
        response = session.request("GET", next_url, headers=headersList, verify=False)
        receiptProductionOrders_list = dict(response.json())

    all_data.extend(update_ReceiptProductionOrders(receiptProductionOrders_list))
    
    df = pd.DataFrame(all_data)

    print(df,'\n\n')
    filtered_df = df[df['ProductionBaseType'] == 202]

    
    filtered_df.to_csv(Receiptcsv_filename, index=False)
    return filtered_df

def update_ReceiptProductionOrders(ReceiptProductionOrders_data):
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    temp_list = []
    # Check if 'value' key exists and is not empty
    if ReceiptProductionOrders_data.get('value'):
        for Single_Order in ReceiptProductionOrders_data['value']:
            # Extract order-level details
            # print('\n\n\n','Single_Order')
            # print(Single_Order.get('DocEntry'),'Single_Order.get('')')
            reqUrl = doc_settings.sap_b1_url + "InventoryGenEntries({DocEntry})"
            modified_Url = reqUrl.format(DocEntry=Single_Order.get('DocEntry'))
            response = session.request("GET", modified_Url, headers=headersList, verify=False)
            # print(response,'response')
            # print(modified_Url,'modified_Url')
            ProductionDict = dict(response.json())
            # print(ProductionDict,'ProductionDict')
            DocEntry = ProductionDict.get('DocEntry')
            DocNum = ProductionDict.get('DocNum')
            DocDate = ProductionDict.get('DocDate')
            TransNum = ProductionDict.get('TransNum')
            # if DocEntry==21146:
            #     print(ProductionDict.get("DocumentLines"))
            # print(ProductionDict.get('TransNum'),'TransNum')
    
            # Check if 'DocumentLines' key exists and iterate over lines
            for line in ProductionDict.get('DocumentLines'):
                # print(line.get('LineNum'),'LineNum')
            # print(len(line.get('BatchNumbers')),'Lenght')
            
                if len(line['BatchNumbers'])>0:
                    # print(len(line.get('BatchNumbers')),'Lenght')
                    LineNumber = line.get('LineNum')
                    # print(LineNumber,'LineNumber')
                    ItemCode = line.get('ItemCode')
                    BaseQuantity = line.get('Quantity')
                    ProductionBaseEntry = line.get('BaseEntry')
                    ProductionBaseType = line.get('BaseType')
                    
                    for batchline in line.get('BatchNumbers'):
                        BatchNumber = batchline.get('BatchNumber')
                        LineQuantity = batchline.get('Quantity')
                        
                        data = {
                            'DocEntry': DocEntry,
                            'DocNum': DocNum,
                            'DocDate': DocDate,
                            'TransNum': TransNum,
                            'LineNumber': LineNumber,
                            'ItemCode': ItemCode,
                            'BaseQuantity': BaseQuantity,
                            'ProductionBaseEntry': ProductionBaseEntry,
                            'ProductionBaseType':ProductionBaseType,
                            'BatchNumber': BatchNumber,
                            'LineQuantity': LineQuantity,
                        }
                        
                        # Print data to verify correctness
                        # print(data)

                        temp_list.append(data)
    else:
        # Print a message if 'value' key is missing or empty
        print("No 'value' key found or it is empty")
    
    return temp_list

# bench --site alpha.localhost execute    khanal_tech_integrations.utils.React_Api.Production_Kiosk.MisMatchProduction.ProductionOrders_Excel
# bench --site alpha.localhost execute  khanal_tech_integrations.utils.React_Api.Production_Kiosk.MisMatchProduction.IssueOrders_Excel
# y

