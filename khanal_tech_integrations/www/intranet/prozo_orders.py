
import frappe
import frappe.utils
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
from khanal_tech_integrations.utils.razorpay.contacts import get_banklist_Vendor



# def get_context(context):
#     PZ_orders = frappe.db.get_list('SAP Sales Order' , 
#                         fields=['created_date', 'docnum', 'docentry','customer_code','customer_name'],
#                         filters={'lineitem_from_warehouse': ['like', '%PZ%']
#                                 })
#     print(PZ_orders)
#     context={
#         "PZ_orders":PZ_orders,
#     }
#     return context

headersList = {
                "Accept": "*/*",
                "User-Agent": "Khanal Tech",
                "Content-Type": "application/json" 
            }
########################
def get_context(context):
    session = AuthenticateSAPB1()
    empty_payload = ''
    
    if frappe.local.request.args.get("current_page"):
        current_page = frappe.local.request.args.get("current_page")
    else:
        current_page = 0
        
    # vendor_code = 'V00525'
    doc_settings = frappe.get_doc('SAP Settings')
    Count_url           =   doc_settings.sap_b1_url+"Orders?$apply=filter(startswith(CardCode,'C'))/aggregate(DocEntry with countdistinct as CountDistinct)"
    AP_invoice_count_response      = session.request("GET", Count_url, data=empty_payload,  headers=headersList,verify=False)
        
    AP_Invoice_count = dict(AP_invoice_count_response.json())
    print(AP_Invoice_count)
    
    AP_invoice_list = []
    i=current_page
    if int(current_page)>0:
        i = int(current_page)-1
    print (i)

    # reqUrl          = doc_settings.sap_b1_url+"PurchaseInvoices?$orderby=DocDate desc&$skip=" + str(20*i)
    reqUrl          = doc_settings.sap_b1_url+"Orders?$filter=startswith(U_SubConPONo, 'PZ') &$orderby=DocDate desc&$skip=" +str(20*i)
    response        = session.request("GET", reqUrl, data=empty_payload,  headers=headersList,verify=False)
    resp_json = response.json()['value'] #List full of dictionaries ?$filter=CardCode eq '{cardcode}' 
    # print (resp_json)
    
    if resp_json: 
        for item in resp_json:
            keysss = ['DocDate', 'DocEntry','DocNum','CardCode','CardName','NumAtCard','DocTotal', 'DocumentStatus' ,'DocDueDate','U_TN','U_SubConPONo',"U_SubConPOEn","U_GrDocNum"] #U_TM
            dict2 = {x:item[x] for x in keysss }
            # dict2['CAshfreeActivity'] = "--"
            # print('U_TN = ', dict2['U_TN'])
            # if dict2['U_TN'] != None:
            #     Cashfree_Status = get_cashfree_status(str(dict2['DocEntry']) + str(dict2['CardCode']))
            #     dict2['CAshfreeActivity'] = Cashfree_Status
            # else:
            #     pass

            AP_invoice_list.append(dict2)

    else:
        AP_invoice_list = ''
  
    context={
        "PZ_orders":AP_invoice_list,
        # "ap_invoice_count":The_AP_Count,#AP_Invoice_count['value']
    }
   
    return context