import frappe
import json
import requests
from jinja2 import Template
import random
from khanal_tech_integrations.utils.cashfree.vrf.auth import AuthenticateCashfree


from khanal_tech_integrations.utils.sap import AuthenticateSAPB1

import re
from khanal_tech_integrations.utils.logistics.alert_invoice import get_single_lineitem,updating_email,WareHouseUpdate

from frappe.utils import add_to_date
import os

headersList = {
        "Accept": "*/*",
        "User-Agent": "Khanal Tech",
        "Content-Type": "application/json" 
    }

@frappe.whitelist()
def Bank_Validation(Ifsc,AccountNumber):
    # print(GST_Number,'in GST_Validation')
    cashfree_session = AuthenticateCashfree()

    req_url = cashfree_session.cashfree_bank_url+"?bankAccount={AccountNumber}&ifsc={Ifsc}"
    modified_url=req_url.format(AccountNumber=AccountNumber,Ifsc=Ifsc)
    headers = {
        'x-client-id': cashfree_session.cashfree_client_id,
        'x-client-secret': cashfree_session.cashfree_secret_id,
        'Content-Type': 'application/json',
        'Authorization': 'Bearer '+ cashfree_session.cashfree_access_token,
        }
    payload=''
    response = requests.request("GET", modified_url, headers=headers, data=payload)
    data = response.json()
    return data
   

# bench --site alpha.localhost execute khanal_tech_integrations.utils.cashfree.vrf.bank_verification.Bank_Validation

# SELECT A LIST OF BP MASTER VENDORS FOR VERIFICATION
@frappe.whitelist()
def SELECT_LIST_OF_BP_MASTER_VENDORS_FOR_VERIFICATION():
    Today = frappe.utils.nowdate()
    FilterDate = add_to_date(Today, days=-1)
    payload = {}
    doc_settings = frappe.get_doc('SAP Settings')

    count_url = doc_settings.sap_b1_url + "BusinessPartners?$apply=filter(UpdateDate ge '{FilterDate}' and U_Bank_Api_Verified eq 'N' and Currency eq 'INR')/aggregate(CardCode with countdistinct as CountDistinct)"
    session = AuthenticateSAPB1()
    Modified_count_url = count_url.format(FilterDate=FilterDate)
    response = session.request("GET", Modified_count_url, data=payload, headers=headersList, verify=False)
    Bpmaster_Count = dict(response.json())

    if Bpmaster_Count.get('value') and len(Bpmaster_Count['value']) > 0:
        counter = Bpmaster_Count['value'][0]['CountDistinct']
        Total = int(counter) // 20 + 1

        for i in range(Total):
            reqUrl = doc_settings.sap_b1_url + "BusinessPartners?$filter=UpdateDate ge '{FilterDate}' and U_Bank_Api_Verified eq 'N' and Currency eq 'INR'&$skip=" 
            
            modified_Url = reqUrl.format(FilterDate=FilterDate) + str(20 * i)
            session = AuthenticateSAPB1()
            response = session.request("GET", modified_Url, data=payload, headers=headersList, verify=False)
            BP_Master_Dict = dict(response.json())

            if BP_Master_Dict.get('value'):
                # Flag to track whether the alert has been sent
                alert_sent = False

                for Single_Bp_data in BP_Master_Dict['value']:

                    # PASS ONE SINGLE VENDOR CODE
                    # WRITE AN INDEPENDENT FUNCTION TO FETCH THE BANK DETAILS FOR THE SINGLE VENDOR


                    for BP_BankDetails in Single_Bp_data.get('BPBankAccounts', []):
                        if (
                            BP_BankDetails.get('AccountNo') and
                            BP_BankDetails['AccountNo'] == Single_Bp_data.get('DefaultAccount')
                        ):
                            print(Single_Bp_data['CardCode'],'CardCode')
                            print(BP_BankDetails['BICSwiftCode'], Single_Bp_data['DefaultAccount'])
                            # Validate the bank details
                            bank_verification_response = Bank_Validation(BP_BankDetails['BICSwiftCode'], Single_Bp_data['DefaultAccount'])

                            if bank_verification_response.get('accountStatusCode') == 'INSUFFICIENT_BALANCE':
                                # Send an alert only if it hasn't been sent before
                                if not alert_sent:
                                    SentAlertMail()
                                    alert_sent = True
                                # Break from the innermost loop
                                break
                            else:
                                # Continue processing if needed
                                Patch_Bank_SAPBPmaster(bank_verification_response, Single_Bp_data['CardCode'])
                                pass
                    
                    # TILL HERE WILL BE AN 

                    i += 1  # Increment the counter

                if alert_sent:
                    # Exit the outer loop if an alert was sent
                    print('Alert sent. Exiting the loop.')
                    break

            # Uncomment the following lines if you want to include the commented code
            elif BP_Master_Dict['value'] is None:
                break

            reqUrl = reqUrl.format(FilterDate=FilterDate) + str(20 * i)
            session = AuthenticateSAPB1()
            response = session.request("GET", reqUrl, data=payload, headers=headersList, verify=False)
            BP_Master_Dict = dict(response.json())

        frappe.msgprint(msg='Data Inserted successfully', title='Success')
        return None

   

    
