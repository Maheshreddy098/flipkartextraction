import json
from warnings import filters
import requests
from khanal_tech_integrations.utils.prozo.authenticate import get_token
from khanal_tech_integrations.utils.prozo.purchase_orders import get_item_id
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
import frappe
from frappe.utils import add_to_date


pz_whse = {'PZ-MU-FG':'24','PZ-GU-FG':'22'}

def get_SAP_customer(Cardcode):#Cardcode=None
    """
    Given an Customer_Code : C00038,it will pull the details from SAP and 
    create a Debitor in PROZO,
    Is needed when while ceating an order we dont have customer in the prozo debtors list.
    """
    
    PROZO_customer_payload = {   
                                "firstName":"Test1",
                                "lastName":"",  
                                "mobile":"1181100221",
                                "email":"test1@gmail.com",
                                "salutation":"Mr.",
                                "company":
                                            {   
                                            "registeredName":"Test1",
                                            "type":"PVT_LTD",
                                            "panCard":"",
                                            "gstin":"",
                                            "aadharNo":"",
                                            "securityChequeNo":""
                                            },
                                "warehouse" :   {"id"   :  24}, #To BE changed
                                "shipper"   :   {"id"   :  4},
                                    "paymentTerm":"NET_30", #toChange
                                    "creditLimit":"",
                                    "accountType":"POSTPAID",
                                    "displayName":"Test1", #CardName
                                    "address":[
                                    {
                                        "name":"lane 1",
                                        "addressLine1":"lane2",
                                        "addressLine2":"","addressLine3":"",
                                        "mobile":"1111111111",
                                        "city":{"id":641},  #I need to the city-mapping 
                                        "postalCode":"274301",
                                        "type":"BILLING"}]
                                                        }
                
    #Cardcode            = 'C03277'
    session             = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url                 = doc_settings.sap_b1_url+"BusinessPartners('{cardcode}')"
    reqUrl              = Url.format(cardcode=Cardcode)
    empty_payload       = ""
    headersList         =     {
                            "Accept": "*/*",
                            "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                            "Content-Type": "application/json" 
                            }
    response = session.request("GET", reqUrl, data = empty_payload,  headers=headersList,verify=False)
    response = response.json()
    All_city =get_all_City()

    if  response.get('CardCode') is not None:
        PROZO_customer_payload['firstName']                     =   response['CardCode']
        PROZO_customer_payload['mobile']                        =   response['Phone1'] #'2233983312'  # 
        PROZO_customer_payload['email']                         =   str(response['CardCode']).lower() + "@gmail.com" #esponse['EmailAddress']
        PROZO_customer_payload['company']['registeredName']     = response['CardName'] #"Logan" 
        #PROZO_customer_payload['salutation']                   = response['CardCode']
        #PROZO_customer_payload['lastName']                     = response['GroupCode']
        #PROZO_customer_payload['company']['type']              = response['CardName']
        #PROZO_customer_payload['paymentTerm']                  = response['BPAddresses']
        for BP_address in response['BPAddresses']:
            if BP_address['AddressType'] == 'bo_ShipTo':
                PROZO_customer_payload['address'][0]['name']            = BP_address['AddressName']
                PROZO_customer_payload['address'][0]['addressLine1']    = BP_address['Street']
                PROZO_customer_payload['address'][0]['addressLine2']    = BP_address['Block']
                PROZO_customer_payload['address'][0]['mobile']          = response['Phone1'] #May be changed if adress have phone contact
                PROZO_customer_payload['address'][0]['city']['id']      = All_city[str(BP_address['City'])]
                PROZO_customer_payload['address'][0]['postalCode']      = BP_address['ZipCode']
        
        result              = json.dumps(PROZO_customer_payload)
        prozo_payload       = { "debtor"    :    result  }
        #print(prozo_payload)
        Customer_url        = "https://staging.prozo.com/wms/v1/debtor"
        files               = {'file': ( None, None, 'text/plain')}
        headers             =   {       'id'        : '1',
                                        'source'    : '2',
                                        'tenant'    : 'tenant_28',
                                'Accept-Encoding'   : 'gzip',
                                'Accept-Encoding'   : 'deflate',
                                'Accept-Encoding'   : 'br',
                                    'Authorization' : 'eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwiYXVkaWVuY2UiOiJ3ZWIiLCJjcmVhdGVkIjoxNjY3Mzc0OTEwMDgwLCJpc0FkbWluIjp0cnVlLCJleHAiOjE3MzczNzQ5MTAsInRlbmFudCI6InRlbmFudF8yOCJ9.4rC8Jsdghbsz1LKqlz92JIbAt7_RNU8kzgOqH3vndMUvBiCITrzUUhL9GII4anT_ZNMq-FzD2420gsamWYM0rg'
                                }
        PRZ_response = requests.post( Customer_url,    data   =   prozo_payload,
                                                    headers   =   headers,
                                                      files   =   files )
    return PRZ_response #None 



