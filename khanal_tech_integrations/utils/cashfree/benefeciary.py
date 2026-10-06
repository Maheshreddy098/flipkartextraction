#%%
import requests, json
import frappe
from khanal_tech_integrations.utils.cashfree.auth import authorize , verify
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
default_url     = frappe.db.get_single_value('Cashfree Settings', 'cashfree_url')
def add():
    token           = authorize()
    verify(token    =   token)
    print(token)

    url             = default_url + "/payout/v1/addBeneficiary"

    Benef_payload   = { "beneId": "BUDD0013",
                        "name"  : "Vendor Buddhiraj", 
                        "email" : "Buddhiraj@cashfree.com",  
                        "phone" : "8972203110",
                  "bankAccount" : "90001144133", 
                        "ifsc"  : "HDFC0000007", 
                    "address1"  : "Babu Street Tech park"  }

    headers = {
                 'Authorization': 'Bearer '+str(token),
                 'Content-Type' : 'text/plain'
                }
    response = requests.request("POST", url, headers=headers, data=json.dumps(Benef_payload))

    print(response.json())
    return None

# %%
def get_beneficiary_detail():
    beneId = "BUDD0011"
    token = authorize()
    # print(token)
    #verify(token=token)
    payload={}

    url = default_url + "/payout/v1/getBeneficiary/BUDD0011" #+ str(beneId) #V0028
    
    headers = {
                'Authorization': 'Bearer ' + str(token),
                }

    response = requests.request("GET", url, headers=headers, data=payload)
    return response.json()

# %%
def create_beneficiary_from_Vendor():
    VendorCode          = "V00525"
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
    response = response.json()
    Benef_payload =     { "beneId"  : "JOHN19011343",
                            "name"  : "john doe", 
                            "email" : "johndoe@cashfree.com",  
                            "phone" : "9876543210",
                    "bankAccount"   : "00111332233", 
                            "ifsc"  : "HDFC0000001", 
                        "address1"  : "ABC Street11", 
                            "city"  : "Bangalore",  
                         "state"    : "Karnataka",  
                        "pincode"   : "560001"
                        }
    if  response.get('CardCode') is not None:
        first_bank_details          = response['BPBankAccounts'][0]
        Benef_payload['beneId']     = first_bank_details['BPCode']
        Benef_payload['name']       = first_bank_details['AccountName']
        # Benef_payload['email']      = None #first_bank_details['BPCode']
        # Benef_payload['phone']      = first_bank_details['Phone']
        Benef_payload['bankAccount']= first_bank_details['AccountNo']
        # Benef_payload['ifsc']       = first_bank_details['BICSwiftCode']
        # Benef_payload['address1']   = first_bank_details['Street']S
        # Benef_payload['city']       = first_bank_details['City']
        # Benef_payload['state']      = None #first_bank_details['BPCode']
        # Benef_payload['pincode']    = first_bank_details['ZipCode']
    ###################################################################
    token = authorize()
    headers = {
                    'Authorization': 'Bearer '+str(token),
                    'Content-Type'  : 'text/plain'
                }
    url = default_url + "/payout/v1/addBeneficiary"

    response = requests.request("POST", url, headers=headers, data=json.dumps(Benef_payload))

    print(response.text)
    return None

# %%
@frappe.whitelist()
def post_payment(vendor_code,amount,docentry): #beneficiary_id , amount
    print("Vendor code is :", vendor_code,"docentry is :",docentry )
    beneficiary_id  = vendor_code #VendorCode from SAP

    token           = authorize()
    verify(token    =   token)
    url =  default_url + "/payout/v1/requestTransfer"

    payment_payload = {
                    "beneId"    : beneficiary_id , 
                    "amount"    : float(amount) ,
                "transferId"    :  str(docentry)  + str(vendor_code) ,      #  "TEST0023", #DOCENTRY + VENDOR CODE
              #"transferMode"    : "string",
                    "remarks"   :  "Test from frontend"
                        }
    print("Transfer id is :" ,payment_payload['transferId'] )
    hheaders = {
                    'Authorization': 'Bearer '+str(token),
                    'Content-Type'  : 'text/plain'
                }
    payment_response = requests.request("POST", url, headers=hheaders, data=json.dumps(payment_payload))
    print(payment_response)
    payment_resp = payment_response.json()
    print(payment_resp)
    
    return payment_response
def PATCH_AP_invoice(): #DocEntry
    docentry = 1098
    session             = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url                 = doc_settings.sap_b1_url+"PurchaseInvoices({ap_invc_code})"
    reqUrl              = Url.format(ap_invc_code=docentry)
    empty_payload       = ""
    headersList         =   {
                            "Accept": "*/*",
                            "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                            "Content-Type": "application/json" 
                            }
    response = session.request("GET", reqUrl, data = empty_payload,  headers=headersList,verify=False)
    resDict  = response.json()

    return resDict


# %%

def post_paym(): #beneficiary_id , amount

    beneficiary_id  = 'V00525' #VendorCode from SAP
    amount          = 75000      #BILL TOTAL / DOC TOTAL
    token           = authorize()
    verify(token    =   token)
    url =  default_url + "/payout/v1/requestTransfer"

    payment_payload = {
                    "beneId"    : beneficiary_id , 
                    "amount"    : 2500, #int(amount) ,
                "transferId"    : "TEST0028", # str(docentry)  + str(vendor_code) ,      #  , #DOCENTRY + VENDOR CODE
              #"transferMode"    : "string",
                    "remarks"   : "test hai bhai"
                        }
    hheaders = {
                    'Authorization': 'Bearer '+str(token),
                    'Content-Type'  : 'text/plain'
                }
    payment_response = requests.request("POST", url, headers=hheaders, data=json.dumps(payment_payload))
    payment_response = payment_response.json()
    print(payment_response)
    # {"status": "PENDING", "subCode": "201", "message": "Transfer request pending at the bank", "data": {"referenceId": "23796736", "utr": "", "acknowledged": 0}}
    
    return payment_response

# %%
def get_cashfree_status(trasnferid):

    empty_payload = {}

    token           = authorize()
    verify(token    =   token)
    url             =  default_url +  "/payout/v1/getTransferStatus?transferId=" + str(trasnferid)

    hheaders = {
                    'Authorization': 'Bearer '+str(token),
                    'Content-Type'  : 'text/plain'
                }
    payment_response = requests.request("GET", url, headers=hheaders, data=json.dumps(empty_payload))
    payment_response = payment_response.json()
    print(payment_response)
    #print(payment_response['data']['transfer']['status'])
    #print(payment_response['data']['transfer']['reason'])
    result = '--'
    if payment_response.get('data') is not None:
        result = payment_response['data']['transfer']['status']
        print(payment_response['data']['transfer'])
    else:
        print("Null response")

    return result
