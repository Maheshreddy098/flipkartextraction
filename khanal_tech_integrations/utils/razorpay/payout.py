import requests
import json
import frappe
from khanal_tech_integrations.utils.razorpay.auth import rz_token
from khanal_tech_integrations.utils.razorpay.contacts import get_banklist_Vendor
from khanal_tech_integrations.utils.razorpay.fund_account import POST_outgoing_payment,get_fund_account
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1

url = "https://api.razorpay.com/v1/payouts"

def create(**kwargs):
    payload =       {
                "account_number"    : "2323230052367951",
                "fund_account_id"   : kwargs.get('fun_acc_id'), #"fa_KtgxeCh3lACu6x",
                        "amount"    : kwargs.get('amount'),
                        "currency"  : "INR",
                        "mode"      : "NEFT", #"IMPS"
                        "purpose"   : "payout",# kwargs.get('remark'),
                "queue_if_low_balance": True,
                "reference_id"      : kwargs.get('out_payment_docentry'),
                "narration"         : None,
                        "notes"     : {
                            "Outgoing_payment_docnum"   : str(kwargs.get('docnum')),
                                "AP_invoice_docnum"     : str(kwargs.get('inv_docnum')),
                                "Transaction_Note"      : str(kwargs.get('note')) 
                                                }
                        }

    headers         = {  'Content-Type': 'application/json' }
    response        = requests.request("POST", url, headers=headers, data=json.dumps(payload),auth=rz_token())
    print('payout response :',response)
    print(response.text)
    status_Code_error = '200'
    if response.json().get('error') is not None:
        error_is    = response.json()['error']['description']
        if error_is == "Minimum transaction amount should be 100 paise":
            status_Code_error = '400'
        elif error_is == "The amount must be an integer.":
            status_Code_error = '405'
    # elif  response.json().get('id') is not None
    else:
        status_Code_error = '200'

    print(status_Code_error)
    return status_Code_error#.json()
#{"error":{"code":"BAD_REQUEST_ERROR","description":"Minimum transaction amount should be 100 paise","source":"business","step":null,"reason":"input_validation_failed","metadata":{},"field":"amount"}}
# {"error":{"code":"BAD_REQUEST_ERROR","description":"The amount must be an integer.","source":"business","step":null,"reason":"input_validation_failed","metadata":{},"field":"amount"}}
def test():
    create(name='Test',email='email@email.com')

def fetch_all():
    reqURL = url + "?account_number=2323230052367951"
    response    = requests.request("GET", reqURL,auth=rz_token())
    return response.json()

def fetch_fund_account(id):
    url         = url +str(id)
    response    = requests.request("GET", url,auth=rz_token())
    return response.json()


