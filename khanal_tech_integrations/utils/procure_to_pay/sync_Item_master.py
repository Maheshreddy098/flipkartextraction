import frappe
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1

headersList = {
                    "Accept": "*/*",
                    "User-Agent": "Khanal Tech",
                    "Content-Type": "application/json",
                    "Prefer": "odata.maxpagesize=100",
                }
payload = ''

# bench --site dev.localhost execute khanal_tech_integrations.utils.procure_to_pay.sync_Item_master.get_sap_item_master

@frappe.whitelist()
def initialize_item():
    get_item_groups()
    get_sap_item_master()

@frappe.whitelist()
def get_sap_item_master():
    session = AuthenticateSAPB1()

    doc_settings = frappe.get_doc('SAP Settings')
    # item_master = sap.get_item_master()
    reqUrl = doc_settings.sap_b1_url+"Items?$select=ItemCode,ItemName,ForeignName,ItemsGroupCode,SalesUnit,PurchaseUnit,U_TaxRate,Frozen" #+ str(20*i)
    response = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
    item_master = dict(response.json())
    # print (item_master['odata.nextLink'])

    while item_master.get('odata.nextLink', None):
        update_item_master(item_master)
        print (item_master['odata.nextLink'])
        next_url = doc_settings.sap_b1_url+item_master['odata.nextLink']
        response = session.request("GET", next_url, data=payload, headers=headersList, verify=False)
        item_master = dict(response.json())
        # update_item_master(item_master)

    update_item_master(item_master)


def update_item_master(item_master_data):
    # Sync Item Masters of SAP B1 with Khanal Tech and Erpnext and vice versa
    for i in range(len(item_master_data['value'])):
        item_code = item_master_data['value'][i]['ItemCode']
        # print (item_code)
        if frappe.db.exists("Item", item_code):
            item_master_doc = frappe.get_doc("Item",item_code)
            new_doc = False
        else:
            item_master_doc = frappe.new_doc("Item")
            new_doc = True

        # item_master_doc = frappe.new_doc("Item")
        item_master_doc.item_code = item_code
        item_master_doc.item_name = item_master_data['value'][i]['ItemName'][:139] if item_master_data['value'][i]['ItemName'] else ''
        # if item_master_data['value'][i]['ItemsGroupCode']:
        item_master_doc.item_group = frappe.get_value("Item Group", {"custom_item_group_code": item_master_data['value'][i]['ItemsGroupCode']})
        # else:
        #     print ('All Item Groups')
        #     item_master_doc.item_group = 'All Item Groups'

        if item_master_data['value'][i]['SalesUnit']:
            create_uom_if_not_exists(item_master_data['value'][i]['SalesUnit'])
        if item_master_data['value'][i]['PurchaseUnit']:
            create_uom_if_not_exists(item_master_data['value'][i]['PurchaseUnit'])
        item_master_doc.stock_uom = item_master_data['value'][i]['SalesUnit'] if item_master_data['value'][i]['SalesUnit'] else 'Nos'
        item_master_doc.purchase_uom = item_master_data['value'][i]['PurchaseUnit'] if item_master_data['value'][i]['PurchaseUnit'] else 'Nos'
        item_master_doc.is_purchase_item = 1 if item_master_data['value'][i]['ItemsGroupCode'] in [180] else 0
        item_master_doc.disabled = 0 if item_master_data['value'][i]['Frozen'] == 'tNO' else 1

        
        if new_doc:
            item_master_doc.insert()
        else:
            item_master_doc.save()
        # item_master_doc.insert()
    frappe.db.commit()

def create_uom_if_not_exists(uom_name):
    """
    Create a new UOM (Unit of Measure) if it does not already exist.
    
    Args:
        uom_name (str): The name of the UOM.

    Returns:
        None
    """
    if not frappe.db.exists("UOM", uom_name):
        uom_doc = frappe.new_doc("UOM")
        uom_doc.uom_name = uom_name
        uom_doc.insert()

@frappe.whitelist()
def get_item_groups():
    session = AuthenticateSAPB1()

    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url+"ItemGroups"
    response = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
    item_groups = dict(response.json())

    for i in range(len(item_groups['value'])):
        if frappe.db.exists("Item Group", {"custom_item_group_code": item_groups['value'][i]['Number']}):
            item_groups_doc = frappe.get_doc("Item Group", {"custom_item_group_code": item_groups['value'][i]['Number']})
            new_doc = False
        else:
            item_groups_doc = frappe.new_doc("Item Group")
            new_doc = True
        
        item_groups_doc.item_group_name = item_groups['value'][i]['GroupName']
        item_groups_doc.custom_item_group_code = item_groups['value'][i]['Number']
        
        if new_doc:
            item_groups_doc.insert()
        else:
            item_groups_doc.save()
    frappe.db.commit()

    return None


@frappe.whitelist()
def delete():
    x = 'Item'
    print(len(frappe.get_list(x)))
    for documentt in frappe.get_list(x):
        documentt = frappe.get_doc( x , documentt.name)
        print (documentt.name)
        documentt.delete()
        frappe.db.commit()