@frappe.whitelist()
def Patch_Bank_SAPBPmaster(Bank_Response,Ven_CardCode):
    try:
        session = AuthenticateSAPB1() 
        if Bank_Response['status'] =='SUCCESS':
            Bank_Formated_String = f"""Account Status: {Bank_Response.get("accountStatus", "null")}\nName At Bank: {Bank_Response['data'].get("nameAtBank", "null")}\nRef Id: {Bank_Response['data'].get("refId", "null")}\nBank Name: {Bank_Response['data'].get("bankName", "null")}\nCity: {Bank_Response['data'].get("city", "null")}\nBranch: {Bank_Response['data'].get("branch", "null")}\nMicr: {Bank_Response['data'].get("micr", "null")}
            """
            # Bank_Formated_String = f"""Account Status : {Bank_Response["accountStatus"]}\nName At Bank : {Bank_Response['data']["nameAtBank"]}\nRef Id : {Bank_Response['data']["refId"]}\nBank Name : {Bank_Response['data']["bankName"]}\nCity : {Bank_Response['data']["city"]}\nBranch : {Bank_Response['data']["branch"]}\nMicr : {Bank_Response['data']["micr"]}
            #                     """
        else:
            Bank_Formated_String = f"""Message : {Bank_Response["message"]}\nAccount Status : {Bank_Response["accountStatus"]}\nAccount Status Code : {Bank_Response["accountStatusCode"]}
                        """
        doc_settings = frappe.get_doc('SAP Settings')
        Url = f"{doc_settings.sap_b1_url}BusinessPartners('{Ven_CardCode}')"
        # print(Url)
        Business_payload ={
                                "U_Bank_Api_Verified": 'Y',
                                "U_Bank_Api_Details": Bank_Formated_String,
            }
        session             = AuthenticateSAPB1()
        
        # Make the PATCH request with proper error handling
        response = session.request("PATCH", Url, headers=headersList, data=json.dumps(Business_payload),verify=False)
        print(response.text)
        if response.status_code == 204:
            print("Bank information updated successfully")
        else:
            print(f"Failed to update bank information. Status Code: {response.status_code}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

    return 'Bank Patched'

# bench --site dev.localhost execute khanal_tech_integrations.utils.cashfree.vrf.bank_verification.SELECT_LIST_OF_BP_MASTER_VENDORS_FOR_VERIFICATION



# {'status': 'SUCCESS', 'subCode': '200', 'message': 'Bank Account details verified successfully', 'accountStatus': 'VALID', 'accountStatusCode': 'ACCOUNT_IS_VALID', 'data': {'nameAtBank': 'Mr  MUHAMMED SHAHIL', 'refId': '718487736', 'bankName': 'STATE BANK OF INDIA', 'utr': '325010377191', 'city': 'MALAPPURAM', 'branch': 'MONGAM', 'micr': 676002922}}






@frappe.whitelist()
def SentAlertMail():
    file_path = os.path.join(os.path.dirname(__file__), 'emailnotification.html')
    with open(file_path, 'r') as f:
        template_str = f.read()
    template = Template(template_str)
    rendered_message = template.render(
            data='Auto Verification of Bank accounts and GST for newly added Business Partners has been terminated due to insufficient funds in Cashfree wallet. Kindly top-up the wallet to resume Auto Verification'
    )
    email_args={
            #"recipients":['shahil@khanalfoods.com'],
            "recipients":['financeteam@khanalfoods.com','shahil@khanalfoods.com','mratyunjay@khanalfoods.com','harsha@khanalfoods.com','yogesha@khanalfoods.com'],
            "message":rendered_message,
            "subject":'Insifficent funds in Cashfree wallet',    
            }
    frappe.enqueue(method=frappe.sendmail,queue='short',timeout=300, **email_args)
    print('alert message sent')
    




# bench --site beta.khanaltech.com execute khanal_tech_integrations.utils.cashfree.vrf.bank_verification.Update_BankVerification_SAP

# # bench --site khanaltech.com execute  --args "{ 'EMP00062-BP' }"  khanal_tech_integrations.utils.cashfree.vrf.bank_verification.MANUALLY_UPDATE_BANK_VERIFICATION
@frappe.whitelist()
def MANUALLY_UPDATE_BANK_VERIFICATION(CardCode):
    if not CardCode:
        return {"ok": False, "message": "CardCode is required."}

    # Ensure only users with permission can trigger SAP updates from UI.
    # This keeps the method callable from frontend while respecting Frappe permissions.
    if not frappe.has_permission("SAP Vendor Registration", ptype="write"):
        frappe.throw("Not permitted to update bank verification.", frappe.PermissionError)

    payload = ""
    card_codes = [c.strip() for c in str(CardCode).split(",") if c and c.strip()]
    results = []

    stopped_due_to_balance = False

    for single_code in card_codes:
        try:
            doc_settings = frappe.get_doc("SAP Settings")
            url = f"{doc_settings.sap_b1_url}BusinessPartners('{single_code}')"
            session = AuthenticateSAPB1()
            response = session.request(
                "GET", url, data=payload, headers=headersList, verify=False
            )

            if response.status_code != 200:
                results.append(
                    {
                        "card_code": single_code,
                        "status": "sap_fetch_failed",
                        "http_status": response.status_code,
                        "response": (response.text or "")[:500],
                    }
                )
                continue

            bp_master = dict(response.json())
            if bp_master.get("U_Bank_Api_Verified") != "N":
                results.append({"card_code": single_code, "status": "already_verified"})
                continue

            default_account = bp_master.get("DefaultAccount")
            if not default_account:
                results.append(
                    {"card_code": single_code, "status": "missing_default_account"}
                )
                continue

            matched_bank = None
            for bank_row in bp_master.get("BPBankAccounts", []) or []:
                if bank_row.get("AccountNo") and bank_row["AccountNo"] == default_account:
                    matched_bank = bank_row
                    break

            if not matched_bank:
                results.append(
                    {
                        "card_code": single_code,
                        "status": "bank_account_not_found",
                        "default_account": default_account,
                    }
                )
                continue

            ifsc = matched_bank.get("BICSwiftCode")
            if not ifsc:
                results.append(
                    {
                        "card_code": single_code,
                        "status": "missing_ifsc",
                        "default_account": default_account,
                    }
                )
                continue

            bank_verification_response = Bank_Validation(ifsc, default_account)
            if bank_verification_response.get("accountStatusCode") == "INSUFFICIENT_BALANCE":
                # Notify once and stop further processing to avoid spamming Cashfree.
                try:
                    SentAlertMail()
                except Exception:
                    frappe.log_error(
                        frappe.get_traceback(),
                        "SentAlertMail failed in MANUALLY_UPDATE_BANK_VERIFICATION",
                    )
                results.append({"card_code": single_code, "status": "insufficient_balance"})
                stopped_due_to_balance = True
                break

            Patch_Bank_SAPBPmaster(
                bank_verification_response, bp_master.get("CardCode") or single_code
            )
            results.append(
                {
                    "card_code": single_code,
                    "status": "patched",
                    "account_status_code": bank_verification_response.get(
                        "accountStatusCode"
                    ),
                }
            )
        except Exception as e:
            frappe.log_error(
                frappe.get_traceback(),
                f"MANUALLY_UPDATE_BANK_VERIFICATION failed for {single_code}",
            )
            results.append({"card_code": single_code, "status": "error", "error": str(e)})

    message = (
        "Stopped: insufficient balance in Cashfree wallet."
        if stopped_due_to_balance
        else "Bank verification update completed."
    )

    return {"ok": not stopped_due_to_balance, "message": message, "results": results}




# @frappe.whitelist()
# def Update_BankVerification_SAP():
#     Today = frappe.utils.nowdate()
#     FilterDate = add_to_date(Today,days=-1)
#     payload={}
#     print(FilterDate,'FilterDate')
#     doc_settings = frappe.get_doc('SAP Settings')
#     # count_url = doc_settings.sap_b1_url+"Invoices?$apply=filter(UpdateDate ge '{FilterDate}' and U_TrackingNo eq null)/aggregate(DocEntry with countdistinct as CountDistinct)"

#     count_url = doc_settings.sap_b1_url+"BusinessPartners?$apply=filter(UpdateDate ge '{FilterDate}' and U_Bank_Api_Verified eq 'N')/aggregate(CardCode with countdistinct as CountDistinct)"
#     session     = AuthenticateSAPB1()
#     Modified_count_url = count_url.format(FilterDate=FilterDate)
#     response      = session.request("GET", Modified_count_url, data=payload,  headers=headersList,verify=False)
#     Bpmaster_Count = dict(response.json())
#     print(Bpmaster_Count,'Bpmaster_Count')
#     if Bpmaster_Count['value'] is not None and len(Bpmaster_Count['value']) > 0:
#         print(Bpmaster_Count['value'][0]['CountDistinct'])
#         counter = Bpmaster_Count['value'][0]['CountDistinct']
#         print(counter,'counter')
#         Total   = int(counter) // 20 + 1
#         print(Total,'Total')
#         ##############################
#         for i in range(Total):
#             print(i,'count')
#             # INITIALIZATION
#             # reqUrl        = doc_settings.sap_b1_url+"Invoices?$filter=UpdateDate ge '{FilterDate}'and U_TrackingNo eq null&$skip=" 

#             reqUrl        = doc_settings.sap_b1_url+"BusinessPartners?$filter=UpdateDate ge '{FilterDate}'and U_Bank_Api_Verified eq 'N'&$skip=" 
#             modfified_Url = reqUrl.format(FilterDate=FilterDate)  + str(20*i)
#             session       = AuthenticateSAPB1()
#             response      = session.request("GET", modfified_Url, data=payload,  headers=headersList,verify=False)
                
#             BP_Master_Dict = dict(response.json())            
#             if BP_Master_Dict['value'] is not None:
#                 print ('Going into')
#                 for Single_Bp_data in BP_Master_Dict['value']:
#                     # print(Single_Bp_data['CardCode'],'CardCode')
#                     # print(Single_Bp_data['DefaultAccount'],'DefaultAccount')
#                     for BP_BankDetails in Single_Bp_data['BPBankAccounts']: 
#                         if BP_BankDetails['AccountNo'] is not None:                       
#                             if BP_BankDetails['AccountNo'] == Single_Bp_data['DefaultAccount']:
#                                 # print(BP_BankDetails['BICSwiftCode'],'IFSC code')
#                                 # * Bank Validation
#                                 bank_verification_response=Bank_Validation(BP_BankDetails['BICSwiftCode'],Single_Bp_data['DefaultAccount'])
#                                 # print(bank_verification_response,'Bank_Validation Response')
#                                 # * Patch the updated value Validation
#                                 if bank_verification_response['accountStatusCode'] == 'INSUFFICIENT_BALANCE':
#                                     SentAlertMail()
#                                     break  # This will exit the while loop
#                                 else:
#                                     # Continue processing if needed
#                                     Patch_Bank_SAPBPmaster(bank_verification_response,Single_Bp_data['CardCode'])
                            

#                 i += 1
#                 #increment the counter
#             elif BP_Master_Dict['value'] is None:
#                 break
            
            
#             reqUrl    = reqUrl.format(FilterDate=FilterDate)  + str(20*i)
#             session   = AuthenticateSAPB1()
#             response  = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
                
#             BP_Master_Dict = dict(response.json())
#         frappe.msgprint(msg ='Data Inserted successfully',title ='Success')
#         return None
#     pass

# bench --site dev.localhost execute khanal_tech_integrations.utils.cashfree.vrf.bank_verification.Update_BankVerification_SAP




# bench --site khanaltech.com execute  --args "{ 'V00033,V00034,V00181' }"  khanal_tech_integrations.utils.cashfree.vrf.bank_verification.MANUALLY_UPDATE_BANK_VERIFICATION

# V00659
# # bench --site khanaltech.com execute  --args "{ 'V01754' }"  khanal_tech_integrations.utils.cashfree.vrf.bank_verification.MANUALLY_UPDATE_BANK_VERIFICATION

