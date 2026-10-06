import requests
import json
import frappe
from frappe.utils import add_to_date, now, get_datetime, now_datetime
import pandas as pd
from datetime import datetime, timedelta
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1

# csv_filename = '/Users/shahilkhan/Desktop/WorkSpace/MTR/'

headersList = {
                    "Accept": "*/*",
                    "User-Agent": "Khanal Tech",
                    "Content-Type": "application/json",
                    "Prefer": "odata.maxpagesize=300",
                }
payload = ''


#  'Snapdeal'      : 'C02574',
#  'Amazon_IN_API' : 'C01186',
#  'CRED'          : 'C03358',
#  'FLIPKART'      : 'C03121',
#  'DOGSEE_SITE_IN': 'C00623',
#  'HN_SITE_IN'    : 'C01026',
#  'ONDC_NSTORE'   : 'C03494',
#  'AMAZON_FBA_IN_BOM5' : 'C01186',


# bench --site dev.localhost execute  --args "('2024-06-01','2024-07-31','June 01 to July 31 Ar invoice' )"  khanal_tech_integrations.utils.Report.Ar_invoice.Invoice_Excel



csv_filename = '/Users/harsh/Downloads/'


@frappe.whitelist()
def Invoice_Excel(FromDate,ToDate,CardCode):


    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')

    # reqUrl = doc_settings.sap_b1_url + "Invoices?$filter=DocDate ge '{FromDate}' and DocDate le '{Today}' and CancelStatus ne 'csCancellation'"
    # reqUrl = doc_settings.sap_b1_url + "Invoices?$filter=DocDate ge '{FromDate}' and DocDate le '{Today}' and CardCode eq '{CardCodeName}'"
    req_url = (
    f"{doc_settings.sap_b1_url}Invoices?$filter="
    f"DocDate ge '{FromDate}' and DocDate le '{ToDate}'"
    )
        # f"(CancelStatus ne 'csCancellation' or CancelStatus ne 'csYes')"

    # modified_Url = reqUrl.format(FromDate=FromDate, Today=ToDate)
    # modified_Url = reqUrl.format(FromDate=FromDate, Today=ToDate,CardCodeName=CardCode)

    print(req_url,'modified_Url')
    response = session.request("GET", req_url, headers=headersList, verify=False)
    # print(response,'response')
    Invoice_list = dict(response.json())
    # print(Invoice_list,'Invoice_list')
    
    all_data = []
    
    while Invoice_list.get('odata.nextLink', None):
        all_data.extend(update_Invoice(Invoice_list))
        print(Invoice_list['odata.nextLink'])
        next_url = doc_settings.sap_b1_url + Invoice_list['odata.nextLink']
        response = session.request("GET", next_url, headers=headersList, verify=False)
        Invoice_list = dict(response.json())

    all_data.extend(update_Invoice(Invoice_list))
    
    df = pd.DataFrame(all_data)



    
    df.to_excel(f"{csv_filename}{CardCode}part 1.xlsx", index=False)
    return 'File Saved'


@frappe.whitelist()
def Ar_Invoice_List(FromDate,ToDate):

    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    req_url = (
    f"{doc_settings.sap_b1_url}Invoices?$filter="
    f"DocDate ge '{FromDate}' and DocDate le '{ToDate}'"
    )

    response = session.request("GET", req_url, headers=headersList, verify=False)
    # print(response,'response')
    Invoice_list = dict(response.json())

    all_data = []

    while Invoice_list.get('odata.nextLink', None):
        all_data.extend(update_Invoice(Invoice_list))
        print(Invoice_list['odata.nextLink'])
        next_url = doc_settings.sap_b1_url + Invoice_list['odata.nextLink']
        response = session.request("GET", next_url, headers=headersList, verify=False)
        Invoice_list = dict(response.json())

    all_data.extend(update_Invoice(Invoice_list))

    df = pd.DataFrame(all_data)

    # df.to_excel(f"{csv_filename}July 01 to 21.xlsx", index=False)

    return df



@frappe.whitelist()
def invoice_total(CardCode, FromDate, ToDate,Type):
    '''
    Get the total invoice amount for a given date range and CardCode
    '''
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc("SAP Settings")
    req_url = (
        f"{doc_settings.sap_b1_url}Invoices?$filter="
        f"DocDate ge '{FromDate}' and DocDate le '{ToDate}' and CardCode eq '{CardCode}'" 
        f"and Cancelled eq 'tNO' &$select=DocTotal,DocTotalFc"
    )

    headersList["Prefer"] = "odata.maxpagesize=3000"

    response = session.request("GET", req_url, headers=headersList, verify=False)
    total_invoice = response.json()
    # print(total_invoice,'total_invoice')
    if Type=='Export':
        # pass
        total = sum(item["DocTotalFc"] for item in total_invoice["value"])
    else:
        total = sum(item["DocTotal"] for item in total_invoice["value"])
    
    return total

def update_Invoice(Invoice_data):
    temp_list = []

    if Invoice_data.get('value'):
        for Single_DN in Invoice_data['value']:
            SingleAr = SingleArInvoice(Single_DN.get('DocEntry'))
            DocEntry = SingleAr.get('DocEntry')
            DocNum = SingleAr.get('DocNum')
            CardName = SingleAr.get('CardName')
            CardCode = SingleAr.get('CardCode')
            DocDate = SingleAr.get('DocDate')
            DocDueDate = SingleAr.get('DocDueDate')
            DocTotal = SingleAr.get('DocTotal')
            VatSum = SingleAr.get('VatSum')
            CancelStatus=SingleAr.get('CancelStatus')
            DocCurrency=SingleAr.get('DocCurrency')
            DocTotalFc=SingleAr.get('DocTotalFc')
            

            for line in SingleAr.get('DocumentLines', []):
                LineNumber = line.get('LineNum')
                ItemCode = line.get('ItemCode')
                BaseQuantity = line.get('Quantity')
                ProductionBaseEntry = line.get('BaseEntry')
                ProductionBaseType = line.get('BaseType')
                Price = line.get('Price')

                batch_numbers = line.get('BatchNumbers')
               
                # print(batch_numbers,'batch_numbers')
                if batch_numbers:
                    for batchline in line.get('BatchNumbers'):
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
                            'ProductionBaseEntry': ProductionBaseEntry,
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
                                    'ProductionBaseEntry': ProductionBaseEntry,
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
                            'ProductionBaseEntry': ProductionBaseEntry,
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


def SingleArInvoice(IN_DocEntry):
    SAPsession =  AuthenticateSAPB1()
    doc_settings    = frappe.get_doc('SAP Settings')
    invoice_Url = doc_settings.sap_b1_url+"Invoices({DocEntry})"
    modfified_Url = invoice_Url.format(DocEntry=IN_DocEntry)   
    response        = SAPsession.request("GET", modfified_Url,   headers=headersList,verify=False)
    Single_Dict  = dict(response.json())
    return Single_Dict

def GetBatchDetails(DocEntry,LineNum,ItemCode):
    SAPsession =  AuthenticateSAPB1()
    doc_settings    = frappe.get_doc('SAP Settings')
    DN_Url = doc_settings.sap_b1_url+"DeliveryNotes({DocEntry})"
    modfified_Url = DN_Url.format(DocEntry=DocEntry)   
    response        = SAPsession.request("GET", modfified_Url,   headers=headersList,verify=False)
    Single_Dict  = dict(response.json())

    for line in Single_Dict.get('DocumentLines', []):
        # print(line.get('ItemCode'),DocEntry,LineNum,ItemCode)
        if line.get('ItemCode') == ItemCode:
            return line.get('BatchNumbers')
    
    
    return []  
