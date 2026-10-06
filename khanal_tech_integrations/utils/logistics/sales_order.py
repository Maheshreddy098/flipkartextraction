from xml.dom.expatbuilder import parseString
import requests
import json
import frappe
from frappe.utils import add_to_date, now, get_datetime, now_datetime
import re
import os
from jinja2 import Template
from datetime import datetime,date
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
from khanal_tech_integrations.utils.logistics.alertList import SeriesName
from khanal_tech_integrations.utils.Sales.SaleOrderReport import SingleSalesOrder


# khanal_tech_integrations.utils.logistics.sales_order.delete
headersList = {
                "Accept": "*/*",
                "User-Agent": "Khanal Tech",
                "Content-Type": "application/json" 
            }

@frappe.whitelist()
def update():
    """
    Update Sales Orders from SAP to Khanal Tech Integrations 
    """
    session = AuthenticateSAPB1()
    payload = ''

    #CHECK THE LAST MAX UPDATED INV. TRANSFERS
    start_page = 0
    try:
        last_page_doc = frappe.get_last_doc('SAP Sales Order Log')
        start_page = last_page_doc.last_skip
    except:
        start_page = 1

    #for i in range(int(start_page),2):
    i = int(start_page)
    if i and i>1:
        i = i - 1

    # INITIALIZATION
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url+"Orders?$skip=" + str(20*i) #Orders
    session = AuthenticateSAPB1()
    response = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
        
    Orders = dict(response.json())
    # print(Orders)
    next_page = Orders.get("odata.nextLink",None)

    #while True:
    while next_page is not None:
        try:
            if Orders['value'] is not None:
                for Single_order in Orders['value']:

                    doc                     = frappe.new_doc('SAP Sales Order')
                    doc.docentry            = Single_order['DocEntry']
                    doc.docnum              = Single_order['DocNum']
                    doc.customer_code       = Single_order['CardCode']
                    doc.customer_name       = Single_order['CardName']
                    doc.created_date        = Single_order['DocDate']
                    doc.sales_person_code   = Single_order['SalesPersonCode']
                    doc.cancellation_status = Single_order['CancelStatus']
                    doc.ref_number          = Single_order['NumAtCard']
                    doc.currency            = Single_order['DocCurrency'] 
                    doc.series_no           = Single_order['Series'] 
                    if Single_order['DocCurrency'] == "INR":
                        doc.doc_total           = Single_order['DocTotal']
                    else:
                        doc.doc_total           = Single_order['DocTotalFc']
                    
                    Single_whse             = None
                    whse_list               = []
                    for Single_line in Single_order['DocumentLines']:
                        whse_list.append(Single_line['WarehouseCode'])
                    whse_set                = set(whse_list)
                    if len(whse_set) == 1:
                        # Single_whse         = whse_set.pop()
                        doc.lineitem_from_warehouse = whse_set.pop()
                        # print('PZ')
                    

                    try:
                        #try saving, skip if already exist
                        doc.save()
                        frappe.db.commit() #
                        update_deatils(Single_order['DocEntry'],Single_order['ContactPersonCode'])
                        print(doc,'Saved')
                    except frappe.DuplicateEntryError:
                        print(doc,'Duplicate')
                        pass
                i += 1

                #increment the counter
            elif Orders['value'] is None:
                break
            
        except Exception as e:
            #break
            print (e)
        reqUrl    = doc_settings.sap_b1_url+"Orders?$skip=" + str(20*i)
        session   = AuthenticateSAPB1()
        response  = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
        Orders    = dict(response.json())
        next_page = Orders.get("odata.nextLink",None)
    
    #Update the last page
    doc1           = frappe.new_doc('SAP Sales Order Log')
    doc1.last_skip = i
    doc1.save()

    frappe.msgprint(msg='Data Inserted successfully',title='Success')

@frappe.whitelist()
def delete():
    x = 'SAP Sales Order'
    print(len(frappe.get_list(x)))
    doc = frappe.get_last_doc('SAP Sales Order Log')
    doc.last_skip = 0
    doc.save()
    frappe.db.commit() 
    for documentt in frappe.get_list(x):
        documentt = frappe.get_doc( x , documentt.name)
        documentt.delete()

