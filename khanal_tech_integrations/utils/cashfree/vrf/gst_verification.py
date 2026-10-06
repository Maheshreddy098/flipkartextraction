import frappe
import json
import requests

from khanal_tech_integrations.utils.sap import AuthenticateSAPB1

import re
from khanal_tech_integrations.utils.logistics.alert_invoice import get_single_lineitem,updating_email,WareHouseUpdate

from frappe.utils import add_to_date
from khanal_tech_integrations.utils.safexpress.attachpod_to_sap import Update_waybill_and_filePath

headersList = {
        "Accept": "*/*",
        "User-Agent": "Khanal Tech",
        "Content-Type": "application/json" ,
         "Prefer": "odata.maxpagesize=100",
    }

payload={}


# SampleGSTFormat = {
#     "reference_id": 107060,
#     "GSTIN": "29AAFCK9270L1ZU",
#     "legal_name_of_business": "AAR KAY GEE xxxxxASSOCIATESX",
#     "trade_name_of_business": "KHANAL FOODS PRIVATE LIMITED",
#     "center_jurisdiction": "RANGE-BED7",
#     "state_jurisdiction": "LGSTO 036 - Bengaluru",
#     "date_of_registration": "2017-07-01",
#     "constitution_of_business": "Private Limited",
#     "taxpayer_type": "Regular",
#     "gst_in_status": "Active",
#     "last_update_date": "2023-07-11",
#     "nature_of_business_activities": [
#         "Office / Sale Office",
#         "Export",
#         "Warehouse / Depot",
#         "Retail Business",
#         "Others",
#         "Wholesale Business",
#         "Factory / Manufacturing"
#     ],
#     "principal_place_address": "D M Nagappa, No 40, Bengaluru, Mahadevpura Post, Karnataka, 560037",
#     "additional_address_array": [
#         {
#             "address": "38 and 39, kacherakanahalli, Soukya road, Bengaluru Rural, Karnataka, 560067"
#         },
#         {
#             "address": "Malur Industrial Area, Sy. No.130,256,259,268 and 283, Kolar,, Hosakote Village Lakkur Hobli Malur Taluk, Bengaluru Rural, Karnataka, 563130"
#         },
#         {
#             "address": "NO. 42/1 and  43,, JADIGENAHALLI HOBLI, HOSKOTE TALUK, Bengaluru,, KACHERAKANAHALLI VILLAGE, Bengaluru Rural, Karnataka, 560067"
#         },
#         {
#             "address": "Venkatapura Villages,, Marasandra and Madnahatti, Dist -Kolar, Malur, Bangalore,, Kasaba Hobli, Malur Taluk, Kolar, Karnataka, 563130"
#         },
#         {
#             "address": "Plot No.3, Bangalore, Mahadevapura, Whitefield Road, Bengaluru Urban, Karnataka, 560048"
#         },
#         {
#             "address": "99/2, Doddaballapur, Hegadihalli Village, Thoobagere Hobli, Bengaluru Rural, Karnataka, 561205"
#         },
#         {
#             "address": "Plot Nos 179 and 192, Malur, Malur Phase II Industrial Area, Kolar, Karnataka, 563130"
#         },
#         {
#             "address": "No.G 02 Ground Floor, Plot 72 and 73, Bengaluru, Hoodi Village , KR Puram Hobli, Whitefield, Bengaluru Urban, Karnataka, 560066"
#         }
#     ],
#     "valid": True,
#     "message": "GSTIN Exists"
# }




@frappe.whitelist()
def GST_Validation(GST_Number):
    # print(GST_Number,'in GST_Validation')
    req_url = "https://api.cashfree.com/verification/gstin"
    headers = {
    'x-client-id': 'CF525029CJM9GDF3NHKFSHPJCN80',
    'x-client-secret': '550168bc65b663152c8e2aec8c10918f3b625449',
    'Content-Type': 'application/json'
    }
    payload = json.dumps({
    "GSTIN": GST_Number,
    "businessName": ""
    })
    response = requests.request("POST", req_url, headers=headers, data=payload)
    # print(response)
    data = response.json()
    return data 


    

