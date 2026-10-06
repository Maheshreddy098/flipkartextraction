import frappe
import json
import requests
import base64
import time
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
from khanal_tech_integrations.utils.safexpress.auth import AuthenticateSafexpress
from frappe.utils.file_manager import get_file_path
from frappe.utils import file_manager
import re
from khanal_tech_integrations.utils.logistics.alert_invoice import get_single_lineitem,updating_email,WareHouseUpdate
from khanal_tech_integrations.utils.logistics.alertList import SeriesName,List_Item_HSN
from frappe.utils import add_to_date
from khanal_tech_integrations.utils.safexpress.attachpod_to_sap import Update_waybill_and_filePath,Get_Single_Pod,PATCH_POD_AR_invoice

headersList = {
        "Accept": "*/*",
        "User-Agent": "Khanal Tech",
        "Content-Type": "application/json" ,
        "Prefer": "odata.maxpagesize=100",
    }





@frappe.whitelist()
def Fetching_from_Sap(NoOfDays=10):
    Today = frappe.utils.nowdate()
    FilterDate = add_to_date(Today,days=-int(NoOfDays))
    payload={}
    doc_settings = frappe.get_doc('SAP Settings')
    count_url = doc_settings.sap_b1_url+"Invoices?$apply=filter(UpdateDate ge '{FilterDate}' and U_TrackingNo eq null and TransportationCode eq 1)/aggregate(DocEntry with countdistinct as CountDistinct)"
    session     = AuthenticateSAPB1()
    Modified_count_url = count_url.format(FilterDate=FilterDate)
    response      = session.request("GET", Modified_count_url, data=payload,  headers=headersList,verify=False)
    Arinvoice_Count = dict(response.json())
    print(Arinvoice_Count,';Arinvoice_Count')
    if Arinvoice_Count['value'] is not None:
        counter = Arinvoice_Count['value'][0]['CountDistinct']
        Total   = counter//20 + 1
        print(Total,'Total')
        ##############################
        for i in range(Total):
            print(i,'count')
            # INITIALIZATION
            reqUrl        = doc_settings.sap_b1_url+"Invoices?$filter=UpdateDate ge '{FilterDate}'and U_TrackingNo eq null&$skip=" 
            modfified_Url = reqUrl.format(FilterDate=FilterDate)  + str(20*i)
            session       = AuthenticateSAPB1()
            response      = session.request("GET", modfified_Url, data=payload,  headers=headersList,verify=False)
                
            Ar_Invoice_Dict = dict(response.json())            
            if Ar_Invoice_Dict['value'] is not None:
                print ('Going into')
                for Single_Invoice in Ar_Invoice_Dict['value']:
                    if frappe.db.exists("SAP AR Invoice Detail", Single_Invoice['DocEntry']):
                        print('present DocEntry',Single_Invoice['DocEntry'])
                        Update_waybill_and_filePath(Single_Invoice['DocEntry'])
                      
                    else:
                        print('not present DocEntry',Single_Invoice['DocEntry'])
                        Saved_InvDoc(Single_Invoice)


                i += 1
                #increment the counter
            elif Ar_Invoice_Dict['value'] is None:
                break
            
            
            reqUrl    = reqUrl.format(FilterDate=FilterDate)  + str(20*i)
            session   = AuthenticateSAPB1()
            response  = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
                
            Ar_Invoice_Dict = dict(response.json())
        frappe.msgprint(msg ='Data Inserted successfully',title ='Success')
        return None
    pass





# bench --site khanaltech.com execute khanal_tech_integrations.utils.safexpress.automated_invoice_attach.Fetching_from_Sap
# bench --site dev.localhost execute khanal_tech_integrations.utils.safexpress.automated_invoice_attach.Fetching_from_Sap