PZ_orders = frappe.db.get_list('SAP Sales Order' , 
                        fields=['created_date', 'docnum', 'docentry','customer_code','customer_name'],
                        filters={'lineitem_from_warehouse': ['like', '%PZ%']
                                })
def get_PZ_so():

    """
    Pull all the Saales order with PZ present in SAP 
    """
    session             =   AuthenticateSAPB1()
    empty_payload       =   ''
    doc_settings = frappe.get_doc('SAP Settings')
    Count_url           =   doc_settings.sap_b1_url+"Orders?$apply=filter(startswith(CardCode,'C'))/aggregate(DocEntry with countdistinct as CountDistinct)"
    # INITIALIZATION
    session                         =   AuthenticateSAPB1()
    Vendor_count_response           = session.request("GET", Count_url, data=empty_payload,  headers=headersList,verify=False)
    Vendor_count                    = dict(Vendor_count_response.json())
    
    if Vendor_count.get('value') is not None:
        The_AP_Count                = int(Vendor_count['value'][0]['CountDistinct'])
        The_AP_Count                = The_AP_Count//20 + 1
        print("The SO count is :",The_AP_Count)
        for i in range(140,The_AP_Count):
            # print(i)
            session                 = AuthenticateSAPB1()
            reqUrl                  = doc_settings.sap_b1_url+"Orders?$skip=" + str(20*i)
            response                = session.request("GET", reqUrl, data=empty_payload,  headers=headersList,verify=False)
            twenty_response         = response.json()['value'] #List full of dictionaries
            for SO in twenty_response:
                Lineitem1                 = SO['DocumentLines'][0]
                if Lineitem1['WarehouseCode'][:2] == 'PZ':
                    print("This one is prozo :",SO['DocNum'])
                    PATCH_prozo(    DocEntry        =   SO['DocEntry'],
                                    referenceID     =   Lineitem1['WarehouseCode'])
 
    return "Hogaya Bhai sahab"

def PATCH_prozo(DocEntry,referenceID): #
    session             = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url                 = doc_settings.sap_b1_url+"Orders({order_code})"
    reqUrl              = Url.format(order_code=DocEntry)
    headersList         =   {
                            "Accept": "*/*",
                            "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                            "Content-Type": "application/json" 
                            }
    payload = json.dumps({ "U_SubConPONo": referenceID})

    response = session.request("PATCH", reqUrl, headers=headersList, data=payload,verify=False)
    #response = session.request("GET", reqUrl, data = empty_payload,  headers=headersList,verify=False)
    print(response)

    return None




@frappe.whitelist()
def update_deatils(DocEntry,ContactPersonCode):
    doc = frappe.get_doc("SAP Sales Order", DocEntry)
    if SeriesName.get(doc.series_no) is not None:
        doc.series_name         = SeriesName[doc.series_no]
    else:
        doc.series_name         = ""   
    salesperson = frappe.db.get_list('SAP Salesperson', filters={'salesperson_code': doc.sales_person_code}, fields=['salesperson_name','email'])
    for sale_person in salesperson:
        doc.sales_person_email   = sale_person['email']
        # doc.sales_person_email   = 'shahil@khanalfoods.com'
        doc.sales_person_name    = sale_person['salesperson_name']
    session = AuthenticateSAPB1()
    payload = ''    
    doc_settings = frappe.get_doc('SAP Settings')
    cardUrl      = doc_settings.sap_b1_url+"BusinessPartners('{cardCode}')"
    Modified_cardUrl = cardUrl.format(cardCode=doc.customer_code)
    # print(Modified_cardUrl)
    headersList = {
            "Accept": "*/*",
            "Content-Type": "application/json" 
        }
    cardresponse    = session.request("GET", Modified_cardUrl, data=payload,  headers=headersList,verify=False)
    Details  = dict(cardresponse.json())
    LineItems = Details['ContactEmployees']
    if Details.get('ContactEmployees') is not None:
        for SingleItem in LineItems:
            if SingleItem['InternalCode'] == int(ContactPersonCode):
                doc.contact_person_code    = SingleItem['InternalCode']
                doc.contact_person_name    = SingleItem['Name']
                # doc.contact_person_email  = 'shahilkhanarimbra@gmail.com'
                doc.contact_person_email   = SingleItem['E_Mail']
            else:
                pass
    doc.save()
    frappe.db.commit() #
    # sent_mail(DocEntry)
    # if doc.currency == 'INR':
    sent_mail(DocEntry)
    # else:
    #     print(doc.currency)
    pass
    return None

