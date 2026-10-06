import frappe
import json
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
from frappe.utils.file_manager import save_file
from frappe.utils import file_manager
from frappe.utils.file_manager import get_file_path, get_files_path
from PIL import Image
import io
import os 
from jinja2 import Template
import random
headersList = {
                "Accept": "*/*",
                "User-Agent": "Khanal Tech",
                "Content-Type": "application/json" 
            }


@frappe.whitelist()
def ProcurementAdding_To_SAP(data,inputData):
    
    print(frappe.utils.nowdate(),'date')
    
    data_dict = json.loads(data)
    # print(type(inputData))
    # json_data = json.dumps(inputData)
    print(inputData)

    print(data_dict['PonumberDocentry'],'DocEntry')
    getdoc                                = frappe.get_doc("SAP Purchase Order", data_dict['PonumberDocentry'])
    doc                                   = frappe.new_doc('GatePass')
    doc.purchasedocentry                  = data_dict['PonumberDocentry']
    doc.purchasedocnum                    = getdoc.docnum
    doc.location                          = data_dict['location']
    doc.securityname                      = data_dict['security']
    doc.invoicevalue                      = data_dict['invoicevalue']
    doc.vechilenumber                     = data_dict['vehiclenumber']
    doc.drivername                        = data_dict['drivername']
    doc.drivernumber                      = data_dict['drivernumber']
    doc.clockin                           = data_dict['clockin']
    doc.clockout                          = data_dict['clockout']
    doc.invoice_date                      = data_dict['invoicedate']
    doc.invoicenumber                     = data_dict['invoicenumber']
    doc.created_date                      =frappe.utils.nowdate()
    doc.itemitems                         =inputData
    
    doc.save()
    
    # # #? -------------------------------------------
    # doc.save()
    frappe.db.commit()
  
    input_dict = json.loads(inputData)
    # print(input_dict,'input_dict')
    
    doc_settings = frappe.get_doc('SAP Settings')
    Url                     = doc_settings.sap_b1_url+"PurchaseOrders({Docentry})"
    reqUrl_modified         = Url.format(Docentry=data_dict['PonumberDocentry']) 
    session       = AuthenticateSAPB1()
    payload = ''
    response      = session.request("GET", reqUrl_modified, data=payload,  headers=headersList,verify=False)
    print(response)
    PurchaseorderOrder  = dict(response.json())
    data_dict['clockin']
    print(type(data_dict['clockin']),'frappe clock in')
    print(type(data_dict['clockout']),'frappe clock out')
    
    print(type(data_dict['invoicedate']),'invoice date')
    print(type(doc.clockin),'clockin')
    print(type(doc.clockout),'clockout')
    purchase_payload = {    
          "U_GateEntNo": doc.name,
          "U_GP_Whse"  : doc.location ,
          "U_SecurityName"  : doc.securityname ,
          "U_GP_VehicleNumber"  : doc.vechilenumber ,
          "U_GP_DriversName"  : doc.drivername ,
          "U_GP_DriverNumber"  : doc.drivernumber ,
          "U_GP_InvoiceDate"  : data_dict['invoicedate'] ,
          "U_GP_InvNumber"  : data_dict['invoicenumber'] ,
          "U_GP_InvValue"  : doc.invoicevalue ,
          "U_GP_VehicleInTime"  : data_dict['clockin'] ,
          "U_GP_VehicleOutTime"  : data_dict['clockout'] ,
        #   "U_GP_InvValue"  : doc.location ,

          "DocumentLines": [ ]
                    }
    # LineNum_Count = 0
    linenum_quantity = {i['LineNum']:i['InputValue'] for i in input_dict}
    print(linenum_quantity,'linenum_quantity')
    
    linenum_itemcode = {i['LineNum']:i['ItemCode'] for i in input_dict}
    print(linenum_itemcode,'linenum_itemcode')
    print(len(PurchaseorderOrder['DocumentLines']),'lenght')
    for single_Lineitem in PurchaseorderOrder['DocumentLines']:
        single_return_item = {
                                "LineNum": 0,
                                "ItemCode": "PMHN0214",
                                "U_GP_Qty": 3222,
                            }
        
        print(linenum_itemcode[str(single_Lineitem['LineNum'])],'line')
        print(linenum_quantity[str(single_Lineitem['LineNum'])],'qty')
        single_return_item['LineNum'] = single_Lineitem['LineNum']
        single_return_item['ItemCode'] = linenum_itemcode[str(single_Lineitem['LineNum'])]
        single_return_item['U_GP_Qty'] = linenum_quantity[str(single_Lineitem['LineNum'])]
        purchase_payload['DocumentLines'].append(single_return_item)

            

    Url_PATCH                     = doc_settings.sap_b1_url+"PurchaseOrders({Docentry})"
    reqUrl_modified_PATCH           = Url_PATCH.format(Docentry=data_dict['PonumberDocentry']) 
    response1 = session.request("PATCH", reqUrl_modified_PATCH, data=json.dumps(purchase_payload),  headers=headersList,verify=False)
    print(response1,'response')
    print(response1.text)
  
    print('response is --- ',str(response1)[:40])
    
    if response1.status_code == 204:
        print("Worked")
        getdoc.status                         ='Closed'  
        getdoc.save()
        sent_alert_GrnTeam(doc.name)
        return {'name':doc.purchasedocentry}
    elif response1.status_code in [404, 400]:
        doc.delete()
        print(doc.name,'delete')
        error_response = response1.json()
        error_message = error_response["error"]["message"]["value"]
        print(error_message)
        return error_message
    else:
        print("Error")
        return "Error"

