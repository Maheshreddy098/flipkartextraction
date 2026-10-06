import requests
import json
import frappe
from frappe.utils import add_to_date, now, get_datetime, now_datetime
import pandas as pd
from datetime import datetime, timedelta
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1

from khanal_tech_integrations.utils.Report.Ar_invoice import GetBatchDetails

csv_filename = '/Users/shahilkhan/Desktop/WorkSpace/MTR/'

headersList = {
                    "Accept": "*/*",
                    "User-Agent": "Khanal Tech",
                    "Content-Type": "application/json",
                    "Prefer": "odata.maxpagesize=300",
                }
payload = ''


# bench --site dev.localhost execute  --args "('2024-06-01','2024-07-31','June 01 to July 31 Credit Note' )" khanal_tech_integrations.utils.Report.Ar_CreditNote.CreditNote_Excel

csv_filename = '/Users/shahilkhan/Desktop/WorkSpace/'


@frappe.whitelist()
def CreditNote_Excel(FromDate,ToDate,CardCode):


    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')

    reqUrl = doc_settings.sap_b1_url + "CreditNotes?$filter=DocDate ge '{FromDate}' and DocDate le '{Today}'"
    # reqUrl = doc_settings.sap_b1_url + "CreditNotes?$filter=DocDate ge '{FromDate}' and DocDate le '{Today}' and CardCode eq '{CardCodeName}'"

    modified_Url = reqUrl.format(FromDate=FromDate, Today=ToDate)
    # modified_Url = reqUrl.format(FromDate=FromDate, Today=ToDate,CardCodeName=CardCode)

    print(modified_Url,'modified_Url')
    response = session.request("GET", modified_Url, headers=headersList, verify=False)
    # print(response,'response')
    CreditNote_list = dict(response.json())
    # print(CreditNote_list,'CreditNote_list')
    
    all_data = []
    
    while CreditNote_list.get('odata.nextLink', None):
        all_data.extend(update_CreditNote(CreditNote_list))
        print(CreditNote_list['odata.nextLink'])
        next_url = doc_settings.sap_b1_url + CreditNote_list['odata.nextLink']
        response = session.request("GET", next_url, headers=headersList, verify=False)
        CreditNote_list = dict(response.json())

    all_data.extend(update_CreditNote(CreditNote_list))
    
    df = pd.DataFrame(all_data)



    
    df.to_excel(f"{csv_filename}{CardCode}Part 1.xlsx", index=False)
    return 'File Saved'


@frappe.whitelist()
def CreditNote_List(FromDate,ToDate):

    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')

    reqUrl = doc_settings.sap_b1_url + "CreditNotes?$filter=DocDate ge '{FromDate}' and DocDate le '{Today}'"

    modified_Url = reqUrl.format(FromDate=FromDate, Today=ToDate)

    # print(modified_Url,'modified_Url')
    response = session.request("GET", modified_Url, headers=headersList, verify=False)
    # print(response,'response')
    CreditNote_list = dict(response.json())
    # print(CreditNote_list,'CreditNote_list')

    all_data = []

    while CreditNote_list.get('odata.nextLink', None):
        all_data.extend(update_CreditNote(CreditNote_list))
        print(CreditNote_list['odata.nextLink'])
        next_url = doc_settings.sap_b1_url + CreditNote_list['odata.nextLink']
        response = session.request("GET", next_url, headers=headersList, verify=False)
        CreditNote_list = dict(response.json())

    all_data.extend(update_CreditNote(CreditNote_list))

    df = pd.DataFrame(all_data)

    # df.to_excel(f"{csv_filename}{CardCode}.xlsx", index=False)
    return df


@frappe.whitelist()
def credit_note_total(CardCode, FromDate, ToDate,Type):
    """
    Get the total credit note amount for a given date range and CardCode
    """
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc("SAP Settings")
    req_url = (
        f"{doc_settings.sap_b1_url}CreditNotes?$filter="
        f"DocDate ge '{FromDate}' and DocDate le '{ToDate}' and CardCode eq '{CardCode}'"
        f"and Cancelled eq 'tNO' &$select=DocTotal,DocTotalFc"
    )

    headersList["Prefer"] = "odata.maxpagesize=3000"

    response = session.request("GET", req_url, headers=headersList, verify=False)
    total_creditNote = response.json()

    if Type=='Export':
        # pass
        total = sum(item["DocTotalFc"] for item in total_creditNote["value"])
    else:
        total = sum(item["DocTotal"] for item in total_creditNote["value"])
    
    return total


