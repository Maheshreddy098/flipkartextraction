#%%
import json
from warnings import filters
import requests
from khanal_tech_integrations.utils.prozo.authenticate import get_token
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
import frappe
from frappe.utils import add_to_date, getdate, today


pz_whse = {'PZ-MU-FG':'24','PZ-GU-FG':'22'}

@frappe.whitelist()
def process_po():    
    """
    The main function under purchase order process to create PO from inventory
    transfers from KFL to Prozo
    """
    inventory_transfers = frappe.db.get_list('SAP Inventory Transfers',
                                            filters={'towarehouse': ['in',['PZ-MU-FG','PZ-GU-FG']],'delivered':'N','po_posted_prozo':['not like','Y']})
    for inventory_tranfer in inventory_transfers:
        # if po_id is None:
        #     print ('ERROR')
        # elif po_id is not None:
        transfer_details_doc = frappe.get_doc('SAP Inventory Transfers',inventory_tranfer)
        transfer_details = transfer_details_doc.as_dict()
        #print (transfer_details)
        po_id = create(transfer_details['docdate'],transfer_details['docnum'],transfer_details['towarehouse'])
        for line_item in transfer_details['line_items']:
            
            item_id = get_item_id(line_item['itemcode'])
            quantity = line_item['batchquantity']
            mrp = line_item['unitprice']
            #ADD LINE ITEMS
            add_items(po_id,item_id,mrp,quantity)
            
        #PLACE PO        
        place_po(po_id)
        transfer_details_doc.po_posted_prozo = 'Y'
        transfer_details_doc.prozo_po_id = po_id
        transfer_details_doc.save()
        
@frappe.whitelist()
def process_po_linewise(inventory_tranfer_docentry): 
    #bench --site budd.localhost execute khanal_tech_integrations.utils.prozo.purchase_orders.process_po_linewise   
    """
    The main function under purchase order process to create PO from inventory
    transfers from KFL to Prozo
    """
    
    transfer_details_doc = frappe.get_doc('SAP Inventory Transfers',inventory_tranfer_docentry)
    transfer_details = transfer_details_doc.as_dict()
    #print (transfer_details)
    po_id = create(transfer_details['docdate'],transfer_details['docnum'],transfer_details['towarehouse']) #Creating PO
    for line_item in transfer_details['line_items']:
            
        item_id = get_item_id(line_item['itemcode'])
        quantity = line_item['batchquantity']
        mrp = line_item['unitprice']
        #ADD LINE ITEMS
        add_items(po_id,item_id,mrp,quantity) #Adding the lineitems from original Stock Transfer
            
        #PLACE PO        
    place_po(po_id)
    transfer_details_doc.po_posted_prozo = 'Y'
    transfer_details_doc.prozo_po_id = po_id
    transfer_details_doc.save()


def get_item_id(item_code=None):
    token = get_token()
    url = "https://staging.prozo.com/wms/v1/product?flag=1&limit=200&typeCodeCSV=0"
    payload={}
    headers = {
                'id': '1',
                'source': '2',
                'tenant': 'tenant_28',
                'Authorization': token,
                'Content-Type': 'application/json'
                }
    response = requests.request("GET", url, headers=headers, data=payload)
    #print(response.json())
    item_list = response.json()
    #print (item_list[0]['sku'])
    # TODO: USE barCode FOR NOW CHANGE IT TO "sku"
    item_id = next((item["id"] for item in item_list if item['sku'] == item_code), None)
    
    return item_id



def create(po_date=None,inv_trans_no=None,to_whse=None):
    token = get_token()
    url = "https://staging.prozo.com/wms/v1/po"

    payload = json.dumps({
                    "party": {
                        "id": 1915
                    },
                    "warehouse": {
                        "id": pz_whse[to_whse]
                    },
                    "poDate": po_date.strftime("%d-%m-%Y %H:%M"),
                    "expectedDeliveryDate": add_to_date(po_date,days=7).strftime("%d-%m-%Y %H:%M"),
                    "poExpiryDate": add_to_date(po_date,days=7).strftime("%d-%m-%Y %H:%M"),
                    "ref": 'DC No. '+str(inv_trans_no),
                    "notes": "",
                    "customFields": []
                    })
    headers = {
                'id': '1',
                'source': '2',
                'tenant': 'tenant_28',
                'Authorization': token,
                'Content-Type': 'application/json'
                }

    response = requests.request("POST", url, headers=headers, data=payload)

    res_dict = dict(response.headers)
    if res_dict.get('id'):
        return res_dict.get('id')
    else:
        return None
    