@frappe.whitelist()
def Order_Creation_flow(docentry=None):
    order_docentry          = docentry
    All_orders              = get_all_orders()
    for single_order in All_orders:
        if single_order.get('referenceNumber') is None:
            single_order['referenceNumber'] = None
    Orders_docNum_list      = [order['referenceNumber'] for order in All_orders]
    
    session                 = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url                     = doc_settings.sap_b1_url+"Orders({DocEntry})" 
    reqUrl                  = Url.format(DocEntry=order_docentry)
    empty_payload           = ""
    headersList             =     {
                                    "Accept"        : "*/*",
                                    "User-Agent"    : "Thunder Client (https://www.thunderclient.com)",
                                    "Content-Type"  : "application/json" 
                                    }
    response                = session.request("GET", reqUrl, data = empty_payload,  headers=headersList,verify=False)
    SO_response             = response.json()
    
    if  SO_response.get('CardCode') is not None:
        if SO_response['DocNum'] not in Orders_docNum_list:
            ################
            Customer_List       = get_customers()
            Customers_id_list   = [customer['firstName'] for customer in Customer_List]
            Customers_Dict      = { c['firstName'] : c['id'] for c in Customer_List}
            if SO_response['CardCode'] not in Customers_id_list:
                
                print("Hello,New Customer")
                Customer_response= get_SAP_customer(SO_response['CardCode'])
                if Customer_response.headers.get('id') is not None: #need to debug response['id']
                    print("For SAP Customer" + str(SO_response['CardCode']) + " PROZO customer id is " + str(Customer_response.headers['id']) )
                    print("Order Creation Flow running again.")
                    Order_Creation_flow(docentry)
                else:
                    print("Customer wasnt created")
                    print(Customer_response.json())
                    
            else:
                    #Create Order and Then add Lineitems
                Customer_ID     = Customers_Dict[SO_response['CardCode']]
                Order_response  = create_order(SAP_Docentry =   order_docentry, Debtor_id       =   Customer_ID)
                if Order_response.headers.get('id') is not None: 
                    print("Order creation successful,now adding lineitems.")
                    add_lineitems_into_order(docEntry       =   order_docentry ,    Prozo_order_id  =   Order_response.headers['id'] )
                else:
                    print("order creation failed -",Order_response.json() )
        else:
            print("Order id :" + str(SO_response['DocNum']) + "Alread exists in PROZO B2B orders.")
    else:
        print("SAP response was not pulled : ERROR")
            
    return None
    

def get_customers():
    """
    Pull all the existing customers in prozo Database.
    """

    url = "https://staging.prozo.com/wms/v1/debtor"#?flag=1&limit=20&id=1936"
    payload={}
    headers = {
                    'id': '1',
                    'source': '2',
                   'tenant': 'tenant_28',
                    'Authorization': 'eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwiYXVkaWVuY2UiOiJ3ZWIiLCJjcmVhdGVkIjoxNjY3Mzc0OTEwMDgwLCJpc0FkbWluIjp0cnVlLCJleHAiOjE3MzczNzQ5MTAsInRlbmFudCI6InRlbmFudF8yOCJ9.4rC8Jsdghbsz1LKqlz92JIbAt7_RNU8kzgOqH3vndMUvBiCITrzUUhL9GII4anT_ZNMq-FzD2420gsamWYM0rg'
                    }

    response = requests.request("GET", url, headers=headers, data=payload)
    return response.json()