def Saved_InvDoc(Single_Invoice):
    session       = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    doc = frappe.new_doc('SAP AR Invoice Detail')
    # print(Single_Invoice['DocEntry'])
    doc.docentry             = Single_Invoice['DocEntry']
    # empty_list.append( Single_Invoice['DocEntry'])
    doc.docnum               = Single_Invoice['DocNum']
    doc.cancellation_status  = Single_Invoice['CancelStatus']
    doc.doc_date             = Single_Invoice['DocDate']
    doc.created_date         = Single_Invoice['CreationDate']
    doc.lastupdated_date     = Single_Invoice['UpdateDate']
    doc.due_date             = Single_Invoice['DocDueDate']
    doc.ref_num              = Single_Invoice['NumAtCard']
    doc.customer_code        = Single_Invoice['CardCode']
    doc.bill_address         = Single_Invoice['Address']  
    doc.ship_address         = Single_Invoice['Address2']
    doc.customer_name        = Single_Invoice['CardName']

    doc.doc_currency         = Single_Invoice['DocCurrency'] 
    doc.series_no             = Single_Invoice['Series'] 

    if Single_Invoice['DocCurrency'] == "INR":
        doc.bill_total           = Single_Invoice['DocTotal']
        doc.tax_total            = Single_Invoice['VatSum'] 
    else:
        doc.bill_total           = Single_Invoice['DocTotalFc']
        doc.tax_total            = Single_Invoice['VatSumFc'] 

    if Single_Invoice['U_Pod_Link']:
        doc.pod_url                  = Single_Invoice['U_Pod_Link']
        doc.pod_status               = 'Completed'
        doc.way_bill_number          = Single_Invoice['U_TrackingNo']
        doc.transporter_type         = Single_Invoice['U_TN']

    paymenturl = doc_settings.sap_b1_url+"PaymentTermsTypes({code})"
    Payment_Modified_Url = paymenturl.format(code=Single_Invoice['PaymentGroupCode'])
    payload = ""
    paymentresponse = session.request("GET", Payment_Modified_Url, data=payload,  headers=headersList,verify=False)
    paymentlist = dict(paymentresponse.json())
    net_value=paymentlist['PaymentTermsGroupName']
    if "%" in net_value:
        # print(net_value,'%')
        doc.term            = net_value
        doc.last_due_date   = Single_Invoice['DocDueDate']
    else:
        match = re.search(r'\d+', net_value)
        if match:
            net_int_value       = int(match.group())
            doc.term            = net_int_value
            # print(net_int_value,'num')
            last_date           = add_to_date(Single_Invoice['DocDate'],days=+int(net_int_value))
            doc.last_due_date   = last_date
        else:
            doc.term            = net_value
            doc.last_due_date   = Single_Invoice['DocDueDate']

    Emptylist_SO_doc         = []
    for item in Single_Invoice['DocumentLines']:
        Emptylist_SO_doc.append(item['BaseEntry'])
    emptyset                 = set(Emptylist_SO_doc)
    DN_docentrylist          = list(emptyset) 
    # print(DN_docentrylist)
    DN_DocEntry              = None
    if len(DN_docentrylist) != 0:
        DN_DocEntry          = DN_docentrylist[0]
    # print(DN_DocEntry)
    doc.ref_delivery_note    = DN_DocEntry


    Warehouse                 =[]
    for warelist in Single_Invoice['DocumentLines']:
        Warehouse.append(warelist['LocationCode'])
    warehouseset                 = set(Warehouse)
    WarehouseList          = list(warehouseset) 
    # print(WarehouseList)
    Location_code              = None
    if len(WarehouseList) != 0:
        Location_code          = WarehouseList[0]
    # print(Location_code)
    # print(Location_code,'Location_code')
    doc.ware_housecode    = Location_code

    doc.customer_gst =Single_Invoice['EWayBillDetails']['BillToGSTIN']
    doc.place_of_supply= Single_Invoice['AddressExtension']['PlaceOfSupply']

    try:
        doc.save()
        doc = frappe.get_doc("SAP AR Invoice Detail",Single_Invoice['DocEntry'])
        LineItems = get_single_lineitem(Single_Invoice['DocEntry'])
        # print(LineItems)
        for LineItem in LineItems:
            # print(LineItem)
            doc.append("line_items",LineItem)
        doc.save()
        frappe.db.commit()
        updating_email(Single_Invoice['DocEntry'],Single_Invoice['ContactPersonCode'],Single_Invoice['SalesPersonCode'])
        WareHouseUpdate(Single_Invoice['DocEntry'])
        Update_waybill_and_filePath(Single_Invoice['DocEntry'])
        print(doc,'saved')
        return doc
    except frappe.DuplicateEntryError:
        print(doc,'duplicate')
        return doc

