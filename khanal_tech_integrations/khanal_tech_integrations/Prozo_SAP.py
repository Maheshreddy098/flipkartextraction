#SAP API
#%%
import requests
import json
import frappe
#import time
# import urllib3
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1, get_single_inventory_transfer
from khanal_tech_integrations.unicommerce.client.unicommerce import UCClient
# urllib3.disable_warnings()


def AuthenticateUniware():
    """Compatibility wrapper backed by UCClient."""
    client = UCClient()
    client.login()
    access_token = client.token or ""
    facility = (client.facility_code or "").split(",")[0].strip() if client.facility_code else ""
    return {"access_token": access_token, "facility": facility}

#{'successful': True, 'message': None, 'errors': [], 'warnings': None, 'vendorName': 'Ecommerce Dispatch', 'purchaseOrderCode': 'PO0028'}

#bench --site medusa.localhost execute khanal_tech_integrations.khanal_tech_integrations.Prozo_SAP.Check_Uniware_PO_Exists
def create_GRN(PO_number):
    createGRN_payload = {   "wsGRN": {"vendorInvoiceNumber": "Generated via API", "vendorInvoiceDate": 1662555146000,  "currencyCode": "INR"   }, #Date to be filled 
                                      "purchaseOrderCode": str(PO_number)  , "vendorInvoiceDateCheckDisable": False}
    uniware_session = AuthenticateUniware()
    GRN_creation_url = "https://khanalfoods.unicommerce.com/services/rest/v1/purchase/inflowReceipt/create"
    headersList1 = { "Accept": "*/*", "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                    "Content-Type": "application/json"
                    }
    headersList1["facility"] = 'khanalfoods'
    headersList1['Authorization'] = 'bearer ' + uniware_session['access_token']
    GRNcreation_response = requests.request("POST", GRN_creation_url, data=json.dumps(createGRN_payload),  headers=headersList1)
    Created_GRN_Dict = dict(GRNcreation_response.json())
    if Created_GRN_Dict['successful'] == 'True': #GRN is created already then add SKUs into this 
        print('Newly created GRN is :',Created_GRN_Dict['inflowReceiptCode'])
        resultt = Created_GRN_Dict['inflowReceiptCode']
    return Created_GRN_Dict

#----------------
@frappe.whitelist()
def Getting_GRN_LineItems(single_GRN):
    existing_GRN = {   "inflowReceiptCode": str(single_GRN) } 
    GRN_details_url = "https://khanalfoods.unicommerce.com/services/rest/v1/purchase/inflowReceipt/getInflowReceipt"
    uniware_session = AuthenticateUniware()
    headersList1 = { "Accept": "*/*",
                    "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                    "Content-Type": "application/json"    
                    }
    headersList1["facility"] = 'khanalfoods'
    headersList1['Authorization'] = 'bearer ' + uniware_session['access_token']
    GRN_details_response = requests.request("POST", GRN_details_url, data=json.dumps(existing_GRN),  headers=headersList1)
    Existing_GRN_Items = GRN_details_response.json()['inflowReceiptItems']
    GRN_SKUadding_formated_List = []
    for batchwise_item in Existing_GRN_Items:
        inflowItem = { "skuCode": None, "quantity": 1, "unitPrice": 1,
            "wsBatchDetail": { "wsBatchGroupFieldValue" : { "vendorBatchNumber": "NA" }}                     }
        inflowItem['skuCode'] = batchwise_item['itemSKU']
        inflowItem["quantity"] = batchwise_item['quantity']
        inflowItem['wsBatchDetail']['wsBatchGroupFieldValue']['vendorBatchNumber'] = batchwise_item['batchDTO']['batchCode']['batchFieldsDTO']['vendorBatchNumber']
        #'batchDTO' : {'batchCode': '','batchFieldsDTO': {'vendorBatchNumber':'NA'}
        GRN_SKUadding_formated_List.append(inflowItem)
    final_list = GRN_SKUadding_formated_List
    return final_list