def single_customer(customer):
    url         =   "https://staging.prozo.com/wms/v1/debtor?flag=1&limit=20&id=" + str(customer)

    payload     =   {}
    headers     =   {
                    'tenant': 'tenant_28',
                    'Authorization': 'eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwiYXVkaWVuY2UiOiJ3ZWIiLCJjcmVhdGVkIjoxNjY3Mzc0OTEwMDgwLCJpc0FkbWluIjp0cnVlLCJleHAiOjE3MzczNzQ5MTAsInRlbmFudCI6InRlbmFudF8yOCJ9.4rC8Jsdghbsz1LKqlz92JIbAt7_RNU8kzgOqH3vndMUvBiCITrzUUhL9GII4anT_ZNMq-FzD2420gsamWYM0rg'
                    }

    response = requests.request("GET", url, headers=headers, data=payload)
    return response.json()

#%%

def create_order(SAP_Docentry,Debtor_id): #Payload
    """
    Given an SAP Docentry it will pull the SO details from SAP,
    and it will raise an Order in prozo with provided Debtor_id/Customer_id.
    """
    order_docentry      = SAP_Docentry
    Customer_id         = Debtor_id
    session             = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url                 = doc_settings.sap_b1_url+"Orders({DocEntry})" #"v1//BusinessPartners('{cardcode}')"
    reqUrl              = Url.format(DocEntry=order_docentry)
    empty_payload       = ""
    headersList         =     {
                            "Accept"        : "*/*",
                            "User-Agent"    : "Thunder Client (https://www.thunderclient.com)",
                            "Content-Type"  : "application/json" 
                              }
    response            = session.request("GET", reqUrl, data = empty_payload,  headers=headersList,verify=False)
    SO_response         = response.json()
    temp_payload        = {         "customer"  :   {"id":None},
                            "billingAddress"    :   {"id":661},
                            "shippingAddress"   :   {"id":661},
                            "warehouse"         :   {"id":22},
                            "referenceNumber"   :   "DocNum is enterd here",
                            "type"              :   "B2B",
                            "notes"             :    "DocEntry is enetered here"
                     }   
    if  SO_response.get('CardCode') is not None:
        Single_customer                         = single_customer(Customer_id )
        print(Single_customer)
        temp_payload['customer']['id']          = Single_customer[0]['id']
        temp_payload['billingAddress']['id']    = Single_customer[0]['address'][0]['id']
        temp_payload['shippingAddress']['id']   = Single_customer[0]['address'][0]['id']
        temp_payload['warehouse']['id']         = Single_customer[0]['warehouse']['id']
        temp_payload['referenceNumber']         = SO_response['DocNum']
        temp_payload['notes']                   = SO_response['DocEntry']

        #print(temp_payload)

        url = "https://staging.prozo.com/wms/v1/offline_order"
     
                
        files                   = {'file': ( None, None, 'text/plain')}
        stringed_dictionary     = json.dumps(temp_payload)
        payload_stringed        =    {   "order"  :  stringed_dictionary }
        #print(payload_stringed)

        files                   = {'file': ( None, None, 'text/plain')}
    
        headers     =               {
                                    'id'        : '1',
                                    'source'    : '2',
                                    'tenant'    : 'tenant_28',
                            'Accept-Encoding'   : 'gzip',
                            'Accept-Encoding'   : 'deflate',
                            'Accept-Encoding'   : 'br',
                                'Authorization' : 'eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwiYXVkaWVuY2UiOiJ3ZWIiLCJjcmVhdGVkIjoxNjY3Mzc0OTEwMDgwLCJpc0FkbWluIjp0cnVlLCJleHAiOjE3MzczNzQ5MTAsInRlbmFudCI6InRlbmFudF8yOCJ9.4rC8Jsdghbsz1LKqlz92JIbAt7_RNU8kzgOqH3vndMUvBiCITrzUUhL9GII4anT_ZNMq-FzD2420gsamWYM0rg'
                                    }
        PROZO_response = requests.post( url, data   =   payload_stringed,
                                            headers =   headers,
                                            files   =   files  )
    return PROZO_response