@frappe.whitelist()
def check_gst_validity(docname):
    print(docname,'docname')
    doc = frappe.get_doc('SAP Vendor Registration', docname)
    print(doc.gst_number,'$'*10)
    print(doc,'doc')
    
    response=GST_Validation(doc.gst_number)
    response =200
    if response.status_code == 200:
        print('if')
        data = response.json()  
        if data['message'] =='GSTIN Exists':
           
            Gst_Formated_String = f"""
                Legal Name of Business    : {data.get("legal_name_of_business", "")}
                Trade Name of Business    : {data.get("trade_name_of_business", "")}
                Center Jurisdiction       : {data.get("center_jurisdiction", "")}
                State Jurisdiction        : {data.get("state_jurisdiction", "")}
                Date of Registration      : {data.get("date_of_registration", "")}
                Constitution of Business  : {data.get("constitution_of_business", "")}
                Taxpayer Type             : {data.get("taxpayer_type", "")}
                Gst Status                : {data.get("gst_in_status", "")}
                Last Update Date          : {data.get("last_update_date", "")}
                Principal Place Address   : {data.get("principal_place_address", "")}
                Valid                     : {data.get("valid", "")}
                Message                   : {data.get("message", "")}
            """

            doc.gst_details             =Gst_Formated_String
        else:
            Gst_Formated_String = f"""
                                Message                   : {data["message"]}
                                """
            doc.gst_details             =Gst_Formated_String
            
    else:
        Gst_Formated_String = f"""
                                Message                   : "GST Number is invalid or verification failed"
                            """
        doc.gst_details             =Gst_Formated_String
    doc.save()
    frappe.db.commit()
    



# bench --site dev.localhost execute khanal_tech_integrations.utils.cashfree.vrf.gst_verification.Gst_Verification_API




# ! -------------- -------------- -------------- -------------- -------------- New Code -------------- -------------- -------------- -------------- -------------- -------------- --------------


@frappe.whitelist()
def Gst_Verification_API():
    session = AuthenticateSAPB1()
    Today = frappe.utils.nowdate()
    FilterDate = add_to_date(Today,days=-1)

    doc_settings = frappe.get_doc('SAP Settings')
    # reqUrl = doc_settings.sap_b1_url+"BusinessPartners?$filter(UpdateDate ge '{FilterDate}')" 
    req_url = f"{doc_settings.sap_b1_url}BusinessPartners?$filter=UpdateDate ge '{FilterDate}'"

    # Modified_count_url = reqUrl.format(FilterDate=FilterDate)
    response = session.request("GET", req_url, data=payload,  headers=headersList,verify=False)
    bp_master = dict(response.json())
    # print (bp_master)
    
    # for i in range(1,2):
    while bp_master.get('odata.nextLink', None):
        update_bp_master(bp_master)
        print (bp_master['odata.nextLink'])
        next_url = doc_settings.sap_b1_url+bp_master['odata.nextLink']
        response = session.request("GET", next_url, data=payload, headers=headersList, verify=False)
        bp_master = dict(response.json())
        
    update_bp_master(bp_master)

def update_bp_master(bp_master):

    for i in range(len(bp_master['value'])):
        bp_code = bp_master['value'][i]['CardCode']
        print(bp_code,'bp_codebp_code')
        Single_valueCheck=SingleCheck(bp_code)

    pass
    

# bench --site dev.localhost execute khanal_tech_integrations.utils.cashfree.vrf.gst_verification.Gst_Verification_API
# bench --site dev.localhost execute  --args "{ 'V01468' }"  khanal_tech_integrations.utils.cashfree.vrf.gst_verification.SingleCheck

def SingleCheck(CardCode):
    print(CardCode,'CardCode')
    session   = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    # mod_reqUrl    = reqUrl.format(CardCode=CardCode)
    req_url = f"{doc_settings.sap_b1_url}BusinessPartners('{CardCode}')"
 
    response = session.request("GET", req_url, payload,  headers=headersList,verify=False)
    BP_Master_Dict = dict(response.json())
    
    for BP_address in BP_Master_Dict['BPAddresses']:
        if BP_address['AddressType'] == "bo_BillTo" and BP_address['GSTIN'] is not None and BP_address['U_Gst_Api_Verified'] == "N":
            gst_respponse = GST_Validation(BP_address['GSTIN'])
      
            # data = SampleGSTFormat
                
            Patch_GST_SAP(BP_address['RowNum'],BP_Master_Dict['CardCode'],BP_Master_Dict['CardName'],gst_respponse,BP_address['AddressName'])
    
    pass