#? data      =  {"location":"Ecom Mahadevapura","security":"Do quo sit quis natu","vehiclenumber":"423","drivername":"Brenna Byers","drivernumber":"995","invoicedate":"1998-04-10","invoicenumber":"181","invoicevalue":"Eum sed ut aut et es","clockin":"2008-01-13T00:24","clockout":"2011-11-21T12:08","PonumberDocentry":"3290"} 
#? inputData = [{"ItemCode":"RMHN0051","ItemDescription":"HN Organic Virgin Coconut Oil - 250ML - Semi Finished","Quantity":"1500","InputValue":"233"},{"ItemCode":"RMHN0052","ItemDescription":"HN Organic Virgin Coconut Oil - 500ML - Semi Finished","Quantity":"1200","InputValue":""},{"ItemCode":"EXCM0024","ItemDescription":"Transportation Freight","Quantity":"1500","InputValue":""},{"ItemCode":"EXCM0024","ItemDescription":"Transportation Freight","Quantity":"1200","InputValue":""},{"ItemCode":"EXHN0001","ItemDescription":"Expense - TC Certificate","Quantity":"1","InputValue":""}] 


@frappe.whitelist()
def GetLineitem_Details(poNumber):
    # print(poNumber)
    SingleDoc = frappe.get_doc("SAP Purchase Order", poNumber)
    dict_response = json.loads(SingleDoc.lineitem)
    return dict_response

@frappe.whitelist()
def sent_alert_GrnTeam(docname):
    # print(poNumber)
    doc = frappe.get_doc("GatePass", docname)
    # dict_response = json.loads(doc.itemitems)
    file_path = os.path.join(os.path.dirname(__file__), 'grnemail.html')
        # print(file_path,'filepath')
    with open(file_path, 'r') as f:
        # contents = f.read()
        # print(contents)
        template_str = f.read()
    # print(template_str,'template_str')

    template = Template(template_str)
    # print(template,'template')
    purchaseDoc=frappe.get_doc("SAP Purchase Order", doc.purchasedocentry)
    str_created_date = doc.created_date.strftime("%d %B %Y")
    rendered_message = template.render(
            subject='working',
            doc=doc,
            listing=json.loads(doc.itemitems),
            vendorname=purchaseDoc.cardname,
            str_created_date=str_created_date,
            clockin= doc.clockin.strftime('%I:%M %p'),
            clockout= doc.clockout.strftime('%I:%M %p')
        )

    if doc.location == 'DOGSEE':
        recipients = ['darshan@khanalfoods.com','shivakumar@khanalfoods.com','shubham@khanalfoods.com']
    elif doc.location == 'HN - MALUR':
        recipients = ['rakesh.babu@khanalfoods.com','shivakumar@khanalfoods.com','shubham@khanalfoods.com']
    elif doc.location == 'E-COM':
        recipients = ['darshan@khanalfoods.com','shivakumar@khanalfoods.com','shubham@khanalfoods.com']
    elif doc.location == 'ATP':
        recipients = ['darshan@khanalfoods.com','shivakumar@khanalfoods.com','shubham@khanalfoods.com']
    else:
        recipients = ['darshan@khanalfoods.com','shivakumar@khanalfoods.com','shubham@khanalfoods.com']
    
    email_args={
            "recipients":recipients,
            "message":rendered_message,
            "subject":'Gate Pass Received :'+doc.name + " in " + str_created_date,    
                    }
    frappe.enqueue(method=frappe.sendmail,queue='short',timeout=300, **email_args)
    

# Generate a new document name using the custom Naming Series
# new_document_name = get_custom_naming_series()
# print(new_document_name)

# bench --site dev.localhost execute khanal_tech_integrations.utils.purchase.posting_sap.get_custom_naming_series
