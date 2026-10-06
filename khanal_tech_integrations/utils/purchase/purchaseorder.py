from xml.dom.expatbuilder import parseString
import requests
import json
import frappe
from frappe.utils import add_to_date, now, get_datetime, now_datetime

from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
from khanal_tech_integrations.utils.logistics.alertList import SeriesName


headersList = {
                "Accept": "*/*",
                "User-Agent": "Khanal Tech",
                "Content-Type": "application/json" 
            }



@frappe.whitelist()
def fetch_purchase_orders():
    """
    Update Invoices from SAP to Khanal Tech Integrations 
    """
    session = AuthenticateSAPB1()
    payload = ''

    #CHECK THE LAST MAX UPDATED INV. TRANSFERS
    start_page = 10
    try:
        last_page_doc = frappe.get_last_doc('SAP PurchaseOrders Log')
        start_page    = last_page_doc.last_skip
    except:
        start_page    = 1
    
    #for i in range(int(start_page),2):
    i = int(start_page)
    if i and i>1:
        i = i - 1

    # INITIALIZATION
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl      = doc_settings.sap_b1_url+"PurchaseOrders?$filter=DocumentStatus eq 'bost_Open'&$skip=" + str(20*i) #PurchaseOrders

    # reqUrl      = doc_settings.sap_b1_url+"PurchaseOrders" + str(20*i) #PurchaseOrders
    session     = AuthenticateSAPB1()
    response    = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
        
    PurchaseOrders  = dict(response.json())
    # print(PurchaseOrders)
    # print(f"/n/n/n/n{PurchaseOrders}")
    next_page   = PurchaseOrders.get("odata.nextLink",None)
    while next_page is not None:
    
        try:
            if PurchaseOrders['value'] is not None:
                print ('Going into',i)
                for Single_Order in PurchaseOrders['value']:
                    doc                            = frappe.new_doc('SAP Purchase Order')
                    doc.docentry                   = Single_Order['DocEntry']
                    doc.cardcode                   = Single_Order['CardCode']
                    doc.cardname                   = Single_Order['CardName']
                    doc.contactperson              = Single_Order['ContactPersonCode']
                    doc.doctotal                   = Single_Order['DocTotal']
                    doc.status                     = 'Open'
                    if str(Single_Order['Series']) =='-1':
                        doc.docnum                 = Single_Order['DocNum']
                    else:
                        doc.docnum                 = f"{SeriesName[str(Single_Order['Series'])]}/{Single_Order['DocNum']}"
                    jsonDocumentLines = json.dumps(Single_Order['DocumentLines'])
                    doc.lineitem                   =jsonDocumentLines
                    try:
                        doc.save()
                        frappe.db.commit()
                       
                        print(doc,'saved')
                    except frappe.DuplicateEntryError:
                        print(doc,'duplicate')
                        pass
                    
                    
                i += 1
                #increment the counter
            elif PurchaseOrders['value'] is None:
                break
            
        except Exception as e:
            #break
            print (e)
        reqUrl       = doc_settings.sap_b1_url+"PurchaseOrders?$filter=DocumentStatus eq 'bost_Open'&$skip=" + str(20*i) #PurchaseOrders
        session      = AuthenticateSAPB1()
        response     = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
            
        PurchaseOrders   = dict(response.json())
        next_page    = PurchaseOrders.get("odata.nextLink",None)
    
    #Update the last page
    


 
    doc1 = frappe.new_doc('SAP PurchaseOrders Log')  # Replace with your desired document name
    doc1.last_skip = i
    doc1.save()
    frappe.msgprint(msg ='Data Inserted successfully',title ='Success')
    # if empty_list:
        #run  the function for mail for each items inside the list

    return None
    # print(PurchaseOrders['value'])
    #while True:
    # empty_list = []
    


@frappe.whitelist()
def delete():
    x = 'SAP Purchase Order'
    print(len(frappe.get_list(x)))
    for documentt in frappe.get_list(x):
        documentt = frappe.get_doc( x , documentt.name)
        documentt.delete()











# @frappe.whitelist()
# def update_purchase_orders():
#     session = AuthenticateSAPB1()
#     payload = ''
#     Today = frappe.utils.nowdate()
#     FilterDate = add_to_date(Today,days=-25)
#     print(FilterDate,'FilterDate')
#     doc_settings = frappe.get_doc('SAP Settings')
#     # reqUrl              = doc_settings.sap_b1_url+"PurchaseInvoices?$filter=CardCode eq '{cardcode}' and DocumentStatus eq 'bost_Open' &$orderby=DocDate desc&$skip=" +str(20*i)

#     reqUrl        = doc_settings.sap_b1_url+"PurchaseOrders?$filter=UpdateDate ge '{FilterDate}' and DocumentStatus eq 'bost_Open'"
#     modfified_Url = reqUrl.format(FilterDate=FilterDate)
#     session       = AuthenticateSAPB1()
#     response      = session.request("GET", modfified_Url, data=payload,  headers=headersList,verify=False)
#     UpdatedPurchaseorder = dict(response.json())
#     # print(UpdatedPurchaseorder,'UpdatedPurchaseorder')
#     if UpdatedPurchaseorder['value'] is not None:
#         print('if')
#         for SinglePo in UpdatedPurchaseorder['value']:
            