# @frappe.whitelist()
# def MANUALLY_UPDATE_POD_LINK(DOCENTRY):
#     # Split the input DOCENTRY into a list
#     list_of_DOCENTRY = DOCENTRY.split(',')
#     payload = ''
#     # Loop through each DOCENTRY
#     for Single_DOCENTRY in list_of_DOCENTRY:
#         doc_settings = frappe.get_doc('SAP Settings')
#         Url = f"{doc_settings.sap_b1_url}Invoices({Single_DOCENTRY})"
#         print(Url)
#         session = AuthenticateSAPB1()
#         response = session.request("GET", Url, data=payload, headers=headersList, verify=False)
#         # Check if the response status code is 200 (OK)
#         if response.status_code == 200:
#             Single_Invoice = dict(response.json()) 
#             # DocEntry=Single_Invoice['DocEntry']
#             # print(DocEntry)
#             if frappe.db.exists("SAP AR Invoice Detail", Single_Invoice['DocEntry']):
#                 print('present DocEntry',Single_Invoice['DocEntry'])
#                 # Update_waybill_and_filePath(Single_Invoice['DocEntry'])
                
#             else:
#                 print('not present DocEntry',Single_Invoice['DocEntry'])
#                 doc                      = frappe.new_doc('SAP AR Invoice Detail')
#                 # print(Single_Invoice['DocEntry'])
#                 doc.docentry             = Single_Invoice['DocEntry']
#                 # empty_list.append( Single_Invoice['DocEntry'])
#                 doc.docnum               = Single_Invoice['DocNum']
#                 doc.cancellation_status  = Single_Invoice['CancelStatus']
#                 doc.doc_date             = Single_Invoice['DocDate']
#                 doc.created_date         = Single_Invoice['CreationDate']
#                 doc.lastupdated_date     = Single_Invoice['UpdateDate']
#                 doc.due_date             = Single_Invoice['DocDueDate']
#                 doc.ref_num              = Single_Invoice['NumAtCard']
#                 doc.customer_code        = Single_Invoice['DOCENTRY']
#                 doc.bill_address         = Single_Invoice['Address']  
#                 doc.ship_address         = Single_Invoice['Address2']
#                 doc.customer_name        = Single_Invoice['CardName']
                
#                 doc.doc_currency         = Single_Invoice['DocCurrency'] 
#                 doc.series_no             = Single_Invoice['Series'] 

#                 if Single_Invoice['DocCurrency'] == "INR":
#                     doc.bill_total           = Single_Invoice['DocTotal']
#                     doc.tax_total            = Single_Invoice['VatSum'] 
#                 else:
#                     doc.bill_total           = Single_Invoice['DocTotalFc']
#                     doc.tax_total            = Single_Invoice['VatSumFc'] 

#                 paymenturl = doc_settings.sap_b1_url+"PaymentTermsTypes({code})"
#                 Payment_Modified_Url = paymenturl.format(code=Single_Invoice['PaymentGroupCode'])
#                 payload = ""
#                 paymentresponse = session.request("GET", Payment_Modified_Url, data=payload,  headers=headersList,verify=False)
#                 paymentlist = dict(paymentresponse.json())
#                 net_value=paymentlist['PaymentTermsGroupName']
#                 if "%" in net_value:
#                     # print(net_value,'%')
#                     doc.term            = net_value
#                     doc.last_due_date   = Single_Invoice['DocDueDate']
#                 else:
#                     match = re.search(r'\d+', net_value)
#                     if match:
#                         net_int_value       = int(match.group())
#                         doc.term            = net_int_value
#                         # print(net_int_value,'num')
#                         last_date           = add_to_date(Single_Invoice['DocDate'],days=+int(net_int_value))
#                         doc.last_due_date   = last_date
#                     else:
#                         doc.term            = net_value
#                         doc.last_due_date   = Single_Invoice['DocDueDate']
                
