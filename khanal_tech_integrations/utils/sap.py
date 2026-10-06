import requests
import json
import frappe
from frappe.utils import add_to_date, now, get_datetime, now_datetime
#import time
import datetime
from collections import ChainMap
import collections

headersList = {
                    "Accept": "*/*",
                    "User-Agent": "Khanal Tech",
                    "Content-Type": "application/json" 
                }

#Function to authenticate SAP B1
def AuthenticateSAPB1():
    """
    Function to Authenticate SAP Business One
    """
    b1_session = requests.Session()

    doc = frappe.get_doc('SAP Settings')

    expires_on = frappe.db.get_single_value('SAP Settings','expires_on')
    
    b1session_val = frappe.db.get_single_value('SAP Settings', 'b1session')
    routeid_val = frappe.db.get_single_value('SAP Settings', 'routeid')
    if (expires_on == '' or not b1session_val):
        try:
            b1_session = renew_sap_session()
        except Exception as e:
            raise e
    elif expires_on != '':
        if now_datetime() >= get_datetime(doc.expires_on):
            try:
                b1_session = renew_sap_session()
            except Exception as e:
                raise e
        else:
            b1_session.cookies.set("B1SESSION", b1session_val)
            if routeid_val:
                b1_session.cookies.set("ROUTEID", routeid_val)
    return b1_session

@frappe.whitelist()
def initiate_session():
    x = AuthenticateSAPB1()
    print (x.headers)
    print (x.cookies)

@frappe.whitelist()
def renew_sap_session():
    b1_session = requests.Session()
    doc = frappe.get_doc('SAP Settings')
    credentials_json = {"CompanyDB": doc.companydb,"Password": doc.get_password('password'),"UserName": doc.username}
    b1_url = doc.sap_b1_url
    reqUrl = b1_url + "Login"
    payload = json.dumps(credentials_json)
    response = b1_session.request("POST", reqUrl, data=payload,  headers=headersList, verify=False)
    cookies = b1_session.cookies.get_dict()
    try:
        body = response.json()
    except Exception:
        body = {}
    if not response.ok:
        err_msg = "Unknown"
        if isinstance(body.get("error"), dict):
            m = body["error"].get("message")
            err_msg = m.get("value", err_msg) if isinstance(m, dict) else (m or err_msg)
        elif isinstance(body.get("odata.error"), dict):
            m = body["odata.error"].get("message")
            err_msg = m.get("value", err_msg) if isinstance(m, dict) else (m or err_msg)
        else:
            err_msg = response.text[:500] if response.text else err_msg
        raise ValueError(f"SAP Login failed ({response.status_code}): {err_msg}")
    b1session = cookies.get("B1SESSION") or body.get("SessionId")
    routeid = cookies.get("ROUTEID")
    if not b1session:
        raise ValueError(
            "SAP Login did not return B1SESSION cookie or SessionId. "
            "Check SAP Service Layer URL, CompanyDB, UserName and Password, and that the service is running."
        )
    doc.b1session = b1session
    doc.routeid = routeid or ""
    session_timeout = body.get("SessionTimeout", 30)
    try:
        doc.expires_on = add_to_date(now_datetime(), minutes=int(session_timeout))
    except (TypeError, ValueError):
        doc.expires_on = add_to_date(now_datetime(), minutes=30)
    doc.save(ignore_permissions=True)
    return b1_session


