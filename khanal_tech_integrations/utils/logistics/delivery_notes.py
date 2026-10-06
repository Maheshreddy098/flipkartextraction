from xml.dom.expatbuilder import parseString
import requests
import json
import frappe
from frappe.utils import add_to_date, now, get_datetime, now_datetime
import re

from khanal_tech_integrations.utils.sap import AuthenticateSAPB1

headersList = {
                "Accept": "*/*",
                "User-Agent": "Khanal Tech",
                "Content-Type": "application/json" 
              }

# "khanal_tech_integrations.utils.logistics.delivery_notes.update",

@frappe.whitelist()
def update():
    """
    Update Delivery Notes from SAP to Khanal Tech Integrations 
    """
    session = AuthenticateSAPB1()
    payload = ''

    #CHECK THE LAST MAX UPDATED INV. TRANSFERS
    start_page = 10
    try:
        last_page_doc = frappe.get_last_doc('SAP Delivery Notes Log')
        start_page    = last_page_doc.last_skip
    except:
        start_page    = 1

    #for i in range(int(start_page),2):
    i = int(start_page)
    if i and i>1:
        i = i - 1

    # INITIALIZATION
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl        = doc_settings.sap_b1_url+"DeliveryNotes?$skip=" + str(20*i)
    session       = AuthenticateSAPB1()
    response      = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
        
    DeliveryNotes = dict(response.json())
    next_page     = DeliveryNotes.get("odata.nextLink",None)

    #while True:
    while next_page is not None:
        try:
            if DeliveryNotes['value'] is not None:
                #print ('Going into')
                for Single_DN in DeliveryNotes['value']:
                    doc                       = frappe.new_doc('SAP Delivery Notes')
                    doc.docentry              = Single_DN['DocEntry']
                    doc.docnum                = Single_DN['DocNum']
                    print(Single_DN['DocNum'])
                    doc.created_date          = Single_DN['DocDate']
                    doc.updated               = Single_DN['UpdateDate']
                    doc.customer_code         = Single_DN['CardCode']
                    doc.shipped_date          = Single_DN['U_ShippingDate']
                    doc.cancellation_status   = Single_DN['CancelStatus']   #Cancellation Status csCancellation,csNo/csYes

                    doc.transporter_name      = Single_DN['U_TN']
                    doc.ref                   = Single_DN['TaxExtension']['NFRef']
                    Emptylist_SO_doc          = []
                    for item in Single_DN['DocumentLines']:
                        Emptylist_SO_doc.append(item['BaseEntry'])
                    emptyset                  = set(Emptylist_SO_doc)
                    SO_docentrylist           = list(emptyset) #
                    SO_DocEntry               = None
                    if len(SO_docentrylist)  != 0:
                        SO_DocEntry           = SO_docentrylist[0]
                    doc.ref_sales_order       = SO_DocEntry
                    doc.tracking_id           = Single_DN['U_TrackingNo']
                    
                    #doc.save()
                    try:
                        #try saving, skip if already exist
                        doc.save()
                        frappe.db.commit() #
                    except frappe.DuplicateEntryError:
                        pass
                i += 1
                #increment the counter
            elif DeliveryNotes['value'] is None:
                break
            
        except Exception as e:
            #break
            print (e)
        reqUrl    = doc_settings.sap_b1_url+"DeliveryNotes?$skip=" + str(20*i)
        session   = AuthenticateSAPB1()
        response  = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
            
        DeliveryNotes = dict(response.json())
        next_page     = DeliveryNotes.get("odata.nextLink",None)
    
    #Update the last page
    doc1           = frappe.new_doc('SAP Delivery Notes Log')
    doc1.last_skip = i
    doc1.save()
    frappe.msgprint(msg ='Data Inserted successfully',title ='Success')