# bench --site dev.localhost execute  --args "{ '24330' }"  khanal_tech_integrations.utils.logistics.sales_order.sent_mail

# 24443
# 24450
# 24454
# 24458
# 24330

# Order Recevied
@frappe.whitelist()
def sent_mail(DocEntry):
    doc = frappe.get_doc("SAP Sales Order", DocEntry)
    nonsplitemail=doc.contact_person_email
    contact_email=[]
    if nonsplitemail  is not None:
        if ';' in nonsplitemail:
            contact_email = nonsplitemail.split(';')
        else:
            contact_email = [nonsplitemail]

    print('\n',contact_email)
    if contact_email:
        if doc.currency == 'INR':
            SentEmailToCustomer=EmailToCustomer(doc,contact_email)
    

    if doc.sales_person_email:
        Saleemail=SalesPersonEmail(doc)

 
            


def SalesPersonEmail(doc):
    new_date_str = datetime.strftime(doc.created_date, '%b %d %Y')
    OrderDeatils=SingleSalesOrder(doc.name)
    EmailTemplate_Doc = frappe.get_doc('Email Template', 'Sales Order')
    html_content=EmailTemplate_Doc.response_html.format(name=doc.customer_name,po_number=doc.ref_number, doc_date=new_date_str,customer_or_salesperson=doc.sales_person_name,Revenue=OrderDeatils['DocTotal'],COGs=OrderDeatils['CogsTotal'],PNL=OrderDeatils['PNL_value'],PNL_percentage=OrderDeatils['PNL_percentage'])
    current_directory = os.path.dirname(__file__)
    # print(SaleEmployeeEmail,'\n\n')
    # file_path = os.path.abspath(os.path.join(current_directory, 'EmailTemplate.html'))
    file_path = os.path.abspath(os.path.join(current_directory, '..','Report','Emailtemplate.html'))
    # print(file_path)
    
    with open(file_path, 'r') as f:
        template_str = f.read()


    # MessageContent=Tabletructure
    template = Template(template_str)
    rendered_message = template.render(
        message   =html_content
    )
    po_number=doc.ref_number
    internalPerson_email_list = []

    for SingleEmail in EmailTemplate_Doc.custom_internal_email_recipients:
        # Append each email address to the list
        internalPerson_email_list.append(SingleEmail.employee_email)

    recipients_list = list(set(internalPerson_email_list))
    # recipients_list = list(set(internalPerson_email_list))
    recipients_list = list(set(internalPerson_email_list)) + [doc.sales_person_email] 

    # doc.sales_person_email
    external_poc_list = EmailTemplate_Doc.custom_external_poc
    external_poc_list = external_poc_list.split(',') if external_poc_list else []


    cc_list = list(set(external_poc_list))
    # sentemailto
    email_args = {
            "recipients": recipients_list,
            "message": rendered_message,
            "cc":cc_list,
            "subject": EmailTemplate_Doc.subject +  f' {doc.series_name}/{doc.docnum}',
        }
    # if attachments:email_args['attachments']=attachments
    frappe.enqueue(method=frappe.sendmail, queue='short', timeout=300, **email_args)
    doc.email_status = 'Sent'
    doc.save()
    frappe.db.commit()