@frappe.whitelist()
def bulk_process_inventory_transfers():
    """
    Update Inventory transfers from SAP to Khanal Tech Integrations 
    """
    session = AuthenticateSAPB1()
    payload = ''

    #CHECK THE LAST MAX UPDATED INV. TRANSFERS
    start_page = 10
    try:
        last_page_doc = frappe.get_last_doc('SAP Inventory Transfers Update Logs')
        start_page = last_page_doc.last_skip
    except:
        start_page = 1
    #for i in range(int(start_page),2):
    i = int(start_page)
    if i and i>1:
        i = i - 1

    # INITIALIZATION
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url+"StockTransfers?$skip=" + str(20*i)
    session = AuthenticateSAPB1()
    response = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
        
    transfer_requests = dict(response.json())
    next_page = transfer_requests.get("odata.nextLink",None)

    while True:
    #while next_page is not None:
        print ('SKIP : ', i)
        doc_settings = frappe.get_doc('SAP Settings')
        reqUrl = doc_settings.sap_b1_url+"StockTransfers?$skip=" + str(20*i)
        session = AuthenticateSAPB1()
        response = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
        transfer_requests = dict(response.json())
        
        try:
            if transfer_requests['value'] is not None:
                for transfer_request in transfer_requests['value']:
                    # print (transfer_request['DocNum'],' i:',i)
                    if frappe.db.exists('SAP Inventory Transfers',transfer_request['DocEntry']):
                        #skip
                        pass
                    else:
                        doc     = frappe.new_doc('SAP Inventory Transfers')
                        doc.docentry        = transfer_request['DocEntry']
                        doc.series          = transfer_request['Series']
                        doc.docdate         = transfer_request['DocDate']
                        doc.docnum          = transfer_request['DocNum']
                        doc.fromwarehouse   = transfer_request['FromWarehouse']
                        doc.towarehouse     = transfer_request['ToWarehouse']
                        doc.cardcode        = transfer_request['CardCode']
                        doc.comments        = transfer_request['Comments']
                        doc.delivered       = transfer_request['U_Delivered']
                        #doc.save()
                        try:
                            #try saving, skip if already exist
                            doc.save()
                        except frappe.DuplicateEntryError:
                            pass

                        doc = frappe.get_doc("SAP Inventory Transfers",transfer_request['DocEntry'])
                        LineItems = get_single_inventory_transfer(transfer_request['DocEntry'])
                        for LineItem in LineItems:
                            doc.append("line_items",LineItem)
                        doc.save()
                    frappe.db.commit() #
                i +=1
                #increment the counter
            elif transfer_requests['value'] is None:
                break
            
        except Exception as e:
            #break
            print ('Exception : ',e)

        next_page = transfer_requests.get("odata.nextLink",None)
        if next_page is None:
            break

    #Update the last page
    doc1 = frappe.new_doc('SAP Inventory Transfers Update Logs')
    doc1.last_skip = i
    doc1.save()

    frappe.msgprint(msg='Data Inserted successfully',title='Success')
    return None
#############################################################################################
@frappe.whitelist()
def single_process_inventory_transfers(DocEntry):
    """
    Update Inventory transfers from SAP to Khanal Tech Integrations given a single docEntry.
    """
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url+"StockTransfers(" + str(DocEntry) + ")"
    payload = ""

    headersList = {
                "Accept": "*/*",
                "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                "Content-Type": "application/json" 
            }
    response = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
    transfer_request = dict(response.json())

    if transfer_request['DocEntry'] is not None:
        print ('Going into')
        if frappe.db.exists('SAP Inventory Transfers',transfer_request['DocEntry']):
            doc     = frappe.get_doc('SAP Inventory Transfers',transfer_request['DocEntry'])
            print('Already in the database.')
        else:
            doc     = frappe.new_doc('SAP Inventory Transfers')
            doc.docentry        = transfer_request['DocEntry']
            doc.series          = transfer_request['Series']
            doc.docdate         = transfer_request['DocDate']
            doc.docnum          = transfer_request['DocNum']
            doc.fromwarehouse   = transfer_request['FromWarehouse']
            doc.towarehouse     = transfer_request['ToWarehouse']
            doc.cardcode        = transfer_request['CardCode']
            doc.comments        = transfer_request['Comments']
            doc.delivered       = transfer_request['U_Delivered']
            #doc.save()
            try:
                #try saving, skip if already exist
                doc.save()
            except frappe.DuplicateEntryError:
                pass

        doc = frappe.get_doc("SAP Inventory Transfers",transfer_request['DocEntry'])
        doc.line_items = []
        doc.save()
        frappe.db.commit() #
        LineItems = get_single_inventory_transfer(transfer_request['DocEntry'])
        for LineItem in LineItems:
            doc.append("line_items",LineItem)
            print('Line Updated')
        doc.save()
        frappe.db.commit() #
    elif transfer_request['value'] is None:
        print('Response from SAP failed.')
    return None

