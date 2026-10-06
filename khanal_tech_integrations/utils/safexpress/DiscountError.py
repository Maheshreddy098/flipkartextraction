import frappe
import json
import requests

from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
from khanal_tech_integrations.utils.safexpress.auth import AuthenticateSafexpress
import re
import  pandas as pd



headersList = {
        "Accept": "*/*",
        "User-Agent": "Khanal Tech",
        "Content-Type": "application/json" ,
         "Prefer": "odata.maxpagesize=900",
    }


# bench --site dev.localhost execute khanal_tech_integrations.utils.safexpress.DiscountError.ChangeInvoice

@frappe.whitelist()
def ChangeInvoice():
    df = pd.read_excel('/Users/shahilkhan/Downloads/Workspace/Json File/Error File.xlsx', 'KAIN')
    # # print(df,'df')
    for i, row in df.iterrows():
        pass
        
        # DocEntry = int(row['DocEntry'])
        # doc_settings = frappe.get_doc('SAP Settings')


        # reqUrl=doc_settings.sap_b1_url+"Invoices({DocEntry})/Cancel"
        # modfified_Url = reqUrl.format(DocEntry=DocEntry)
        # session = AuthenticateSAPB1()
        # invoiceDetails = session.request("POST", modfified_Url, headers=headersList, verify=False)
        # print(invoiceDetails)
        # print(DocEntry,'DocEntry')
        # Invoice = Single_Invoice(DocEntry)
        # # print(Invoice['DocNum'],'DocNum')
        # Invoice.pop('@odata.metadata', None)
        # Invoice.pop('@odata.etag', None)

        # Delivery_payload = {
        #     "CardCode": Invoice['CardCode'],
        #     "Comments": f"Reconstructed due to a 35% error {Invoice['Comments']}",
        #     "PayToCode": Invoice['PayToCode'],
        #     "ShipToCode": Invoice['ShipToCode'],
        #     "DocDate": Invoice['DocDate'],
        #     "DocDueDate": Invoice['DocDueDate'],
        #     "U_BillingFrom": Invoice['U_BillingFrom'],
        #     "U_BillTo": Invoice['U_BillTo'],
        #     "TransportationCode": 1,
        #     "UseBillToAddrToDetermineTax": 'tYES',
        #     "DocumentLines": []
        # }

        # for Single_DocumentLines in Invoice['DocumentLines']:
        #     lineitem_delivery = {
        #         "LineNum": Single_DocumentLines['LineNum'],
        #         "ItemCode": Single_DocumentLines['ItemCode'],
        #         "AccountCode": Single_DocumentLines['AccountCode'],
        #         'WarehouseCode': Single_DocumentLines['WarehouseCode'],
        #         "Quantity": Single_DocumentLines['Quantity'],
        #         "TaxCode": Single_DocumentLines['TaxCode'],
        #         'TaxType': Single_DocumentLines['TaxType'],
        #         'TaxLiable': Single_DocumentLines['TaxLiable'],
        #         'TaxTotal': Single_DocumentLines['TaxTotal'],
        #         "UnitPrice": Single_DocumentLines['UnitPrice'],
        #         'U_BuyerName': Single_DocumentLines.get('U_BuyerName', ''),
        #         'U_Order': Single_DocumentLines.get('U_Order', ''),
        #         'U_OrderID': Single_DocumentLines.get('U_OrderID', ''),
        #         'U_OrderedOn': Single_DocumentLines.get('U_OrderedOn', ''),
        #         'U_City': Single_DocumentLines.get('U_City', ''),
        #         'U_State': Single_DocumentLines.get('U_State', ''),
        #         'U_PINCode': Single_DocumentLines.get('U_PINCode', ''),
        #         'U_Country': Single_DocumentLines.get('U_Country', ''),
        #         'BatchNumbers': []
        #     }

        #     # Check if 'BatchNumbers' exists and has at least one item
        #     if 'BatchNumbers' in Single_DocumentLines and len(Single_DocumentLines['BatchNumbers']) > 0:
        #         batch_number_info = {
        #             'BatchNumber': Single_DocumentLines['BatchNumbers'][0]['BatchNumber'],
        #             "Quantity": Single_DocumentLines['BatchNumbers'][0]['Quantity'],
        #             "ItemCode":Single_DocumentLines['ItemCode'],
        #         }
        #         lineitem_delivery['BatchNumbers'].append(batch_number_info)

        #     Delivery_payload["DocumentLines"].append(lineitem_delivery)

        
        # print('List of lineitem in delivery payload : ',len(Delivery_payload['DocumentLines']))
        # print('\n\n\n\n',json.dumps(Delivery_payload),'\n\n\n\n')
        # json_df = pd.DataFrame([Delivery_payload])
        # new_file_path = f'/Users/shahilkhan/Downloads/Workspace/Json File/KAIN24_{DocEntry}.json'
        # json_df.to_json(new_file_path, orient='records', lines=True)

    # return None
    pass






# bench --site dev.localhost execute khanal_tech_integrations.utils.safexpress.DiscountError.ChangeCreditNote


