from xml.dom.expatbuilder import parseString
import requests
import json
import frappe
from frappe.utils import add_to_date, now, get_datetime, now_datetime
import re


from khanal_tech_integrations.utils.sap import AuthenticateSAPB1

headersList = {
                "Accept": "*/*",
                "User-Agent": "Khanal Tech",
                "Content-Type": "application/json" 
            }
countt = {
    "odata.metadata": "$metadata#PurchaseOrders(CountDistinct)",
    "value": [
        {
            "odata.id": None,
            "CountDistinct": 1469
        }
    ]
}
@frappe.whitelist()
def get_AP_invoices():

    """
    Update Delivery Notes from SAP to Khanal Tech Integrations 
    """
    session = AuthenticateSAPB1()
    empty_payload = ''
    doc_settings = frappe.get_doc('SAP Settings')
    Count_url = doc_settings.sap_b1_url+"PurchaseInvoices?$apply=aggregate(DocEntry with countdistinct as CountDistinct)"

    # INITIALIZATION
    
    session       = AuthenticateSAPB1()
    PO_invoice_count_response      = session.request("GET", Count_url, data=empty_payload,  headers=headersList,verify=False)
        
    PO_Invoice_count = dict(PO_invoice_count_response.json())
    PO_invoice_list = []
    
    if PO_Invoice_count.get('value') is not None:
        The_AP_Count = PO_Invoice_count['value'][0]['CountDistinct']
        The_AP_Count = The_AP_Count//20 + 2
        for i in range(The_AP_Count):
            print(i)
            session         = AuthenticateSAPB1()
            reqUrl          = doc_settings.sap_b1_url+"PurchaseInvoices?$skip=" + str(20*i)
            response        = session.request("GET", reqUrl, data=empty_payload,  headers=headersList,verify=False)
            twenty_response = response.json()['value'] #List full of dictionaries
            PO_invoice_list += twenty_response
    PO_invoice_Minimal_list = []
    ############################
    for item in PO_invoice_list:
        keysss = ['DocDate', 'DocEntry','DocNum','CardCode','CardName','NumAtCard','DocTotal', 'DocumentStatus' ]
        dict2 = {x:item[x] for x in keysss }
        PO_invoice_Minimal_list.append(dict2)
    print(PO_invoice_Minimal_list[0])  
    return PO_invoice_list
    #doc_settings.sap_b1_url+BusinessPartners?$apply=filter(startswith(CardCode, 'V' ))/aggregate(CardCode with countdistinct as CountDistinct) 


def get_AP_invoices_forVendor():
    """
    Given a vendor code it will pull 
    all the purchase invoices(APinvoices) for that vendor from SAP 
    """
    vendor_code     = 'V00853'
    empty_payload   = ''
    session         = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl          = doc_settings.sap_b1_url+"PurchaseInvoices?$filter=CardCode eq '{cardcode}' &$skip=0"
    VendorSpeicific_url = reqUrl.format(cardcode=vendor_code)
    twenty_response = session.request("GET", VendorSpeicific_url, data=empty_payload,  headers=headersList,verify=False)
    print(twenty_response)
    twenty_response_v = twenty_response.json()['value'] #List full of dictionaries
    PO_invoice_Minimal_list = []
    ############################
    for item in twenty_response_v:
        keysss = ['DocDate', 'DocEntry','DocNum','CardCode','CardName','NumAtCard','DocTotal', 'DocumentStatus' ]
        dict2 = {x:item[x] for x in keysss }
        PO_invoice_Minimal_list.append(dict2)
    #print(PO_invoice_Minimal_list[0])  
    return  PO_invoice_Minimal_list #PO_invoice_Minimal_list

#func[0]
def get_button_count_forVendor(vendor_Cardcode):

    session = AuthenticateSAPB1()
    empty_payload = ''
    doc_settings = frappe.get_doc('SAP Settings')
    Count_url = doc_settings.sap_b1_url+"PurchaseInvoices?$apply=filter(CardCode eq '{cardcode}')/aggregate(DocEntry with countdistinct as CountDistinct)"
    modfified_Url = Count_url.format(cardcode=vendor_Cardcode)
    ###############################################################greater than equal to -FROmdate- and less than equal to -TO_Date - #####################

    # INITIALIZATION
    
    session       = AuthenticateSAPB1()
    PO_invoice_count_response      = session.request("GET", modfified_Url, data=empty_payload,  headers=headersList,verify=False)
        
    PO_Invoice_count = dict(PO_invoice_count_response.json())
    print(PO_Invoice_count)
    The_AP_Count = 5
    if PO_Invoice_count.get('value') is not None:
        The_AP_Count = int(PO_Invoice_count['value'][0]['CountDistinct'])
        print(The_AP_Count)
        The_AP_Count = The_AP_Count//20 + 1
        print(The_AP_Count,'##')
    return The_AP_Count