###############################################################################################################
###############################################################################################################
###############################################################################################################

def get_single_inventory_transfer(DocEntry):
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url+"StockTransfers(" + str(DocEntry) + ")"
    payload = ""

    headersList = {
                "Accept": "*/*",
                "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                "Content-Type": "application/json" 
            }
    response = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
    inventory_transfer = dict(response.json())

    LineItems = inventory_transfer['StockTransferLines']
    
    LineItem_list = []
    for LineItem in LineItems:
       
        for BatchDetail in LineItem['BatchNumbers']:
            #doc.line_items
            LineItem_list.append({"itemcode":LineItem['ItemCode'],
                                  "itemdescription":LineItem['ItemDescription'],
            "quantity"          :LineItem['Quantity'],
            "towarehousecode"   : LineItem['WarehouseCode'],
            "unitprice"         : LineItem["UnitPrice"],
            "fromwarehousecode" : LineItem['FromWarehouseCode'], 
            "batchnumber"       : BatchDetail['BatchNumber'],
            "batchquantity"     :BatchDetail['Quantity'],
            'expirydate'        : BatchDetail['ExpiryDate'],
            'manufacturingdate' : BatchDetail['ManufacturingDate'],
            'addmisiondate'     :  BatchDetail['AddmisionDate'], })
            #print (LineItem['ItemCode'],LineItem['ItemDescription'],LineItem['Quantity'],LineItem['WarehouseCode'],LineItem['FromWarehouseCode'], BatchDetail['BatchNumber'],BatchDetail['Quantity'],BatchDetail['ExpiryDate'],BatchDetail['ManufacturingDate'])
    return LineItem_list

def Update_inventory_level():
    """
    Update Inventory transfers from SAP to Khanal Tech Integrations 
    """
    # INITIALIZATION
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url+"SQLQueries('ECB2CwhseBatchQuantity')/List" #Item batch Quantity from EC-G will be changed only
    
    response = session.request("GET", reqUrl, headers=headersList,verify=False)
    Query_results = dict(response.json())
    next_page = Query_results.get("odata.nextLink",None)

    def _store_inventory_rows(query_results):
        for single_query_values in query_results.get('value') or []:
            docname = single_query_values['ItemCode']+'-'+single_query_values['DistNumber']+'-'+single_query_values['WhsCode']
            if frappe.db.exists("Inventory in Whse", docname):
                doc = frappe.get_doc("Inventory in Whse", docname)
            else:
                doc = frappe.new_doc('Inventory in Whse')
            print(single_query_values['ItemCode'])
            doc.itemcode   = single_query_values['ItemCode']
            doc.mnfdate    = single_query_values['MnfDate']
            doc.distnumber = single_query_values['DistNumber']
            doc.expdate    = single_query_values['ExpDate']
            doc.whscode    = single_query_values['WhsCode']
            doc.quantity   = str(single_query_values['Quantity'])
            try:
                doc.save()
            except Exception as e:
                print(e)

    _store_inventory_rows(Query_results)

    while next_page is not None:
        session = AuthenticateSAPB1()
        reqUrl = doc_settings.sap_b1_url+"" + next_page
        print(next_page)
        response = session.request("GET", reqUrl,  headers=headersList,verify=False)
        Query_results = dict(response.json())
        _store_inventory_rows(Query_results)
        next_page = Query_results.get("odata.nextLink",None)
    frappe.msgprint(msg='Data Inserted successfully',title='Success')
    return None

def Get_FirstExpiry_Batch(itemsku,Req_Quantity=None): #itemcode and quantity needed
    All_batchwise_itemlist = frappe.db.get_list('Inventory in Whse', 
                                                 filters={'whscode'  : 'EC-B2C',
                                                          'quantity':     ['>=', int(Req_Quantity)],
                                                          'itemcode' : str(itemsku)
                                                          },
                                                 order_by='expdate'
                                                ) 
    if len(All_batchwise_itemlist)>0:
        Single_Batch_Doc = frappe.get_doc('Inventory in Whse', All_batchwise_itemlist[0]['name'])
        Soon_to_Be_Expired_Batch = Single_Batch_Doc.distnumber
        
        Single_Batch_Doc.quantity = int(float(Single_Batch_Doc.quantity)) -  int(Req_Quantity) #substracting one item as it has been used
        Single_Batch_Doc.save()
        frappe.db.commit()
        return Soon_to_Be_Expired_Batch
    else:
        return None # Return empty handed