@frappe.whitelist()
def create_from_invoice(that_list=None,Bank_account=None,notes=None): 
    #Notes to be used to put some remark in the payment processing page

    res_List = json.loads(that_list)['list']
    print(type(res_List))
    CardCode = res_List[0]['CardCode']
    print(CardCode)
    print(Bank_account, 'bank account input')
    print(notes,'notes ...')
    print(that_list,'List ...')
   
    # DocEntry            =  Docentry #1629
    # session             = AuthenticateSAPB1()
    # doc_settings = frappe.get_doc('SAP Settings')
    # Url                 = doc_settings.sap_b1_url+"PurchaseInvoices({ap_invc_code})"
    # reqUrl              = Url.format(ap_invc_code=DocEntry)
    empty_payload       = ""
    headersList         =   {
                            "Accept": "*/*",
                            "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                            "Content-Type": "application/json" }
    # response = session.request("GET", reqUrl, data = empty_payload,  headers=headersList,verify=False)
    # res      = response.json()
    # # print(res.keys())
    # # print(reqUrl)
    # resDict = None
    # {'DocNUm': '10550', 'DocDate': '0122', 'CardName': 'Hid', 'CardCode': 'V059', 'DocDueDate': '\n      
    #    01-07-2022', 'TotalPayment': 102586.74, 'id': '2647'}
    total_amount   = 0
    AP_invc_docnum = ''
    for single_payable in res_List:
        total_amount += single_payable["TotalPayment"]
        AP_invc_docnum += str(single_payable["DocNUm"]) + "---"

    session             = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url                 = doc_settings.sap_b1_url+"BusinessPartners('{cardcode}')"
    BPUrl              = Url.format(cardcode=CardCode)
        
    response = session.request("GET", BPUrl, data = empty_payload,  headers=headersList,verify=False)
    BPres    = response.json()
    print('FAX',BPres['Fax'])
    #if BPres.get('Fax') is not None:
    fund_account = get_fund_account(cont_id=BPres['Fax'],Acc_no=Bank_account)
    print("Fund account is ",fund_account)
    resDict = None
    if fund_account != None:
        Outgoing_payment_doc = POST_outgoing_payment(
                                VendorCode      =  CardCode,
                            Invc_Amount_list    = res_List,
                                   fund_acc     =  fund_account ,
                                        Note    =   notes) 
        print('Outgoing payment details', Outgoing_payment_doc)
            #result = {'DocNum':resDict['DocNum'], 'DocEntry' : resDict['DocEntry']}
        if Outgoing_payment_doc is not None:
            resDict  = create(   fun_acc_id = fund_account,
                                    vendor_code = CardCode,
                                        amount  = int(float(total_amount) * 100 ) , 
                                        #remark  = 'AP Invoice', #first_bank_details['BICSwiftCode'] ,
                                 #inv_docentry   = "176536",         #reference_id
                                    docnum      = str(Outgoing_payment_doc['DocNum']), #narration & note-1
                                    out_payment_docentry = str(Outgoing_payment_doc['DocEntry']),
                                    inv_docnum  =  AP_invc_docnum,
                                           note = notes )          #Invc ducnum - note2
            if resDict.get('id') is not None:
                session             = AuthenticateSAPB1()
                Url                 = doc_settings.sap_b1_url+"VendorPayments({payment_code})"
                reqUrl              = Url.format(payment_code=Outgoing_payment_doc['DocEntry'])
                headersList         =   {
                                        "Accept": "*/*",
                                        "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                                        "Content-Type": "application/json" 
                                        }
                payload = json.dumps({ "CounterReference": UTR_id,
                                            'Remark':None,
                                            })

                response = session.request("PATCH", reqUrl, headers=headersList, data=payload,verify=False)
                #response = session.request("GET", reqUrl, data = empty_payload,  headers=headersList,verify=False)
                print(response)
            print(resDict,'--razorpay payment status--')
        # else:
        #     resDict = {'error': 'SAP doesnt have fund_acc for this vendor.'}
    return resDict


def PATCH_AP_invoice(DocEntry,referenceID): #
    """
    This function patch in the field U_TN given 
    the docentry of an invoice and the patched value
    """
    session             = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url                 = doc_settings.sap_b1_url+"PurchaseInvoices({ap_invc_code})"
    reqUrl              = Url.format(ap_invc_code=DocEntry)
    headersList         =   {
                            "Accept": "*/*",
                            "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                            "Content-Type": "application/json" 
                            }
    payload = json.dumps({ "U_TN": referenceID})

    response = session.request("PATCH", reqUrl, headers=headersList, data=payload,verify=False)
    #response = session.request("GET", reqUrl, data = empty_payload,  headers=headersList,verify=False)
    print(response.text)
    return None

def PATCH_VendorPayment(DocEntry,UTR_id): #
    """
    This function patch in the field CounterReference given 
    the docentry of an invoice and the patched value - UTR id
    """
    session             = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url                 = doc_settings.sap_b1_url+"VendorPayments({payment_code})"
    reqUrl              = Url.format(payment_code=DocEntry)
    headersList         =   {
                            "Accept": "*/*",
                            "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                            "Content-Type": "application/json" 
                            }
    payload = json.dumps({ "CounterReference": UTR_id})

    response = session.request("PATCH", reqUrl, headers=headersList, data=payload,verify=False)
    #response = session.request("GET", reqUrl, data = empty_payload,  headers=headersList,verify=False)
    print(response)
    return None
def PATCH_VendorPayment(DocEntry,UTR_id): #
    """
    This function patch in the field U_TN given 
    the docentry of an invoice and the patched value
    """
    session             = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url                 = doc_settings.sap_b1_url+"VendorPayments({payment_code})"
    reqUrl              = Url.format(payment_code=DocEntry)
    headersList         =   {
                            "Accept": "*/*",
                            "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                            "Content-Type": "application/json" 
                            }
    payload = json.dumps({ "CounterReference": UTR_id})

    response = session.request("PATCH", reqUrl, headers=headersList, data=payload,verify=False)
    #response = session.request("GET", reqUrl, data = empty_payload,  headers=headersList,verify=False)
    print(response.text)
    return None
def status_update_payment():
    list_of_payouts = fetch_all()['items']
    print(list_of_payouts[0])
    session             = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url                 = doc_settings.sap_b1_url+"VendorPayments({payment_code})"
    empty_paylod        = ""
    headersList         =   {
                            "Accept": "*/*",
                            "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                            "Content-Type": "application/json" 
                            }
    for single_payout in list_of_payouts:
        if single_payout['status'] == 'processed':# or ''
            reqUrl          = Url.format(payment_code   =   single_payout['reference_id'])
            PATCH_payload   = json.dumps({ "CounterReference":single_payout['utr'] })
            response        = session.request("PATCH", reqUrl, headers=headersList, data=PATCH_payload,verify=False)
            print(response)
        elif single_payout['status'] == 'cancelled' or 'rejected':
            reqUrl          = Url.format(payment_code   =   single_payout['reference_id']) + '/Cancel'
            response        = session.request("POST", reqUrl, headers=headersList, data=empty_paylod,verify=False)
            pass
    return None