# %%
#WORKING
#22-GUR
#24-BHIS

# %%
def get_all_orders():
    url = "https://staging.prozo.com/wms/v1/order?flag=1&limit=40"

    payload     =   {}
    headers     =   {
                'tenant'        : 'tenant_28',
                'Authorization' : 'eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwiYXVkaWVuY2UiOiJ3ZWIiLCJjcmVhdGVkIjoxNjY5NjE2MjIyNjE1LCJpc0FkbWluIjp0cnVlLCJleHAiOjE3Mzk2MTYyMjIsInRlbmFudCI6InRlbmFudF8yOCJ9.KmD7Kl2CVzsotL9gOiFVJ9HJERzYLipL-fn4bQCF1xSNdhnkH11Y5TJxJjc3dBsoS5m9INzaCg0kRAtcXMPbHA',
                'warehouseId'   : '24',
                    }
    #headers['warehouseId']   : '22'
    response = requests.request("GET", url, headers=headers, data=payload)

    return response.json()
# Order_data = get_all_orders()
# All_orders = { c['code'] : c['status'] for c in Order_data}
# %%
def get_single_order(Single_order_id=None):
    """
    Given an prozo_order_id it pulls details of an order
    status log, lineitems with batches , current staus etc.
    """
    Order_id    = Single_order_id
    url         = "https://staging.prozo.com/wms/v1/order/" + str(Order_id)
    #token       = get_token()

    payload     =   {}
    headers     =   { 'tenant'        : 'tenant_28', 
                      'Authorization' : 'eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwiYXVkaWVuY2UiOiJ3ZWIiLCJjcmVhdGVkIjoxNjY5NzA2MzExNjk4LCJpc0FkbWluIjp0cnVlLCJleHAiOjE3Mzk3MDYzMTEsInRlbmFudCI6InRlbmFudF8yOCJ9.t48920YVDO2_uivedZs9R-KptO2C0f1hHqn4UF39WdHsraSx6_r_Uxi-vNjkfHqyj8ZKIoXX-VMW3tfSRVBBDg',
                      }
    response    = requests.request("GET", url, headers=headers, data=payload)

    return response.json()

# %%
def get_all_items():
    """
    This pulls all the order their SKU code and their respective id created in prozo.
    To be used in lineitems adition in PROZO order instead of SKU code we use "order_id"
    """
    url = "https://staging.prozo.com/wms/v1/product?flag=1&limit=500&typeCodeCSV=0"

    payload={}
    headers = {
                'id'    : '1',
                'source': '2',
                'tenant': 'tenant_28',
                'Authorization': 'eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwiYXVkaWVuY2UiOiJ3ZWIiLCJjcmVhdGVkIjoxNjY5NzA2MzExNjk4LCJpc0FkbWluIjp0cnVlLCJleHAiOjE3Mzk3MDYzMTEsInRlbmFudCI6InRlbmFudF8yOCJ9.t48920YVDO2_uivedZs9R-KptO2C0f1hHqn4UF39WdHsraSx6_r_Uxi-vNjkfHqyj8ZKIoXX-VMW3tfSRVBBDg'
            }

    response = requests.request("GET", url, headers=headers, data=payload)

    return response.json()

def get_all_City():
    """
    It pull a list of cities and their id from PROZO address database,
    this is used while creating customer in place of their city : we place city_id.
    """
    url =  "https://staging.prozo.com/wms/v1/city/list"

    payload={}
    headers = {
                'id'    : '1',
                'source': '2',
                'tenant': 'tenant_28',
                'Authorization': 'eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwiYXVkaWVuY2UiOiJ3ZWIiLCJjcmVhdGVkIjoxNjY5NzA2MzExNjk4LCJpc0FkbWluIjp0cnVlLCJleHAiOjE3Mzk3MDYzMTEsInRlbmFudCI6InRlbmFudF8yOCJ9.t48920YVDO2_uivedZs9R-KptO2C0f1hHqn4UF39WdHsraSx6_r_Uxi-vNjkfHqyj8ZKIoXX-VMW3tfSRVBBDg'
            }

    response = requests.request("GET", url, headers=headers, data=payload)
    city_minimal = { city['name']:city['id'] for city in response.json()  }
    print(response.json()[0])

    return city_minimal