#             if frappe.db.exists('SAP Purchase Order' ,  SinglePo['DocEntry'] ) is not None:
#                 print(SinglePo['DocEntry'],'if docenry')
#                 doc                       = frappe.get_doc('SAP Purchase Order' , SinglePo['DocEntry'] )
#                 jsonDocumentLines = json.dumps(SinglePo['DocumentLines'])
#                 doc.lineitem                   =jsonDocumentLines
                
#                 #doc.save()
#             else:
#                 print(SinglePo['DocEntry'],' else docenry')
#                 doc                            = frappe.new_doc('SAP Purchase Order')
#                 doc.docentry                   = SinglePo['DocEntry']
#                 doc.cardcode                   = SinglePo['CardCode']
#                 doc.cardname                   = SinglePo['CardName']
#                 doc.contactperson              = SinglePo['ContactPersonCode']
#                 doc.doctotal                   = SinglePo['DocTotal']
#                 doc.status                     = 'Open'
#                 if str(SinglePo['Series']) =='-1':
#                     doc.docnum                 = SinglePo['DocNum']
#                 else:
#                     doc.docnum                 = f"{SeriesName[str(SinglePo['Series'])]}/{SinglePo['DocNum']}"
#                 jsonDocumentLines = json.dumps(SinglePo['DocumentLines'])
#                 doc.lineitem                   =jsonDocumentLines
#                 pass    
#             try:#try saving, skip if already exist
#                 doc.save()
#                 frappe.db.commit() #
#                 print(doc,'saved')
#             except frappe.DuplicateEntryError:
#                 pass

#                 #increment the counter
#     elif UpdatedPurchaseorder['value'] is None:
#         print('everything uptodate no changes')
#     frappe.msgprint(msg ='Data Updated successfully',title ='Success')
#     return None





@frappe.whitelist()
def update_purchase_orders():
    """
    Update PurchaseOrders from SAP to Khanal Tech Integrations 
    """
    session = AuthenticateSAPB1()
    payload = ''

    Today = frappe.utils.nowdate()
    print(Today,'today')
    FilterDate = add_to_date(Today,days=-1)
    print(FilterDate,'FilterDate')
    ###############################
    doc_settings = frappe.get_doc('SAP Settings')
    # doc_settings.sap_b1_url
    count_url = doc_settings.sap_b1_url+"PurchaseOrders?$apply=filter(DocDate ge '{FilterDate}' and DocumentStatus eq 'bost_Open')/aggregate(DocEntry with countdistinct as CountDistinct)"
    Modified_count_url = count_url.format(FilterDate=FilterDate)
    response      = session.request("GET", Modified_count_url, data=payload,  headers=headersList,verify=False)
    print(response,'response')
    UpdatedPurchaseorder = dict(response.json())
    
    if UpdatedPurchaseorder['value'] is not None:
        if len(UpdatedPurchaseorder['value']) > 0:
            counter = UpdatedPurchaseorder['value'][0]['CountDistinct']
            Total   = counter//20 + 1
            print(Total,'Total')
            ##############################
            for i in range(Total):
                print(i,'count')
            # INITIALIZATION
                reqUrl        = doc_settings.sap_b1_url+"PurchaseOrders?$filter=UpdateDate ge '{FilterDate}'and DocumentStatus eq 'bost_Open'&$skip=" 
                modfified_Url = reqUrl.format(FilterDate=FilterDate)  + str(20*i)
                session       = AuthenticateSAPB1()
                response      = session.request("GET", modfified_Url, data=payload,  headers=headersList,verify=False)
                    
                Purchase_order_list = dict(response.json())
                

                #while True:
                
                    
                if Purchase_order_list['value'] is not None:
                    print ('Going into' ,i)
                    for SinglePo in Purchase_order_list['value']:
                        # print(SinglePo['DocEntry'],'doctentry')
                        if frappe.db.exists('SAP Purchase Order' ,  SinglePo['DocEntry'] ) is not None:
                            print(SinglePo['DocEntry'],'if docenry')
                            doc                       = frappe.get_doc('SAP Purchase Order' , SinglePo['DocEntry'] )
                            jsonDocumentLines = json.dumps(SinglePo['DocumentLines'])
                            doc.lineitem                   =jsonDocumentLines
                            
                            #doc.save()
                        else:
                            print(SinglePo['DocEntry'],' else docenry')
                            doc                            = frappe.new_doc('SAP Purchase Order')
                            doc.docentry                   = SinglePo['DocEntry']
                            doc.cardcode                   = SinglePo['CardCode']
                            doc.cardname                   = SinglePo['CardName']
                            doc.contactperson              = SinglePo['ContactPersonCode']
                            doc.doctotal                   = SinglePo['DocTotal']
                            doc.status                     = 'Open'
                            if str(SinglePo['Series']) =='-1':
                                doc.docnum                 = SinglePo['DocNum']
                            else:
                                doc.docnum                 = f"{SeriesName[str(SinglePo['Series'])]}/{SinglePo['DocNum']}"
                            jsonDocumentLines = json.dumps(SinglePo['DocumentLines'])
                            doc.lineitem                   =jsonDocumentLines
                            pass    
                        try:#try saving, skip if already exist
                            doc.save()
                            frappe.db.commit() #
                            print(doc,'saved')
                        except frappe.DuplicateEntryError:
                            pass   

                        
                    i += 1
                    #increment the counter
                elif Purchase_order_list['value'] is None:
                    break
                
                
                reqUrl    = reqUrl.format(FilterDate=FilterDate)  + str(20*i)
                session   = AuthenticateSAPB1()
                response  = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
                    
                Purchase_order_list = dict(response.json())
            frappe.msgprint(msg ='Data Inserted successfully',title ='Success')
            return None