def get_GST(origin_state,dest_state,item_code):
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url+"States?$select=Code&$filter=startswith(Country,'IN') and startswith(Name,'"+ origin_state +"')"
    response = session.request("GET", reqUrl, headers=headersList,verify=False)
    state_code = dict(response.json())['value'][0]['Code']
    reqUrl = doc_settings.sap_b1_url+"Items?$select=ItemCode,ItemName,ForeignName,U_TaxRate&$filter=startswith(ItemCode, '" + item_code +"') &$orderby=ItemCode"
    response = session.request("GET", reqUrl, headers=headersList,verify=False)
    tax_rate = dict(response.json())['value'][0]['U_TaxRate']
    

    if state_code == 'KT':
        state_code = 'KA'
    if state_code==dest_state:
        tax_type = 'CS'
    else:
        tax_type = 'IG'
    gst_code = state_code + tax_type + str(int(tax_rate))
    return gst_code

##########################################################################################

# All_batchwise_itemlist = frappe.db.get_list('Inventory in Whse', filters={'whscode'  : 'EC-FG'  },fields=['itemcode', 'quantity'] ) 
from collections import defaultdict,Counter
@frappe.whitelist()
def get_pivoted_whseLevel():
    itemlist = frappe.db.get_list('Inventory in Whse', filters={'whscode'  : 'EC-FG'  },fields=['itemcode', 'quantity'] ) 
    intfy = [ {'itemcode':i['itemcode'],'W_quantity':int(float((i['quantity'])))} for i in itemlist ]
    dd =  defaultdict(Counter)
    for product in intfy:
        levels = {k: v for k, v in product.items() if k != "itemcode"}
        dd[product["itemcode"]].update(levels)
    ########Summarized_LIST
    list1 = [{**{"itemcode": k}, **v} for k, v in dd.items()]
    listt = [{i['itemcode']:i['W_quantity']} for i in list1 ]
    return listt

@frappe.whitelist()
def get_channel_pivoted_itemlist(channel_name=None,startDate=None,endDate=None):
    All_orders = frappe.db.get_list('Unicommerce Orders', 
                                            filters={'status': ('in',['COMPLETE', 'PROCESSING']), 
                                                    'channel_name': channel_name,'sap_delivery_docnum':"",
                                                    'displayorderdatetime':('between',[startDate,endDate])},
                                            fields=['shippingpackages']) #
    ALL_item_list       = []
    for single_order_item in All_orders:
        temp_dict       = json.loads(single_order_item['shippingpackages'])
        temp_dict_items = list(temp_dict['items'].values())
        ALL_item_list.append(temp_dict_items)
    ##################--itemName,itemSku,quantity
    # frappe.log_error('ALL_item_list',ALL_item_list)
    flat_list = [item for sublist in ALL_item_list for item in sublist]
    # frappe.log_error('flat_list',flat_list)
    Itemcode_quantity_list = [{'SKU_code':i['itemSku'],'Order_Quantity':i['quantity']} for i in flat_list ]
    ##################
    dd =  defaultdict(Counter)
    for product in Itemcode_quantity_list:
        levels = {k: v for k, v in product.items() if k != "SKU_code"}
        dd[product["SKU_code"]].update(levels)
    ########Summarized_LIST
    list2 = [{**{"SKU_code": k}, **v} for k, v in dd.items()]
    # frappe.log_error('list2',list2)
    return list2
    
        
