
import frappe
import json
import requests
import base64
import time
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
from khanal_tech_integrations.utils.safexpress.auth import AuthenticateSafexpress
from frappe.utils.file_manager import get_file_path
from frappe.utils import file_manager

from frappe.utils import add_to_date
from datetime import datetime  # Added import for datetime

headersList = {
        "Accept": "*/*",
        "User-Agent": "Khanal Tech",
        "Content-Type": "application/json" 
    }


@frappe.whitelist()
def Get_Waybill_in_ArInvoice(Day=4): #
    Today = frappe.utils.nowdate()
    FilterDate = add_to_date(Today,days=-int(Day))
    List_of_INV= frappe.db.get_list('SAP AR Invoice Detail',filters={'series_name': ['in', ["KAIN24","KAIN25" ,"AR2024","AR2025" ,"HRIN24","HRIN25", "MHIN24","MHIN25","KAIN23", "AR2023", "HRIN23", "MHIN23", "Manual"]],'lastupdated_date':['>', FilterDate],'pod_url': ['=', ''],'way_bill_number': ['=', ''] },pluck="docentry" )
    print('lenght of db list is......',len(List_of_INV))
    for Single_Ar in List_of_INV:
        Update_waybill_and_filePath(Single_Ar)

    pass

def Update_waybill_and_filePath(Single_Ar): 
    try:
        doc = frappe.get_doc('SAP AR Invoice Detail', Single_Ar)

        if doc.pod_url:
            print(doc.pod_url, 'POD URL Already Present')
            return  # Exit function if POD already exists

        print('No waybill_and_filePath')

        url = "https://webs.safexpress.com:8443/SafexWaybillTracking/webresources/tracking/all"

        # Prepare possible combinations of series name
        possible_series = [doc.series_name.upper(), doc.series_name.lower()]

        for series in possible_series:
            formatted_doc = f"{series}/{doc.docnum}"
            payload = {
                "docNo": formatted_doc,
                "docType": "INV"
            }

            response = requests.post(url, headers=headersList, json=payload, verify=False)
            print(response, 'Safexpress API Response for', formatted_doc)

            if response.status_code == 200:
                result = response.json()

                if result.get('shipment') and result['shipment'].get('waybill'):
                    doc.way_bill_number = result['shipment']['waybill']
                    doc.save()
                    frappe.db.commit()
                    print(result['shipment']['waybill'], 'Waybill Number Found')

                    # Fetch and format deliveryDate
                    delivery_date_raw = result['shipment'].get('deliveryDate')  # Extract raw delivery date
                    print(delivery_date_raw, 'Raw Delivery Date Found')

                    if delivery_date_raw:
                        try:
                            # Try multiple date formats that Safexpress might use
                            date_formats = [
                                "%d-%b-%Y",  # 25-Nov-2024
                                "%d/%m/%Y",  # 25/11/2024
                                "%Y-%m-%d",  # 2024-11-25
                                "%d-%m-%Y",  # 25-11-2024
                            ]
                            delivery_date_formatted = None
                            
                            for date_format in date_formats:
                                try:
                                    delivery_date_formatted = datetime.strptime(
                                        delivery_date_raw.strip(), date_format
                                    ).strftime("%Y-%m-%d")
                                    break
                                except ValueError:
                                    continue
                            
                            if delivery_date_formatted:
                                doc.pod_date = delivery_date_formatted
                                doc.save()
                                frappe.db.commit()
                                print(delivery_date_formatted, 'Formatted Delivery Date Saved')
                            else:
                                frappe.log_error(
                                    f"Could not parse delivery date: {delivery_date_raw}",
                                    "Safexpress Date Parsing"
                                )
                                print(f"Warning: Could not parse delivery date: {delivery_date_raw}")
                        except Exception as e:
                            error_msg = f"Error formatting delivery date '{delivery_date_raw}': {str(e)}"
                            frappe.log_error(error_msg, "Safexpress Date Parsing")
                            print(error_msg)

                    # Only PATCH SAP if the POD was actually uploaded
                    pod_uploaded = Get_Single_Pod(Single_Ar)
                    if pod_uploaded:
                        PATCH_POD_AR_invoice(Single_Ar)
                    else:
                        print(f"POD not yet available for {Single_Ar} — skipping SAP PATCH")
                    print(doc, 'Document has been Saved after Attaching to SAP')
                    break  # Exit loop after success

            else:
                print(response.status_code, 'API Error:', response.text)

    except Exception as e:
        frappe.log_error(f"Error in Update_waybill_and_filePath for {Single_Ar}: {str(e)}")
        print(f"Exception Occurred for {Single_Ar}:", str(e))


