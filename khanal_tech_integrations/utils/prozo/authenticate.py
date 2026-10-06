#%%
import requests
import json

#%%
import frappe
from frappe.utils import add_to_date, get_datetime, now_datetime, today
from frappe.utils import now
#%%
headersList = {"Accept": "*/*",
                "User-Agent": "KhanalTech",
                "Content-Type": "application/json" 
                }


def get_token():
    prozo_url = "https://staging.prozo.com/wms/v1/auth"

    headersList = {
        "Accept": "*/*",'tenant': 'tenant_28','source': '2',
        "User-Agent": "Thunder Client (https://www.thunderclient.com)",
        "Content-Type": "application/json" }

    payload = {
        "username": "1234567890",
        "password": "khanal"
    }

    response = requests.request("POST", prozo_url, data=json.dumps(payload),  headers=headersList)

    return response.json()['token']

#/Users/buddhirajsahu/frappe-bench/apps.khanal_tech_integrations.khanal_tech_integrations.utils.prozo.authenticate
# %%