# %%
def add_lineitems_into_order(docEntry , Prozo_order_id ):
    """
    Given an order id and related SAP docentry it add lineitems 
    into PROZO order,one by one.
    """
    order_docentry      =   docEntry
    All_items_PROZO     =   get_all_items()
    SKU_list            =   {    item['sku']:item['id'] for item in All_items_PROZO  }
    print(len(SKU_list))
    session             =   AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url                 =   doc_settings.sap_b1_url+"Orders({DocEntry})" #"v1//BusinessPartners('{cardcode}')"
    reqUrl              =   Url.format(DocEntry=order_docentry)
    empty_payload       =   ""
    headersList         =     {
                            "Accept"        : "*/*",
                            "User-Agent"    : "Thunder Client (https://www.thunderclient.com)",
                            "Content-Type"  : "application/json" 
                              }
    response            =   session.request("GET", reqUrl, data = empty_payload,  headers=headersList,verify=False)
    SO_response         =   response.json()
    
    if  SO_response.get('CardCode') is not None:
        Single_item_payload = {   "product" :   {"id":60,},
                                    "order" :   {"id":"140"},   
                                #  "mrp"    :   0,    
                            "totalQuantity" :   20,    
                            "discountRate"  :   0 ,  }
        for line_item in SO_response['DocumentLines']:
            if SKU_list.get(line_item['ItemCode']) is not None:
                #Item is Already Listed in Item listing 
                Single_item_payload['product']['id']    =  SKU_list[line_item['ItemCode']]
                Single_item_payload['order']['id']      =  str(Prozo_order_id) 
                Single_item_payload['totalQuantity']    =  int(line_item['Quantity'])
                # Single_item_payload['mrp']              =  line_item['Price']
                # Single_item_payload['discountRate']     =  line_item['DiscountPercent']

                add_item_url        = "https://staging.prozo.com/wms/v1/order_product"
                headers             = {
                        'tenant': 'tenant_28',
                        'Authorization': 'eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwiYXVkaWVuY2UiOiJ3ZWIiLCJjcmVhdGVkIjoxNjY5NzA2MzExNjk4LCJpc0FkbWluIjp0cnVlLCJleHAiOjE3Mzk3MDYzMTEsInRlbmFudCI6InRlbmFudF8yOCJ9.t48920YVDO2_uivedZs9R-KptO2C0f1hHqn4UF39WdHsraSx6_r_Uxi-vNjkfHqyj8ZKIoXX-VMW3tfSRVBBDg',
                        'Content-Type': 'application/json'
                        }

                response            = requests.request("POST", add_item_url, headers=headers, data= json.dumps(Single_item_payload))
                print(line_item['ItemCode'])
                print(response)
            elif SKU_list.get(line_item['ItemCode']) is None:
                print(str(line_item['ItemCode'])  + "is not in PROZO item-listing.")
    Order_details               = get_single_order(Single_order_id = Prozo_order_id)
    if Order_details.get('products') is None:
        Already_added_lineitems    =  Order_details['products']
        print("Numbers of item added = " + str(len(Already_added_lineitems)) + "out of " + str(len(SO_response['DocumentLines']) ))

    return None #("Numbers of item added = " + str(len(Already_added_lineitems)) + "out of " + str(len(SO_response['DocumentLines']) ))



# %%
# import requests
# import json

# Single_item_payload = json.dumps({"product" :   {"id":60,},
#                                     "order" :   {"id":"127"},   
#                                      "mrp"  :   300,    
#                             "totalQuantity" :   20,    
#                             "discountRate"  :   0})
# url = "https://staging.prozo.com/wms/v1/order_product"

