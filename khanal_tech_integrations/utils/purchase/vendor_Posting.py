



import frappe
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
import json
from khanal_tech_integrations.utils.logistics.alertList import StateList
import time
import requests
import os
from frappe import request
from urllib.parse import urlparse
import io
import base64
import zipfile
from jinja2 import Template
import random
from khanal_tech_integrations.utils.cashfree.vrf.bank_verification import Bank_Validation

# from requests.packages.urllib3.exceptions import InsecureRequestWarning

# requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
headersList = {
        "Accept": "*/*",
        "User-Agent": "Khanal Tech",
        "Content-Type": "application/json" 
    }


@frappe.whitelist()
def PostingVendor_to_SAP(docname):
    doc=frappe.get_doc('SAP Vendor Registration', docname) 
    bill_to=StateList[doc.bill_to_state]
    ship_to=StateList[doc.ship_to_state]

    Files_Uploading_to_AWS(docname)
    # ?------------------------------------------------------
    AttachmentEntry_value=File_Attachment_To_SAP(docname)
    # print(AttachmentEntry_value,'AttachmentEntry_value')
    # ?------------------------------------------------------

    # ?------------------------------------------------------
    Payment_term_Code=Payment_terms_Get(docname)
    # print(Payment_terms_value,'Payment_terms_value')
    # ?------------------------------------------------------
     # ?------------------------------------------------------
    # ! Bank Account Validation
    try:
        Bank_Response = Bank_Validation(doc.ifsc_code, doc.account_number)
        if Bank_Response.get('status') == 'SUCCESS':
            Bank_Formated_String = f"""Account Status: {Bank_Response.get("accountStatus", "null")}\nName At Bank: {Bank_Response['data'].get("nameAtBank", "null")}\nRef Id: {Bank_Response['data'].get("refId", "null")}\nBank Name: {Bank_Response['data'].get("bankName", "null")}\nCity: {Bank_Response['data'].get("city", "null")}\nBranch: {Bank_Response['data'].get("branch", "null")}\nMicr: {Bank_Response['data'].get("micr", "null")}
            """
        else:
            Bank_Formated_String = f"""Message: {Bank_Response.get("message", "null")}\nAccount Status: {Bank_Response.get("accountStatus", "null")}\nAccount Status Code: {Bank_Response.get("accountStatusCode", "null")}
                    """
        doc.bank_details = Bank_Formated_String
    except Exception as e:
        frappe.log_error(f"Cashfree bank validation failed for {docname}: {e}", "Bank Validation Error")
        doc.bank_details = "Bank validation could not be completed automatically. Please verify manually."

    doc.save()
    frappe.db.commit()
    _doc_settings_for_series = frappe.get_doc('SAP Settings')
    _vendor_series = int(_doc_settings_for_series.vendor_bp_series or 86)
    Business_payload = {
        "Series": _vendor_series,
        "CardName": doc.company_name,
        # "Address": doc.address,
        "EmailAddress": doc.email,
        "Phone1": doc.mobile_number,
        "Phone2": doc.telephone_number,
        "Cellular": doc.mobile_number,
        "U_MSME": doc.mesme_present,
        "U_MSME_No":   doc.msmed_number.upper(),
        "CardType": "cSupplier",
        "AttachmentEntry": int(AttachmentEntry_value),
        # "BillToState": bill_to,
        # "ShipToState": ship_to,
        "U_Vtype":doc.vendor_type,
        "UseBillToAddrToDetermineTax" :"tYES",
        "Valid": "tNO",
        "Frozen": "tYES",
        "PayTermsGrpCode":int(Payment_term_Code),
        "SubjectToWithholdingTax": "boYES",
        "AccrualCriteria": "tYES",
        "U_Bank_Api_Verified": 'Y',
        "U_Bank_Api_Details": doc.bank_details,
        "U_IntPOCEmail": doc.internal_point_of_contact,
        "U_Category_Vendors": doc.vendor_category,
        "U_brand_cat_vendors": doc.brand_category_vendor,
        "U_sub_cat_vendors": doc.subcategory_veondor,
        "ContactEmployees": [{
                                "Name":doc.contact_person_name,
                                "Position":doc.designation,
                                "MobilePhone":doc.contact_person_number,
                                "E_Mail":doc.contact_person_email,
                            }],
        "BPAddresses": [
                            {
                                "AddressName": doc.company_name,
                                "Street": doc.address,
                                "State": bill_to,
                                "GSTIN": doc.gst_number.upper(),
                                "MYFType": '',
                                "TaasEnabled": "tYES",
                                "U_UTL_ST_ThLegName": '',
                                "U_UTL_ST_ThTrdName": '',
                                "GstType": 'gstRegularTDSISD',
                                "FederalTaxID": '',
                                "TaxCode": '',
                                "BuildingFloorRoom": "",
                                "AddressType": "bo_BillTo",
                                "AddressName2": '',
                                "AddressName3": '',
                                "TypeOfAddress": '',
                                "StreetNo": '',
                                "Block": '',
                                "ZipCode": doc.bill_to_pincode,
                                "City": '',
                                "County": doc.bill_to_country,
                            },
                            {
                                "AddressName": doc.company_name,
                                "Street": doc.ship_to_address,
                                "State": ship_to,
                                # "GSTIN": "",
                                "MYFType": '',
                                "TaasEnabled": "tYES",
                                "U_UTL_ST_ThLegName": '',
                                "U_UTL_ST_ThTrdName": '',
                                # "GstType": '',
                                "FederalTaxID": '',
                                "TaxCode": '',
                                "BuildingFloorRoom": "",
                                "AddressType": "bo_ShipTo",
                                "AddressName2": '',
                                "AddressName3": '',
                                "TypeOfAddress": '',
                                "StreetNo": '',
                                "Block": '',
                                "ZipCode": doc.ship_to_pincode,
                                "City": '',
                                "County": doc.ship_to_country,
                            },],
        "BPBankAccounts": [
                {
                                "BankCode": doc.bank_code,
                                "AccountNo": doc.account_number,
                                "AccountName": doc.bank_name,
                                "BICSwiftCode": doc.ifsc_code,
                }
            ],
        "BPFiscalTaxIDCollection": [
            {
                                "TaxId0": doc.pan_card_number.upper(),
        },
    ]
    }

    if doc.vendor_code:
        frappe.msgprint(msg ='Vendor Already Created in SAP and The Vendor Code is '+ doc.vendor_code,title ='Success')
    else:
        SAPsession =  AuthenticateSAPB1()
        doc_settings = frappe.get_doc('SAP Settings')
        business_Url = doc_settings.sap_b1_url+"BusinessPartners"
        response = SAPsession.request("POST", business_Url, data=json.dumps(Business_payload),  headers=headersList,verify=False)
        if response.status_code == 400:
            response_data = json.loads(response.text)
            error_value = response_data['error']['message']['value']
            
            frappe.msgprint(msg = error_value,title ='Error')
        else:
            response_data = json.loads(response.text)
            card_code = response_data["CardCode"]
            print(card_code)
            doc.vendor_code = card_code
            doc.save()
            frappe.db.commit() #
            frappe.msgprint(msg ='Vendor created successfully, and the vendor code is '+ card_code,title ='Success')