@frappe.whitelist()
def Adding_SKUs_to_grn(GRN_no,Inv_transfer_doc_LineItems):
    """Function to create GRNs for existing POs from the inventory transfers
    """
    GRN_SKUwise_Details = {
                            "inflowReceiptCode": "NAN",
                            "inflowReceiptItem": None }
    GRN_SKUwise_Details["inflowReceiptCode"] = GRN_no
    uniware_session = AuthenticateUniware()
    for one_item in Inv_transfer_doc_LineItems:
        inflowItems = { "skuCode": None, "quantity": 1, "unitPrice": 1,
            "wsBatchDetail": { "wsBatchGroupFieldValue" : { "vendorBatchNumber": "NA" }}                     }
        inflowItems['skuCode'] = one_item.itemcode
        inflowItems["quantity"] = one_item.batchquantity #batchwise quantity to be used
        inflowItems['wsBatchDetail']['wsBatchGroupFieldValue']['vendorBatchNumber'] = one_item.batchnumber #batchcode from SAP 
        GRN_SKUwise_Details["inflowReceiptItem"] = inflowItems
        SKU_adding_Url = "https://khanalfoods.unicommerce.com/services/rest/v1/purchase/inflowReceipt/addItemSKU"
        headersList = { "Accept": "*/*", 
        "User-Agent": "Thunder Client (https://www.thunderclient.com)",
        "Content-Type": "application/json" ,'facility':'khanalfoods'}
        headersList['Authorization'] = 'bearer ' + uniware_session['access_token']
        response = requests.request("POST", SKU_adding_Url, data=json.dumps(GRN_SKUwise_Details),  headers=headersList)
    #Check the GRN Details with all lineitems
    Existing_GRN_Items = Getting_GRN_LineItems(GRN_no)
    
    return Existing_GRN_Items

# %%
# bench --site medusa.localhost execute khanal_tech_integrations.khanal_tech_integrations.Prozo_SAP.delivery_from_orderlist

            

@frappe.whitelist()
def delivery_from_orderlist(channel,completed_orderlist): #channel,completed_orderlist
    #completed_orderlist = ['SLP3817458722','SLP3781522492']
    Delivery_payload = { "CardCode": "C03186", #filled with channel
                         "DocumentLines": []}
    #Delivery_payload['CardCode'] = channel_dict_mapping[str(channel)]
    for single_order in completed_orderlist:
        # print('Order object type is :',type(single_order))
        order_doc = frappe.get_doc('Unicommerce Orders', single_order['name']) #change single order
        lineitemss = order_doc.line_items
        # print('Length of lineitems : ',len(lineitemss))
        for itemss in lineitemss:
            lineitem_delivery = {
            "LineNum": 0,
            "ItemCode": None,
            "AccountCode": "41102000",
            'WarehouseCode': 'EC-FG',
            "Quantity": "1",
            "TaxCode": "IGST@12", #Maybe changed for specific items
            'TaxType': 'tt_Yes',
            'TaxLiable': 'tYES',
            'TaxTotal': 0.0,
            "UnitPrice": None,
            'PriceAfterVAT': None,
         'U_BuyerName': None, #channel_name
         'U_Order': None, 'U_OrderID': None, 
         'U_OrderedOn': None, 'U_City': None, 'U_State': None, 'U_PINCode': None, 'U_Country': 'India',
         'BatchNumbers': [{'BatchNumber': 'G3H102F04G',"Quantity": 1  }]}
            lineitem_delivery['ItemCode'] = itemss.itemsku
            lineitem_delivery['PriceAfterVAT'] = itemss.total_price
            lineitem_delivery['U_BuyerName'] = order_doc.customer_name
            lineitem_delivery['U_Order'] = order_doc.uniware_id
            lineitem_delivery['U_City'] = order_doc.city
            lineitem_delivery['U_State'] = order_doc.state
            lineitem_delivery['U_PINCode'] = order_doc.pin_code
            lineitem_delivery['U_Country'] = 'India'
            lineitem_delivery['BatchNumbers'][0]['BatchNumber'] = itemss.vendorbatchnumber
            Delivery_payload["DocumentLines"].append(lineitem_delivery) #appending as a lineitems inside inv_payload dictionary
    LineNum_Count = 0
    #print('List of lineitem in delivery payload : ',len(Delivery_payload['DocumentLines']))
    for Line_item in Delivery_payload['DocumentLines']:
        Line_item['LineNum'] = LineNum_Count
        LineNum_Count += 1
    SAPsession =  AuthenticateSAPB1()
    headersList = {
                "Accept": "*/*",
                "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                "Content-Type": "application/json" 
            }
    doc_settings = frappe.get_doc('SAP Settings')
    invoice_Url = doc_settings.sap_b1_url+"DeliveryNotes" #DeliveryNotes
    response = SAPsession.request("POST", invoice_Url, data=json.dumps(Delivery_payload),  headers=headersList,verify=False)
    # if response.json()[] == True:
    #     pass
    #code to be inserted 
    ####response docNum to be collected and pushed into the data point of the order-
    ## DocType using a loop in the list - open doctype and writing data  ## 
    return response.json()