@frappe.whitelist()
def comparision_orders_stock(channel_name=None,startDate=None,endDate=None):
    channel_items   = get_channel_pivoted_itemlist(channel_name=channel_name,startDate=startDate,endDate=endDate)
    inventory_items = get_pivoted_whseLevel() #{'FGHNXXX' : quantity}
    inventory_dict  = dict(ChainMap(*inventory_items))
    # frappe.log_error('inventory_dict',inventory_dict)
    ####################channelitems - {'SKU_code':'FGHNXXXX' ,'Order_Quantity':'Quantity'}
    the_comparision_list = []
    for single_dict in channel_items:
        if inventory_dict.get(single_dict['SKU_code']) is not None:
            single_dict['Whse_quantitiy'] = inventory_dict[single_dict['SKU_code']]
            the_comparision_list.append(single_dict)
        else:
            single_dict['Whse_quantitiy'] = 0
            the_comparision_list.append(single_dict)
    ###############
    frappe.log_error('the_compa÷rision_list',the_comparision_list)
    sendmail(msg=the_comparision_list)
    return the_comparision_list 


####### {'SKU_code':'FGHNXXXX' ,'Order_Quantity':'Quantity','Whse_Quantity':'Quantity3'}
    
#comparision_orders_stock(channel_name='Amazon_IN_API',startDate='2023-01-01',endDate='2023-01-01')
    
# Channel_post_delivery_note(Channel_Name=None,startDate=None,endDate=None):
# bench --site khanaltech.com execute  --args "{ '30' }"  khanal_tech_integrations.utils.logistics.delivery_notes.manual_update
# bench --site khanaltech.com execute  --args "{'CRED','2023-02-16', '2023-02-20'}"  khanal_tech_integrations.utils.sap.Channel_post_delivery_note
# Channel_post_delivery_note('CRED','2023-01-01', '2023-01-01')

@frappe.whitelist()
def sendmail(msg):
    recipients=['buddhiraj@khanalfoods.com','shahil@khanalfoods.com','harsha@khanalfoods.com','yogesha@khanalfoods.com']
    title="Missing Quantity Unicommerce"
    missing_Qty=[]
    for item in msg:
        sku_code = item['SKU_code']
        order_quantity = item['Order_Quantity']
        whse_quantity = item['Whse_quantitiy']

        if order_quantity > whse_quantity:
            missing_item = {'sku_code': sku_code, 'order_quantity': order_quantity, 'whse_quantity': whse_quantity}
            missing_Qty.append(missing_item)
        else:
            pass
    if missing_Qty:
    # create HTML table with some CSS for spacing
        table = "<table style='border-collapse: collapse; margin-top: 10px;'><tr><th style='border: 1px solid black; padding: 5px;'>SKU Code</th><th style='border: 1px solid black; padding: 5px;'>Order Quantity</th><th style='border: 1px solid black; padding: 5px;'>Warehouse Quantity</th></tr>"
        for item in missing_Qty:
            table += f"<tr><td style='border: 1px solid black; padding: 5px;'>{item['sku_code']}</td><td style='border: 1px solid black; padding: 5px;'>{item['order_quantity']}</td><td style='border: 1px solid black; padding: 5px;'>{item['whse_quantity']}</td></tr>"
        table += "</table>"

        email_args={
            "recipients":recipients,
            "message":table,
            "subject":title,
            # "message_type": "html"
        }
        frappe.enqueue(method=frappe.sendmail,queue='short',timeout=300, **email_args)
    else:
        pass

