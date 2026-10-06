from xml.dom.expatbuilder import parseString
import requests
import json
import frappe
from frappe.utils import add_to_date, now, get_datetime, now_datetime
import re

from khanal_tech_integrations.utils.sap import AuthenticateSAPB1

# "khanal_tech_integrations.utils.logistics.ar_invoice.update",

headersList = {
                "Accept": "*/*",
                "User-Agent": "Khanal Tech",
                "Content-Type": "application/json" 
            }

@frappe.whitelist()
def update():
    """
    Update Invoices from SAP to Khanal Tech Integrations 
    """
    session = AuthenticateSAPB1()
    payload = ''

    #CHECK THE LAST MAX UPDATED INV. TRANSFERS
    start_page = 10
    try:
        last_page_doc = frappe.get_last_doc('SAP AR Invoice Log')
        start_page    = last_page_doc.last_skip
    except:
        start_page    = 1

    #for i in range(int(start_page),2):
    i = int(start_page)
    if i and i>1:
        i = i - 1

    # INITIALIZATION
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl      = doc_settings.sap_b1_url+"Invoices?$skip=" + str(20*i) #Orders
    session     = AuthenticateSAPB1()
    response    = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
        
    ARinvoices  = dict(response.json())
    next_page   = ARinvoices.get("odata.nextLink",None)

    #while True:
    while next_page is not None:
    
        try:
            if ARinvoices['value'] is not None:
                #print ('Going into')
                for Single_Invoice in ARinvoices['value']:
                    doc                      = frappe.new_doc('SAP AR Invoice')
                    print(Single_Invoice['DocEntry'])
                    doc.docentry             = Single_Invoice['DocEntry']
                    doc.docnum               = Single_Invoice['DocNum']
                    doc.created_date         = Single_Invoice['DocDate']
                    doc.customer_code        = Single_Invoice['CardCode']
                    doc.bill_total           = Single_Invoice['DocTotal']
                    doc.cancellation_status  = Single_Invoice['CancelStatus'] #2 
                    print( Single_Invoice['CancelStatus'] )
                    Emptylist_SO_doc         = []
                    for item in Single_Invoice['DocumentLines']:
                        Emptylist_SO_doc.append(item['BaseEntry'])
                    emptyset                 = set(Emptylist_SO_doc)
                    DN_docentrylist          = list(emptyset) 
                    DN_DocEntry              = None
                    if len(DN_docentrylist) != 0:
                        DN_DocEntry          = DN_docentrylist[0]
                    doc.ref_delivery_note    = DN_DocEntry
                    doc.tracking_id          = Single_Invoice['TrackingNumber']
                    
                    #doc.save()
                    try:
                        #try saving, skip if already exist
                        doc.save()
                        frappe.db.commit() #
                    except frappe.DuplicateEntryError:
                        pass
                i += 1
                #increment the counter
            elif ARinvoices['value'] is None:
                break
            
        except Exception as e:
            #break
            print (e)
        reqUrl       = doc_settings.sap_b1_url+"Invoices?$skip=" + str(20*i)
        session      = AuthenticateSAPB1()
        response     = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
            
        ARinvoices   = dict(response.json())
        next_page    = ARinvoices.get("odata.nextLink",None)
    
    #Update the last page
    doc1           = frappe.new_doc('SAP AR Invoice Log')
    doc1.last_skip = i
    doc1.save()

    frappe.msgprint(msg ='Data Inserted successfully',title ='Success')

@frappe.whitelist()
def delete():
    x = 'SAP AR Invoice'
    print(len(frappe.get_list(x)))
    for documentt in frappe.get_list(x):
        documentt = frappe.get_doc( x , documentt.name)
        documentt.delete()



@frappe.whitelist()
def manual_update(NoofDay=None):
    """
    Update Delivery Notes from SAP to Khanal Tech Integrations 
    """
    session = AuthenticateSAPB1()
    payload = ''

    Today = frappe.utils.nowdate()
    FilterDate = add_to_date(Today,days=-int(NoofDay))
    ###############################
    doc_settings = frappe.get_doc('SAP Settings')
    count_url = doc_settings.sap_b1_url+"Invoices?$apply=filter(DocDate ge '{FilterDate}')/aggregate(DocEntry with countdistinct as CountDistinct)"
    Modified_count_url = count_url.format(FilterDate=FilterDate)
    response      = session.request("GET", Modified_count_url, data=payload,  headers=headersList,verify=False)
    ARinvoice_Count = dict(response.json())
    if ARinvoice_Count['value'] is not None:
        counter = ARinvoice_Count['value'][0]['CountDistinct']
        Total   = counter//20 + 1
        print(Total,'Total')
    ##############################
        for i in range(Total):
            print(i,'count')
        # INITIALIZATION
            reqUrl        = doc_settings.sap_b1_url+"Invoices?$filter=UpdateDate ge '{FilterDate}'&$skip=" 
            modfified_Url = reqUrl.format(FilterDate=FilterDate)  + str(20*i)
            session       = AuthenticateSAPB1()
            response      = session.request("GET", modfified_Url, data=payload,  headers=headersList,verify=False)
                
            AR_Invoicese = dict(response.json())
            

            #while True:
            
                
            if AR_Invoicese['value'] is not None:
                print ('Going into')
                for Single_Invoice in AR_Invoicese['value']:
                    doc                      = frappe.new_doc('SAP AR Invoice')
                    # print(Single_Invoice['DocEntry'])
                    doc.docentry             = Single_Invoice['DocEntry']
                    doc.docnum               = Single_Invoice['DocNum']
                    doc.created_date         = Single_Invoice['DocDate']
                    doc.customer_code        = Single_Invoice['CardCode']
                    doc.bill_total           = Single_Invoice['DocTotal']
                    doc.cancellation_status  = Single_Invoice['CancelStatus'] #2 
                    # print( Single_Invoice['CancelStatus'] )
                    Emptylist_SO_doc         = []
                    for item in Single_Invoice['DocumentLines']:
                        Emptylist_SO_doc.append(item['BaseEntry'])
                    emptyset                 = set(Emptylist_SO_doc)
                    DN_docentrylist          = list(emptyset) 
                    DN_DocEntry              = None
                    if len(DN_docentrylist) != 0:
                        DN_DocEntry          = DN_docentrylist[0]
                    doc.ref_delivery_note    = DN_DocEntry
                    doc.tracking_id          = Single_Invoice['TrackingNumber']
                    
                    #doc.save()
                    try:
                        #try saving, skip if already exist
                        doc.save()
                        frappe.db.commit() #
                    except frappe.DuplicateEntryError:
                        pass
                i += 1
                #increment the counter
            elif AR_Invoicese['value'] is None:
                break
            
            
            reqUrl    = reqUrl.format(FilterDate=FilterDate)  + str(20*i)
            session   = AuthenticateSAPB1()
            response  = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
                
            AR_Invoicese = dict(response.json())
        frappe.msgprint(msg ='Data Inserted successfully',title ='Success')
        return None



#  bench --site khanaltech.com execute  --args "{ '20' }"  khanal_tech_integrations.utils.logistics.ar_invoice.manual_update
#  bench --site khanaltech.com execute    khanal_tech_integrations.utils.logistics.ar_invoice.update
