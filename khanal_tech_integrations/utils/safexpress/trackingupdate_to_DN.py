import frappe
import json
import requests
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
from frappe.utils import add_to_date


headersList = {
        "Accept": "*/*",
        "User-Agent": "Khanal Tech",
        "Content-Type": "application/json" 
    }





@frappe.whitelist()
def Fetching_ArInvoice():
    Today = frappe.utils.nowdate()
    FilterDate = add_to_date(Today,days=-50)
    payload={}
    doc_settings = frappe.get_doc('SAP Settings')
    count_url = doc_settings.sap_b1_url+"Invoices?$apply=filter(UpdateDate ge '{FilterDate}' )/aggregate(DocEntry with countdistinct as CountDistinct)"
    session     = AuthenticateSAPB1()
    Modified_count_url = count_url.format(FilterDate=FilterDate)
    response      = session.request("GET", Modified_count_url, data=payload,  headers=headersList,verify=False)
    Arinvoice_Count = dict(response.json())
    print(Arinvoice_Count,'Arinvoice_Count')
    if Arinvoice_Count['value'] is not None:
        counter = Arinvoice_Count['value'][0]['CountDistinct']
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
                
            Ar_Invoice_Dict = dict(response.json())            
            if Ar_Invoice_Dict['value'] is not None:
                for Single_Invoice in Ar_Invoice_Dict['value']:
                    print(Single_Invoice['DocEntry'],'AR_Invoice DocEntry')
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

                    Dn_check=Check_DN(DN_DocEntry)

                    
                    # print(Dn_check)
                    if Dn_check == 200:

                        url = "https://webs.safexpress.com:8443/SafexWaybillTracking/webresources/tracking/all"
                        prefixes = ["KAIN24", "AR2024", "HRIN24", "MHIN24","KAIN23", "AR2023", "HRIN23", "MHIN23"]
                        for prefix in prefixes:
                            # if prefix == "Manual":
                            #     formatted_doc = str(doc.docnum)
                            # else:
                            formatted_doc = f"{prefix}/{Single_Invoice['DocNum']}"
                            payload = {
                                "docNo": formatted_doc,
                                "docType": "INV"
                            }
                            response = requests.post(url, headers=headersList, json=payload,verify=False)
                            if response.status_code == 200:
                                
                                result = response.json()
                               
                                # print(f"Success for prefix {prefix}: {result}")
                                if 'waybill' in result['shipment']:
                                    print(result)
                                    Patch_Dn_SAP(DN_DocEntry,result['shipment']['waybill'])
                                    pass
                   


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




def Check_DN(DN_DocEntry):
    Docentry=DN_DocEntry
    if DN_DocEntry is None or DN_DocEntry == "":
        # print(DN_DocEntry)
        pass
    else:
        # print(DN_DocEntry)
        session = AuthenticateSAPB1()
        payload=''
        doc_settings = frappe.get_doc('SAP Settings')
        DN_url                     = doc_settings.sap_b1_url+"DeliveryNotes({Docentry})"
        reqUrl_modified         = DN_url.format(Docentry=Docentry)                        
        session             = AuthenticateSAPB1()
        response = session.request("GET", reqUrl_modified, headers=headersList, data=payload,verify=False)
        # print(response,'response')
        # print(response.text)
        return response.status_code
        


def Patch_Dn_SAP(DN_DocEntry,WayBill):
    print(DN_DocEntry,'value')
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url                     = doc_settings.sap_b1_url+"DeliveryNotes({Docentry})"
    reqUrl_modified         = Url.format(Docentry=DN_DocEntry)        
    payload = json.dumps({  "U_TN": "Safexpress",   "U_TrackingNo": WayBill,})
    
    session             = AuthenticateSAPB1()
    response = session.request("PATCH", reqUrl_modified, headers=headersList, data=payload,verify=False)
    print(response,'response')
    # print(response.text)
    return 'DN Patched'
   

# bench --site khanaltech.com execute khanal_tech_integrations.utils.safexpress.trackingupdate_to_DN.Fetching_ArInvoice
# bench --site dev.localhost execute khanal_tech_integrations.utils.safexpress.trackingupdate_to_DN.Fetching_ArInvoice