def EmailToCustomer(doc,contact_email):
    print(contact_email,'contact_email')
    new_date_str = datetime.strftime(doc.created_date, '%b %d %Y')
    msg = """
                    <div style="margin:0 auto;background:#f2f5f7">
                <table style="margin:auto;background:#f2f5f7  top center no-repeat;padding:35px 0 20px;width:750px"cellpadding="0" cellspacing="0" border="0">
                    <tbody>
                        <tr>
                            <td align="center" valign="middle" style="margin:0;padding:0">
                                <table width="750" border="0" cellpadding="0" cellspacing="0" style="width:750px;margin:auto">
                                    <tbody>
                                        <tr>
                                            <td align="center" valign="middle" style="padding:0 0 24px;margin:0"><a href=""
                                                    target="_blank"
                                                    data-saferedirecturl="https://www.google.com/url?q=https://www.teamcomputers.com&amp;source=gmail&amp;ust=1679554739298000&amp;usg=AOvVaw2tssAqCXSbwiDOCsO24Gng">
                                                    <img src="https://khanaltech.com/files/khanalfoods_logo.jpg" width="60" height="60" alt="" class="CToWUd" data-bit="iit">
                                                </a></td>
                                        </tr>
                                    </tbody>
                                </table>
                                <table width="750" border="0" cellpadding="0" cellspacing="0"
                                    style="width:750px;margin:auto;background:url(https://ci4.googleusercontent.com/proxy/Ic7NVCs2Hj_DUbcW_VKD5QvRjPm2GWgt48QKJi4p_q_TwwHtaNtOUd4PVcqphtxPXNMQDPBpwtKKV8j66a1_vVo9p_9KaGNuw6eYmf36zKEmWv6w00ZEoep59VD08NHGsqUhTzzGjkXpAs91f5FZLAggHNgiejaDrJ8=s0-d-e1-ft#https://www.teamcomputers.com/repositry/edm/customer-order-tracking/order-received/image/content-bg.png) top center no-repeat;padding:0 0 21px">
                                    <tbody>
                                        <tr>
                                            <td align="left" valign="top" style="padding:40px 54px 0;margin:0" colspan="2">
                                                <p style="font-size:17px;color:#666666;font-family:sans-serif;margin:0">Dear
                                                    Customer,</p>
                                                <p>
                                                    <p>   Your order against PO Number: <b> PO-{po_number}</b> has been received on <b> {doc_date} </b> </p>
                                            </td>
                                        </tr>
                                        <tr></tr>
                                        <tr>
                                            <td align="center" valign="top"
                                                style="padding:0 54px 0;margin:0 0;width:50%;border-right:3px solid #dedede">
                                                <p
                                                    style="font-size:16px;color:#666666;font-family:sans-serif;font-weight:600;margin:0 0 12px">
                                                    Customer Name</p>
                                                <p
                                                    style="margin:0;font-size:18px;font-family:sans-serif;color:#000000;font-weight:bold">
                                                    {name}</p>
                                            </td>
                                            <td align="center" valign="top" style="padding:0 54px 0;margin:0;width:50%">
                                                <p
                                                    style="font-size:16px;color:#666666;font-family:sans-serif;font-weight:600;margin:0 0 12px">
                                                    Order Status</p>
                                                <p
                                                    style="margin:0 0 0;font-size:20px;font-family:sans-serif;color:#000000;font-weight:bold">
                                                    Order Received</p>
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </td>
                        </tr>
                        <tr>
                            <td colspan="2" align="center" valign="top" style="padding:0;margin:0">
                                <img src="https://khanaltech.com/files/Frame_1_order.png"
                                    alt="" style="margin:44px 0 46px" class="CToWUd" data-bit="iit">
                            </td>
                        </tr>


                    </tbody>
                </table>
                <table border="0" cellpadding="0" cellspacing="0" width="750" style="width:750px;margin:auto">
                    <tbody>
                        <tr>
                            <td align="center" valign="top"
                                style="padding:0;margin:0;color:#666;font-size:13px;font-family:sans-serif">
                                <p style="font-size: 12px; color: #777;font-style: italic;">Note: This is a system generated email. Please do not reply to this email.</p><br>
                                Copyright © 2022 khanal Foods Pvt. Ltd. | All rights reserved.</td>
                        </tr>
                    </tbody>
                </table>

            </div> 
            
            """.format(name=doc.customer_name,po_number=doc.ref_number, doc_date=new_date_str )

    email_args = {
    "recipients": contact_email,
    "message": msg,
    "subject": 'Order Received',
    }
        # if attachments:email_args['attachments']=attachments
    frappe.enqueue(method=frappe.sendmail, queue='short', timeout=300, **email_args)






