import frappe
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
from frappe.utils import add_to_date, now, get_datetime, now_datetime
from requests.exceptions import ProxyError
from json.decoder import JSONDecodeError
headersList = {
                "Accept": "*/*",
                "User-Agent": "Khanal Tech",
                "Content-Type": "application/json" 
            }


@frappe.whitelist()
def Update_daily_inventory_level():
    """
    Update Inventory Daily Report from SAP to Khanal Tech Integrations 
    """
    # INITIALIZATION
    session = AuthenticateSAPB1()
    # BatchQtyInWarehouse
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url+"SQLQueries('SQLWarehouse_Inventory')/List" #Item batch Quantity from EC-G will be changed only
    
    response = session.request("GET", reqUrl, headers=headersList,verify=False)
    Query_results = dict(response.json())
    next_page = Query_results.get("odata.nextLink",None)
    LineItem_list = []
    while next_page is not None:
        session = AuthenticateSAPB1()
        if Query_results['value'] is not None:
            for single_query_values in Query_results['value']:
                LineItem_list.append({"itemcode":single_query_values['ItemCode'],"distnumber":single_query_values['DistNumber'],"expdate":single_query_values['ExpDate'],"mnfdate":single_query_values['MnfDate'],"quantity":single_query_values['Quantity'],"whscode":single_query_values['WhsCode'],"itemname":single_query_values['ItemName']})#
    

        session = AuthenticateSAPB1()
        reqUrl = doc_settings.sap_b1_url + next_page
        print(next_page)
        response = session.request("GET", reqUrl,  headers=headersList,verify=False)
            
        try:
            Query_results = dict(response.json())
            next_page = Query_results.get("odata.nextLink", None)

        except JSONDecodeError as e:
            print("Error decoding JSON:", e)
    frappe.msgprint(msg='Data Inserted successfully',title='Success')
    # Today = frappe.utils.nowdate()
    # FilterDate = add_to_date(Today,days=+1)
    doc = frappe.new_doc('SAP Inventory Report')
    doc.created_date =  frappe.utils.nowdate()
    for LineItem in LineItem_list:
        doc.append("lineitems",LineItem)

    try:
        doc.save()
        frappe.db.commit()
        print(doc,'saved')
    except frappe.DuplicateEntryError:
        print(doc,'duplicate')
        pass
    return None

# bench --site dev.localhost execute khanal_tech_integrations.utils.purchase.inventory.Update_daily_inventory
# bench --site dev.localhost execute khanal_tech_integrations.utils.purchase.inventory.Update_daily


# bench --site khanaltech.com execute khanal_tech_integrations.utils.purchase.inventory.Update_daily_inventory_existing



@frappe.whitelist()
def Update_daily_count():
    """
    Update Invoices from SAP to Khanal Tech Integrations 
    """
    session = AuthenticateSAPB1()
    payload = ''

    # CHECK THE LAST MAX UPDATED INV. TRANSFERS
    start_page = 1

    # Initialize the counter
    i = int(start_page)
    if i > 1:
        i -= 1

    LineItem_list = []

    while True:
        doc_settings = frappe.get_doc('SAP Settings')
        reqUrl = doc_settings.sap_b1_url+"SQLQueries('SQLWarehouse_Inventory')/List?&$skip=" + str(20 * i)
        session = AuthenticateSAPB1()
        response = session.request("GET", reqUrl, data=payload, headers=headersList, verify=False)

        try:
            Query_results = dict(response.json())
            Inventory_items = Query_results.get("value")
            next_page = Query_results.get("odata.nextLink")

            if Inventory_items is not None and len(Inventory_items) > 0:  # Check for non-empty list
                print('Going into', i)
                for single_query_values in Inventory_items:
                    LineItem_list.append({
                        "itemcode": single_query_values['ItemCode'],
                        "distnumber": single_query_values['DistNumber'],
                        "expdate": single_query_values['ExpDate'],
                        "mnfdate": single_query_values['MnfDate'],
                        "quantity": single_query_values['Quantity'],
                        "whscode": single_query_values['WhsCode'],
                        "itemname": single_query_values['ItemName']
                    })
                i += 1
            else:
                break  # Break the loop when Inventory_items is an empty list

            if next_page is None:
                next_page = doc_settings.sap_b1_url+"SQLQueries('SQLWarehouse_Inventory')/List?&$skip=" + str(20 * i)
            else:
                next_page += "&$skip=" + str(20 * i)
        except JSONDecodeError as e:
            print("Error decoding JSON:", e)

    doc = frappe.new_doc('SAP Inventory Report')
    doc.created_date = frappe.utils.nowdate()
    for LineItem in LineItem_list:
        doc.append("lineitems", LineItem)

    try:
        doc.save()
        frappe.db.commit()
        print(doc, 'saved')
    except frappe.DuplicateEntryError:
        print(doc, 'duplicate')
        pass
    return None


import requests
from requests.exceptions import ConnectionError

@frappe.whitelist()
def Update_daily_inventory_existing():
    """
    Update Inventory Daily Report from SAP to Khanal Tech Integrations 
    """
    # INITIALIZATION
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url+"SQLQueries('SQLWarehouse_Inventory')/List" # Item batch Quantity from EC-G will be changed only

    LineItem_list = []

    i = 0

    while True:
        try:
            response = session.request("GET", reqUrl, headers=headersList, verify=False)
        except ConnectionError as e:
            print("Connection error:", e)
            continue

        try:
            Query_results = dict(response.json())
        except JSONDecodeError as e:
            print("Error decoding JSON:", e)
            continue

        Inventory_items = Query_results.get("value")
        next_page = Query_results.get("odata.nextLink")

        if Inventory_items is not None:
            print(i,'Going inTo')
            for single_query_values in Inventory_items:
                LineItem_list.append({
                    "itemcode": single_query_values['ItemCode'],
                    "distnumber": single_query_values['DistNumber'],
                    "expdate": single_query_values['ExpDate'],
                    "mnfdate": single_query_values['MnfDate'],
                    "quantity": single_query_values['Quantity'],
                    "whscode": single_query_values['WhsCode'],
                    "itemname": single_query_values['ItemName']
                })

        if next_page is None or Inventory_items is None:
            break

        i += 1
        doc_settings = frappe.get_doc('SAP Settings')
        reqUrl = doc_settings.sap_b1_url+"SQLQueries('SQLWarehouse_Inventory')/List?&$skip=" + str(20 * i)

    frappe.msgprint(msg='Data Inserted successfully', title='Success')
    Today = frappe.utils.nowdate()
    FilterDate = add_to_date(Today,days=+4)
    doc = frappe.new_doc('SAP Inventory Report')
    doc.created_date = FilterDate

    for LineItem in LineItem_list:
        doc.append("lineitems", LineItem)

    try:
        doc.save()
        frappe.db.commit()
        print(doc, 'saved')
    except frappe.DuplicateEntryError:
        print(doc, 'duplicate')
        pass

    return None