def update_CreditNote(Invoice_data):
    temp_list = []

    if Invoice_data.get('value'):
        for Single_CN in Invoice_data['value']:
            SingleCN = SingleCreditNote(Single_CN.get('DocEntry'))
            DocEntry = SingleCN.get('DocEntry')
            DocNum = SingleCN.get('DocNum')
            CardName = SingleCN.get('CardName')
            CardCode = SingleCN.get('CardCode')
            DocDate = SingleCN.get('DocDate')
            DocDueDate = SingleCN.get('DocDueDate')
            DocTotal = SingleCN.get('DocTotal')
            VatSum = SingleCN.get('VatSum')
            CancelStatus=SingleCN.get('CancelStatus')
            DocCurrency=SingleCN.get('DocCurrency')
            DocTotalFc=SingleCN.get('DocTotalFc')

            for line in SingleCN.get('DocumentLines', []):
                LineNumber = line.get('LineNum')
                ItemCode = line.get('ItemCode')
                BaseQuantity = line.get('Quantity')
                InvoiceBaseEntry = line.get('BaseEntry')
                ProductionBaseType = line.get('BaseType')
                
                Price = line.get('Price')

                batch_numbers = line.get('BatchNumbers', None)
                if batch_numbers is not None:
                    for batchline in line.get('BatchNumbers'):
                        BatchNumber = batchline.get('BatchNumber', '')
                        LineQuantity = batchline.get('Quantity', '')

                        data = {
                            'DocEntry': DocEntry,
                            'DocNum': DocNum,
                            'DocDate': DocDate,
                            'Without Tax': DocTotal - VatSum,
                            'DocTotal': DocTotal,
                            'CardCode': CardCode,
                            'CardName': CardName,
                            'DocDueDate': DocDueDate,
                            'LineNumber': LineNumber,
                            'ItemCode': ItemCode,
                            'BaseQuantity': BaseQuantity,
                            'InvoiceBaseEntry': InvoiceBaseEntry,
                            'ProductionBaseType': ProductionBaseType,
                            'BatchNumber': BatchNumber,
                            'LineQuantity': LineQuantity,
                            'CancelStatus':CancelStatus,
                            'DocTotalFc':DocTotalFc,
                            'DocCurrency':DocCurrency,
                            'Price':Price
                        }

                        temp_list.append(data)    
                else:
                    if line.get('BaseType')== 15:
                        
                        # print(line.get('BaseEntry'),line.get('LineNum'),line.get('ItemCode'),'**********************')
                        batchdetails=GetBatchDetails(line.get('BaseEntry'),line.get('LineNum'),line.get('ItemCode'))
                        # if SingleAr.get('DocEntry') == 29252:
                            # print(batchdetails,'\n\n')
                        if batchdetails is not None:  
                            for batchline in batchdetails:
                                BatchNumber = batchline.get('BatchNumber', '')
                                LineQuantity = batchline.get('Quantity', '')

                                data = {
                                    'DocEntry': DocEntry,
                                    'DocNum': DocNum,
                                    'DocDate': DocDate,
                                    'Without Tax': DocTotal - VatSum,
                                    'DocTotal':DocTotal,
                                    'CardCode': CardCode,
                                    'CardName': CardName,
                                    'DocDueDate': DocDueDate,
                                    'LineNumber': LineNumber,
                                    'ItemCode': ItemCode,
                                    'BaseQuantity': BaseQuantity,
                                    'InvoiceBaseEntry': InvoiceBaseEntry,
                                    'ProductionBaseType': ProductionBaseType,
                                    'BatchNumber': BatchNumber,
                                    'LineQuantity': LineQuantity,
                                    'CancelStatus':CancelStatus,
                                    'DocTotalFc':DocTotalFc,
                                    'DocCurrency':DocCurrency,
                                    'Price':Price

                                }

                                temp_list.append(data)
                    else:
                        data = {
                            'DocEntry': DocEntry,
                            'DocNum': DocNum,
                            'DocDate': DocDate,
                            'Without Tax': DocTotal - VatSum,
                            'DocTotal':DocTotal,
                            'CardCode': CardCode,
                            'CardName': CardName,
                            'DocDueDate': DocDueDate,
                            'LineNumber': LineNumber,
                            'ItemCode': ItemCode,
                            'BaseQuantity': BaseQuantity,
                            'InvoiceBaseEntry': InvoiceBaseEntry,
                            'ProductionBaseType': ProductionBaseType,
                            'BatchNumber': None,
                            'LineQuantity': None,
                            'CancelStatus':CancelStatus,
                            'DocTotalFc':DocTotalFc,
                            'DocCurrency':DocCurrency,
                            'Price':Price

                        }

                        temp_list.append(data)
                   
              
    else:
        print("No 'value' key found or it is empty")

    return temp_list


def SingleCreditNote(CN_DocEntry):
    SAPsession =  AuthenticateSAPB1()
    doc_settings    = frappe.get_doc('SAP Settings')
    invoice_Url = doc_settings.sap_b1_url+"CreditNotes({DocEntry})"
    modfified_Url = invoice_Url.format(DocEntry=CN_DocEntry)   
    response        = SAPsession.request("GET", modfified_Url,   headers=headersList,verify=False)
    Single_Dict  = dict(response.json())
    return Single_Dict