@frappe.whitelist()
def Patch_GST_SAP(RowNum,CardCode,CardName,Gst_Response,AddressName):
    print(CardName,'CardName')
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url                     = doc_settings.sap_b1_url+"BusinessPartners('{CardCode}')"
    reqUrl_modified         = Url.format(CardCode=CardCode)  
    print('\n\n',Gst_Response,'\n\n')
    if "legal_name_of_business" not in Gst_Response or not Gst_Response["legal_name_of_business"]:
        Business_payload = {
            "BPAddresses": [
                {
                    "RowNum": RowNum,
                    "U_Gst_Verified": "N",
                    "U_Gst_Api_Verified": "Y",
                    "AddressName": AddressName,
                    "AddressType": "bo_BillTo",
                    "BPCode": CardCode,
                    "U_Gst_Legal_Name":"GSTIN Doesn't Exist",
                    "U_Gst_Api_Details": "GSTIN Doesn't Exist"

                }
            ]
        }
    else:
        print("Legal  present.")
        legal_name_of_business = str(Gst_Response.get("legal_name_of_business", "")).lower()
        card_name = str(CardName).lower()
        reason_for_rejection = "Reason For Rejection: GST Name And Bp Name is Not Matching\n" if legal_name_of_business != card_name else ""
        formatted_string = f"""{reason_for_rejection}Legal Name of Business: {Gst_Response.get("legal_name_of_business", "null")}\nTrade Name of Business: {Gst_Response.get("trade_name_of_business", "null")}\nCenter Jurisdiction: {Gst_Response.get("center_jurisdiction", "null")}\nState Jurisdiction: {Gst_Response.get("state_jurisdiction", "null")}\nDate of Registration: {Gst_Response.get("date_of_registration", "null")}\nConstitution of Business: {Gst_Response.get("constitution_of_business", "null")}\nTaxpayer Type: {Gst_Response.get("taxpayer_type", "null")}\nGst Status: {Gst_Response.get("gst_in_status", "null")}\nLast Update Date: {Gst_Response.get("last_update_date", "null")}\nPrincipal Place Address: {Gst_Response.get("principal_place_address", "null")}\nValid: {Gst_Response.get("valid", "null")}\nMessage: {Gst_Response.get("message", "null")}"""   
        Business_payload = {
            "BPAddresses": [
                {
                    "RowNum": RowNum,
                    "U_Gst_Verified": "Y" if Gst_Response["legal_name_of_business"].lower() == CardName.lower() else "N",
                    "U_Gst_Api_Verified": "Y",
                    "AddressName": AddressName,
                    "AddressType": "bo_BillTo",
                    "BPCode": CardCode,
                    "U_Gst_Legal_Name":Gst_Response["legal_name_of_business"],
                    "U_Gst_Api_Details": formatted_string

                }
            ]
        }

    json_report = json.dumps(Business_payload)
    # print('\n\n\n',json_report,'\n\n\n')
    response = session.request("PATCH", reqUrl_modified, headers=headersList, data=json_report,verify=False)


    print(response.text)
    print(response,'response')
    return 'GST Patched'




# {'reference_id': 700262, 'GSTIN': '24ACBFA4426F1ZX', 'legal_name_of_business': 'ACTIVE PACKAGING SOLUTIONS', 'trade_name_of_business': 'ACTIVE PACKAGING SOLUTIONS', 'center_jurisdiction': 'RANGE-I', 'state_jurisdiction': 'Ghatak 42 (Vadodara)', 'date_of_registration': '2023-05-12', 'constitution_of_business': 'Partnership', 'taxpayer_type': 'Regular', 'gst_in_status': 'Active', 'last_update_date': '2023-05-12', 'nature_of_business_activities': ['Others'], 'principal_place_address': 'Samanvay Silicon, GF08, Vadodara, Jetalpur Road, Gujarat, 390020', 'valid': True, 'message': 'GSTIN Exists'} response 