# headers = {
#             'tenant': 'tenant_28',
#             'Authorization': 'eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwiYXVkaWVuY2UiOiJ3ZWIiLCJjcmVhdGVkIjoxNjY5NzA2MzExNjk4LCJpc0FkbWluIjp0cnVlLCJleHAiOjE3Mzk3MDYzMTEsInRlbmFudCI6InRlbmFudF8yOCJ9.t48920YVDO2_uivedZs9R-KptO2C0f1hHqn4UF39WdHsraSx6_r_Uxi-vNjkfHqyj8ZKIoXX-VMW3tfSRVBBDg',
#             'Content-Type': 'application/json'
#             }

# response = requests.request("POST", url, headers=headers, data=Single_item_payload)
# print(type(response))

# print(response)

# %%

def patch_Stock_Allocated(order_id=None):
    """
    Given an order id it pushes the action button called -allocated-
    """

    
    url = "https://staging.prozo.com/wms/v1/order"

    payload = json.dumps({"id":order_id,"action":"Allocate_Stock"})
    headers =   {
                'tenant'        : 'tenant_28',
                'Authorization' : 'eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwiYXVkaWVuY2UiOiJ3ZWIiLCJjcmVhdGVkIjoxNjY5NzA2MzExNjk4LCJpc0FkbWluIjp0cnVlLCJleHAiOjE3Mzk3MDYzMTEsInRlbmFudCI6InRlbmFudF8yOCJ9.t48920YVDO2_uivedZs9R-KptO2C0f1hHqn4UF39WdHsraSx6_r_Uxi-vNjkfHqyj8ZKIoXX-VMW3tfSRVBBDg',
                'id'            : '1',
                'source'        : '2',
                'Content-Type'  : 'application/json'
                }

    response = requests.request("PATCH", url, headers=headers, data=payload)

    print(response.text)



# %%
def Get_batchdetails(order_id):
    """
    Given an PROZO order_id it produces a dictionary of SKU_code
    as key , and list of batch-quantity as values.
    """
            
    item_wise_batch = {}
    Single_order    = get_single_order(Single_order_docentry=order_id)
    for product in Single_order['products']:
        if product.get('orderProductBatches') is not None:
            print(product['product']['sku'],product['orderProductBatches'])
            item_wise_batch[product['product']['sku']] = product['orderProductBatches']

    return item_wise_batch


# %%
def get_status(SAP_docentry):
    """
    Given a SAP_docentry it will pull the latest status 
    for the associated order in PROZO
    """
    Order_data = get_all_orders()
    Status_List = None
    All_orders = { order['referenceNumber'] : order['status'] for order in Order_data}
    if All_orders.get(str(SAP_docentry) ) is not None:
        Single_order    = get_single_order( All_orders[str(SAP_docentry)]  )
        Status_List     = Single_order['statusDetail']
        
        #
    return Status_List #Status_List[-1]['statusName']
