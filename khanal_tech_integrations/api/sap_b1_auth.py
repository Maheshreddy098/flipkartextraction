"""
SAP B1 Authentication Module
Handles authentication and session management for SAP Business One using SAP Test Layer DocType
"""

import requests
import json
import frappe
from frappe.utils import add_to_date, now, get_datetime, now_datetime

headersList = {
    "Accept": "*/*",
    "User-Agent": "Khanal Tech",
    "Content-Type": "application/json"
}


def AuthenticateSAPB1():
    """
    Function to Authenticate SAP Business One
    Uses SAP Test Layer DocType (not SAP Settings)
    """
    b1_session = requests.Session()

    doc = frappe.get_doc('SAP Test Layer')

    expires_on = frappe.db.get_single_value('SAP Test Layer', 'expires_on')

    if not expires_on or expires_on == '':
        try:
            b1_session = renew_sap_session()
        except Exception as e:
            frappe.log_error(f"Error in AuthenticateSAPB1 (empty expires_on): {str(e)}", "SAP B1 Auth Error")
            raise e
    elif expires_on != '':
        if now_datetime() >= get_datetime(doc.expires_on):
            try:
                b1_session = renew_sap_session()
            except Exception as e:
                frappe.log_error(f"Error in AuthenticateSAPB1 (expired session): {str(e)}", "SAP B1 Auth Error")
                raise e
        else:
            b1session = frappe.db.get_single_value('SAP Test Layer', 'b1session')
            routeid = frappe.db.get_single_value('SAP Test Layer', 'routeid')
            
            if b1session and routeid:
                b1_session.cookies.set("B1SESSION", b1session)
                b1_session.cookies.set("ROUTEID", routeid)
            else:
                # If session values are missing, renew the session
                b1_session = renew_sap_session()

    return b1_session


@frappe.whitelist()
def initiate_session():
    """Initialize SAP B1 session"""
    try:
        x = AuthenticateSAPB1()
        # Convert cookies safely
        cookies_dict = {}
        for cookie in x.cookies:
            cookies_dict[cookie.name] = cookie.value
        return {
            "status": "success",
            "message": "Session initiated",
            "cookies": cookies_dict
        }
    except Exception as e:
        frappe.log_error(f"Error initiating session: {str(e)}", "SAP B1 Initiate Session Error")
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist()
def renew_sap_session():
    """
    Renew SAP B1 session
    Uses SAP Test Layer DocType
    """
    b1_session = requests.Session()

    try:
        doc = frappe.get_doc('SAP Test Layer')

        credentials_json = {
            "CompanyDB": doc.companydb,
            "Password": doc.get_password('password'),
            "UserName": doc.username
        }

        b1_url = doc.sap_b1_url
        reqUrl = b1_url + "Login"

        payload = json.dumps(credentials_json)

        response = b1_session.request("POST", reqUrl, data=payload, headers=headersList, verify=False)

        if response.status_code not in [200, 201]:
            error_msg = f"SAP B1 Login failed: {response.status_code} - {response.text}"
            frappe.log_error(error_msg, "SAP B1 Login Error")
            raise Exception(error_msg)

        cookies = b1_session.cookies.get_dict()

        doc.b1session = cookies.get("B1SESSION", "")
        doc.routeid = cookies.get("ROUTEID", "")

        # Calculate expiry time from SessionTimeout (in minutes)
        session_timeout = response.json().get('SessionTimeout', 30)  # Default 30 minutes
        doc.expires_on = add_to_date(now_datetime(), minutes=int(session_timeout))

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return b1_session

    except Exception as e:
        frappe.log_error(f"Error in renew_sap_session: {str(e)}", "SAP B1 Renew Session Error")
        raise e


