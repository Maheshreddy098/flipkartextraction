import requests
import json
import frappe
from khanal_tech_integrations.utils.razorpay.auth import rz_token
from khanal_tech_integrations.utils.razorpay.fund_account import create_func_account,get_fund_account
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1

url = "https://api.razorpay.com/v1/contacts"

def create(**kwargs):
    session             = AuthenticateSAPB1()
    payload = json.dumps({
        "name"      : kwargs.get('name'),
        "email"     : kwargs.get('email'),
        "contact"   : kwargs.get('phone'),
        "type"      : "vendor",
        "reference_id": kwargs.get('card_code'),
        "notes": {
            "random_key_1": "Make it so.",
            "random_key_2": "Tea. Earl Grey. Hot."
                }})

    headers = {  'Content-Type': 'application/json' }

    response    = requests.request("POST", url, headers=headers, data=payload,auth=rz_token())
    resDict     = response.json()
    print(payload)
    print(response.text)
    return response.json()

def test():
    create(name='Test',email='email@email.com')

def fetch_all():
    response = requests.request("GET", url,auth=rz_token())

    print(response.text)

def fetch_contact(id):
    url = url +str(id)
    response = requests.request("GET", url,auth=rz_token())

    print(response.text)

@frappe.whitelist()
def create_customer_fromSAP(VendorCode=None): #vendor_code = 'V00033'vendor_code = None, 
    # VendorCode          = "V00525" #vendor_code #
    print(VendorCode)
    session             = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url                 = doc_settings.sap_b1_url+"BusinessPartners('{cardcode}')"
    reqUrl              = Url.format(cardcode=VendorCode)
    empty_payload       = ""
    headersList         =   {
                            "Accept": "*/*",   "Content-Type": "application/json" ,
                            "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                            }
    response = session.request("GET", reqUrl, data = empty_payload,  headers=headersList,verify=False)
    res      = response.json()
    print('Fax-----',res['Fax'])
    resDict = ""
    if  res.get('CardCode') is not None and res.get('Fax') == None:
        print('fax not none')
        
        resDict = create(name       =   res['CardName'], 
                        email       =   res['CardCode'] + '@gmail.com',
                        phone       =   res['Phone1'] ,#'8984575456',
                        card_code   =   res['CardCode'] ) #
        print(resDict)  
        if resDict.get('id') is not None:
            print("Customer created , now PATCH in FAX details")
            patch_payload   = json.dumps({ "Fax": resDict['id']})
            print("Patch Payload :", patch_payload)
            response        = session.request("PATCH", reqUrl, 
                                        data    =   patch_payload,  
                                        headers =   headersList,verify=False)
            print("PATCH response :", response)
        else:
            print('Contact creation failed!!')
    else:
        print("the cont_id is present in FAX")
    # print(response.text)   
    return  response
def get_banklist_Vendor(vendorcode=None): #
    # print(vendorcode)
    VendorCode          = vendorcode #"V00033" #
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
    response    = session.request("GET", reqUrl, data   =   empty_payload,  
                                                headers =   headersList,
                                                verify  =   False   )
    resDict             = response.json()
    first_bank_details = []
    if resDict.get('BPBankAccounts') is not None:
        first_bank_details  = resDict['BPBankAccounts']
    # print(first_bank_details)
    Bank_Minimal_list = []
    ############################
    if first_bank_details != []:
        for item in first_bank_details:
            keysss  = ['BankCode', 'AccountNo','BICSwiftCode', 'UserNo2'] # UserNo2 is the fund account
            dict2   = {x:item[x] for x in keysss }                    # BICSwiftCode is the IFSC
            fund_ac =   get_fund_account(cont_id=resDict['Fax'],Acc_no=dict2['AccountNo'])  
            if fund_ac != None:
                dict2['Fund_Account'] = fund_ac
            else:
                print('Create fund account')
                fresh_fn_acc = create_func_account(contact_id   = resDict['Fax'] ,
                                                        name    = resDict['CardCode'],
                                                    ifsc_code   = dict2['BICSwiftCode'] ,
                                                    account_no  = dict2['AccountNo'],)
                print(fresh_fn_acc)
                if fresh_fn_acc.get(id) is not None:
                    dict2['Fund_Account'] =  fresh_fn_acc['id']      

            Bank_Minimal_list.append(dict2)
    print(Bank_Minimal_list)
    return Bank_Minimal_list