# ! File  Uploading to  AWS-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@frappe.whitelist()
def Files_Uploading_to_AWS(docname):
    doc = frappe.get_doc('SAP Vendor Registration', docname)
    company_name = doc.company_name
    documents = [
        ("gst_certificate", doc.gst_certificate),
        ("fssai_licence", doc.fssai_licence),
        ("pan_card", doc.pan_card),
        ("gst_declaration_form", doc.gst_declaration_form),
        ("mill_licence", doc.mill_licence),
        ("msme_licence", doc.msme_licence),
        ("msme_declaration", doc.msme_declaration),
        ("standard_for_food_and_safety", doc.standard_for_food_and_safety),
        ("trade_licence", doc.trade_licence),
        ("cancel_cheque", doc.cancel_cheque),
        ("code_of_conduct", doc.code_of_conduct),
        ("food_analysis_report", doc.food_analysis_report),
        ("fsc_certification", doc.fsc_certification),
        ("vendor_agreement", doc.vendor_agreement),
    ]
    base_url = frappe.utils.get_url()
    content_type_dict = {
        'pdf': 'application/pdf',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'ppt': 'application/vnd.ms-powerpoint',
        'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    }
    failed = []
    for doc_type, doc_url in documents:
        if not doc_url or "amazonaws.com" in doc_url:
            continue
        try:
            file_name = os.path.basename(doc_url)
            _, extension = os.path.splitext(file_name)
            unique_filename = f"{company_name}_{doc_type}{extension}"
            url = base_url + doc_url
            response = requests.get(url)
            response.raise_for_status()
            lowercase_extension = extension.lstrip('.').lower()
            content_type = content_type_dict.get(lowercase_extension, 'application/octet-stream')
            aws_upload_url = "https://tg31l9q380.execute-api.us-west-1.amazonaws.com/dev/khanalfoods-fileupload-bucket/" + unique_filename
            aws_response = requests.put(aws_upload_url, headers={'Content-Type': content_type}, data=response.content)
            aws_response.raise_for_status()
            File_url = 'https://khanalfoods-fileupload-bucket.s3.us-west-1.amazonaws.com/' + unique_filename
            doc.set(doc_type, File_url)
            doc.save()
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(f"AWS upload failed for {doc_type} ({docname}): {e}", "Vendor AWS Upload")
            failed.append(doc_type)
    if failed:
        frappe.msgprint(
            f"Warning: {len(failed)} document(s) could not be uploaded to AWS: {', '.join(failed)}. "
            "The vendor will still be created. Please re-upload these files manually.",
            title="Partial Upload Warning",
            indicator="orange"
        )


# @frappe.whitelist()
# def Files_Uploading_to_AWS(docname):
#     doc = frappe.get_doc('SAP Vendor Registration', docname)
#     urls_to_zip = []
#     file_names = []
#     company_name=doc.company_name
#     # Add the URLs of files that are not empty to the list
#     documents = [
#     ("gst_certificate", doc.gst_certificate),
#     ("fssai_licence", doc.fssai_licence),
#     ("pan_card", doc.pan_card),
#     ("gst_declaration_form", doc.gst_declaration_form),
#     ("mill_licence", doc.mill_licence),
#     ("msme_licence", doc.msme_licence),
#     ("msme_declaration", doc.msme_declaration),
#     ("standard_for_food_and_safety", doc.standard_for_food_and_safety),
#     ("trade_licence", doc.trade_licence),
#     ("cancel_cheque", doc.cancel_cheque),
#     ("code_of_conduct", doc.code_of_conduct),
#     ("food_analysis_report", doc.food_analysis_report),
#     ("fsc_certification", doc.fsc_certification),
#     ("vendor_agreement", doc.vendor_agreement),
#     ]

    

#     base_url = 'http://192.168.68.49:8000'
#     # base_url = frappe.utils.get_url()
#     print(base_url,'base_url')
#     file_names = []

#     for doc_type, doc_url in documents:
#         # doc_url cheching amazonaws.com or not
#         if doc_url and "amazonaws.com" not in doc_url:
#             print(doc_url,'doc_url')
#             urls_to_zip.append(base_url + doc_url)
#             file_name = os.path.basename(doc_url)
#             filename, extension = os.path.splitext(file_name)
#             unique_filename = f"{company_name}_{doc_type}{extension}"
#             file_names.append(unique_filename)

#     for url, file_name in zip(urls_to_zip, file_names):
#         try:
#             print(url,file_name,'*'*10)
#             file_extension = url.split('.')[-1]
#             lowercase_extension = file_extension.lower()
            
#             response = requests.get(url)
#             if response.status_code == 200:
#                 content = response.content
#                 # url = "https://tg31l9q380.execute-api.us-west-1.amazonaws.com/dev/khanalfoods-fileupload-bucket/"+file_name #!Live
#                 url="https://gmupurbzq9.execute-api.eu-north-1.amazonaws.com/beta/testingbucketsample/"+file_name #!Test
#                 content_type_dict = {
#                 'pdf': 'application/pdf',
#                 'jpg': 'image/jpeg',
#                 'jpeg': 'image/jpeg',
#                 'png': 'image/png',
#                 'ppt': 'application/vnd.ms-powerpoint',
#                 'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
#                 'doc': 'application/msword',
#                 'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
#                 } 
#                 # checking the extention type       
#                 headers = {
#                     'Content-Type': content_type_dict.get(lowercase_extension, 'application/octet-stream'),  
#                 }

#                 response = requests.put(url, headers=headers, data=content)

#                 if response.status_code == 200:
#                     print("File uploaded successfully.")
#                     File_url='https://testingbucketsample.s3.eu-north-1.amazonaws.com/'+file_name #!Test
#                     # File_url='https://khanalfoods-fileupload-bucket.s3.us-west-1.amazonaws.com/'+file_name #!Live
#                     # spliting the file name to get the field name 
#                     file_changed_name=unique_filename.split("_", 1)[1].rsplit(".", 1)[0]
#                     # Save the url to the filed
#                     print(file_name,'file_name')
#                     print(File_url,'File_url')
#                     print(file_changed_name,'file_changed_name')
#                     setattr(doc, file_changed_name, File_url)
#                     doc.save()
#                     frappe.db.commit()
#                 else:
#                     frappe.throw("Failed to upload the file.")
#                     print(response.text)
#             else:
#                 frappe.throw("Failed to retrieve the file.")
                
#         except Exception as e:
#             frappe.throw(f"Error downloading file: {str(e)}")
#     pass



@frappe.whitelist()
def File_Attachment_To_SAP(docname):
    doc=frappe.get_doc('SAP Vendor Registration', docname) 
    doc_mapping = {
    "fssai_licence": doc.fssai_licence,
    "gst_certificate": doc.gst_certificate,
    "mill_licence": doc.mill_licence,
    "pan_card": doc.pan_card,
    "gst_declaration_form": doc.gst_declaration_form,
    "msme_licence": doc.msme_licence,
    "msme_declaration": doc.msme_declaration,
    "standard_for_food_and_safety": doc.standard_for_food_and_safety,
    "trade_licence": doc.trade_licence,
    "cancel_cheque": doc.cancel_cheque,
    "code_of_conduct": doc.code_of_conduct,
    "food_analysis_report": doc.food_analysis_report,
    "fsc_certification": doc.fsc_certification,
    "vendor_agreement": doc.vendor_agreement,
}

    # Creating Attachment_Payload
    Attachment_Payload = {
        "Attachments2_Lines": [
            {
                "FileName": doc.company_name + "_" + doc_name,
                "SourcePath": doc_value,
                "UserID": "1",
                "U_Bp_Link": doc_value,
            }
            for doc_name, doc_value in doc_mapping.items() if doc_value
        ]
    }

    SAPsession =  AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Attachments2_Url = doc_settings.sap_b1_url+"Attachments2" #Attachments2
    response = SAPsession.request("POST", Attachments2_Url, data=json.dumps(Attachment_Payload),  headers=headersList,verify=False)
    response_data = json.loads(response.text)
    if response.status_code not in (200, 201) or "AbsoluteEntry" not in response_data:
        error_msg = (response_data.get("error", {}).get("message", {}).get("value") or response.text)[:500]
        frappe.throw(f"SAP attachment upload failed: {error_msg}")
    return response_data["AbsoluteEntry"]

# !-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@frappe.whitelist()
def Payment_terms_Get(docname):
    doc=frappe.get_doc('SAP Vendor Registration', docname) 
    # print(doc.payment_terms)
    SAPsession =  AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    # doc_settings.sap_b1_url
    paymenturl = doc_settings.sap_b1_url+"PaymentTermsTypes?$filter=PaymentTermsGroupName eq '{Payment_name}'"
    Payment_Modified_Url = paymenturl.format(Payment_name=doc.payment_terms)
    payload = ""
    paymentresponse = SAPsession.request("GET", Payment_Modified_Url, data=payload,  headers=headersList,verify=False)
    paymentlist = dict(paymentresponse.json())
    rows = paymentlist.get('value') or []
    if not rows:
        frappe.throw(f"Payment term '{doc.payment_terms}' not found in SAP. Please check the payment terms name.")
    PayTermsGrpCode = rows[0]['GroupNumber']
    return PayTermsGrpCode
# !-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

@frappe.whitelist()
def File_To_Public(docname):
    doc = frappe.get_doc('SAP Vendor Registration', docname)
    File_Dict_list = {
        'fssai_licence': os.path.basename(doc.fssai_licence or ''),
        'gst_certificate': os.path.basename(doc.gst_certificate or ''),
        'gst_declaration_form': os.path.basename(doc.gst_declaration_form or ''),
        'mill_licence': os.path.basename(doc.mill_licence or ''),
        'msme_licence': os.path.basename(doc.msme_licence or ''),
        'pan_card': os.path.basename(doc.pan_card or ''),
        'msme_declaration': os.path.basename(doc.msme_declaration or ''),
        'standard_for_food_and_safety': os.path.basename(doc.standard_for_food_and_safety or ''),
        'trade_licence': os.path.basename(doc.trade_licence or ''),
        'cancel_cheque': os.path.basename(doc.cancel_cheque or ''),
        'code_of_conduct': os.path.basename(doc.code_of_conduct or ''),
        'food_analysis_report': os.path.basename(doc.food_analysis_report or ''),
        'fsc_certification': os.path.basename(doc.fsc_certification or ''),
        'vendor_agreement': os.path.basename(doc.vendor_agreement or ''),
    }
    print(len(File_Dict_list),'#'*10)
    # file_dict = {key: value for key, value in File_Dict_list.items() if value is not None}
    file_dict= {key: value for key, value in File_Dict_list.items() if value and value.strip()}

    print(len(file_dict),'@'*10)
    print(file_dict,'!'*10)
    File_ManagerList = list(file_dict.values())
    list_of_doc_file = frappe.db.get_list('File', filters={'file_name': ['in', File_ManagerList]}, fields=['file_name', 'is_private', 'file_url', 'name'], pluck='name')
    for single_file in list_of_doc_file:
        files = frappe.get_doc('File', single_file)
        print(files.is_private,'is_private')
        if files.is_private == 1:
            print('if')
            files.is_private = 0
            try:
                print('try')
                unique_filename = generate_unique_filename(files.file_name,docname)
                # print(unique_filename, '@' * 10)
                files.file_name = unique_filename
                # print(files.file_name, '#' * 10)
                files.save()
                # print(files, '$' * 10)
                #!--------------------------------------------------------------
                File_Names = os.path.basename(files.file_url)
                # print(File_Names, '!' * 10)
                key = next((k for k, v in file_dict.items() if v == File_Names), None)
                if key is not None:
                    setattr(doc, key, files.file_url)
                    doc.save()
                    frappe.db.commit()
                frappe.db.commit()
                frappe.msgprint(msg='The process of setting all files as public has been completed', title='Success')
                #!--------------------------------------------------------------
            except frappe.exceptions.LinkExistsError:
                print('except')
                unique_filename = generate_unique_filename(files.file_name,docname)
                files.file_name = unique_filename
                files.save()
                #!--------------------------------------------------------------
                key = next((k for k, v in file_dict.items() if v == unique_filename), None)
                if key is not None:
                    setattr(doc, key, files.file_url)
                    doc.save()
                    frappe.db.commit()
                frappe.db.commit()
                #!--------------------------------------------------------------
                frappe.msgprint(msg='The process of setting all files as public has been completed', title='Success')
            except Exception as e:
                # print('error','%'*10)
                print(str(e))
            #     print('else except')
            #     files = frappe.get_doc('File', single_file)
            # # print(files.preview_html,'#'*20)
            #     unique_filename = generate_unique_filename(files.file_name,docname)
            #     print(unique_filename,'unique_filename else except')
            #     file_doc = frappe.new_doc('File')
            #     print(file_doc)
            #     file_doc.file_name=unique_filename
            #     file_doc.is_private=0
            #     file_doc.file_size =files.file_size
            #     # file_doc.file_url =files.file_url
            #     file_doc.content_hash =files.content_hash
            #     file_doc.attached_to_name =files.attached_to_name
            #     file_doc.attached_to_doctype =files.attached_to_doctype
            #     file_doc.attached_to_field =files.attached_to_field
            #     file_doc.old_parent =files.old_parent
                


            #     file_doc.save()
            #     print(file_doc,'file_doc')

                # print(unique_filename)
                frappe.msgprint("An error occurred:", str(e))
                # Handle any other exceptions that may occur during the execution of the code

    return None

def generate_unique_filename(original_filename,docname):
    # timestamp = str(int(time.time()))

    doc = frappe.get_doc('SAP Vendor Registration', docname)
    company_name=doc.company_name
    filename, extension = original_filename.rsplit('.', 1)
    unique_filename = f"{filename}_{company_name}.{extension}"
    return unique_filename

# !-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------









# !Downloading All Files -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

@frappe.whitelist()
def download_file(docname):
    doc = frappe.get_doc('SAP Vendor Registration', docname)
    urls_to_zip = []
    file_names = []
    company_name=doc.company_name
    # Add the URLs of files that are not empty to the list
    documents = [
    ("gst_certificate", doc.gst_certificate),
    ("fssai_licence", doc.fssai_licence),
    ("pan_card", doc.pan_card),
    ("gst_declaration_form", doc.gst_declaration_form),
    ("mill_licence", doc.mill_licence),
    ("msme_licence", doc.msme_licence),
    ("msme_declaration", doc.msme_declaration),
    ("standard_for_food_and_safety", doc.standard_for_food_and_safety),
    ("trade_licence", doc.trade_licence),
    ("cancel_cheque", doc.cancel_cheque),
    ("code_of_conduct", doc.code_of_conduct),
    ("food_analysis_report", doc.food_analysis_report),
    ("fsc_certification", doc.fsc_certification),
    ("vendor_agreement", doc.vendor_agreement),
    ]

    # base_url = 'http://192.168.68.49:8000'
    base_url = frappe.utils.get_url()
    print(base_url,'base_url')
    
    file_names = []

    for doc_type, doc_url in documents:
        if doc_url:
            urls_to_zip.append(base_url + doc_url)
            file_name = os.path.basename(doc_url)
            filename, extension = os.path.splitext(file_name)
            unique_filename = f"{company_name}_{doc_type}.{extension}"
            file_names.append(unique_filename)

    

    #create the zip file
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
        for url, file_name in zip(urls_to_zip, file_names):
            try:
                file_content = download_file_content(url)
                zip_file.writestr(file_name, file_content)
            except Exception as e:
                frappe.throw(f"Error downloading file: {str(e)}")

    # Return the base64 encoded content of the zip file
    encoded_zip_content = base64.b64encode(zip_buffer.getvalue()).decode("utf-8")
    return encoded_zip_content

def download_file_content(url):
    with requests.get(url, stream=True) as response:
        response.raise_for_status()
        file_content = io.BytesIO()
        for chunk in response.iter_content(chunk_size=8192):
            file_content.write(chunk)
    return file_content.getvalue()











# khanal_tech_integrations.utils.purchase.vendor_Posting.handle_saved_data
# bench --site dev.localhost execute khanal_tech_integrations.utils.purchase.vendor_Posting.User_Sent_Email
import string
@frappe.whitelist()
def User_Sent_Email(data):
    doc = frappe.get_doc('User', data)
    print(doc)
    characters = string.ascii_letters + string.digits + string.punctuation
    first_name = doc.first_name.capitalize() + '+'
    password = first_name + ''.join(random.choice(characters) for _ in range(10)) 
    print(password,'password')
    doc.new_password= password
    doc.save()
    frappe.db.commit()
    base_url = frappe.utils.get_url()
    # print(base_url,'base_url')
    file_path = os.path.join(os.path.dirname(__file__), 'user_sentmail.html')
    with open(file_path, 'r') as f:
        template_str = f.read()

    template = Template(template_str)
    rendered_message = template.render(
            doc=doc,
            password=password,
            base_url=base_url
    )
    email_args={
            "recipients":doc.email,
            "message":rendered_message,
            "subject":'Welcome To Khanal Foods Pvt Ltd.',    
            }
    frappe.enqueue(method=frappe.sendmail,queue='short',timeout=300, **email_args)
    print("sent_email:", doc.email)









@frappe.whitelist(allow_guest=True)
def get_sap_bank_list():
    """Return the list of banks from SAP's bank master (ODSC table in HANA).
    Used by the vendor registration web form to populate the Bank Name dropdown.
    allow_guest=True because the form is publicly accessible before login.
    """
    from khanal_tech_integrations.unicommerce.reporting.hana.hana_query_engine import HANAReadOnlyQueryEngine
    sap_settings = frappe.get_single("SAP Settings")
    config = {
        "host": sap_settings.hana_host,
        "port": int(sap_settings.hana_port),
        "user": sap_settings.hana_user,
        "password": sap_settings.get_password("hana_password"),
        "schema": sap_settings.hana_schema or "KFL_LIVE",
    }
    engine = HANAReadOnlyQueryEngine(config=config)
    try:
        df = engine.execute_query(
            'SELECT "AbsEntry", "BankCode", "BankName" FROM "KFL_LIVE"."ODSC"'
            ' ORDER BY "BankName"'
        )
        seen = set()
        banks = []
        for _, row in df.iterrows():
            key = (str(row["BankCode"]).strip(), str(row["BankName"]).strip())
            if key in seen:
                continue
            seen.add(key)
            banks.append({"code": key[0], "name": key[1]})
        return banks
    except Exception as e:
        frappe.log_error(f"get_sap_bank_list failed: {e}", "Bank List Error")
        return []
    finally:
        engine.disconnect()


# https://khanalfoods-fileupload-bucket.s3.us-west-1.amazonaws.com/uploading_private.png
# https://testingbucketsample.s3.eu-north-1.amazonaws.com/unique_filename


# bench --site dev.localhost execute khanal_tech_integrations.utils.purchase.vendor_Posting.AWS_s3_File_Attachment