# %%
@frappe.whitelist()
def get_completed_orders():
    channel_list = ['Snapdeal','Amazon_IN']
    Channel_CustomerCode_mapping = {'Snapdeal' : 'C03186','Amazon_IN':'C03186'}
    SAPsession =  AuthenticateSAPB1()
    for channel_id in channel_list[:1]:
        Channelwise_completed_orders = frappe.db.get_list('Unicommerce Orders', filters={'status': 'PROCESSING', 'channel_name': channel_id })
        print(Channelwise_completed_orders)
        Proper_channel = Channel_CustomerCode_mapping[channel_id]
        response = delivery_from_orderlist(SAPsession,Proper_channel,Channelwise_completed_orders[:2])
        print(response)

#bench --site medusa.localhost execute khanal_tech_integrations.khanal_tech_integrations.Prozo_SAP.get_completed_orders

# %%
@frappe.whitelist()
def Create_GRNs_Uniware_PO():
    List_of_InevntoryStockTransfer = frappe.db.get_list('SAP Inventory Transfers',filters={'fromwarehouse': 'EC-FG', 'towarehouse': 'EC-B2C' })
    for inv_document in List_of_InevntoryStockTransfer:
        Single_inv_doc = frappe.get_doc('SAP Inventory Transfers', inv_document['name'])
        if Single_inv_doc.uniware_po_id != None and Single_inv_doc.uniware_po_status== 'APPROVED': #checking if PO is in unicommerce created for this doc
            if Single_inv_doc.uniware_grn_no == None:
                Single_inv_doc.uniware_grn_no = []
                #Then we need to create A single GRN and post some items into it 
                Created_GRN_Dict = create_GRN(Single_inv_doc.uniware_po_id)
                if Created_GRN_Dict['successful'] == 'True': #GRN is created already then add SKUs into this 
                    Single_inv_doc.uniware_grn_no.append(Created_GRN_Dict['inflowReceiptCode'])
                    ##Contain the code to enter SKUs into a GRN
                    Freshly_added_SKUs = Adding_SKUs_to_grn(Created_GRN_Dict['inflowReceiptCode'],Single_inv_doc.line_items)
                    print('Nos of items added into the GRN is', len(Freshly_added_SKUs))

                else:
                    print('GRN creation failed for PO No :', Single_inv_doc.uniware_po_id  )
                    ##Contain the code to enter SKUs into a GRN

            elif Single_inv_doc.uniware_grn_no != None:
                print(Single_inv_doc.uniware_grn_no)
                while Single_inv_doc.uniware_po_status != 'COMPLETE': #<<<<<<<<<<<<<<<<<<Things could break from here
                    Already_GRN_Added_SKUs = []
                    for One_GRN in Single_inv_doc.uniware_grn_no: #uniware_GRN is a list of GRNs
                        for item in Getting_GRN_LineItems(One_GRN):
                            Already_GRN_Added_SKUs.append(item)
                    #Now we need to compare this big list with 
                    #Set substraction result = A-B
                    A = set(converting_documentslineitems_GRNinflow_format(Single_inv_doc))
                    B = set(Already_GRN_Added_SKUs)
                    Result = [item for item in A if item not in B]
                    if len(Result) != 0:
                        Newly_created_GRN = create_GRN(Single_inv_doc.uniware_po_id)
                        if Newly_created_GRN['successful'] == 'True': #GRN is created already then add SKUs into this 
                            Single_inv_doc.uniware_grn_no.append(Newly_created_GRN['inflowReceiptCode'])
                            GRN_SKUwise_Details = {
                            "inflowReceiptCode": "NAN",
                            "inflowReceiptItem": None }
                            GRN_SKUwise_Details["inflowReceiptCode"] = Newly_created_GRN['inflowReceiptCode']
                            uniware_session = AuthenticateUniware()
                            for one_item in Result:
                                SKU_adding_Url = "https://khanalfoods.unicommerce.com/services/rest/v1/purchase/inflowReceipt/addItemSKU"
                                headersList = { "Accept": "*/*", 
                                                    "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                                                    "Content-Type": "application/json" ,'facility':'khanalfoods'
                                                }
                                headersList['Authorization'] = 'bearer ' + uniware_session['access_token']
                                response = requests.request("POST", SKU_adding_Url, data=json.dumps(one_item),  headers=headersList)
                                print(response.json()['successful'])
    

