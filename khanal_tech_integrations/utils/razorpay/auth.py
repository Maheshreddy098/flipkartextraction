#%%
import requests
import json
import frappe


def rz_token():
    token = frappe.db.get_single_value('razorpay_settings','token')
    secret = frappe.db.get_single_value('razorpay_settings','secret')

    return (token,secret)