#apps/khanal_tech_integrations/khanal_tech_integrations/utils/logistics/delivery_notes.py
#bench --site medusa.localhost execute khanal_tech_integrations.utils.logistics.delivery_notes.bulk_update_Delivery_Notes
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
    count_url = doc_settings.sap_b1_url+"DeliveryNotes?$apply=filter(DocDate ge '{FilterDate}')/aggregate(DocEntry with countdistinct as CountDistinct)"
    Modified_count_url = count_url.format(FilterDate=FilterDate)
    response      = session.request("GET", Modified_count_url, data=payload,  headers=headersList,verify=False)
    DeliveryNotes_Count = dict(response.json())
    if DeliveryNotes_Count['value'] is not None:
        counter = DeliveryNotes_Count['value'][0]['CountDistinct']
        Total   = counter//20 + 1
        print(Total,'Total')
    ##############################
        for i in range(Total):
            print(i,'count')
        # INITIALIZATION
            reqUrl        = doc_settings.sap_b1_url+"DeliveryNotes?$filter=UpdateDate ge '{FilterDate}'&$skip=" 
            modfified_Url = reqUrl.format(FilterDate=FilterDate)  + str(20*i)
            session       = AuthenticateSAPB1()
            response      = session.request("GET", modfified_Url, data=payload,  headers=headersList,verify=False)
                
            DeliveryNotes = dict(response.json())
            

            #while True:
            
                
            if DeliveryNotes['value'] is not None:
                print ('Going into')
                for Single_DN in DeliveryNotes['value']:
                    doc                       = frappe.new_doc('SAP Delivery Notes')
                    doc.docentry              = Single_DN['DocEntry']
                    doc.docnum                = Single_DN['DocNum']
                    # print(Single_DN['DocNum'])
                    doc.created_date          = Single_DN['DocDate']
                    doc.updated               = Single_DN['UpdateDate']
                    doc.customer_code         = Single_DN['CardCode']
                    doc.shipped_date          = Single_DN['U_ShippingDate']
                    doc.cancellation_status   = Single_DN['CancelStatus']   #Cancellation Status csCancellation,csNo/csYes
                    doc.transporter_name      = Single_DN['U_TN']
                    doc.ref                   = Single_DN['TaxExtension']['NFRef']
                    Emptylist_SO_doc          = []
                    for item in Single_DN['DocumentLines']:
                        Emptylist_SO_doc.append(item['BaseEntry']) 
                    emptyset                  = set(Emptylist_SO_doc)
                    SO_docentrylist           = list(emptyset) #
                    SO_DocEntry               = None
                    if len(SO_docentrylist)  != 0:
                        SO_DocEntry           = SO_docentrylist[0]
                    doc.ref_sales_order       = SO_DocEntry
                    doc.tracking_id           = Single_DN['U_TrackingNo']
                    
                    #doc.save()
                    try:
                        #try saving, skip if already exist
                        doc.save()
                        frappe.db.commit() #
                    except frappe.DuplicateEntryError:
                        pass
                i += 1
                #increment the counter
            elif DeliveryNotes['value'] is None:
                break
            
            
            reqUrl    = reqUrl.format(FilterDate=FilterDate)  + str(20*i)
            session   = AuthenticateSAPB1()
            response  = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
                
            DeliveryNotes = dict(response.json())
        frappe.msgprint(msg ='Data Inserted successfully',title ='Success')
        return None
########################################################
@frappe.whitelist()
def delete():
    x = 'SAP Delivery Notes'
    print(len(frappe.get_list(x)))
    for documentt in frappe.get_list(x):
        documentt = frappe.get_doc( x , documentt.name)
        documentt.delete()


@frappe.whitelist()
def updating_existingvalues():
    session = AuthenticateSAPB1()
    payload = ''
    Today = frappe.utils.nowdate()
    FilterDate = add_to_date(Today,days=-45)
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl        = doc_settings.sap_b1_url+"DeliveryNotes?$filter=UpdateDate ge '{FilterDate}'"
    modfified_Url = reqUrl.format(FilterDate=FilterDate)
    session       = AuthenticateSAPB1()
    response      = session.request("GET", modfified_Url, data=payload,  headers=headersList,verify=False)
    UpdatedDeliveryNotes = dict(response.json())
    if UpdatedDeliveryNotes['value'] is not None:
        for Single_DN in UpdatedDeliveryNotes['value']:
            if frappe.db.exists('SAP Delivery Notes' ,  Single_DN['DocEntry'] ) is not None:
                doc                       = frappe.get_doc('SAP Delivery Notes' , Single_DN['DocEntry'] )
                print(Single_DN['DocEntry'])
                doc.docentry              = Single_DN['DocEntry']
                doc.docnum                = Single_DN['DocNum']
                doc.created_date          = Single_DN['DocDate']
                doc.customer_code         = Single_DN['CardCode']
                doc.shipped_date          = Single_DN['U_ShippingDate']
                doc.cancellation_status   = Single_DN['CancelStatus']   #Cancellation Status csCancellation,csNo/csYes
                doc.updated               = Single_DN['UpdateDate']   #Shubham-
                doc.transporter_name      = Single_DN['U_TN']
                doc.ref                   = Single_DN['TaxExtension']['NFRef']
                doc.tracking_id           = Single_DN['U_TrackingNo']
                
                #doc.save()
                try:
                    #try saving, skip if already exist
                    doc.save()
                    frappe.db.commit() #
                except frappe.DuplicateEntryError:
                    pass
            else:
                pass    

                #increment the counter
    elif UpdatedDeliveryNotes['value'] is None:
        pass
    frappe.msgprint(msg ='Data Updated successfully',title ='Success')
    return None




