import frappe
from frappe.utils import add_to_date, get_datetime, now_datetime, today
import requests




def AuthenticateSafexpress():
    """Function to authenticate SafeXpress API. 
    Renew the token only if expired and 
    returns the doc instance
	"""
    doc = frappe.get_doc('Safexpress Settings')
        
    # RENEW TOKEN ONLY IF EXPIRED
    expires_on = frappe.db.get_single_value('Safexpress Settings', 'expires_on')
    
    if expires_on == '':
        try:
            safexpress_doc = renew_session()
            return safexpress_doc
        except Exception as e:
            frappe.log_error(f"Error renewing Safexpress session: {str(e)}", "Safexpress Auth")
            raise e
    
    if expires_on != '': 
        if now_datetime() >= get_datetime(doc.expires_on):
            try:
                safexpress_doc = renew_session()
                return safexpress_doc
            except Exception as e:
                frappe.log_error(f"Error renewing Safexpress session: {str(e)}", "Safexpress Auth")
                raise e
        # DO NOT RENEW IF NOT EXPIRED
        else:
            return doc
    
    # Fallback - should not reach here, but return doc if it does
    return doc



import requests
import logging

# logging.basicConfig(level=logging.DEBUG)  # Set the logging level to DEBUG

def renew_session():
    """Renew Safexpress authentication session."""
    doc = frappe.get_doc('Safexpress Settings')
    requrl = doc.login_url
    payload = {
        "grant_type": 'client_credentials',
        "scope": 'server/waybillapps',
        "username": doc.username,
        "password": doc.password
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': '*/*',
        'Authorization': 'Basic Zm1xYWRsY2ZyY29jdW5hY2xyaWxodTRsbTpqamZ0M3Izb2ZtOWxsbmJudmZxMHZic2FwN2oxZWRrNm4wYzE5am5yM2VlMWVxcnNxNWE=',
        'Cookie': 'XSRF-TOKEN=5de4fefb-a52f-439f-83c2-ad473f2cef5b'
    }
    try:
        response = requests.request("POST", requrl, headers=headers, data=payload, timeout=10, verify=False)
        response.raise_for_status()
        resp_json = response.json()
        doc.access_token = resp_json['access_token']
        doc.expires_on = add_to_date(now_datetime(), seconds=int(resp_json["expires_in"]))
        doc.save()
        frappe.db.commit()
        logging.info("Safexpress session renewed successfully")
        return doc
    except requests.exceptions.Timeout as e:
        error_msg = f"Safexpress auth request timeout: {e}"
        logging.error(error_msg)
        frappe.log_error(error_msg, "Safexpress Auth - Timeout")
        raise
    except requests.exceptions.RequestException as e:
        error_msg = f"Safexpress auth request exception: {e}"
        logging.error(error_msg)
        frappe.log_error(error_msg, "Safexpress Auth - Request Error")
        raise
    except ValueError as e:
        error_msg = f"Safexpress auth JSON parsing error: {e}"
        logging.error(error_msg)
        frappe.log_error(error_msg, "Safexpress Auth - JSON Error")
        raise
    except Exception as e:
        error_msg = f"Safexpress auth unexpected error: {e}"
        logging.error(error_msg)
        frappe.log_error(error_msg, "Safexpress Auth - Unexpected Error")
        raise

    # response=requests.request("POST", requrl, headers=headers, data=payload)
    # print(response)
    # print(response.text)
    # resp_json = response.json()
    # doc.access_token = resp_json['access_token']
    # doc.expires_on = add_to_date(now_datetime(), seconds=int(resp_json["expires_in"]))
    # doc.save()
    # frappe.db.commit()
    # return doc
 

    # bench --site dev.localhost execute khanal_tech_integrations.utils.safexpress.auth.AuthenticateSafexpress

#%%
# import requests
# def SafeXpressAuth():
#     url = "https://api-auth.safexpress.com/oauth2/token"

#     payload={   "grant_type": 'client_credentials',
#                 "scope": 'server/waybillapps',
#                 "username":'fmqadlcfrcocunaclrilhu4lm',
#                 "password":'jjft3r3ofm9llnbnvfq0vbsap7j1edk6n0c19jnr3ee1eqrsq5a'
#                 }
#     headers = {
#     'Content-Type': 'application/x-www-form-urlencoded',
#     'Authorization': 'Basic Zm1xYWRsY2ZyY29jdW5hY2xyaWxodTRsbTpqamZ0M3Izb2ZtOWxsbmJudmZxMHZic2FwN2oxZWRrNm4wYzE5am5yM2VlMWVxcnNxNWE=',
#     'Cookie': 'XSRF-TOKEN=6d10c3b7-9dc5-496c-af3d-3fe9a5549618'
#     }

#     response = requests.request("POST", url, headers=headers, data=payload)

#     print(response.text)

# SafeXpressAuth()

# %%
