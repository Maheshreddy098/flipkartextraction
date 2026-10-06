import requests
import json
import frappe
from khanal_tech_integrations.utils.razorpay.auth import rz_token
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1

url = "https://api.razorpay.com/v1/fund_accounts"

def create_func_account(**kwargs):
    payload = {
                "contact_id"    : kwargs.get('contact_id'), #"cont_KsZoQbS1OaaV6w",
                "account_type"  : "bank_account",
                "bank_account"  : {
                        "name"  : kwargs.get('name'),
                        "ifsc"  : kwargs.get('ifsc_code'),
             "account_number"   : kwargs.get('account_no')}
                }

    headers = {  'Content-Type': 'application/json' }
    response = requests.request("POST", url, headers=headers, data=json.dumps(payload),auth=rz_token())
    return response.json()

def test():
    create_func_account(name='Test',email='email@email.com')

def fetch_all_fund_accounts():
    response = requests.request("GET", url,auth=rz_token())
    return response.json()['items']#[0]['bank_account'].keys()

def fetch_fund_account(id):
    url         = url +str(id)
    response    = requests.request("GET", url,auth=rz_token())
    print(response.text)

def create_from_Vendor(cardcode):
    VendorCode          = cardcode #"V00525"
    session             = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url                 = doc_settings.sap_b1_url+"BusinessPartners('{cardcode}')"
    reqUrl              = Url.format(cardcode=VendorCode)
    empty_payload       = ""
    headersList         =   {
                            "Accept": "*/*",
                            "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                            "Content-Type": "application/json" 
                            }
    response = session.request("GET", reqUrl, data = empty_payload,  headers=headersList,verify=False)
    res      = response.json()
    if  res.get('CardCode') is not None and res['BPBankAccounts'] is not None:
        for bank_details in  res['BPBankAccounts']:
            resDict = create_func_account(contact_id = res['Fax'] ,
                                            name    = bank_details['AccountName'],
                                        ifsc_code   = bank_details['UserNo1'] ,
                                        account_no  = bank_details['AccountNo'],)
            
            print('For vendor :',VendorCode,"The Razorpay acc is",resDict['id'])
    return resDict
##############################################################################
def POST_outgoing_payment(VendorCode,Invc_Amount_list,fund_acc=None,Note=None): #VendorCode,Invoice_docentry ,paid_amount
    
    # Invoice_docentry            = AP_invoice_docentry
    session                     = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Payment_Url                 = doc_settings.sap_b1_url+"VendorPayments"
    Lineitem_Invoice_payload    = {
                                    "CardCode": str(VendorCode),
                                    "TransferAccount": "12200300",
                                    "TransferSum": None,
                                    "Reference1": '',
                                    "Reference2": "TEST_refer",
                                    "CounterReference": None, #"TEST_Counter",
                                    "Remarks": Note, 
                                    "JournalRemarks": "API Outgoing Payments to - " + str(fund_acc),
                                   # "ContactPersonCode": 142,
                                    "ApplyVAT": "tNO",
                                    "Series": 24,
                                    "TransactionCode": "",
                                    "PaymentType": "bopt_None",
                                    "TransferRealAmount": 0.0,
                                    "DocObjectCode": "bopot_OutgoingPayments",
                                    "DocTypte": "rSupplier",
                                    "ControlAccount": "21100100", #to be choosed
                                    "UnderOverpaymentdiffFC": 0.0,
                                    "AuthorizationStatus": "pasWithout",
                                    "PaymentChecks": [],
                                    "PaymentInvoices": [
                                        ]
                                    }
    initial_count = 0
    total_amount   = 0
    
    for single_payable in Invc_Amount_list:
        lineitem_against_invoice = {
                                            "LineNum": 0,
                                            "DocEntry"  : "placeholder docentry",
                                            "SumApplied": "amount_placeholder",   ################
                                            "InvoiceType": "it_PurchaseInvoice",
                                            "InstallmentId": 1
                              }
        lineitem_against_invoice["LineNum"]     = initial_count
        initial_count += 1
        lineitem_against_invoice["DocEntry"]    = single_payable["id"]
        print(single_payable["id"])
        lineitem_against_invoice["SumApplied"]  = single_payable["TotalPayment"]
        total_amount += single_payable["TotalPayment"]
        Lineitem_Invoice_payload["PaymentInvoices"].append(lineitem_against_invoice)
    Lineitem_Invoice_payload["TransferSum"]     = total_amount

    print('/n/n/n-----------The Payload---------/n/n',Lineitem_Invoice_payload)
    headersList         =   {
                            "Accept": "*/*",
                            "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                            "Content-Type": "application/json" 
                            }

    response = session.request("POST", Payment_Url, headers=headersList, data=json.dumps(Lineitem_Invoice_payload),verify=False)
    #response = session.request("GET", reqUrl, data = empty_payload,  headers=headersList,verify=False)
    
    resDict = response.json()
    result = None
    if resDict.get('DocNum') is not None:
        result = {'DocNum':resDict['DocNum'],
                    'DocEntry' : resDict['DocEntry']}
    return result
##################################################################


      
###########
# frappe.db.get_list('Razorpay Fund Account',filters={'name_cardcode': 'V00011'},fields=['bank_name', 'account_code'])
######################################
def get_fund_account(cont_id=None,Acc_no=None):
    All_fund_acc = fetch_all_fund_accounts()
    result = None
    for single_acc in All_fund_acc:
        if single_acc['contact_id'] == cont_id and single_acc['bank_account']['account_number'] == Acc_no :
            result =  single_acc['id']
            print(single_acc['bank_account']['account_number'])
    return result