def temp_update():
    payload = ''
    Today = frappe.utils.nowdate()
    FilterDate = add_to_date(Today,days=-15)
    DN_list = frappe.db.get_list('SAP Delivery Notes' , filters={'created_date': ['>',FilterDate] },pluck= 'docentry' )
    
    for Single_DN in DN_list:
        session = AuthenticateSAPB1()
        doc_settings = frappe.get_doc('SAP Settings')
        reqUrl        = doc_settings.sap_b1_url+"DeliveryNotes({docentry_})"
        modfified_Url = reqUrl.format(docentry_=Single_DN)
        session       = AuthenticateSAPB1()
        response      = session.request("GET", modfified_Url, data=payload,  headers=headersList,verify=False)
        print(Single_DN,response)
        
        SAP_DeliveryNotes = dict(response.json())
        if SAP_DeliveryNotes.get('DocEntry') is not None:
            doc                       = frappe.get_doc('SAP Delivery Notes' , Single_DN )
            # print(Single_DN)
            # doc.docentry              = Single_DN['DocEntry']
            # doc.docnum                = Single_DN['DocNum']
            # doc.created_date          = Single_DN['DocDate']
            # doc.customer_code         = Single_DN['CardCode']
            doc.shipped_date          = SAP_DeliveryNotes['U_ShippingDate']
            doc.cancellation_status   = SAP_DeliveryNotes['CancelStatus']   #Cancellation Status csCancellation,csNo/csYes
            doc.updated               = SAP_DeliveryNotes['UpdateDate']
            doc.transporter_name      = SAP_DeliveryNotes['U_TN']
            # doc.ref                   = Single_DN['TaxExtension']['NFRef']
            doc.tracking_id           = SAP_DeliveryNotes['U_TrackingNo']
            #doc.save()
            try:
                #try saving, skip if already exist
                doc.save()
                frappe.db.commit() #
            except frappe.DuplicateEntryError:
                pass
    frappe.msgprint(msg ='Data Updated successfully',title ='Success')
    return None








# bench --site dev.localhost execute khanal_tech_integrations.utils.logistics.delivery_notes.manual_update
# bench --site khanaltech.com execute khanal_tech_integrations.utils.logistics.delivery_notes.updating_existingvalues

# bench --site khanaltech.com execute khanal_tech_integrations.utils.logistics.delivery_notes.temp_update
# bench --site dev.localhost execute  --args "{ '10' }"  khanal_tech_integrations.utils.logistics.delivery_notes.manual_update

# bench --site khanaltech.com execute  --args "{ '30' }"  khanal_tech_integrations.utils.logistics.delivery_notes.manual_update




#? ---------------Delect tracking ID from frappe & SAP due to Ar invoice Duplicate upto - 01/03/2023

@frappe.whitelist()
def Remove_Duplicate():
    #! live data:-------- out off 90 . 56 done and 36 is pending because of (Delivery Document date is Locked,Customer C03277 is inactive)
    Duplicate_Docentry = [ 12330, 12453, 12452, 12457, 12596, 12612, 12762, 12753, 12761, 12807, 12813, 12814, 12818, 12821, 12834, 12845, 12866, 13142, 13151, 13156, 13191, 13198, 13197, 13248, 13302, 13304, 13319, 13284, 13289, 13315, 13317, 13320, 13335, 13431] 
    #! test data ,2759,6602
    # Duplicate_Docentry=[1166,2759,6602]
    # print(len(Duplicate_Docentry))
    for Single_Docentry in Duplicate_Docentry:
        doc=frappe.get_doc('SAP Delivery Notes',Single_Docentry)
        print(doc)
        doc.transporter_name=""
        doc.shipped_date=""
        doc.tracking_id=""
        doc.delivery_status=""
        # doc.shipping_details=""
        doc.save()
        frappe.db.commit()
        purchase_payload = {    
          "U_ShippingDate"  : "",
          "U_TN"            : "" ,
          "U_TrackingNo"    : "" ,
            }
        doc_settings = frappe.get_doc('SAP Settings')
        reqUrl        = doc_settings.sap_b1_url+"DeliveryNotes({docentry_})"
        modfified_Url = reqUrl.format(docentry_=Single_Docentry)
        session       = AuthenticateSAPB1()
        response      = session.request("PATCH", modfified_Url, data=json.dumps(purchase_payload),  headers=headersList,verify=False)
        # SAPsession.request( "POST", invoice_Url, data=json.dumps(Business_payload),  headers=headersList,verify=False)
        print(Single_Docentry,response)
    pass


# bench --site dev.localhost execute khanal_tech_integrations.utils.logistics.delivery_notes.Remove_Duplicate
