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
                    "Prefer": "odata.maxpagesize=900",
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



# bench --site dev.localhost execute  --args "('2024-05-01','2024-08-06','Incoming payments upto Aug 08 with DocCurrency' )" khanal_tech_integrations.utils.Report.IncomingPayment.Incomingpayment_Excel

csv_filename = '/Users/shahilkhan/Desktop/WorkSpace/Export/'


@frappe.whitelist()
def Incomingpayment_Excel(FromDate,ToDate,CardCode):


    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')

    reqUrl = doc_settings.sap_b1_url + "IncomingPayments?$filter=DocDate ge '{FromDate}' and DocDate le '{Today}'"
    # reqUrl = doc_settings.sap_b1_url + "CreditNotes?$filter=DocDate ge '{FromDate}' and DocDate le '{Today}' and CardCode eq '{CardCodeName}'"

    modified_Url = reqUrl.format(FromDate=FromDate, Today=ToDate)
    # modified_Url = reqUrl.format(FromDate=FromDate, Today=ToDate,CardCodeName=CardCode)

    print(modified_Url,'modified_Url')
    response = session.request("GET", modified_Url, headers=headersList, verify=False)
    # print(response,'response')
    IncomingPayment_list = dict(response.json())
    # print(IncomingPayment_list,'IncomingPayment_list')
    
    all_data = []
    
    while IncomingPayment_list.get('odata.nextLink', None):
        all_data.extend(update_Incomingpayment(IncomingPayment_list))
        print(IncomingPayment_list['odata.nextLink'])
        next_url = doc_settings.sap_b1_url + IncomingPayment_list['odata.nextLink']
        response = session.request("GET", next_url, headers=headersList, verify=False)
        IncomingPayment_list = dict(response.json())

    all_data.extend(update_Incomingpayment(IncomingPayment_list))
    
    df = pd.DataFrame(all_data)



    
    # df.to_excel(f"{csv_filename}_{CardCode} Part 2.xlsx", index=False)
    return 'File Saved'





@frappe.whitelist()
def IncomingPayment_List(FromDate,ToDate):
    print(FromDate,ToDate,'FromDate,ToDate')

    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')

    reqUrl = doc_settings.sap_b1_url + "IncomingPayments?$filter=DocDate ge '{FromDate}' and DocDate le '{Today}'"
    # reqUrl = doc_settings.sap_b1_url + "CreditNotes?$filter=DocDate ge '{FromDate}' and DocDate le '{Today}' and CardCode eq '{CardCodeName}'"

    modified_Url = reqUrl.format(FromDate=FromDate, Today=ToDate)
    # modified_Url = reqUrl.format(FromDate=FromDate, Today=ToDate,CardCodeName=CardCode)

    print(modified_Url,'modified_Url')
    response = session.request("GET", modified_Url, headers=headersList, verify=False)
    # print(response,'response')
    IncomingPayment_list = dict(response.json())
    # print(IncomingPayment_list,'IncomingPayment_list')
    
    all_data = []
    
    while IncomingPayment_list.get('odata.nextLink', None):
        all_data.extend(update_Incomingpayment(IncomingPayment_list))
        print(IncomingPayment_list['odata.nextLink'])
        next_url = doc_settings.sap_b1_url + IncomingPayment_list['odata.nextLink']
        response = session.request("GET", next_url, headers=headersList, verify=False)
        IncomingPayment_list = dict(response.json())

    all_data.extend(update_Incomingpayment(IncomingPayment_list))
    
    df = pd.DataFrame(all_data)

    return df


#  bench --site dev.localhost execute  --args "('C03516','2024-01-01','2024-08-18' )" khanal_tech_integrations.utils.Report.IncomingPayment.incoming_total