@frappe.whitelist()
def close_purchase_orders():
    session = AuthenticateSAPB1()
    payload = ''

    ###############################

    Today = frappe.utils.nowdate()
    print(Today,'today')
    FilterDate = add_to_date(Today,days=-1)
    print(FilterDate,'FilterDate')
    ###############################
    # count_url = doc_settings.sap_b1_url+"DeliveryNotes?$apply=filter(DocDate ge '{FilterDate}')/aggregate(DocEntry with countdistinct as CountDistinct)"
    doc_settings = frappe.get_doc('SAP Settings')
    count_url = doc_settings.sap_b1_url+"PurchaseDeliveryNotes?$apply=filter(UpdateDate ge '{FilterDate}')/aggregate(DocEntry with countdistinct as CountDistinct)"
    Modified_count_url = count_url.format(FilterDate=FilterDate)
    response      = session.request("GET", Modified_count_url, data=payload,  headers=headersList,verify=False)
    print(response,'response')
    PurchaseDeliveryNotes = dict(response.json())
    if PurchaseDeliveryNotes['value'] is not None:
        if len(PurchaseDeliveryNotes['value']) > 0:
            counter = PurchaseDeliveryNotes['value'][0]['CountDistinct']
            Total   = counter//20 + 1
            print(Total,'Total')
            for i in range(Total):
                print(i,'count')
            # INITIALIZATION
                reqUrl        = doc_settings.sap_b1_url+"PurchaseDeliveryNotes?$filter=UpdateDate ge '{FilterDate}'&$skip=" 
                modfified_Url = reqUrl.format(FilterDate=FilterDate)  + str(20*i)
                session       = AuthenticateSAPB1()
                response      = session.request("GET", modfified_Url, data=payload,  headers=headersList,verify=False)
                    
                purchaseDeliveryList = dict(response.json())

                if purchaseDeliveryList['value'] is not None:
                    print ('Going into' ,i)
                    for SinglePurchase in purchaseDeliveryList['value']:
                        print(SinglePurchase['DocEntry'],'doctentry')
                        # print(SinglePurchase['DocumentStatus'],'DocumentStatus')
                        # print(SinglePo['DocEntry'])
                        Emptylist_Purchase          = []
                        for item in SinglePurchase['DocumentLines']:
                            Emptylist_Purchase.append(item['BaseEntry']) 
                        emptyset                  = set(Emptylist_Purchase)
                        Purchase_DN_List           = list(emptyset) #
                        PurchaseDocEntry               = None
                        if len(Purchase_DN_List)  != 0:
                            PurchaseDocEntry           = Purchase_DN_List[0]
                        print(PurchaseDocEntry,'PurchaseDocEntry')
                        posturl = doc_settings.sap_b1_url+"PurchaseOrders({DocEntry})/Close"
                        modified_posturl = posturl.format(DocEntry=PurchaseDocEntry)
                        empty_paylod=""
                        response1        = session.request("POST", modified_posturl, headers=headersList, data=empty_paylod,verify=False)
                        print(response1,'response')
                        print(response1.text)
                    i += 1
                    #increment the counter
                elif purchaseDeliveryList['value'] is None:
                    break
                
                
                reqUrl    = reqUrl.format(FilterDate=FilterDate)  + str(20*i)
                session   = AuthenticateSAPB1()
                response  = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
                    
                purchaseDeliveryList = dict(response.json())
            frappe.msgprint(msg ='Data Inserted successfully',title ='Success')
            return None
        pass
    pass




    # bench --site khanaltech.com execute khanal_tech_integrations.utils.purchase.purchaseorder.fetch_purchase_orders
    # bench --site khanaltech.com execute khanal_tech_integrations.utils.purchase.purchaseorder.update_purchase_orders
    # bench --site beta.khanaltech.com execute khanal_tech_integrations.utils.purchase.purchaseorder.update_purchase_orders
    # bench --site beta.khanaltech.com execute khanal_tech_integrations.utils.purchase.purchaseorder.close_purchase_orders
    # bench --site khanaltech.com execute  --args "{ '5' }"  khanal_tech_integrations.utils.purchase.purchaseorder.update_purchase_orders