# %%
@frappe.whitelist()
def invoice_from_order(): #channel,completed_orderlist
    '''
    Given a SAP DocEntry it will pull the lineitems detail and the associated PROZO order detail with batch,
    and blend that together to create a invoice in SAP.
    '''
    SAP_Docentry        = 6806

    #####################################################################################
    order_docentry      = SAP_Docentry
    session             = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url                 = doc_settings.sap_b1_url+"Orders({DocEntry})" #"v1//BusinessPartners('{cardcode}')"
    reqUrl              = Url.format(DocEntry=order_docentry)
    empty_payload       = ""
    headersList         =     {
                            "Accept"        : "*/*",
                            "User-Agent"    : "Thunder Client (https://www.thunderclient.com)",
                            "Content-Type"  : "application/json" 
                              }
    response            = session.request("GET", reqUrl, data = empty_payload,  headers=headersList,verify=False)
    SO_response         = response.json()
    Invoice_payload = { "CardCode"         : "C_Dummy" ,
                         "Comments"         : None,
                         "PayToCode"        : None,
                         #"ShipToCode"       : bill_to_code,
                         "U_BillingFrom"    : 'to_be_replaced',
                         'U_BillTo'         : None,
                         "UseBillToAddrToDetermineTax": "tYES",
                         #"PlaceOfSupply": PayToState, #Here i am inserting the State Code
                         "DocumentLines"    : []}

    All_orders              = get_all_orders()
    Orders_docNum_dict      = { order['referenceNumber'] : order['id']  for order in All_orders}
    Orders_Status_dict      = { order['referenceNumber'] : order['status']  for order in All_orders}

    if  SO_response.get('CardCode') is not None and Orders_docNum_dict.get(str(SO_response['DocNum'] )) is not None:
        print(Orders_docNum_dict[str(SO_response['DocNum'] )])
        comment = "ecommerce B2C orders for SO-{}  Posted Using API from PROZO".format(SO_response['DocNum'] )
        Invoice_payload['CardCode']         = SO_response['CardCode']
        Invoice_payload['Comments']         = None
        Invoice_payload['PayToCode']        = SO_response['PayToCode']
        Invoice_payload['U_BillTo']         = SO_response['U_BillTo'] #U_BillingFrom
        Invoice_payload['U_BillingFrom']    = SO_response['U_BillingFrom'] #U_BillingFrom

        print(SO_response['U_BillTo'])

        Item_wiseBatch                      = Get_batchdetails(order_id = int(Orders_docNum_dict[str(SO_response['DocNum'] )] ))

        
        ##########################################################################################


        for item in SO_response['DocumentLines']:
            lineitem_delivery = { "LineNum": 0,
                                 "ItemCode": None,
                                 "AccountCode": None, # 41106001 - Karnataka Local Sales, 41106002 - Karnataka Central Sales
                                'WarehouseCode': 'EC-B2C', "Quantity": "1",
                                "TaxCode": "KACS12", #Will changed for specific items
                                'TaxType': 'tt_Yes',  
                                'TaxLiable': 'tYES',
                                'TaxTotal': 0.0,      
                                "UnitPrice": None,
                                'BatchNumbers': [    ]
                                    }
            single_batch = {'BatchNumber': 'PLACEHOLDER_BATCH',  "Quantity": 1  }    
        
            lineitem_delivery['LineNum']            = item['LineNum']
            lineitem_delivery['ItemCode']           = item['ItemCode']
            lineitem_delivery['AccountCode']        = item['AccountCode']
            lineitem_delivery['WarehouseCode']      = 'PZ-MU-FG' #item['WarehouseCode'] #PZ-MU-
            lineitem_delivery['TaxCode']            = item['TaxCode']
            print( lineitem_delivery['ItemCode'] , item['WarehouseCode'] )
            lineitem_delivery['Quantity']           = item['Quantity']
            lineitem_delivery['UnitPrice']          = item['UnitPrice']
            #lineitem_delivery['TaxCode'] =  get_GST(origin_state,order_doc.state,itemss.itemsku)#'GST@' + str(itemss.integratedgstpercentage) 
            
            batch_assigned                          =  [{'quantity': 10, 'productBatch': {'batchNo': 'G3H11705'}}] #Item_wiseBatch[item['ItemCode']]
            for batch_quantity in batch_assigned:
                single_batch['BatchNumber']         = None
                single_batch['Quantity']            = batch_quantity['quantity']
                if batch_quantity['productBatch'].get('batchNo')is not None:
                    single_batch['BatchNumber']     = batch_quantity['productBatch']['batchNo']
                else:
                    print("Batch is not available.")
                lineitem_delivery['BatchNumbers'].append(single_batch)  

            #appending as a lineitems inside inv_payload dictionary
            Invoice_payload["DocumentLines"].append(lineitem_delivery) 
            # print ('Delivery_payload before: ',Delivery_payload)
        
        print('List of lineitem in delivery payload : ',len(Invoice_payload['DocumentLines']))
    
    SAPsession =  AuthenticateSAPB1()
    print ('DELIVERY PAYLOAD')
    print (json.dumps(Invoice_payload))
    invoice_Url = doc_settings.sap_b1_url+"Invoices" #DeliveryNotes
    response = SAPsession.request("POST", invoice_Url, data=json.dumps(Invoice_payload),  headers=headersList,verify=False)
    # print('response is',response.json())
    ####response docNum to be collected and pushed into the data point of the order-
    ## DocType using a loop in the list - open doctype and writing data  ## 
    return response.json()