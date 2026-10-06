import frappe
from frappe.utils import add_to_date, get_datetime, now_datetime, today
import requests
import datetime
doc = frappe.get_doc('AWS_CashFree Settings')


def AuthenticateCashfree():
    """Function to authenticate Cashfree API. 
    Renew the token only if expired and 
    returns the doc instance
	"""
        
    # RENEW TOKEN ONLY IF EXPIRED
    expires_on = frappe.db.get_single_value('AWS_CashFree Settings', 'cashfree_expiry')

    if (expires_on==''):
        try:
            cashfree_doc = renew_session()
        except Exception as e:
            raise e
    
    elif (expires_on != ''): 
        if now_datetime() >= get_datetime(doc.cashfree_expiry):
            try:
                cashfree_doc = renew_session()
            except Exception as e:
                raise e
        # DO NOT RENEW IF NOT EXPIRED
        else:
            cashfree_doc = doc
        return cashfree_doc

def renew_session():
    requrl = doc.cashfree_login_url
    payload = ""
    headers = {
        'x-client-id': doc.cashfree_client_id,
        'x-client-secret': doc.cashfree_secret_id
        }
    response=requests.request("POST", requrl, headers=headers, data=payload)
    resp_json = response.json()
    print(resp_json)
    doc.cashfree_access_token = resp_json['data']['token']
    doc.cashfree_expiry = datetime.datetime.fromtimestamp(resp_json["data"]['expiry'])

    doc.save()
    frappe.db.commit()
    return doc


#  bench --site dev.localhost execute khanal_tech_integrations.utils.cashfree.vrf.auth.AuthenticateCashfree