@frappe.whitelist()
def manual_update(NoofDay=None):
    """
    Update Delivery Notes from SAP to Khanal Tech Integrations 
    """
    session = AuthenticateSAPB1()
    payload = ''

    Today = frappe.utils.nowdate()
    print(Today,'today')
    FilterDate = add_to_date(Today,days=-int(NoofDay))
    print(FilterDate,'FilterDate')
    ###############################
    doc_settings = frappe.get_doc('SAP Settings')
    count_url = doc_settings.sap_b1_url+"Orders?$apply=filter(DocDate ge '{FilterDate}')/aggregate(DocEntry with countdistinct as CountDistinct)"
    Modified_count_url = count_url.format(FilterDate=FilterDate)
    response      = session.request("GET", Modified_count_url, data=payload,  headers=headersList,verify=False)
    So_order_Count = dict(response.json())
    if So_order_Count['value'] is not None:
        counter = So_order_Count['value'][0]['CountDistinct']
        Total   = counter//20 + 1
        print(Total,'Total')
    ##############################
        for i in range(Total):
            # print(i,'count')
        # INITIALIZATION
            reqUrl        = doc_settings.sap_b1_url+"Orders?$filter=DocDate ge '{FilterDate}'&$skip=" 
            modfified_Url = reqUrl.format(FilterDate=FilterDate)  + str(20*i)
            session       = AuthenticateSAPB1()
            response      = session.request("GET", modfified_Url, data=payload,  headers=headersList,verify=False)
                
            So_order_List = dict(response.json())
            

            #while True:
            
                
            if So_order_List['value'] is not None:
                print ('Going into' ,i)
                for Single_order in So_order_List['value']:
                    print(Single_order['DocEntry'],'docentry')
                    print(Single_order['DocNum'],'DocNum')
                    print(Single_order['DocDate'],'Docdate')
                    doc                     = frappe.new_doc('SAP Sales Order')
                    doc.docnum              = Single_order['DocNum']
                    doc.docentry            = Single_order['DocEntry']
                    doc.customer_code       = Single_order['CardCode']
                    doc.customer_name       = Single_order['CardName']
                    doc.created_date        = Single_order['DocDate']
                    doc.sales_person_code   = Single_order['SalesPersonCode']
                    doc.cancellation_status = Single_order['CancelStatus']
                    doc.ref_number          = Single_order['NumAtCard']
                    doc.currency            = Single_order['DocCurrency'] 
                    doc.series_no           = Single_order['Series'] 
                    if Single_order['DocCurrency'] == "INR":
                        doc.doc_total           = Single_order['DocTotal']
                    else:
                        doc.doc_total           = Single_order['DocTotalFc']
                    # print(Single_order['CancelStatus'])                    
                    #doc.save()
                    Single_whse             = None
                    whse_list               = []
                    for Single_line in Single_order['DocumentLines']:
                        whse_list.append(Single_line['WarehouseCode'])
                    whse_set                = set(whse_list)
                    if len(whse_set) == 1:
                        # Single_whse         = whse_set.pop()
                        doc.lineitem_from_warehouse = whse_set.pop()
                       
                    

                    try:
                        #try saving, skip if already exist
                        doc.save()
                        temp_update_deatils(Single_order['DocEntry'],Single_order['ContactPersonCode'])
                        frappe.db.commit() #
                        print(doc,' saved')
                        
                    except frappe.DuplicateEntryError:
                        print(doc,' duplicate')
                        pass
                i += 1
                #increment the counter
            elif So_order_List['value'] is None:
                break
            
            
            reqUrl    = reqUrl.format(FilterDate=FilterDate)  + str(20*i)
            session   = AuthenticateSAPB1()
            response  = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
                
            So_order_List = dict(response.json())
        frappe.msgprint(msg ='Data Inserted successfully',title ='Success')
        return None