# %%
@frappe.whitelist()
def Getting_GRN_LineItems(single_GRN):
    existing_GRN = {   "inflowReceiptCode": str(single_GRN) } 
    GRN_details_url = "https://khanalfoods.unicommerce.com/services/rest/v1/purchase/inflowReceipt/getInflowReceipt"
    uniware_session = AuthenticateUniware()
    headersList1 = { "Accept": "*/*",
                            "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                            "Content-Type": "application/json"
                                    }
    headersList1["facility"] = 'khanalfoods'
    headersList1['Authorization'] = 'bearer ' + uniware_session['access_token']
    GRN_details_response = requests.request("POST", GRN_details_url, data=json.dumps(existing_GRN),  headers=headersList1)
    Existing_GRN_Items = GRN_details_response.json()['inflowReceiptItems']
    GRN_SKUadding_formated_List = []
    for batchwise_item in Existing_GRN_Items:
        inflowItem = { "skuCode": None, "quantity": 1, "unitPrice": 1,
            "wsBatchDetail": { "wsBatchGroupFieldValue" : { "vendorBatchNumber": "NA" }}                     }
        inflowItem['skuCode'] = batchwise_item['itemSKU']
        inflowItem["quantity"] = batchwise_item['quantity']
        inflowItem['wsBatchDetail']['wsBatchGroupFieldValue']['vendorBatchNumber'] = batchwise_item['batchDTO']['batchCode']['batchFieldsDTO']['vendorBatchNumber']
        #'batchDTO' : {'batchCode': '','batchFieldsDTO': {'vendorBatchNumber':'NA'}
        GRN_SKUadding_formated_List.append(inflowItem)
    final_list = GRN_SKUadding_formated_List
    return final_list



def converting_documentslineitems_GRNinflow_format(document):
    Inv_transfer_doc_LineItems = document.line_items
    GRN_SKUadding_formated_List = []
    for one_item in Inv_transfer_doc_LineItems:
        inflowItem = { "skuCode": None, "quantity": 1, "unitPrice": 1,
            "wsBatchDetail": { "wsBatchGroupFieldValue" : { "vendorBatchNumber": "NA" }}                     }
        inflowItem['skuCode'] = one_item.itemcode
        inflowItem["quantity"] = one_item.batchquantity #batchwise quantity to be used
        inflowItem['wsBatchDetail']['wsBatchGroupFieldValue']['vendorBatchNumber'] = one_item.batchnumber #batchcode from SAP 
        GRN_SKUadding_formated_List.append(inflowItem)
    return GRN_SKUadding_formated_List
     