bundle_items_CFG = {
                'FGDC0032':{'CFGDC0001':[{'ItemCode':'FGDC0031','Quantity':3},]}, 
                'FGDC0033':{'CFGDC0002':[{'ItemCode':'FGDC0031','Quantity':5},]},     
                'FGDC0064':{'CFGDC0003':[{'ItemCode':'FGDC0063','Quantity':3},]},   
                'FGDC0065':{'CFGDC0004':[{'ItemCode':'FGDC0063','Quantity':5},]},  
                'FGDC0201':{'CFGDC0005':[{'ItemCode':'FGDC0055','Quantity':3},]},  
                'FGDC0039':{'CFGDC0006':[{'ItemCode':'FGDC0038','Quantity':3},]},  
                'FGDC0040':{'CFGDC0007':[{'ItemCode':'FGDC0038','Quantity':5},]}, 
                'FGDC0077':{'CFGDC0008':[{'ItemCode':'FGDC0076','Quantity':3},]},  
                'FGDC0092':{'CFGDC0009':[{'ItemCode':'FGDC0091','Quantity':3},]}, 
                'FGDC0098':{'CFGDC0010':[{'ItemCode':'FGDC0097','Quantity':3},]},  
                'FGDC0119':{'CFGDC0011':[{'ItemCode':'FGDC0118','Quantity':3},]}, 
                'FGDC0200':{'CFGDC0012':[{'ItemCode':'FGDC0049','Quantity':3},]}, 
                'FGDC0086':{'CFGDC0013':[{'ItemCode':'FGDC0085','Quantity':3},]}, 
                'FGDC0087':{'CFGDC0014':[{'ItemCode':'FGDC0085','Quantity':5},]}, 
                'FGDC0099':{'CFGDC0015':[{'ItemCode':'FGDC0097','Quantity':5},]}, 
                'FGDC0112':{'CFGDC0016':[{'ItemCode':'FGDC0111','Quantity':3},]}, 
                'FGDC0132':{'CFGDC0017':[{'ItemCode':'FGDC0131','Quantity':3},]}, 
                ###################################################################
                'FGHN0106':{'CFGHN0001':[{'ItemCode':'FGHN0015','Quantity':5},]}, 
                'FGHN0107':{'CFGHN0003':[{'ItemCode':'FGHN0025','Quantity':3},]}, 
                'FGHN0108':{'CFGHN0004':[{'ItemCode':'FGHN0025','Quantity':5},]},
                'FGHN0126':{'CFGHN0002':[{'ItemCode':'FGHN0015','Quantity':2},]},
                'FGHN0122':{'CFGHN0005':[{'ItemCode':'FGHN0094','Quantity':3},]},
                'FGHN0124':{'CFGHN0006':[{'ItemCode':'FGHN0058','Quantity':2},]}, 
                'FGHN0118':{'CFGHN0007':[{'ItemCode':'FGHN0059','Quantity':1},
                                         {'ItemCode':'FGHN0058','Quantity':1},]}, 
                'FGHN0120':{'CFGHN0008':[{'ItemCode':'FGHN0015','Quantity':1},
                                         {'ItemCode':'FGHN0025','Quantity':1},
                                         {'ItemCode':'FGHN0041','Quantity':1},]},  
                'FGHN0056':{'CFGHN0009':[{'ItemCode':'FGHN0054','Quantity':3},]},  
                'FGHN0105':{'CFGHN0010':[{'ItemCode':'FGHN0015','Quantity':3},]},  
                'FGHN0113':{'CFGHN0011':[{'ItemCode':'FGHN0041','Quantity':2},]},  
                'FGHN0125':{'CFGHN0012':[{'ItemCode':'FGHN0054','Quantity':5},]},  
                'FGHN0119':{'CFGHN0013':[{'ItemCode':'FGHN0015','Quantity':1},
                                         {'ItemCode':'FGHN0025','Quantity':1},]},  
                'FGHN0123':{'CFGHN0014':[{'ItemCode':'FGHN0039','Quantity':1},
                                         {'ItemCode':'FGHN0030','Quantity':1},]},  
                'FGHN0128':{'CFGHN0015':[{'ItemCode':'FGHN0030','Quantity':1}, 
                                         {'ItemCode':'FGHN0039','Quantity':1},
                                         {'ItemCode':'FGHN0086','Quantity':1},
                                         {'ItemCode':'FGHN0096','Quantity':1},]},  }