#                 Emptylist_SO_doc         = []
#                 for item in Single_Invoice['DocumentLines']:
#                     Emptylist_SO_doc.append(item['BaseEntry'])
#                 emptyset                 = set(Emptylist_SO_doc)
#                 DN_docentrylist          = list(emptyset) 
#                 # print(DN_docentrylist)
#                 DN_DocEntry              = None
#                 if len(DN_docentrylist) != 0:
#                     DN_DocEntry          = DN_docentrylist[0]
#                 # print(DN_DocEntry)
#                 doc.ref_delivery_note    = DN_DocEntry


#                 Warehouse                 =[]
#                 for warelist in Single_Invoice['DocumentLines']:
#                     Warehouse.append(warelist['LocationCode'])
#                 warehouseset                 = set(Warehouse)
#                 WarehouseList          = list(warehouseset) 
#                 # print(WarehouseList)
#                 Location_code              = None
#                 if len(WarehouseList) != 0:
#                     Location_code          = WarehouseList[0]
#                 # print(Location_code)
#                 # print(Location_code,'Location_code')
#                 doc.ware_housecode    = Location_code

#                 doc.customer_gst =Single_Invoice['EWayBillDetails']['BillToGSTIN']
#                 doc.place_of_supply= Single_Invoice['AddressExtension']['PlaceOfSupply']

#                 try:
#                     doc.save()
#                     doc = frappe.get_doc("SAP AR Invoice Detail",Single_Invoice['DocEntry'])
#                     LineItems = get_single_lineitem(Single_Invoice['DocEntry'])
#                     # print(LineItems)
#                     for LineItem in LineItems:
#                         # print(LineItem)
#                         doc.append("line_items",LineItem)
#                     doc.save()
#                     frappe.db.commit()
#                     updating_email(Single_Invoice['DocEntry'],Single_Invoice['ContactPersonCode'],Single_Invoice['SalesPersonCode'])
#                     WareHouseUpdate(Single_Invoice['DocEntry'])
#                     Update_waybill_and_filePath(Single_Invoice['DocEntry'])
#                     print(doc,'saved')
#                 except frappe.DuplicateEntryError:
#                     print(doc,'duplicate')
#                     pass

#             pass
#         else:
#             print('not')
             
            

#     # Add any necessary post-loop code here
#     return None
# bench --site khanaltech.com execute  --args "{'365'}" khanal_tech_integrations.utils.safexpress.automated_invoice_attach.Fetching_from_Sap
# bench --site khanaltech.com execute  --args "{ '19269,19265,19263,19262,19260,19258,19199,19195,19197,19178,19174,19254,19267,19491,19466,19465,19464,19492,19450,19437,19449,19448,19438,19435,19431,19428,19443,19436,19439,19379,19375,19378,19380,19383,19370,19367,19352,19374,19373,19369,19368,19366,19364,19363,19351,19405,19406,19270,19271,19266,19975,19926,19949,19888,19916,19915,19914,19887,19878,19901,19895,19879,19877,19882,19652,19517,19518,20671,20666,20563,20537,20833,20832,20826,20594,21078,20952,20930,20929,20900,21248,21191,21188,21190,21215,21318,21328,21323,21325,21321,21304,21302,21287,21285,22116,22761,22722' }"  khanal_tech_integrations.utils.safexpress.automated_invoice_attach.MANUALLY_UPDATE_POD_LINK