@frappe.whitelist()
def incoming_total(CardCode, FromDate, ToDate):
    """
    Get the total incoming payment amount for a given date range and CardCode
    """
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc("SAP Settings")
    req_url = (
        f"{doc_settings.sap_b1_url}IncomingPayments?$filter="
        f"DocDate ge '{FromDate}' and DocDate le '{ToDate}' and CardCode eq '{CardCode}' "
        f"&$select=DocEntry,TransferSum,DocCurrency,DocRate,PaymentInvoices,Cancelled"
    )

    headersList["Prefer"] = "odata.maxpagesize=3000"
    total_appliedLC = 0
    total_appliedFC = 0

    try:
        response = session.request("GET", req_url, headers=headersList, verify=False)
        response.raise_for_status()  # Raises an HTTPError if the response code was unsuccessful
        total_incoming = response.json()
        print(total_incoming)
        payment_invoices=total_incoming['value']
        # print(payment_invoices)
        # if Type == 'Export':
        #     print('if')
        for SinglePaytemList in payment_invoices:
            # print(len (SinglePaytemList['PaymentInvoices']))
            # ADVANCE PAYMENT / PAYMENT ON ACCOUNT
            if len(SinglePaytemList['PaymentInvoices']) < 1:
                # print ('if',SinglePaytemList["TransferSum"])
                total_appliedLC += SinglePaytemList["TransferSum"]
                total_appliedFC += ((SinglePaytemList["TransferSum"]/SinglePaytemList["DocRate"]) if SinglePaytemList["DocRate"]>0 else 0)  

            # PAYMENT AGAINST INVOICES
            else:
                # print('Normal payment')
                # print(SinglePaytemList['PaymentInvoices'] )
                lineTotalFC = 0
                lineTotalLC = 0
                for invoice in SinglePaytemList['PaymentInvoices']:
                    
                    if invoice["DocRate"]>0: 
                        # in foreign currency
                        lineTotalFC += float(invoice['AppliedFC'])
                    else:
                        # in local currency
                        lineTotalLC += float(invoice['SumApplied'])

                total_appliedFC += lineTotalFC
                total_appliedLC += lineTotalLC
        # else:
        #     print('else')

        #     total_applied = sum(float(item["TransferSum"]) for item in total_incoming if "TransferSum" in item)


          

        # If total is zero, and we expected some results, log or print for further debugging
        # if total_applied == 0.0:
        #     pass
            # print(f"No valid 'TransferSum' found in the response: {total_incoming}")

    except Exception as e:
        # Handle any exceptions that occur during the API request
        frappe.log_error(f"Error in incoming_total: {str(e)}", "Incoming Payment Error")
        print(f"Error fetching incoming total: {str(e)}")
        # total_applied = 0.0




    # print(total_applied,'totaltotal')
    return {'AppliedLC':total_appliedLC,'AppliedFC':total_appliedFC}

def update_Incomingpayment(Invoice_data):
    temp_list = []

    if Invoice_data.get('value'):
        for SingleIncoming in Invoice_data['value']:
            DocEntry = SingleIncoming.get('DocEntry')
            DocNum = SingleIncoming.get('DocNum')
            CardName = SingleIncoming.get('CardName')
            CardCode = SingleIncoming.get('CardCode')
            DocDate = SingleIncoming.get('DocDate')
            DocType=SingleIncoming.get('DocType')
            TransferSum=SingleIncoming.get('TransferSum')
            CounterReference=SingleIncoming.get('CounterReference')
            Remarks=SingleIncoming.get('Remarks')
            JournalRemarks=SingleIncoming.get('JournalRemarks')
            DocCurrency=SingleIncoming.get('DocCurrency')
            if DocCurrency != 'INR':
                FCTotal =SingleIncoming.get('TransferSum')/SingleIncoming.get('DocRate')
            else:
                FCTotal=0
            data = {
                'DocEntry': DocEntry,
                'DocNum': DocNum,
                'DocDate': DocDate,
                'CardCode': CardCode,
                'CardName': CardName,
                'DocType':DocType,
                'TransferSum':TransferSum,
                'CounterReference':CounterReference,
                'Remarks':Remarks,
                'JournalRemarks':JournalRemarks,
                'DocCurrency':DocCurrency,
                'FCTotal':FCTotal
            }

            temp_list.append(data)
              
    else:
        print("No 'value' key found or it is empty")

    return temp_list