@frappe.whitelist()
def ChangeCreditNote():
    df = pd.read_excel('/Users/shahilkhan/Downloads/Workspace/Json File/Error File.xlsx', 'KACN')
    # # print(df,'df')
    for i, row in df.iterrows():
        DocEntry = int(row['DocEntry'])
        print(DocEntry,'DocEntry')
        doc_settings = frappe.get_doc('SAP Settings')


        reqUrl=doc_settings.sap_b1_url+"CreditNotes({DocEntry})/Cancel"
        modfified_Url = reqUrl.format(DocEntry=DocEntry)
        session = AuthenticateSAPB1()
        invoiceDetails = session.request("POST", modfified_Url, headers=headersList, verify=False)
        print(invoiceDetails.text)
        # print(DocEntry,'DocEntry')
        # credit = Single_CreditNote(DocEntry)
        # # print(credit['DocNum'],'DocNum')
        # credit.pop('@odata.metadata', None)
        # credit.pop('@odata.etag', None)

        # Delivery_payload = {
        #     "CardCode": credit['CardCode'],
        #     "Comments": f"Reconstructed due to a 35% error {credit['Comments']}",
        #     "PayToCode": credit['PayToCode'],
        #     "ShipToCode": credit['ShipToCode'],
        #     "DocDate": credit['DocDate'],
        #     "DocDueDate": credit['DocDueDate'],
        #     "U_BillingFrom": credit['U_BillingFrom'],
        #     "U_BillTo": credit['U_BillTo'],
        #     "TransportationCode": 1,
        #     "UseBillToAddrToDetermineTax": 'tYES',
        #     "DocumentLines": []
        # }

        # for Single_DocumentLines in credit['DocumentLines']:
        #     lineitem_delivery = {
        #         "LineNum": Single_DocumentLines['LineNum'],
        #         "ItemCode": Single_DocumentLines['ItemCode'],
        #         "AccountCode": Single_DocumentLines['AccountCode'],
        #         'WarehouseCode': Single_DocumentLines['WarehouseCode'],
        #         "Quantity": Single_DocumentLines['Quantity'],
        #         "TaxCode": Single_DocumentLines['TaxCode'],
        #         'TaxType': Single_DocumentLines['TaxType'],
        #         'TaxLiable': Single_DocumentLines['TaxLiable'],
        #         'TaxTotal': Single_DocumentLines['TaxTotal'],
        #         "UnitPrice": Single_DocumentLines['UnitPrice'],
        #         'U_BuyerName': Single_DocumentLines.get('U_BuyerName', ''),
        #         'U_Order': Single_DocumentLines.get('U_Order', ''),
        #         'U_OrderID': Single_DocumentLines.get('U_OrderID', ''),
        #         'U_OrderedOn': Single_DocumentLines.get('U_OrderedOn', ''),
        #         'U_City': Single_DocumentLines.get('U_City', ''),
        #         'U_State': Single_DocumentLines.get('U_State', ''),
        #         'U_PINCode': Single_DocumentLines.get('U_PINCode', ''),
        #         'U_Country': Single_DocumentLines.get('U_Country', ''),
        #         'BatchNumbers': []
        #     }

        #     # Check if 'BatchNumbers' exists and has at least one item
        #     if 'BatchNumbers' in Single_DocumentLines and len(Single_DocumentLines['BatchNumbers']) > 0:
        #         batch_number_info = {
        #             'BatchNumber': Single_DocumentLines['BatchNumbers'][0]['BatchNumber'],
        #             "Quantity": Single_DocumentLines['BatchNumbers'][0]['Quantity'],
        #             "ItemCode":Single_DocumentLines['ItemCode'],
        #         }
        #         lineitem_delivery['BatchNumbers'].append(batch_number_info)

        #     Delivery_payload["DocumentLines"].append(lineitem_delivery)

        
        # print('List of lineitem in delivery payload : ',len(Delivery_payload['DocumentLines']))
        # print('\n\n\n\n',json.dumps(Delivery_payload),'\n\n\n\n')
        # json_df = pd.DataFrame([Delivery_payload])
        # new_file_path = f'/Users/shahilkhan/Downloads/Workspace/Json File/KACN/KACN24_{DocEntry}.json'
        # json_df.to_json(new_file_path, orient='records', lines=True)

    return None



def Single_Invoice(DocEntry):
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl=doc_settings.sap_b1_url+"Invoices({DocEntry})"
    modfified_Url = reqUrl.format(DocEntry=DocEntry)
    session = AuthenticateSAPB1()
    invoiceDetails = session.request("GET", modfified_Url, headers=headersList, verify=False)
    invoiceDetails_json = invoiceDetails.json()
    # print(invoiceDetails_json)
    return invoiceDetails_json


def Single_CreditNote(DocEntry):
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl=doc_settings.sap_b1_url+"CreditNotes({DocEntry})"
    modfified_Url = reqUrl.format(DocEntry=DocEntry)
    session = AuthenticateSAPB1()
    Credit = session.request("GET", modfified_Url, headers=headersList, verify=False)
    Credit_json = Credit.json()
    # print(Credit_json)
    return Credit_json