@frappe.whitelist()
def MANUALLY_UPDATE_POD_LINK(DOCENTRY):
    try:
        # Split the input DOCENTRY into a list
        list_of_DOCENTRY = DOCENTRY.split(',')
        payload = ''
        # Loop through each DOCENTRY
        for Single_DOCENTRY in list_of_DOCENTRY:
            try:
                doc_settings = frappe.get_doc('SAP Settings')
                Url = f"{doc_settings.sap_b1_url}Invoices({Single_DOCENTRY})"
                # print(Url)
                session = AuthenticateSAPB1()
                response = session.request("GET", Url, data=payload, headers=headersList, verify=False)
                
                # Check if the response status code is 200 (OK)
                if response.status_code == 200:
                    Single_Invoice = dict(response.json()) 
                    if frappe.db.exists("SAP AR Invoice Detail", Single_Invoice['DocEntry']):
                        print('present DocEntry',Single_Invoice['DocEntry'])
                        Update_waybill_and_filePath(Single_Invoice['DocEntry'])
                    else:
                        print('not present DocEntry',Single_Invoice['DocEntry'])
                        doc                      = frappe.new_doc('SAP AR Invoice Detail')
                        # print(Single_Invoice['DocEntry'])
                        doc.docentry             = Single_Invoice['DocEntry']
                        # empty_list.append( Single_Invoice['DocEntry'])
                        doc.docnum               = Single_Invoice['DocNum']
                        doc.cancellation_status  = Single_Invoice['CancelStatus']
                        doc.doc_date             = Single_Invoice['DocDate']
                        doc.created_date         = Single_Invoice['CreationDate']
                        doc.lastupdated_date     = Single_Invoice['UpdateDate']
                        doc.due_date             = Single_Invoice['DocDueDate']
                        doc.ref_num              = Single_Invoice['NumAtCard']
                        doc.customer_code        = Single_Invoice['CardCode']
                        doc.bill_address         = Single_Invoice['Address']  
                        doc.ship_address         = Single_Invoice['Address2']
                        doc.customer_name        = Single_Invoice['CardName']
                        
                        doc.doc_currency         = Single_Invoice['DocCurrency'] 
                        doc.series_no             = Single_Invoice['Series'] 

                        if Single_Invoice['DocCurrency'] == "INR":
                            doc.bill_total           = Single_Invoice['DocTotal']
                            doc.tax_total            = Single_Invoice['VatSum'] 
                        else:
                            doc.bill_total           = Single_Invoice['DocTotalFc']
                            doc.tax_total            = Single_Invoice['VatSumFc'] 

                        paymenturl = doc_settings.sap_b1_url+"PaymentTermsTypes({code})"
                        Payment_Modified_Url = paymenturl.format(code=Single_Invoice['PaymentGroupCode'])
                        payload = ""
                        paymentresponse = session.request("GET", Payment_Modified_Url, data=payload,  headers=headersList,verify=False)
                        paymentlist = dict(paymentresponse.json())
                        net_value=paymentlist['PaymentTermsGroupName']
                        if "%" in net_value:
                            # print(net_value,'%')
                            doc.term            = net_value
                            doc.last_due_date   = Single_Invoice['DocDueDate']
                        else:
                            match = re.search(r'\d+', net_value)
                            if match:
                                net_int_value       = int(match.group())
                                doc.term            = net_int_value
                                # print(net_int_value,'num')
                                last_date           = add_to_date(Single_Invoice['DocDate'],days=+int(net_int_value))
                                doc.last_due_date   = last_date
                            else:
                                doc.term            = net_value
                                doc.last_due_date   = Single_Invoice['DocDueDate']
                        
                        Emptylist_SO_doc         = []
                        for item in Single_Invoice['DocumentLines']:
                            Emptylist_SO_doc.append(item['BaseEntry'])
                        emptyset                 = set(Emptylist_SO_doc)
                        DN_docentrylist          = list(emptyset) 
                        # print(DN_docentrylist)
                        DN_DocEntry              = None
                        if len(DN_docentrylist) != 0:
                            DN_DocEntry          = DN_docentrylist[0]
                        # print(DN_DocEntry)
                        doc.ref_delivery_note    = DN_DocEntry


                        Warehouse                 =[]
                        for warelist in Single_Invoice['DocumentLines']:
                            Warehouse.append(warelist['LocationCode'])
                        warehouseset                 = set(Warehouse)
                        WarehouseList          = list(warehouseset) 
                        # print(WarehouseList)
                        Location_code              = None
                        if len(WarehouseList) != 0:
                            Location_code          = WarehouseList[0]
                        # print(Location_code)
                        # print(Location_code,'Location_code')
                        doc.ware_housecode    = Location_code

                        doc.customer_gst =Single_Invoice['EWayBillDetails']['BillToGSTIN']
                        doc.place_of_supply= Single_Invoice['AddressExtension']['PlaceOfSupply']

                        try:
                            doc.save()
                            doc = frappe.get_doc("SAP AR Invoice Detail",Single_Invoice['DocEntry'])
                            LineItems = get_single_lineitem(Single_Invoice['DocEntry'])
                            for LineItem in LineItems:
                                doc.append("line_items",LineItem)
                            doc.save()
                            frappe.db.commit()
                            updating_email(Single_Invoice['DocEntry'],Single_Invoice['ContactPersonCode'],Single_Invoice['SalesPersonCode'])
                            WareHouseUpdate(Single_Invoice['DocEntry'])
                            Update_waybill_and_filePath(Single_Invoice['DocEntry'])
                            print(doc,'saved')
                        except frappe.DuplicateEntryError:
                            print(doc,'duplicate')
                            pass
                else:
                    print('not')
            except Exception as e:
                print(f"An error occurred while processing Single_DOCENTRY {Single_DOCENTRY}: {str(e)}")
    except Exception as e:
        print(f"An error occurred while processing DOCENTRY: {str(e)}")
    
    # Add any necessary post-loop code here
    return None