def Get_Single_Pod(docentry):
    """Fetch and upload POD document for a given invoice."""
    try:
        doc = frappe.get_doc('SAP AR Invoice Detail', docentry)
        
        if not doc.way_bill_number:
            print(f"No waybill number for DocEntry {docentry}, skipping POD fetch")
            return None
            
        safexpress_session = AuthenticateSafexpress()
        headersList["x-api-key"] = safexpress_session.api_key
        headersList['authorization'] = safexpress_session.access_token
        headersList['Identifier'] = safexpress_session.identifier
        payload = {}
        req_url = safexpress_session.pod_url + str(doc.way_bill_number)
        
        response = requests.request(
            "GET", 
            req_url, 
            headers=headersList, 
            data=payload,
            timeout=30,  # Add timeout
            verify=False
        )
        print(response, 'AuthenticateSafexpress')
        
        if response.status_code == 200:
            resp_json = response.json()

            # Check if 'data' key is present in the response
            if 'data' in resp_json and resp_json['data'] is not None:
                base64_string = resp_json['data'].get('base64String')
                if base64_string is not None and base64_string != "null":
                    print('base64_string is not none')
                    content_file = resp_json['data']['base64String']
                    tiff_data = base64.b64decode(content_file)
                    timestamp = str(int(time.time()))
                    file_name = doc.series_name + '_' + doc.docnum + '_' + timestamp + '.tiff'

                    # url="https://gmupurbzq9.execute-api.eu-north-1.amazonaws.com/beta/testingbucketsample/"+file_name #!Test
                    url = "https://tg31l9q380.execute-api.us-west-1.amazonaws.com/dev/khanalfoods-fileupload-bucket/" + file_name  #!Live

                    headers = {
                        'Content-Type': 'image/tiff',
                    }
                    # Upload to S3
                    upload_response = requests.put(
                        url, 
                        headers=headers, 
                        data=tiff_data,
                        timeout=60,  # Add timeout for file upload
                        verify=False
                    )
                    
                    if upload_response.status_code in [200, 201]:
                        ar_doc = frappe.get_doc('SAP AR Invoice Detail', doc.docentry)
                        # File_url='https://testingbucketsample.s3.eu-north-1.amazonaws.com/'+file_name #!Test
                        File_url = 'https://khanalfoods-fileupload-bucket.s3.us-west-1.amazonaws.com/' + file_name  #!Live
                        ar_doc.pod_url = File_url
                        ar_doc.pod_status = 'Completed'
                        ar_doc.save()
                        frappe.db.commit()
                        print(f"POD uploaded successfully for DocEntry {docentry}: {File_url}")
                        return File_url
                    else:
                        error_msg = f"S3 upload failed for DocEntry {docentry}: {upload_response.status_code} - {upload_response.text}"
                        frappe.log_error(error_msg, "Safexpress POD Upload")
                        print(error_msg)
                else:
                    print(f"No base64_string for DocEntry {docentry}")
            else:
                print(f"No data in response for DocEntry {docentry}")
        elif response.status_code == 404:
            print(f"POD not found for waybill {doc.way_bill_number} (DocEntry {docentry})")
        else:
            error_msg = f"POD API error for DocEntry {docentry}: {response.status_code} - {response.text}"
            frappe.log_error(error_msg, "Safexpress POD API")
            print(error_msg)
        return None
    except Exception as e:
        error_msg = f"Error in Get_Single_Pod for DocEntry {docentry}: {str(e)}"
        frappe.log_error(error_msg, "Safexpress POD Processing")
        print(error_msg)
        return None
     

def RemovePOD_Link(docentry):
    doc = frappe.get_doc('SAP AR Invoice Detail', docentry)
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url = doc_settings.sap_b1_url + "Invoices({inv_docentry})"
    reqUrl = Url.format(inv_docentry=doc.docentry)
    try:
        if not doc.pod_url:
            # Perform the desired action here
            payload = json.dumps(
                {
                    "U_TN": "",
                    # "TransportationCode": ,
                    "U_TrackingNo": "",
                    "U_Pod_Link": "",
                })
            response = session.request("PATCH", reqUrl, headers=headersList, data=payload, verify=False)
            print(response.text)
            print(response)
            return response
        else:
            print(doc, 'removed waybill because of pod not present')
            doc.way_bill_number = ''
            doc.save()
            frappe.db.commit()
    except Exception as e:
        print(f"An error occurred while processing docentry {docentry}: {str(e)}")



@frappe.whitelist()
def PATCH_POD_AR_invoice(docentry): #
    doc = frappe.get_doc('SAP AR Invoice Detail', docentry)
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url = doc_settings.sap_b1_url + "Invoices({inv_docentry})"
    reqUrl = Url.format(inv_docentry=doc.docentry)

    try:
        if doc.pod_url:
            pod_date = str(doc.pod_date) if doc.pod_date else None
            if not pod_date:
                frappe.log_error(
                    f"pod_date missing for docentry {docentry} — skipping SAP PATCH",
                    "Safexpress POD Patch",
                )
                print(f"pod_date missing for docentry {docentry} — skipping SAP PATCH")
                return None

            payload = json.dumps(
                {
                    "U_TN": "Safexpress",
                    "TransportationCode": 1,
                    "U_TrackingNo": doc.way_bill_number,
                    "U_Pod_Link": doc.pod_url,
                    "U_POD_DATE": pod_date,
                    "U_FrappeGRNKey": "1",
                })
            response = session.request("PATCH", reqUrl, headers=headersList, data=payload, verify=False)
            if response.status_code not in (200, 204):
                frappe.log_error(
                    f"SAP PATCH failed for docentry {docentry}: "
                    f"HTTP {response.status_code} — {response.text[:300]}",
                    "Safexpress POD Patch",
                )
            print(response.text)
            print(response.status_code)
            return response
        else:
            print(doc, 'removed waybill because of pod not present')
            doc.way_bill_number = ''
            doc.pod_status = 'Pending'
            doc.save()
            frappe.db.commit()
    except Exception as e:
        print(f"An error occurred while processing docentry {docentry}: {str(e)}")
# bench --site khanaltech.com execute --args "{ '253' }"  khanal_tech_integrations.utils.safexpress.attachpod_to_sap.Get_Waybill_in_ArInvoice

# https://testingbucketsample.s3.eu-north-1.amazonaws.com/KAIN22_22349_1692958250.tiff