@frappe.whitelist()
def Channel_post_delivery_note1(Channel_Name=None,startDate=None,endDate=None):
    """
    This function will go to selected channel -- get completed order list send to create a single invoice out of it'
    """
    channel_list = ['Snapdeal','Amazon_IN_API','CRED','FLIPKART','DOGSEE_SITE_IN','HN_SITE_IN','ONDC_NSTORE']
    channel_id = Channel_Name
    # KHANAL INDUSTRIES WILL BE PROXY FOR AMAZON C03318 AMAZON IN KHANAL INDUSTRIES C03301
    Channel_CustomerCode_mapping = {'Snapdeal'      : 'C02574',
                                    'Amazon_IN_API' : 'C01186',
                                    'CRED'          : 'C03358',
                                    'FLIPKART'      : 'C03121',
                                    'DOGSEE_SITE_IN': 'C00623',
                                    'HN_SITE_IN'    : 'C01026',
                                    'ONDC_NSTORE'   : 'C03494',
                                    }
    print ('Customer is : ', channel_id)
    print ('startDate: ',startDate)
    print('endDate : ',endDate)
    if startDate or endDate:
        SGST_orders = frappe.db.get_list('Unicommerce Orders', 
                                        filters={'status': ('in',['COMPLETE',
                                                                #   'PROCESSING'
                                                                  ]), 
                                        'channel_name': channel_id,'state':'KA','sap_delivery_docnum':"",
                                        'displayorderdatetime':('between',[startDate,endDate])},
                                        pluck='name') #
        IGST_orders = frappe.db.get_list('Unicommerce Orders', 
                                        filters={'status': ('in',['COMPLETE',
                                                                #   'PROCESSING'
                                                                  ]), 
                                        'channel_name': channel_id,'state':('not in',['KA']),'sap_delivery_docnum':"",
                                        'displayorderdatetime':('between',[startDate,endDate])},
                                        pluck='name') #
    else:
        SGST_orders = frappe.db.get_list('Unicommerce Orders', 
                                        filters={'status': ('in',['COMPLETE',
                                                                #   'PROCESSING'
                                                                  ]), 
                                        'channel_name': channel_id,'state':'KA',
                                        'sap_delivery_docnum':""},
                                        pluck='name') #
        IGST_orders = frappe.db.get_list('Unicommerce Orders', 
                                        filters={'status': ('in',['COMPLETE',
                                                                #   'PROCESSING'
                                                                  ]), 
                                        'channel_name': channel_id,'state':('not in',['KA']),
                                        'sap_delivery_docnum':""},
                                        pluck='name') #
    CustomerCode_from_channel = Channel_CustomerCode_mapping[channel_id]
    
    print ('SGST_orders : ',len(SGST_orders))
    print ('IGST_orders : ',len(IGST_orders))
    Summary_Dict = [ {'Order_Type':'SGST Orders', 'No of Orders': len(SGST_orders),'DeliveryNote Docnum':None },
                     {'Order_Type':'IGST Orders', 'No of Orders': len(IGST_orders),'DeliveryNote Docnum':None } ]
    

    # LOCAL ORDERS
    if len(SGST_orders)>0 :
        bill_to_code = 'B2C SGST ADD'
        Delivery_response = delivery_from_orderlist1(CustomerCode_from_channel,SGST_orders,bill_to_code,startDate,endDate)
        print(str(Delivery_response)[:40])
        print('PUSHING SGST ORDERS')
        if Delivery_response.get('DocNum') is not None:
            print("***********SGST_orders - Delivery_response['DocNum']   ",Delivery_response['DocNum'])
            Summary_Dict[0]['DeliveryNote Docnum'] = Delivery_response['DocNum']
            for singledoc in SGST_orders:
                order_doc = frappe.get_doc('Unicommerce Orders', singledoc)  #order_doc.sap_delivery_no
                #DELIVERY DOC NUM IS NOT GETTING UPDATED NEED TO FIX THIS
                order_doc.sap_delivery_docnum = Delivery_response['DocNum']
                order_doc.save()
                for lineitem in order_doc.line_items:
                    lineitem.sap_delivery_no = Delivery_response['DocNum']
                order_doc.save()
                frappe.db.commit()
        elif Delivery_response.get('error') is not None:
            Summary_Dict[0]['DeliveryNote Docnum'] = Delivery_response['error']
            print (Delivery_response['error'])
            print ('ERROR',Delivery_response)
        #frappe.db.commit()

    #Outside state orders
    if len(IGST_orders)>0:
        bill_to_code = 'B2C IGST ADD'
     
        Delivery_response = delivery_from_orderlist1(CustomerCode_from_channel,IGST_orders,bill_to_code,startDate,endDate)
        print(str(Delivery_response)[:40])
        print('PUSHING IGST ORDERS')
        if Delivery_response.get('DocNum') is not None:
            print("**********IGST_orders - Delivery_response['DocNum']   ",Delivery_response['DocNum'])
            Summary_Dict[1]['DeliveryNote Docnum'] = Delivery_response['DocNum']
            for singledoc in IGST_orders:
                order_doc = frappe.get_doc('Unicommerce Orders', singledoc)  #order_doc.sap_delivery_no
                order_doc.sap_delivery_docnum = Delivery_response['DocNum']
                order_doc.save()
                for lineitem in order_doc.line_items:
                    lineitem.sap_delivery_no = Delivery_response['DocNum']
                order_doc.save()
                frappe.db.commit()
        elif Delivery_response.get('error') is not None:
            Summary_Dict[1]['DeliveryNote Docnum'] = Delivery_response['error']
            print (Delivery_response['error'])
            print ('ERROR',Delivery_response)
            #frappe.db.commit()
    # frappe.enqueue(Update_inventory_level,queue="long",job_name='Update_inventory_level')
    # Update_inventory_level() # Update Inventory level after all the DC creation.
    # Sending mail about the result
    return Summary_Dict

