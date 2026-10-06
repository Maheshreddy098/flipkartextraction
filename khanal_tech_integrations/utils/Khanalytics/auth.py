import frappe
from frappe import auth
from datetime import datetime

@frappe.whitelist( allow_guest=True )
def login(usr, pwd):
    print(usr,'@'*10)
    print(pwd,'!'*10)
    try:
        login_manager = frappe.auth.LoginManager()
        login_manager.authenticate(user=usr, pwd=pwd)
        login_manager.post_login()
    except frappe.exceptions.AuthenticationError:
        frappe.clear_messages()
        # print(frappe.local.response.message,'frappe.local')
        frappe.local.response["message"] = {
            "success_key":0,
            "message":frappe.local.response.message
        }

        return

    # api_generate = generate_keys(frappe.session.user)
    user = frappe.get_doc('User', frappe.session.user)
    # frappe.response["home_page"]=='/'

    frappe.response["message"] = {
        "success_key":1,
        "message":"Authentication success",
        "sid":frappe.session.sid,
        "api_key":user.api_key,
        "api_secret":user.get_password('api_secret'),
        "username":user.username,
        "email":user.email,
        "user":user.username,
        "Roles":user.roles,
        "Current_DateTime":datetime.now()

    }

    # print(frappe.response)



def generate_keys(user):
    user_details = frappe.get_doc('User', user)
    api_secret = frappe.generate_hash(length=15)

    if not user_details.api_key:
        api_key = frappe.generate_hash(length=15)
        user_details.api_key = api_key

    user_details.api_secret = api_secret
    user_details.save()

    return api_secret


#? {url and port }/api/method/khanal_tech_integrations.utils.Khanalytics.auth.Get_Salesperson
# bench --site dev.localhost execute khanal_tech_integrations.utils.Khanalytics.auth.Get_Salesperson

import requests
import base64
@frappe.whitelist( )
def Get_User():
    
    # url = "http://dev.localhost:8000/api/method/frappe.auth.Get_User"
    api_key = "0cba98a0c2fc8ee"
    api_secret = "7e7c778caa40171"

    # Combine the API key and secret in the format "api_key:api_secret" and encode it in base64
    credentials = base64.b64encode(f"{api_key}:{api_secret}".encode()).decode()
    print(credentials)
    headers = {
        'Authorization': f"Basic {credentials}"
    }
    # response = requests.get(url, headers=headers)

    # # Check if the request was successful
    # if response.status_code == 200:
    #     data = response.json()
    #     # Access the data you need from the response, such as 'username', 'email', etc.
    #     username = data.get("message").get("username")
    #     email = data.get("message").get("email")
    #     print(f"Username: {username}")
    #     print(f"Email: {email}")
    # else:
        # print(f"Request failed with status code: {response.status_code}")
Get_User()

# %%


@frappe.whitelist( )
def Get_Salesperson():
    doc=frappe.db.get_list('SAP Salesperson')
    return doc