def add_items(po_id=None,item_id=None,mrp=None,quantity=None):
    token = get_token()
    url = "https://staging.prozo.com/wms/v1/po/product"
    headers = {
                'id': '1',
                'source': '2',
                'tenant': 'tenant_28',
                'Authorization': token,
                'Content-Type': 'application/json'
                }
    payload = json.dumps({
                            "product": {
                                "id": item_id
                            },
                            "po": {
                                "id": po_id
                            },
                            "mrp": mrp,
                            "discount": 0,
                            "quantity": quantity
                            })

    response = requests.request("POST", url, headers=headers, data=payload)
    res_dict = dict(response.headers)
    #print (res_dict)

def place_po(po_id):
    """Function to close the PO in Prozo
    """
    token = get_token()
    url = "https://staging.prozo.com/wms/v1/po"
    headers = {
                'id': '1',
                'source': '2',
                'tenant': 'tenant_28',
                'Authorization': token,
                'Content-Type': 'application/json'
                }
    payload = json.dumps({
                            "id": po_id,
                            "status": 1
                            })

    response = requests.request("PATCH", url, headers=headers, data=payload)
    res_dict = dict(response.headers)
    #print (res_dict)
    #print (response.text)



def list_all():
    """
    List all existing Purchase Orders
    """
    token = get_token()
    print (token)
    url = "https://staging.prozo.com/wms/v1/po"
    headers = {
            "Accept": "*/*",
            "User-Agent": "Thunder Client (https://www.thunderclient.com)",
            'source': '2',
            'tenant': 'tenant_28',
            'Authorization':token,
            'Content-Type': 'application/json'

                    }
    payload = {}
    params = {"flag":1,
               "limit": 200,
               "warehouseId":22}

    response = requests.request("GET",url,params=params,headers=headers,data={})#payload)

    return response.json()

def get_grn(po_id=17):
    '''
    GET GRN details given a PO number of Prozo
    '''
    token = get_token()

    url = "https://staging.prozo.com/wms/v1/grn"
    payload={}
    headers ={
            'id': '1',
            'source': '2',
            'tenant': 'tenant_28',
            'Authorization':token
                    }

    params = {'poId':po_id,'flag':1}

    response = requests.request("GET", url, headers=headers,params=params, data=payload)
    resp_json = response.json()
    products_list = []
    #products = [product["products"] for product in resp_json]
    #products_list = [products for products in product["products"] for product in resp_json]

    #print (resp_json)
    for product in resp_json:
        if product.get("products"):
            for products in product["products"]:
                products_list.append(products)

    return products_list

@frappe.whitelist()
def complete_grn():
    token = get_token()

    url = "https://staging.prozo.com/wms/v1/grn"
    payload={}
    headers ={
            'id': '1',
            'source': '2',
            'tenant': 'tenant_28',
            'Authorization':token
                    }

    pending_grn_po = frappe.db.get_list('SAP Inventory Transfers',
                                        filters={'towarehouse': ['in',['PZ-MU-FG','PZ-GU-FG']],'delivered':'N','po_posted_prozo':'Y'},
                                        pluck='name')
    print (pending_grn_po)

    for pos in pending_grn_po:
        doc = frappe.get_doc('SAP Inventory Transfers',pos)
        print (doc)
        po_id = doc.prozo_po_id

        pz_grn_items = get_grn(po_id)

        line_item_status = []
        if len(pz_grn_items)>0:
            for line_item in doc.line_items:
                pz_item_detail = next((item for item in pz_grn_items if item['barCode'] == line_item.itemcode),None)
                print (pz_item_detail)
                if (pz_item_detail['productBatch']['batchNo'] == line_item.batchnumber):
                    print ('Batch Matches')
                    if (int(pz_item_detail['acceptedQuantity']) == int(line_item.batchquantity)):
                        print ('Quantity Matches')
                        line_item.pz_grn_qty = int(pz_item_detail['acceptedQuantity'])
                        line_item.pz_grn_complete = 'Y'
                        line_item_status.append('Y')
                    else:
                        print ('Quantity Not matching!')
                        line_item_status.append('N')
                print (line_item.itemcode,line_item.quantity,line_item.batchnumber,line_item.batchquantity)
            
            doc.delivered = 'N' if 'N' in line_item_status else 'Y'
            doc.save()
            frappe.db.commit()

            update_sap_inv_trf_status(inv_trf_id=doc.docentry)
        else:
            # Not updated yet
            message = 'Inventory transfer Items not GRN yet'
            pass



def update_sap_inv_trf_status(inv_trf_id=None):
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    url = doc_settings.sap_b1_url+"StockTransfers("+ str(inv_trf_id) + ")"

    payload = json.dumps({
                            "U_ShippingDate": today(),
                            "U_Delivered": "Y"
                            })
    headers = {
    'Content-Type': 'text/plain',
    }

    response = session.request("PATCH", url, headers=headers, data=payload,verify=False)

    #print(response.text)


#total=getgrn(token).json()
# %%