@frappe.whitelist()
def temp_update_deatils(DocEntry,ContactPersonCode):
    doc = frappe.get_doc("SAP Sales Order", DocEntry)
    if SeriesName.get(doc.series_no) is not None:
        doc.series_name         = SeriesName[doc.series_no]
    else:
        doc.series_name         = ""   
    salesperson = frappe.db.get_list('SAP Salesperson', filters={'salesperson_code': doc.sales_person_code}, fields=['salesperson_name','email'])
    for sale_person in salesperson:
        doc.sales_person_email   = sale_person['email']
        # doc.sales_person_email   = 'shahil@khanalfoods.com'
        doc.sales_person_name    = sale_person['salesperson_name']
    session = AuthenticateSAPB1()
    payload = ''  
    doc_settings = frappe.get_doc('SAP Settings')  
    cardUrl      = doc_settings.sap_b1_url+"BusinessPartners('{cardCode}')"
    Modified_cardUrl = cardUrl.format(cardCode=doc.customer_code)
    # print(Modified_cardUrl)
    headersList = {
            "Accept": "*/*",
            "Content-Type": "application/json" 
        }
    cardresponse    = session.request("GET", Modified_cardUrl, data=payload,  headers=headersList,verify=False)
    Details  = dict(cardresponse.json())
    LineItems = Details['ContactEmployees']
    if Details.get('ContactEmployees') is not None:
        for SingleItem in LineItems:
            if SingleItem['InternalCode'] == int(ContactPersonCode):
                doc.contact_person_code    = SingleItem['InternalCode']
                doc.contact_person_name    = SingleItem['Name']
                # doc.contact_person_email  = 'shahilkhanarimbra@gmail.com'
                doc.contact_person_email   = SingleItem['E_Mail']
            else:
                pass
    doc.save()
    frappe.db.commit() #
    print(doc,'doc')
    return None


#  bench --site dev.localhost execute  --args "{ '4' }"  khanal_tech_integrations.utils.logistics.sales_order.manual_update

# bench --site dev.localhost execute khanal_tech_integrations.utils.logistics.sales_order.update

# bench --site khanaltech.com execute  --args "{ '15' }"  khanal_tech_integrations.utils.logistics.sales_order.manual_update


# # Initialize a list to store the warehouses
# warehouses = []

# # Loop through each line in the order
# for line in order_lines:
#     # Get the warehouse code for this line
#     warehouse_code = line.get("WarehouseCode")
    
#     # If the warehouse code is not already in the list, add it
#     if warehouse_code and warehouse_code not in warehouses:
#         warehouses.append(warehouse_code)

# # Set the lineitem_from_warehouse field to a list of warehouses
# doc.lineitem_from_warehouse = []
# for warehouse in warehouses:
#     row = doc.lineitem_from_warehouse.new()
#     row.warehouse_code = warehouse




