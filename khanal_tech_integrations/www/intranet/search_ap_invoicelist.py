import frappe
import frappe.utils
from khanal_tech_integrations.utils.banking.AP_invoices import get_AP_invoices
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
from khanal_tech_integrations.utils.cashfree.benefeciary import get_cashfree_status
from khanal_tech_integrations.utils.razorpay.contacts import get_banklist_Vendor

headersList = {
                "Accept": "*/*",
                "User-Agent": "Khanal Tech",
                "Content-Type": "application/json" 
            }

def get_context(context):
    session = AuthenticateSAPB1()
    empty_payload = ''
    if frappe.local.request.args.get("ap_invoice"):
        vendor_code = frappe.local.request.args.get("ap_invoice")
    else:
        vendor_code = None
    
    if frappe.local.request.args.get("current_page"):
        current_page = frappe.local.request.args.get("current_page")
    else:
        current_page = 0
    doc_settings = frappe.get_doc('SAP Settings')
    Count_url = doc_settings.sap_b1_url+"PurchaseInvoices?$apply=filter(CardCode eq '{cardcode}')/aggregate(DocEntry with countdistinct as CountDistinct)"
    modfified_Url = Count_url.format(cardcode=vendor_code)
    print(vendor_code)    
    AP_invoice_count_response      = session.request("GET", modfified_Url, data=empty_payload,  headers=headersList,verify=False)
        
    AP_Invoice_count = dict(AP_invoice_count_response.json())
    print(AP_Invoice_count)
    AP_invoice_list = []
    i=current_page
    if int(current_page)>0:
        i = int(current_page)-1
    print (i)

    # reqUrl          = doc_settings.sap_b1_url+"PurchaseInvoices?$orderby=DocDate desc&$skip=" + str(20*i)
    reqUrl              = doc_settings.sap_b1_url+"PurchaseInvoices?$filter=CardCode eq '{cardcode}' and DocumentStatus eq 'bost_Open' &$orderby=DocDate desc&$skip=" +str(20*i)
    VendorSpeicific_url = reqUrl.format(cardcode=vendor_code)
    response            = session.request("GET", VendorSpeicific_url, data=empty_payload,  headers=headersList,verify=False)
    resp_json           = response.json()['value'] #List full of dictionaries
    
    # print (resp_json)
    
    if resp_json: 
        for item in resp_json:
            keysss  = ['DocDate', 'DocEntry','DocNum','CardCode','CardName','NumAtCard','DocTotal', 'DocumentStatus' ,'DocDueDate','U_TN','PaidToDate'] #U_TM
            dict2   = {x:item[x] for x in keysss }
       
            AP_invoice_list.append(dict2)

    else:
        AP_invoice_list = ''

    vendorlist = get_banklist_Vendor(vendorcode =  vendor_code ) 



    vendorlistName = frappe.db.get_list('SAP Vendor Details', fields=['vendor_code', 'vendor_name'])
    Details=''
    print(type(vendor_code))
    if vendor_code is not None:
        Details = frappe.get_doc('SAP Vendor Details', vendor_code)
        context['Details'] = Details


    print(Details)  
    context={
        "vendorlistName":vendorlistName,
        "ap_invoice_list":AP_invoice_list,
        "vendorlist":vendorlist,
        
    }
    return context