@frappe.whitelist()
def DNsendmail(DICT,Title=None):
    recipients=['buddhiraj@khanalfoods.com','mratyunjay@khanalfoods.com','shahil@khanalfoods.com','harsha@khanalfoods.com','yogesha@khanalfoods.com']
    # create HTML table with some CSS for spacing
    table = "<table style='border-collapse: collapse; margin-top: 10px;'><tr><th style='border: 1px solid black; padding: 5px;'>Order_Type</th><th style='border: 1px solid black; padding: 5px;'>No of Orders</th><th style='border: 1px solid black; padding: 5px;'>DN_docnum</th></tr>"
    for item in DICT:
        table += f"<tr><td style='border: 1px solid black; padding: 5px;'>{item['Order_Type']}</td><td style='border: 1px solid black; padding: 5px;'>{item['No of Orders']}</td><td style='border: 1px solid black; padding: 5px;'>{item['DeliveryNote Docnum']}</td></tr>"
    table += "</table>"

    email_args={
        "recipients":recipients,
        "message":table,
        "subject":Title,
        # "message_type": "html"
                }
    frappe.enqueue(method=frappe.sendmail,queue='short',timeout=300, **email_args)
    return None

@frappe.whitelist()
def manual_inventory_update(Total:int=20) -> None :
    """
    Update Inventory Level from SAP to Frappe
    """
    
    print(Total,'Total')

    for i in range(Total):
        print(i,'count')
    # INITIALIZATION
        doc_settings = frappe.get_doc('SAP Settings')
        reqUrl        =  doc_settings.sap_b1_url+"SQLQueries('ECB2CwhseBatchQuantity')//List?&$skip="
        modfified_Url =  reqUrl + str(20*i)
        session       = AuthenticateSAPB1()
        response      = session.request("GET", modfified_Url,  headers=headersList,verify=False)
            
        QueryResult = dict(response.json())

        if QueryResult['value'] is not None:
            for single_query_values in QueryResult['value']:
                if frappe.db.exists("Inventory in Whse", single_query_values['ItemCode']+'-'+single_query_values['DistNumber']+'-'+single_query_values['WhsCode']):
                    doc = frappe.get_doc("Inventory in Whse", single_query_values['ItemCode']+'-'+single_query_values['DistNumber']+'-'+single_query_values['WhsCode'])
                else:
                    doc = frappe.new_doc('Inventory in Whse')
                #print(single_query_values['ItemCode'])    
                doc.itemcode   = single_query_values['ItemCode']
                doc.mnfdate    = single_query_values['MnfDate']
                doc.distnumber = single_query_values['DistNumber']
                doc.expdate    = single_query_values['ExpDate']
                doc.whscode    = single_query_values['WhsCode'] 
                doc.quantity   = str(single_query_values['Quantity'])
                try:
                    doc.save()
                    frappe.db.commit()
                except Exception as e:
                    print (e)
        #frappe.db.commit()
    frappe.msgprint(msg='Data Inserted successfully',title='Success')
    return None
