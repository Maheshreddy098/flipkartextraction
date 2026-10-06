import frappe
import json
import requests
from jinja2 import Template
import random
from khanal_tech_integrations.utils.cashfree.vrf.auth import AuthenticateCashfree

import re

from khanal_tech_integrations.utils.sap import AuthenticateSAPB1



from frappe.utils import add_to_date
import os

headersList = {
        "Accept": "*/*",
        "User-Agent": "Khanal Tech",
        "Content-Type": "application/json" 
    }

@frappe.whitelist()
def Get_VendorList_for_Initial_Email():
    """
    Add VendorPayments Email  
    """
    session = AuthenticateSAPB1()
    payload = ''

    today = frappe.utils.nowdate()
    print(today, 'today')
    # 2023-12-14
    FilterDate = add_to_date(today, days=-2)
    # print(filter_date, 'filter_date')
    
    
    doc_settings = frappe.get_doc('SAP Settings')
    count_url = f"{doc_settings.sap_b1_url}VendorPayments?$apply=filter(DocDate ge '{FilterDate}' and U_EmailSent eq 'No' and U_BankIntg eq 'Yes' and not startswith(CardCode, 'EMP'))/aggregate(DocEntry with countdistinct as CountDistinct)"
    
    response = session.request("GET", count_url, data=payload, headers=headersList, verify=False)
    outgoing_response = dict(response.json())
    print(outgoing_response,'outgoing_response')
    
    if 'value' in outgoing_response and outgoing_response['value']:
        counter = outgoing_response['value'][0].get('CountDistinct', 0)
        total = (counter // 20) + 1
        print(total, 'total')
        
        for i in range(total):
            print(i, 'count')
            
            req_url = f"{doc_settings.sap_b1_url}VendorPayments?$filter=DocDate ge '{FilterDate}' and U_EmailSent eq 'No' and U_BankIntg eq 'Yes' and not startswith(CardCode, 'EMP') &$skip={20 * i}"
            # modified_url = req_url.format(filter_date=filter_date)
            
            session = AuthenticateSAPB1()
            response = session.request("GET", req_url, data=payload, headers=headersList, verify=False)
            # print(response.text)
            
            outgoing_payment_list = dict(response.json())
            if 'value' in outgoing_payment_list and outgoing_payment_list['value']:
                print('Going into', i)
                for single_outpayment in outgoing_payment_list['value']:
                    
                    nonsplit_email = single_outpayment.get('U_emalToBeNotif')
                    contact_email = nonsplit_email.split(',') if nonsplit_email else []
                    # print(contact_email, 'contact_email')
                    print(single_outpayment.get('DocEntry'))
                    vendorEmailList=Get_Vendor_EmailList(single_outpayment['CardCode'],single_outpayment['ContactPersonCode'])
                    
                    # Merge the two lists
                    merged_email_list = contact_email + vendorEmailList
                    # Emptylist_SO_doc = []
                    # for item in single_outpayment['PaymentInvoices']:
                    #     Emptylist_SO_doc.append(item['DocEntry'])

                    empty_dict = {}
                    for item in single_outpayment['PaymentInvoices']:
                        empty_dict[item['DocEntry']] = item['SumApplied']

                    # print(empty_dict)
                    PurchaseInvoices_Data=PurchaseInvoices_Response(empty_dict)
                

                    # print(merged_email_list, 'merged_email_list')
                    if merged_email_list:
                        Email_message='Initiated'
                        PaymentReferenceNo=''
                        # print(merged_email_list,'merged_email_list')
                        # single_outpayment.get('CardName')

                        # Sent_OutgoingPayment_mail(merged_email_list,single_outpayment.get('TransferSum'),Email_message,PaymentReferenceNo,PurchaseInvoices_Data,single_outpayment.get('CardName'))
                        Patch_message="Initial Email Sent"
                        result=PATCH_OutgoingPayment(single_outpayment.get('DocEntry'),Patch_message)
                        if result == 204:
                            Sent_OutgoingPayment_mail(merged_email_list,single_outpayment.get('TransferSum'),Email_message,PaymentReferenceNo,PurchaseInvoices_Data,single_outpayment.get('CardName'))
                        else:
                            pass

                    
                    
                i += 1
            else:
                break
            
    else:
        print("'value' key not found in outgoing_response")
    return None

@frappe.whitelist()
def Get_VendorList_for_Conforming_Email():
    """
    Add VendorPayments Email  
    """
    session = AuthenticateSAPB1()
    payload = ''

    today = frappe.utils.nowdate()
    print(today, 'today')
    # filter_date = add_to_date(today, days=-1)
    # print(filter_date, 'filter_date')
  
    doc_settings = frappe.get_doc('SAP Settings')
    count_url = f"{doc_settings.sap_b1_url}VendorPayments?$apply=filter(U_EmailSent eq 'Initial Email Sent' and U_PayRefNo ne 'null')/aggregate(DocEntry with countdistinct as CountDistinct)"
    
    response = session.request("GET", count_url, data=payload, headers=headersList, verify=False)
    outgoing_response = dict(response.json())
    print(outgoing_response,'outgoing_response')
    
    if 'value' in outgoing_response and outgoing_response['value']:
        counter = outgoing_response['value'][0].get('CountDistinct', 0)
        total = (counter // 20) + 1
        print(total, 'total')
        
        for i in range(total):
            print(i, 'count')
            
            req_url = f"{doc_settings.sap_b1_url}VendorPayments?$filter=U_EmailSent eq 'Initial Email Sent' and U_PayRefNo ne 'null'&$skip={20 * i}"
            # modified_url = req_url.format(filter_date=filter_date)
            
            session = AuthenticateSAPB1()
            response = session.request("GET", req_url, data=payload, headers=headersList, verify=False)
            # print(response.text)
            
            outgoing_payment_list = dict(response.json())
            if 'value' in outgoing_payment_list and outgoing_payment_list['value']:
                print('Going into', i)
                for single_outpayment in outgoing_payment_list['value']:
                    
                    nonsplit_email = single_outpayment.get('U_emalToBeNotif')
                    contact_email = nonsplit_email.split(',') if nonsplit_email else []
                    # print(contact_email, 'contact_email')
                    print(single_outpayment.get('DocEntry'))
                    vendorEmailList=Get_Vendor_EmailList(single_outpayment['CardCode'],single_outpayment['ContactPersonCode'])
                    # Merge the two lists
                    merged_email_list = contact_email + vendorEmailList
                    empty_dict = {}
                    for item in single_outpayment['PaymentInvoices']:
                        empty_dict[item['DocEntry']] = item['SumApplied']

                    # print(empty_dict)
                    PurchaseInvoices_Data=PurchaseInvoices_Response(empty_dict)

                    # print(merged_email_list, 'merged_email_list')
                    if merged_email_list:
                        Email_message='Processed'
                        
                        # Sent_OutgoingPayment_mail(merged_email_list,single_outpayment.get('TransferSum'),Email_message,single_outpayment.get('U_PayRefNo'),PurchaseInvoices_Data,single_outpayment.get('CardName'))
                        Patch_message="Conforming Email Sent"
                        result=PATCH_OutgoingPayment(single_outpayment.get('DocEntry'),Patch_message)
                        if result == 204:
                            Sent_OutgoingPayment_mail(merged_email_list,single_outpayment.get('TransferSum'),Email_message,single_outpayment.get('U_PayRefNo'),PurchaseInvoices_Data,single_outpayment.get('CardName'))
                        else:
                            pass           
                        # print(result)
                    
                    
                i += 1
            else:
                break
            
    else:
        print("'value' key not found in outgoing_response")
    return None


# bench --site dev.localhost execute khanal_tech_integrations.utils.Finance.Outgoingpayment.Get_VendorList_for_Initial_Email

# khanal_tech_integrations.utils.Finance.Outgoingpayment.Get_VendorList_for_Initial_Email   
# khanal_tech_integrations.utils.Finance.Outgoingpayment.Get_VendorList_for_Conforming_Email



@frappe.whitelist()
def Get_Vendor_EmailList(CardCode, ContactPersonCode):
    session = AuthenticateSAPB1()
    payload = '' 
    doc_settings = frappe.get_doc('SAP Settings')   
    cardUrl = doc_settings.sap_b1_url + "BusinessPartners('{cardCode}')"
    Modified_cardUrl = cardUrl.format(cardCode=CardCode)

    cardresponse = session.request("GET", Modified_cardUrl, data=payload, headers=headersList, verify=False)
    Details = dict(cardresponse.json())
    LineItems = Details.get('ContactEmployees', [])

    def is_valid_email(email):
        # Basic email validation using a simple regex
        email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        return bool(re.match(email_regex, email))

    result_list = []

    try:
        contact_person_code_int = int(ContactPersonCode)
    except (TypeError, ValueError):
        # Handle the case where ContactPersonCode is None or not a valid integer
        contact_person_code_int = None

    for SingleItem in LineItems:
        if contact_person_code_int is not None and SingleItem.get('InternalCode') == contact_person_code_int:
            email_address = SingleItem.get('E_Mail')
            if email_address and is_valid_email(email_address):
                result_list.append(email_address)

    # Append U_IntPOCEmail if not None and is a valid email
    u_int_poc_email = Details.get('U_IntPOCEmail')
    if u_int_poc_email and is_valid_email(u_int_poc_email):
        result_list.append(u_int_poc_email)


    # print(result_list,'result_list')
    return result_list




@frappe.whitelist()
def Sent_OutgoingPayment_mail(merged_email_list,TotalAmount,Email_message,PaymentReferenceNo,PurchaseInvoices_Data,CardName):

    # print(merged_email_list,'merged_email_list')
    file_path = os.path.join(os.path.dirname(__file__), 'outgoingEmail.html')
    # print(file_path,'filepath')
    with open(file_path, 'r') as f:
        # contents = f.read()
        # print(contents)
        template_str = f.read()
    print(PaymentReferenceNo,'PaymentReferenceNo')
    if PaymentReferenceNo is not None and PaymentReferenceNo != '':
        template_msg = f"and the Reference (UTR) Number is {PaymentReferenceNo}"
    else:
        template_msg = ""  # If PaymentReferenceNo is null or not present, set an empty string or handle it as needed
        

    template = Template(template_str)
    rendered_message = template.render(
            TotalAmount=TotalAmount,
            Email_message=Email_message,
            template_msg=template_msg,
            PurchaseInvoices_Data=PurchaseInvoices_Data,
            CardName=CardName
        )
   
    
    recipients=['shahil@khanalfoods.com','yogesha@khanalfoods.com','harsha@khanalfoods.com']
    # merged_email_list
    email_args={
            "recipients":merged_email_list,
            "message":rendered_message,
            "cc": ['ar@khanalfoods.com'],  # Add the CC email address here
            "subject": f'Notification: Payment  {Email_message} : {CardName}',
            # "subject":`Notification: GRN Uploaded to Draft - Invoice #+12342`,    
                    }
    # print(email_args,'email_args')
    frappe.enqueue(method=frappe.sendmail,queue='short',timeout=300, **email_args)
        # print('sent')
       

def PATCH_OutgoingPayment(DocEntry,Patch_message):
    print(DocEntry,'value')
    print(Patch_message,'Patch_message')
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url                     = doc_settings.sap_b1_url+"VendorPayments({DocEntry})"
    reqUrl_modified         = Url.format(DocEntry=DocEntry)        
    payload = json.dumps({  "U_EmailSent": "" + Patch_message + ""})
    
    session             = AuthenticateSAPB1()
    response = session.request("PATCH", reqUrl_modified, headers=headersList, data=payload,verify=False)
    print(response,'response')
    print(response.text)
    return response.status_code

  






def PurchaseInvoices_Response(PurchaseInvoices_List):
    print(PurchaseInvoices_List,'PurchaseInvoices_List')
    doc_settings = frappe.get_doc('SAP Settings') 
    payload = ''
 
    # List to store results
    results_list = []
    
    for Single_DocEntry in PurchaseInvoices_List:
        session = AuthenticateSAPB1()
        Url = doc_settings.sap_b1_url + "PurchaseInvoices({DocEntry})"
        reqUrl_modified = Url.format(DocEntry=Single_DocEntry) 
        response = session.request("GET", reqUrl_modified, headers=headersList, data=payload, verify=False)
        
        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            AP_Invoice_response = response.json()
            
            # Extract specific fields and create a new dictionary
            new_item = {
                'DocEntry'      : Single_DocEntry,
                'Doc_No'        : AP_Invoice_response.get('DocNum'),
                'Date'          : AP_Invoice_response.get('DocDate'),
                'INV_No'        : AP_Invoice_response.get('NumAtCard'),
                'INV_Date'      : AP_Invoice_response.get('TaxDate'),
                # 'Base_Amt'      : AP_Invoice_response.get('BaseAmount'),
                'Gst'           : AP_Invoice_response.get('VatSum'),
                'TDS'           : AP_Invoice_response.get('WTAmount'),
                'Total_Amt'     : AP_Invoice_response.get('DocTotal'),
                'Pending_Amt'     : int(AP_Invoice_response.get('DocTotal'))-int(AP_Invoice_response.get('PaidToDate')),
                'Paid_Amt'      : PurchaseInvoices_List[Single_DocEntry],
            }
            # Append the new dictionary to the output list
            # Calculate Base_Amt by summing up LineTotal values in DocumentLines
            DocumentLines = AP_Invoice_response.get('DocumentLines')
            Base_Amt = sum(single.get('LineTotal', 0) for single in DocumentLines)

            # Add Base_Amt to the new_item dictionary
            new_item['Base_Amt'] = Base_Amt
            results_list.append(new_item)
            
        else:
            print(f"Failed to retrieve data for DocEntry {Single_DocEntry}. Status Code: {response.status_code}")


    # print(results_list,'results_list')
    print(f"\n\n\n\n{results_list}\n\n\n",'results_list')
    return results_list