@frappe.whitelist()
def get_all_vendors():
    """
    Pull all the vendors present in SAP 
    """
    session             =   AuthenticateSAPB1()
    empty_payload       =   ''
    doc_settings = frappe.get_doc('SAP Settings')
    Count_url           =   doc_settings.sap_b1_url+"BusinessPartners?$apply=filter(startswith(CardCode,'V'))/aggregate(CardCode with countdistinct as CountDistinct)"
    # INITIALIZATION
    session                         =   AuthenticateSAPB1()
    Vendor_count_response           = session.request("GET", Count_url, data=empty_payload,  headers=headersList,verify=False)
        
    Vendor_count                    = dict(Vendor_count_response.json())
    print(Vendor_count)
    Vendor_count_List               = []
    
    if Vendor_count.get('value') is not None:
        The_AP_Count                = int(Vendor_count['value'][0]['CountDistinct'])
        The_AP_Count                = The_AP_Count//20 + 1
        for i in range(The_AP_Count):
            print(i)
            session                 = AuthenticateSAPB1()
            reqUrl                  = doc_settings.sap_b1_url+"BusinessPartners?$filter=startswith(CardCode,'V')&$skip=" + str(20*i)
            response                = session.request("GET", reqUrl, data=empty_payload,  headers=headersList,verify=False)
            twenty_response         = response.json()['value'] #List full of dictionaries
            for vendor in twenty_response:
                doc                 = frappe.new_doc('SAP Vendor Details')
                doc.vendor_code     = vendor['CardCode']
                doc.vendor_name     = vendor['CardName']
                doc.vendor_name     = vendor['CardName']
                # doc.phone           = vendor['CardName']
                # doc.email           = vendor['CardName']
                # doc.bank_account    = vendor['CardName']
                # doc.ifsc_code       = vendor['CardName']
                # doc.address         = vendor['CardName']
                doc.save()
                frappe.db.commit() 


            # Vendor_count_List += twenty_response
    # Vendor_Minimal_list = []
    ############################
    # for item in Vendor_count_List:
    #     keysss = ['CardCode','CardName']
    #     dict2 = {x:item[x] for x in keysss }
    #     Vendor_Minimal_list.append(dict2)
    # print(Vendor_Minimal_list[0])  
    return "Hogaya Bhai sahab"

@frappe.whitelist()
def delete_v():
    x = 'SAP Vendor Details'
    print(len(frappe.get_list(x)))
    for documentt in frappe.get_list(x):
        documentt = frappe.get_doc( x , documentt.name)
        documentt.delete()
    return None
def vendor_pulling_chronjob():
    """
    This function will delete the vendors stored in frappe,
    and repull from SAP
    """
    delete_v()
    get_all_vendors()
    return None


#######################################################################################################

def POST_outgoing_payment(): #VendorCode,Invoice_docentry ,paid_amount
    VendorCode = 'V00033'
    Invoice_docentry = 1629
    paid_amount = 1850


    # docentry            = 2325
    # referenceID          = "TEST001"
    session                     = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Payment_Url                 = doc_settings.sap_b1_url+"VendorPayments"
    Lineitem_Invoice_payload    = {
                                    "CardCode": str(VendorCode),
                                    "TransferAccount": "12200300",
                                    "TransferSum": paid_amount,
                                    "Reference1": "12169",
                                    "Reference2": "TEST_refer",
                                    "CounterReference": "TEST_Counter",
                                    "Remarks": "DummyRazerpay",
                                    "JournalRemarks": "API Outgoing Payments - " + str(VendorCode),
                                    "ContactPersonCode": 142,
                                    "ApplyVAT": "tNO",
                                    "Series": 24,
                                    "TransactionCode": "",
                                    "PaymentType": "bopt_None",
                                    "TransferRealAmount": 0.0,
                                    "DocObjectCode": "bopot_OutgoingPayments",
                                    "DocTypte": "rSupplier",
                                    "ControlAccount": "21100100",
                                    "UnderOverpaymentdiffFC": 0.0,
                                    "AuthorizationStatus": "pasWithout",
                                    "PaymentChecks": [],
                                    "PaymentInvoices": [
                                        {
                                            "LineNum": 0,
                                            "DocEntry"  : Invoice_docentry,
                                            "SumApplied": paid_amount,   ################
                                            "InvoiceType": "it_PurchaseInvoice",
                                            "InstallmentId": 1
                                        }]}
    headersList         =   {
                            "Accept": "*/*",
                            "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                            "Content-Type": "application/json" 
                            }

    response = session.request("POST", Payment_Url, headers=headersList, data=json.dumps(Lineitem_Invoice_payload),verify=False)
    #response = session.request("GET", reqUrl, data = empty_payload,  headers=headersList,verify=False)
    print(response)
    resDict = response.json()
    result = None
    if resDict.get('DocNum') is not None:
        result = resDict['DocNum']

    return result

  