invoice_waybill_dict = {
    "19269":"100003578764",
    "19265":"100003576172",
    "19263":"100003575818",
    "19262":"100003575315",
    "19260":"100003572501",
    "19258":"100003572097",
    "19199":"100003530852",
    "19195":"100003530060",
    "19197":"100003530899",
    "19178":"100003502117",
    "19174":"100003501358",
    "19254":"100003572285",
    "19267":"100003576814",
    "19491":"100003755730",
    "19466":"100003754757",
    "19465":"100003755280",
    "19464":"100003755085",
    "19492":"100003755469",
    "19450":"100003728063",
    "19437":"100003721857",
    "19449":"100003727794",
    "19448":"100003727611",
    "19438":"100003722308",
    "19435":"100003721632",
    "19431":"100003720805",
    "19428":"100003758067",
    "19443":"100003727919",
    "19436":"100003721040",
    "19439":"100003722653",
    "19379":"100003697391",
    "19375":"100003687655",
    "19378":"100003689587",
    "19380":"100003692840",
    "19383":"100003692439",
    "19370":"100003689369",
    "19367":"100003693061",
    "19352":"100003688663",
    "19374":"100003693348",
    "19373":"100003691890",
    "19369":"100003688048",
    "19368":"100003688923",
    "19366":"100003693548",
    "19364":"100003692205",
    "19363":"100003689833",
    "19351":"100003687484",
    "19405":"100003697839",
    "19406":"100003697720",
    "19270":"100003579337",
    "19271":"100003579574",
    "19266":"100003579893",
    "19975":"100004129415",
    "19926":"100004130968",
    "19949":"100004129985",
    "19888":"100004075774",
    "19916":"100004077171",
    "19915":"100004075633",
    "19914":"100004075247",
    "19887":"100004076562",
    "19878":"100004075493",
    "19901":"100004129597",
    "19895":"100004075919",
    "19879":"100004077016",
    "19877":"100004076129",
    "19882":"100004076853",
    "19652":"100003224525",
    "19517":"100003785891",
    "19518":"100003784026",
    "20594":"100004678709",
    "22116":"100006062329",
    "22761":"100006635505",
    "22722":"100006601530"
}

@frappe.whitelist()
def Updating_using_List():
    for single_doc_entry in invoice_waybill_dict:
        waybill_number = invoice_waybill_dict.get(single_doc_entry)
        
        try:
            doc = frappe.get_doc('SAP AR Invoice Detail', single_doc_entry)
            print(f"Invoice DocEntry {single_doc_entry}: Waybill {waybill_number}")
            doc.way_bill_number = waybill_number
            doc.save()
            frappe.db.commit()
            Get_Single_Pod(single_doc_entry)
            PATCH_POD_AR_invoice(single_doc_entry)
            
        except Exception as e:
            pass

# Define your get_single_pod and patch_pod_ar_invoice functions here if they are not already defined

    # bench --site khanaltech.com execute khanal_tech_integrations.utils.safexpress.automated_invoice_attach.Updating_using_List