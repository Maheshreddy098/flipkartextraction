import requests, json
import frappe
from khanal_tech_integrations.utils.cashfree.auth import authorize , verify
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
default_url     = frappe.db.get_single_value('Cashfree Settings', 'cashfree_url')

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
    print('Payment rrsponse is :', payment_response)
    
    payment_resp = payment_response.json()
    print(payment_resp['status'] ,'payment subcode ----', payment_resp['subCode'])
    if payment_resp.get('data') is not None:
        refr_ID = payment_resp['data']['referenceId']
        PATCH_AP_invoice(DocEntry=docentry , referenceID=refr_ID)
    print('ggg',payment_resp['subCode'])
    response=payment_resp['subCode']
    return  response 
# {"status": "PENDING", "subCode": "201", "message": "Transfer request pending at the bank", "data": {"referenceId": "23796736", "utr": "", "acknowledged": 0}}
# {'status': 'ERROR', 'subCode': '400', 'message': 'Transfer Id already exists'}
# {'status': 'ERROR', 'subCode': '404', 'message': 'Beneficiary does not exist'}

def PATCH_AP_invoice(DocEntry,referenceID): #
    # docentry            = 2325
    # referenceID          = "TEST001"
    session             = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url                 = doc_settings.sap_b1_url+"PurchaseInvoices({ap_invc_code})"
    reqUrl              = Url.format(ap_invc_code=DocEntry)
    empty_payload       = ""
    headersList         =   {
                            "Accept": "*/*",
                            "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                            "Content-Type": "application/json" 
                            }
    payload = json.dumps({ "U_TN": referenceID})
    headers = {
                    'Content-Type': 'text/plain',
                    }

    response = session.request("PATCH", reqUrl, headers=headersList, data=payload,verify=False)
    #response = session.request("GET", reqUrl, data = empty_payload,  headers=headersList,verify=False)
    print(response.text)
    #resDict  = response.json()

    return None

