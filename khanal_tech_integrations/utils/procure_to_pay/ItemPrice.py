import frappe
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
import json

headersList = {
                    "Accept": "*/*",
                    "User-Agent": "Khanal Tech",
                    "Content-Type": "application/json",
                    # "Prefer": "odata.maxpagesize=500",
                }
payload = ''

# bench --site khanal.localhost execute khanal_tech_integrations.utils.procure_to_pay.ItemPrice.get_item_price

@frappe.whitelist()
def get_item_price(ItemPriceID=None, *args, **kwargs):
    """
    Post an Item Price to SAP.

    This function posts an item price to SAP using the provided Item Price ID.

    Args:
        ItemPriceID (str): The ID of the Item Price.

    Returns:
        None
    """
    
    session = AuthenticateSAPB1()

    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url+"SQLQueries('GetLastPurchasePrice')/List?$skip=1500"

    response = session.request("GET", reqUrl,  headers=headersList,verify=False)
    item_price_data = dict(response.json())
    # print (item_price_data)

    while item_price_data.get('odata.nextLink', None):
    # for i in range(1,3):
        session = AuthenticateSAPB1()
        update_item_price(item_price_data)
        print (item_price_data['odata.nextLink'])
        next_url = doc_settings.sap_b1_url+item_price_data['odata.nextLink']
        response = session.request("GET", next_url, headers=headersList, verify=False)
        import time
        # time.sleep(20)
        item_price_data = dict(response.json())
        
    update_item_price(item_price_data)

def update_item_price(item_price_data):

    for i in range(len(item_price_data['value'])):
        item_code = item_price_data['value'][i]['ItemCode']
        # print (item_code)
        if frappe.db.exists("Item Price", {"item_code": item_code, "price_list": 'Standard Buying'}):
            item_price_doc = frappe.get_doc("Item Price",{"item_code": item_code})
            new_doc = False
        else:
            item_price_doc = frappe.new_doc("Item Price")
            new_doc = True

        item_price_doc.item_code = frappe.get_value("Item", {"item_code": item_code})
        item_price_doc.price_list = 'Standard Buying'
        item_price_doc.buying = 1
        item_price_doc.currency = 'INR'
        item_price_doc.price_list_rate = item_price_data['value'][i]['LastPurPrc']

        if new_doc:
            item_price_doc.insert()
        else:
            item_price_doc.save()
    frappe.db.commit()
        
@frappe.whitelist()
def fetch_items():
    items_doc = frappe.get_all("Item", filters=[["item_code", "not like", "FG%"], ["item_code", "not like", "CFG%"], ["item_code", "not like", "%.%"]], fields=["item_code"])
    # print (items_doc)
    for item in items_doc:
        item_price = get_single_item_price(item['item_code'])
        # print (item['item_code'], item_price)
        if item_price:
            if frappe.db.exists("Item Price", {"item_code": item['item_code'], "price_list": 'Standard Buying'}):
                item_price_doc = frappe.get_doc("Item Price",{"item_code": item['item_code']})
                new_doc = False
            else:
                item_price_doc = frappe.new_doc("Item Price")
                new_doc = True
            item_price_doc = frappe.new_doc("Item Price")
            item_price_doc.item_code = item['item_code']
            item_price_doc.price_list = 'Standard Buying'
            item_price_doc.buying = 1
            item_price_doc.currency = 'INR'
            item_price_doc.price_list_rate = item_price
            
            if new_doc:
                item_price_doc.insert()
            else:
                try:
                    item_price_doc.save()
                except:
                    pass
            frappe.db.commit()


@frappe.whitelist()
def get_single_item_price(ItemCode=None, *args, **kwargs):
    """
    Gets an Item Price from SAP.

    This function get an item price from SAP using the provided Item Price ID.

    Args:
        ItemPriceID (str): The ID of the Item Price.

    Returns:
        Last Purchase Price of the Item
    """
    
    session = AuthenticateSAPB1()

    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url+"SQLQueries('GetLastPurchasePriceItem')/List?ItemCode='"+ItemCode+"'"

    response = session.request("GET", reqUrl,  headers=headersList,verify=False)
    try:
        item_price_data = dict(response.json())
        return item_price_data['value'][0]['LastPurPrc']
    except:
        # frappe.throw("Item Price not found in SAP")
        print (ItemCode, " Item Price not found in SAP")
        return 0
    
