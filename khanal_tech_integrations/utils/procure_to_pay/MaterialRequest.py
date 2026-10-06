import frappe
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
import json

headersList = {
                    "Accept": "*/*",
                    "User-Agent": "Khanal Tech",
                    "Content-Type": "application/json",
                    "Prefer": "odata.maxpagesize=100",
                }
payload = ''


# bench --site khanal.localhost execute khanal_tech_integrations.utils.procure_to_pay.MaterialRequest.post_material_request

@frappe.whitelist()
def post_material_request(MatReqID=None, *args, **kwargs):
    """
    Post a Material Request to SAP.

    This function posts a purchase request to SAP using the provided Material Request ID.

    Args:
        MatReqID (str): The ID of the Material Request.

    Returns:
        None
    """
    
    session = AuthenticateSAPB1()

    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url+"PurchaseRequests" #+ str(20*i)
    # doc = frappe.get_doc("Material Request", MatReqID)
    employee_no=frappe.get_value("Employee", {"user_id": MatReqID.get('owner')}, "employee")
    emp_url = doc_settings.sap_b1_url+"EmployeesInfo?$filter=EmployeeCode eq '"+employee_no+"'"
    emp_response = session.request("GET", emp_url,  headers=headersList,verify=False)
    emp_data = dict(emp_response.json())
    employee_id = emp_data['value'][0]['EmployeeID']
    payload = {
                "DocDate": MatReqID.transaction_date.strftime('%Y-%m-%d'),#"2024-03-13", Posting Date
                "TaxDate": MatReqID.transaction_date.strftime('%Y-%m-%d'), # Document Date
                "DocDueDate": MatReqID.schedule_date.strftime('%Y-%m-%d') ,#"2024-03-18", # Valid Until
                "RequriedDate": MatReqID.schedule_date.strftime('%Y-%m-%d'), # Requried Date
                "DocCurrency": "INR",
                "ReqType": 171,
                "Requester": employee_id,
                # "RequesterName": "Prasoom Sah",
                # "RequesterEmail": "aditya@khanalfoods.com",
                # "SendNotification": "tNO",
                "DocumentLines": [
                    # {
                    #     "ItemCode": "COCM0021",
                    #     "Quantity": "2"
                    # }
                    ]
                }
    for line in MatReqID.items:
        payload["DocumentLines"].append({
            "ItemCode": line.item_code,
            "Quantity": line.qty,
            "WarehouseCode": line.warehouse.split(" - ")[0],
            "UnitPrice": line.rate
        })
        
    response = session.request("POST", reqUrl, data=json.dumps(payload),  headers=headersList,verify=False)
    print (response.status_code)
    if response.status_code == 201:
        MatReqID.custom_sap_doc_entry = response.json().get('DocEntry', None)
        MatReqID.custom_sap_doc_num = response.json().get('DocNum', None)
        MatReqID.save()
        frappe.msgprint("Material Request Posted to SAP with and Purchase Request No. : "+str(response.json().get('DocNum', None)))
    else:
        print (response.json())
        frappe.throw(response.json())
    # print (response.json())
    # print (response.json().get('DocEntry', None))
    # print (response.json().get('DocNum', None))
    # # MatReqID.sap_doc_entry = response.json().get('DocEntry', None)
    # print (payload)
        
@frappe.whitelist()
def cancel_material_request(MatReqID=None, *args, **kwargs):
    """
    Cancel a Material Request in SAP.

    This function cancels a purchase request in SAP using the provided Material Request ID.

    Args:
        MatReqID (str): The ID of the Material Request.

    Returns:
        None
    """
    
    session = AuthenticateSAPB1()

    doc_settings = frappe.get_doc('SAP Settings')
    if MatReqID.custom_sap_doc_entry:
        reqUrl = doc_settings.sap_b1_url+"PurchaseRequests("+MatReqID.custom_sap_doc_entry+")/Cancel"
        payload = {
                    # "CANCELED": "tYES"
                    }
        # Get the status of the purchase request in SAP before proceeding to cancel it
        status_url = doc_settings.sap_b1_url+"PurchaseRequests("+MatReqID.custom_sap_doc_entry+")"
        status_response = session.request("GET", status_url,  headers=headersList,verify=False)
        status_data = dict(status_response.json())
        if status_data['CancelStatus'] == "tYES":
            frappe.throw("Document already canceled")

        if status_data['DocumentStatus'] == "bost_Open":
            response = session.request("POST", reqUrl, data=json.dumps(payload),  headers=headersList,verify=False)
            print (response.status_code)
            if response.status_code == 204:
                frappe.msgprint("Material Request Canceled")
        elif status_data['DocumentStatus'] == "bost_Close":
            frappe.throw("Cannot cancel a closed document. Please check the status in SAP")          
            # MatReqID.custom_sap_doc_entry = None
            # MatReqID.custom_sap_doc_num = None
            # MatReqID.save()
        # frappe.msgprint(response.json())
            
@frappe.whitelist()
def prevent_material_req_amending(MatReqID=None, *args, **kwargs):
    """
    Prevent amending a Material Request in SAP.

    This function prevents amending a purchase request in SAP using the provided Material Request ID.

    Args:
        MatReqID (str): The ID of the Material Request.

    Returns:
        None
    """
    
    # session = AuthenticateSAPB1()

    # doc_settings = frappe.get_doc('SAP Settings')
    if MatReqID.custom_sap_doc_entry:
        if MatReqID.docstatus == 2 and MatReqID.cancelled:
            frappe.throw("Cannot amend a canceled document")
        # reqUrl = doc_settings.sap_b1_url+"PurchaseRequests("+MatReqID.custom_sap_doc_entry+")/PreventAmending"
        # payload = {
        #             # "CANCELED": "tYES"
        #             }
        # response = session.request("POST", reqUrl, data=json.dumps(payload),  headers=headersList,verify=False)
        # print (response.status_code)
        # if response.status_code == 204:
        #     frappe.msgprint("Material Request Prevented from Amending")
        #     # MatReqID.custom_sap_doc_entry = None
        #     # MatReqID.custom_sap_doc_num = None
        #     # MatReqID.save()
        # # frappe.msgprint(response.json()