# * email tempalte
# ----------------------------------
#                   <div style="margin:0 auto;background:#f2f5f7">
#     <table
#         style="margin:auto;background:#f2f5f7 url(https://ci3.googleusercontent.com/proxy/xwND59mNeT26AkoXHN3xrnLZMbru1_7YtaodMljuyh1gVpjQPpfRxLYTM0nSvXEKPT4jBfIEZSkIacqNNv5O5D4GHYZuPGAE4VVgGeKMzcx-87SsdB03srVc8elw4wcPH1XMJ5wEsxA0d0nZEynQFTrkGvmkbA=s0-d-e1-ft) top center no-repeat;padding:35px 0 20px;width:750px"
#         cellpadding="0" cellspacing="0" border="0">
#         <tbody>
#             <tr>
#                 <td align="center" valign="middle" style="margin:0;padding:0">
#                     <table width="750" border="0" cellpadding="0" cellspacing="0" style="width:750px;margin:auto">
#                         <tbody>
#                             <tr>
#                                 <td align="center" valign="middle" style="padding:0 0 24px;margin:0"><a href=""
#                                         target="_blank"
#                                         data-saferedirecturl="https://www.google.com/url?q=https://www.teamcomputers.com&amp;source=gmail&amp;ust=1679554739298000&amp;usg=AOvVaw2tssAqCXSbwiDOCsO24Gng">
#                                         <img src="https://khanaltech.com/files/khanalfoods_logo.jpg" width="100"
#                                             height="100" alt="" class="CToWUd" data-bit="iit">
#                                     </a></td>
#                             </tr>
#                         </tbody>
#                     </table>
#                     <table width="750" border="0" cellpadding="0" cellspacing="0"
#                         style="width:750px;margin:auto;background:url(https://ci4.googleusercontent.com/proxy/Ic7NVCs2Hj_DUbcW_VKD5QvRjPm2GWgt48QKJi4p_q_TwwHtaNtOUd4PVcqphtxPXNMQDPBpwtKKV8j66a1_vVo9p_9KaGNuw6eYmf36zKEmWv6w00ZEoep59VD08NHGsqUhTzzGjkXpAs91f5FZLAggHNgiejaDrJ8=s0-d-e1-ft#https://www.teamcomputers.com/repositry/edm/customer-order-tracking/order-received/image/content-bg.png) top center no-repeat;padding:0 0 21px">
#                         <tbody>
#                             <tr>
#                                 <td align="left" valign="top" style="padding:40px 54px 0;margin:0" colspan="2">
#                                     <p style="font-size:17px;color:#666666;font-family:sans-serif;margin:0">Dear
#                                         Sir/Ma'am,</p>
#                                     <p
#                                         style="font-size:17px;color:#666666;font-family:sans-serif;margin-bottom:0;height:58px;line-height:1.4">
#                                         Your order against <span
#                                             style="margin:0;font-family:sans-serif;color:#000000;font-weight:bold">PO
#                                             Number: PO-11496</span> has been received on 18/10/2022</p>
#                                 </td>
#                             </tr>
#                             <tr></tr>
#                             <tr>
#                                 <td align="center" valign="top"
#                                     style="padding:0 54px 0;margin:0 0;width:50%;border-right:3px solid #dedede">
#                                     <p
#                                         style="font-size:16px;color:#666666;font-family:sans-serif;font-weight:600;margin:0 0 12px">
#                                         Customer Name</p>
#                                     <p
#                                         style="margin:0;font-size:20px;font-family:sans-serif;color:#000000;font-weight:bold">
#                                         KHANAL FOODS PVT LTD</p>
#                                 </td>
#                                 <td align="center" valign="top" style="padding:0 54px 0;margin:0;width:50%">
#                                     <p
#                                         style="font-size:16px;color:#666666;font-family:sans-serif;font-weight:600;margin:0 0 12px">
#                                         Order Status</p>
#                                     <p
#                                         style="margin:0 0 0;font-size:20px;font-family:sans-serif;color:#000000;font-weight:bold">
#                                         Order Received</p>
#                                 </td>
#                             </tr>
#                         </tbody>
#                     </table>
#                 </td>
#             </tr>
#             <tr>
#                 <td colspan="2" align="center" valign="top" style="padding:0;margin:0">
#                     <img src="https://ci3.googleusercontent.com/proxy/z2OUAntKgFJniNqDrl6mQAqCr_tutz5Hea7oXY5ZgwnQmi1843K5ggW4iz_otz_lRs2pDKSutiAO5_EJtn4Iz_r59GHDYxqPBjFnb0yGMRJlYe6qXucz1I2ewoPtTZUIn4OtLFbsUqShlMTwhPiMQ_gO5vXEoocl=s0-d-e1-ft"
#                         alt="" style="margin:44px 0 46px" class="CToWUd" data-bit="iit">
#                 </td>
#             </tr>


#         </tbody>
#     </table>
#     <table border="0" cellpadding="0" cellspacing="0" width="750" style="width:750px;margin:auto">
#         <tbody>
#             <tr>
#                 <td align="center" valign="top"
#                     style="padding:0;margin:0;color:#666;font-size:13px;font-family:sans-serif">Copyright © 2022 khanal
#                     Foods Pvt. Ltd. | All rights reserved.</td>
#             </tr>
#         </tbody>
#     </table>

# </div> 
