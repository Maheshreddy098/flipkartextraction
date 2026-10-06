from xml.dom.expatbuilder import parseString
import requests
import json
import frappe
from frappe.utils import add_to_date, now, get_datetime, now_datetime
import re
from datetime import datetime,date
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
import locale
import re
from khanal_tech_integrations.utils.logistics.alertList import SeriesName,List_Item_HSN

# import frappe.utils.print_format
# frappe.utils.print_format.download_pdf
# from frappe.utils.print_format import download_pdf
# from frappe.translate import print_language
# from frappe.www.printview import validate_print_permission
# "khanal_tech_integrations.utils.logistics.ar_invoice.update",

headersList = {
                "Accept": "*/*",
                "User-Agent": "Khanal Tech",
                "Content-Type": "application/json" 
            }



@frappe.whitelist()
def fetch_ar_invoice():
    """
    Update Invoices from SAP to Khanal Tech Integrations 
    """
    session = AuthenticateSAPB1()
    payload = ''

    #CHECK THE LAST MAX UPDATED INV. TRANSFERS
    start_page = 10
    try:
        last_page_doc = frappe.get_last_doc('SAP AR Invoice Detail Log')
        start_page    = last_page_doc.last_skip
    except:
        start_page    = 1
    
    #for i in range(int(start_page),2):
    i = int(start_page)
    if i and i>1:
        i = i - 1

    # INITIALIZATION
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl      = doc_settings.sap_b1_url+"Invoices?$filter=GSTTransactionType eq 'gsttrantyp_GSTTaxInvoice'&$skip=" + str(20*i) #Orders
    session     = AuthenticateSAPB1()
    response    = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
        
    ARinvoices  = dict(response.json())
    next_page   = ARinvoices.get("odata.nextLink",None)
    # print(ARinvoices['value'])
    #while True:
    # empty_list = []
    while next_page is not None:
    
        try:
            if ARinvoices['value'] is not None:
                print ('Going into',i)
                for Single_Invoice in ARinvoices['value']:
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


                    
                    # doc.email_status               = 'Not Sent'
                    # print( Single_Invoice['CancelStatus'] )
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
                        # Update_waybill_and_filePath(Single_Invoice['DocEntry'])
                        print(doc,'saved')
                    except frappe.DuplicateEntryError:
                        print(doc,'duplicate')
                        pass
                    
                    
                i += 1
                #increment the counter
            elif ARinvoices['value'] is None:
                break
            
        except Exception as e:
            #break
            print (e)
        reqUrl       = doc_settings.sap_b1_url+"Invoices?$filter=GSTTransactionType eq 'gsttrantyp_GSTTaxInvoice'&$skip=" + str(20*i)
        session      = AuthenticateSAPB1()
        response     = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
            
        ARinvoices   = dict(response.json())
        next_page    = ARinvoices.get("odata.nextLink",None)
    
    #Update the last page
    doc1           = frappe.new_doc('SAP AR Invoice Detail Log')
    doc1.last_skip = i
    doc1.save()

    frappe.msgprint(msg ='Data Inserted successfully',title ='Success')
    # if empty_list:
        #run  the function for mail for each items inside the list

    return None



def WareHouseUpdate(DocEntry):
    doc = frappe.get_doc("SAP AR Invoice Detail", DocEntry)
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url+"WarehouseLocations(" + str(doc.ware_housecode) + ")"
    payload = ""
    response = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
    warehouse = dict(response.json())
    doc.ware_name               = warehouse['Name'] 
    doc.ware_street             = warehouse['Street'] 
    doc.ware_block              = warehouse['Block'] 
    doc.ware_zipcode            = warehouse['ZipCode'] 
    doc.ware_city               = warehouse['City'] 
    doc.ware_gstin              = warehouse['GSTIN'] 
    doc.save()
    frappe.db.commit()
    return None





def get_single_lineitem(DocEntry):
    
    # print(DocEntry,'in get_single_lineitem')
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url+"Invoices(" + str(DocEntry) + ")"
    payload = ""
    response = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
    line_items = dict(response.json())

    LineItems = line_items['DocumentLines']
    
    LineItem_list = []
    for LineItem in LineItems:
        if List_Item_HSN.get(LineItem['ItemCode']) is not None:
            LineItem_list.append({"itemcode":LineItem['ItemCode'],"itemdescription":LineItem['ItemDescription'],'hsn_code':List_Item_HSN[LineItem['ItemCode']],
            "quantity":LineItem['Quantity'],"uom":LineItem['MeasureUnit'],"mrp": LineItem['UnitPrice'],"rate": LineItem['Price'],
            "taxtotal": LineItem["LineTotal"],"tax": LineItem["TaxPercentagePerRow"],"scheme_discount": LineItem["U_AddDisc"],"gross_total": LineItem["GrossTotal"]})#
        else:
            LineItem_list.append({"itemcode":LineItem['ItemCode'],"itemdescription":LineItem['ItemDescription'],'hsn_code':'None',
            "quantity":LineItem['Quantity'],"uom":LineItem['MeasureUnit'],"mrp": LineItem['UnitPrice'],"rate": LineItem['Price'],
            "taxtotal": LineItem["LineTotal"],"tax": LineItem["TaxPercentagePerRow"],"scheme_discount": LineItem["U_AddDisc"],"gross_total": LineItem["GrossTotal"]})#

    # print(LineItem_list)
    return LineItem_list

@frappe.whitelist()
def updating_email(DocEntry,ContactPerson,SalesPerson):
    doc = frappe.get_doc("SAP AR Invoice Detail", DocEntry)
    if SeriesName.get(doc.series_no) is not None:
        doc.series_name         = SeriesName[doc.series_no]
    else:
        doc.series_name         = ""
    salesperson = frappe.db.get_list('SAP Salesperson', filters={'salesperson_code': SalesPerson}, fields=['salesperson_name','email'])
    # print(salesperson,'salesperson')
    # print(salesperson.email,'email')
    for sale_person in salesperson:
        doc.salesperson_email   = sale_person['email']
        doc.salesperson_name    = sale_person['salesperson_name']
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
    # print('doc.place_of_supply',doc.place_of_supply)
    stateUrl      = doc_settings.sap_b1_url+"States?$filter=startswith(Country,'IN') and startswith(Code,'{statecode}')"
    Modified_stateUrl = stateUrl.format(statecode=doc.place_of_supply)
    stateresponce    = session.request("GET", Modified_stateUrl, data=payload,  headers=headersList,verify=False)
    Statename  = dict(stateresponce.json())
    if Statename['value'] is not None:
        for Single_State in Statename['value']:
            doc.state_of_supply =Single_State['Name']


    # Details  = dict(cardresponse.json())
    LineItems = Details['ContactEmployees']
    if Details.get('ContactEmployees') is not None:
        for SingleItem in LineItems:
            # print(SingleItem['InternalCode'])
            if ContactPerson is not None and ContactPerson != 'null':
                if SingleItem['InternalCode'] == int(ContactPerson):
                    doc.contact_name = SingleItem['Name']
                    doc.contact_phone = SingleItem['MobilePhone']
                    doc.contact_email = SingleItem['E_Mail']
                
                
            else:
                pass
    doc.save()
    frappe.db.commit() #
    # print(doc,'saved')
    # if doc.doc_currency == 'INR':
    #     sent_mail(DocEntry)
    #     pass
    # else:
    #     print(doc.doc_currency)
    #     pass
    return None

# Tax Invoice generated for your order
@frappe.whitelist()
def sent_mail(DocEntry):
    # recipients,msg,title,attachments=None
    ################################################ add the attachment
    # ,attachments=None
    doc = frappe.get_doc("SAP AR Invoice Detail", DocEntry)
    currency = frappe.get_doc('Currency', doc.doc_currency)
    # print(currency.symbol)
    sales_personemail=doc.salesperson_email
    nonsplitemail=doc.contact_email
    contact_email=[]
    if nonsplitemail is not None:
        if ';' in nonsplitemail:
            contact_email = nonsplitemail.split(';')
        else:
            contact_email = [nonsplitemail]
    recipients=[]
    if not sales_personemail and not contact_email:
        # print('both empty')
        pass  # do nothing
    elif not sales_personemail:
        recipients=[contact_email]
    elif not contact_email:
        recipients=[sales_personemail]
    else:
        recipients=[sales_personemail,contact_email]

    if not recipients:
        pass  # do nothing
        doc.email_status = 'Email Not Sent'
        doc.save()
        frappe.db.commit()
    else:
        new_date_str = datetime.strftime(doc.last_due_date, '%b %d %Y')
        value = float(doc.bill_total) 
        formatted_value = '{:,.2f}'.format(value)
        # print(recipients[0],'1st')
        for sentemailto in recipients:
            # print(sentemailto,'sentemailto')
            if sentemailto == sales_personemail:
                customer_or_salesperson = doc.salesperson_name
            else:
                customer_or_salesperson = "Customer"


            msg = """
           
                <div style="margin:0 auto;background:#f2f5f7">
                    <table 
                        style="margin:auto;background:#f2f5f7 url() top center no-repeat;padding:35px 0 20px;width:750px"        
                        cellpadding="0" cellspacing="0" border="0">

                        <tbody>
                        <tr>
                            <td align="center" valign="middle" style="margin:0;padding:0">
                            <table width="750" border="0" cellpadding="0" cellspacing="0" style="width:750px;margin:auto">
                        <tbody>
                        <tr>
                            <td align="center" valign="middle" style="padding:0 0 24px;margin:0"><a href="" target="_blank"
                                data-saferedirecturl="#">
                                <img src="https://khanaltech.com/files/khanalfoods_logo.jpg" width="60" height="60" alt="" class="CToWUd"
                                data-bit="iit">
                            </a></td>
                        </tr>
                        </tbody>
                    </table>
                    <table width="750" border="0" cellpadding="0" cellspacing="0"
                        style="width:750px;margin:auto;background:url(https://ci4.googleusercontent.com/proxy/Ic7NVCs2Hj_DUbcW_VKD5QvRjPm2GWgt48QKJi4p_q_TwwHtaNtOUd4PVcqphtxPXNMQDPBpwtKKV8j66a1_vVo9p_9KaGNuw6eYmf36zKEmWv6w00ZEoep59VD08NHGsqUhTzzGjkXpAs91f5FZLAggHNgiejaDrJ8=s0-d-e1-ft) top center no-repeat;padding:0 0 21px">
                        <tbody>
                        <tr>
                            <td align="left" valign="top" style="padding:40px 54px 0;margin:0" colspan="2">
                            <p style="font-size:17px;color:#666666;font-family:sans-serif;margin:0">Dear
                                {customer_or_salesperson},</p>
                            <p>We would like to inform you that an invoice has been generated for a total amount of <br> <b>{currency}
                                {amount}/-. </b> The payment due date is <b>{due_date} </b> .</p> <br>
                            </td>
                        </tr>
                        <tr></tr>
                        <tr>
                            <td align="center" valign="top" style="padding:0 54px 0;margin:0 0;width:50%;border-right:3px solid #dedede">
                            <p style="font-size:16px;color:#666666;font-family:sans-serif;font-weight:600;margin:0 0 12px">
                                Customer Name</p>
                            <p style="margin:0;font-size:18px;font-family:sans-serif;color:#000000;font-weight:bold">
                                {name}</p>
                            </td>
                            <td align="center" valign="top" style="padding:0 54px 0;margin:0;width:50%">
                            <p style="font-size:16px;color:#666666;font-family:sans-serif;font-weight:600;margin:0 0 12px">
                                Order Status</p>
                            <p style="margin:0 0 0;font-size:20px;font-family:sans-serif;color:#000000;font-weight:bold">
                                Invoice Created</p>
                            </td>
                        </tr>
                        </tbody>
                    </table>
                    </td>
                    </tr>
                 <tr>
                        <td colspan="2" align="center" valign="top" style="padding:0;margin:0">
                        <img
                            src="https://khanaltech.com/files/Frame_2_invoice.png"
                            alt="" style="margin:44px 0 46px" class="CToWUd" data-bit="iit">
                        </td>
                    </tr>
                    </tbody>
                    </table>
                    <table border="0" cellpadding="0" cellspacing="0" width="750" style="width:750px;margin:auto">
                        <tbody>
                        <tr>
                            <td align="center" valign="top" style="padding:0;margin:0;color:#666;font-size:13px;font-family:sans-serif">
                            <p style="font-size: 12px; color: #777;font-style: italic;">Note: This is a system generated email. Please do
                                not reply to this email.</p><br>
                            Copyright © 2023 khanalFoods Pvt. Ltd. | All rights reserved.
                            </td>
                        </tr>
                    
                        </tbody>
                    </table>

                    </div>
                        """.format(name=doc.customer_name,invoicenum=doc.docnum,amount=formatted_value, due_date=new_date_str,customer_or_salesperson=customer_or_salesperson ,currency=currency.symbol)
                ######################################## pdf adding 
            # attachments=[frappe.attach_print('SAP AR Invoice Detail',doc.docentry,file_name=doc.docentry )]
            # recipients=[sales_personemail,contact_email]
            name=doc.series_name
            docnum=doc.docnum
            email_args = {
                    "recipients": sentemailto,
                    "message": msg,
                    "subject": 'Tax Invoice generated for your order with Invoice No.'+ name +"/"+docnum,
                }
            # if attachments:email_args['attachments']=attachments
            frappe.enqueue(method=frappe.sendmail, queue='short', timeout=300, **email_args)
            doc.email_status = 'Sent'
            doc.save()
            frappe.db.commit()
            print('Sending email to:', sentemailto)

    return None
    



 
  



@frappe.whitelist()
def delete():
    x = 'SAP AR Invoice Detail'
    print(len(frappe.get_list(x)))
    for documentt in frappe.get_list(x):
        documentt = frappe.get_doc( x , documentt.name)
        documentt.delete()
        print(documentt)










## Payment Reminder For  Invoice
@frappe.whitelist()
def sent_notification():
    Today = frappe.utils.nowdate()
    print(Today)
    afterDay = add_to_date(Today,days=+10)
    print(afterDay)
    ar_invoicelist=frappe.db.get_list('SAP AR Invoice Detail',filters=[['last_due_date', 'between', [Today, afterDay]],{'doc_currency':'INR'}], pluck="docentry")
    print(len(ar_invoicelist))
    for single_doc in ar_invoicelist:
        # context.no_cache=True
        print(single_doc)
        session = AuthenticateSAPB1()
        doc_settings = frappe.get_doc('SAP Settings')
        reqUrl = doc_settings.sap_b1_url+"Invoices({docentry})?$filter=DocumentStatus eq 'bost_Open'"
        Modified_Url = reqUrl.format(docentry=single_doc)
        payload = ""
        response = session.request("GET", Modified_Url, data=payload,  headers=headersList,verify=False)
        status_code = response.status_code
        # print(status_code)
        if status_code == 200:
            doc = frappe.get_doc('SAP AR Invoice Detail',single_doc,cache=False)
            # print(doc)
            nowdate_obj = datetime.strptime(Today, '%Y-%m-%d').date()
            difference = (doc.last_due_date - nowdate_obj).days
            if difference == 0:
                difference="Last"
            else:
                difference=difference
            sales_personemail=doc.salesperson_email
            contact_email=[]
            if doc.contact_email is not None:
                nonsplitemail = doc.contact_email
                if ';' in nonsplitemail:
                    contact_email = nonsplitemail.split(';')
                else:
                    contact_email = [nonsplitemail]
            recipients = []

            if not sales_personemail and not contact_email:
                # do nothing
                pass
            elif not sales_personemail:
                recipients = contact_email
            elif not contact_email:
                recipients = [sales_personemail]
            else:
                recipients = [sales_personemail] + contact_email

            recipients = [email for email in recipients if email]

            if not recipients:
                pass  # do nothing
            else:
                # print(recipients)
                new_date_str = datetime.strftime(doc.last_due_date, '%b %d %Y')
                # print(new_date_str)
                value = float(doc.bill_total) 
                formatted_value = '{:,.2f}'.format(value)
                msg = """
                <div style="margin:0 auto;background:#f2f5f7">
                    <table style="margin:auto;background:#f2f5f7 url() top center no-repeat;padding:35px 0 20px;width:750px"
                        cellpadding="0" cellspacing="0" border="0">

                        <tbody>
                            <tr>
                                <td align="center" valign="middle" style="margin:0;padding:0">
                                    <table width="750" border="0" cellpadding="0" cellspacing="0" style="width:750px;margin:auto">
                                        <tbody>
                                            <tr>
                                                <td align="center" valign="middle" style="padding:0 0 24px;margin:0"><a href=""
                                                        target="_blank" data-saferedirecturl="#">
                                                        <img src="https://khanaltech.com/files/khanalfoods_logo.jpg" width="60"
                                                            height="60" alt="" class="CToWUd" data-bit="iit">
                                                    </a></td>
                                            </tr>
                                        </tbody>
                                    </table>
                                    <table width="750" border="0" cellpadding="0" cellspacing="0"
                                        style="width:750px;margin:auto;background:url(https://ci4.googleusercontent.com/proxy/Ic7NVCs2Hj_DUbcW_VKD5QvRjPm2GWgt48QKJi4p_q_TwwHtaNtOUd4PVcqphtxPXNMQDPBpwtKKV8j66a1_vVo9p_9KaGNuw6eYmf36zKEmWv6w00ZEoep59VD08NHGsqUhTzzGjkXpAs91f5FZLAggHNgiejaDrJ8=s0-d-e1-ft) top center no-repeat;padding:0 0 21px">
                                        <tbody>
                                            <tr>
                                                <td align="left" valign="top" style="padding:40px 54px 0;margin:0" colspan="2">
                                                    <p style="font-size:17px;color:#666666;font-family:sans-serif;margin:0">Dear
                                                        Customer,</p>
                                                    <p>We would like to remind you about the payment that is due on {last_due_date}. </p>
                                                    <p>As of today, the payment is <b> {difference} </b> days due for Payment, and the
                                                        outstanding amount is <b>Rs. {amount}/- </b> We kindly request that you settle
                                                        the payment as soon as possible</p>
                                                    <p>If you have already made the payment, please disregard this message, and we
                                                        apologize for any inconvenience.</p><br>
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
                                                        Payment Reminder</p>
                                                </td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </td>
                            </tr>
                            <tr>
                            </tr>
                            <tr>
                                <td colspan="2" align="center" valign="top" style="padding:0 0px;margin:0">
                                    <table width="750" border="0" cellpadding="0" cellspacing="0"
                                        style="width:726px;margin:auto;padding:0 0 34px;background-color: #89b2b9;">
                                        <tbody>
                                            <tr>
                                                <td colspan="2" align="center"
                                                    style="padding:0;margin:0;background:#f3fdff;width:726px">
                                                    <p style="font-size:13px;color:#00abc5;font-family:sans-serif;margin:20px 0 32px">In
                                                        case of queries
                                                        or more feedback, do reach out to your Point of Contacts below.</p>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td align="left" valign="top"
                                                    style="padding:0 54px 0;margin:0;width:50%;">
                                                    <p style="margin:0;font-size:16px;color:white;font-family:sans-serif">
                                                        {salesperson_name}</p>
                                                    


                                                    <p style="color:white;font-family:sans-serif;font-size:14px"><img
                                                            src="https://ci4.googleusercontent.com/proxy/tjf-UpIQnqR3hn4aaT5B1SGYq-RXxF0Htb6EsMEbmnO2Nz-7RT6ejcjj3cFl26GrXakI64l_W1cOhTO_nuyjTqUl5iRROcvkqUGNtE6zOevlWtXxX4jOh4S6yTw0EdSvwcDAAXGqL3zYlceHCcmTftqLY_OFRRb4ZZ4=s0-d-e1-ft"
                                                            alt="" style="vertical-align:middle;margin:0 10px 0 0" class="CToWUd"
                                                            data-bit="iit"><a href="mailto:{sales_personemail}"
                                                            target="_blank">{sales_personemail}</a></p>


                                                    <p style="color:white;font-family:sans-serif;font-size:14px;margin:0 0 0"><img
                                                            src="https://ci3.googleusercontent.com/proxy/YAYUsm_lCNlujSLRPunkqLhy1ZaER-PSInCVcgbUt4m9J1HcdMm5t4EKBH-osYn0JK52pvBF29Cg80sKhckTd2AyssrjT-alyRVuLnPXnAPeW5Fe77quU3XflIwcKoQiaR57hI_Y-sdLRXVHNWn8gxjRAlDezLPg8YM=s0-d-e1-ft"
                                                            alt="" style="vertical-align:middle;margin:0 10px 0 0" class="CToWUd"
                                                            data-bit="iit">NA</p>
                                                </td>
                                
                                            </tr>
                                        </tbody>
                                    </table>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                    <table border="0" cellpadding="0" cellspacing="0" width="750" style="width:750px;margin:auto">
                        <tbody>
                            <tr>
                                <td align="center" valign="top"
                                    style="padding:0;margin:0;color:#666;font-size:13px;font-family:sans-serif">
                                    <p style="font-size: 12px; color: #777;font-style: italic;">Note: This is a system generated email.
                                        Please do
                                        not reply to this email.</p><br>
                                    Copyright © 2023 khanalFoods Pvt. Ltd. | All rights reserved.
                                </td>
                            </tr>

                        </tbody>
                    </table>

                </div>
                        """.format(name=doc.customer_name,invoicenum=doc.docnum,amount=formatted_value, last_due_date=new_date_str ,difference=difference ,salesperson_name=doc.salesperson_name,sales_personemail=doc.salesperson_email)
                    
                name=doc.series_name
                docnum=doc.docnum
                
                recipients += ['ar@khanalfoods.com']


                # sentemailto=recipients.append('ar@khanalfoods.com')
                
                email_args = {
                        "recipients": recipients,
                        "message": msg,
                        "subject": 'Payment Reminder For  Invoice No.'+ name +"/"+docnum,
                    }
                # if attachments:email_args['attachments']=attachments
                frappe.enqueue(method=frappe.sendmail, queue='short', timeout=300, **email_args)
                # print(frappe.enqueue(method=frappe.sendmail, queue='short', timeout=300, **email_args))

                print('Sending email to:', recipients)
                    # sentemailto=[]
                    # sales_personemail=[]
                    # contact_email=[]
                    # recipients =[]
                    # print('sentemailto', sentemailto)
        else:
            pass
    return


## Payment Overdue Reminder For  Invoice

@frappe.whitelist()
def exceed_duedate():
    Today = frappe.utils.nowdate()
    FromDate = add_to_date(Today,days=-1)
    Hundredaysback = add_to_date(Today,days=-100)
    exceed_list = frappe.db.get_list('SAP AR Invoice Detail',filters=[['last_due_date', 'between', [Hundredaysback, FromDate]],{'doc_currency':'INR'}], pluck="docentry")

    print(len(exceed_list),'exceed_list')
    # print(len(ar_invoicelist),'ar_invoicelist')
    for single_doc in exceed_list:
        print(single_doc)
        session = AuthenticateSAPB1()
        doc_settings = frappe.get_doc('SAP Settings')
        reqUrl = doc_settings.sap_b1_url+"Invoices({docentry})?$filter=DocumentStatus eq 'bost_Open'"
        Modified_Url = reqUrl.format(docentry=single_doc)
        payload = ""
        response = session.request("GET", Modified_Url, data=payload,  headers=headersList,verify=False)
        status_code = response.status_code
        # print(status_code)
        if status_code == 200:
            doc = frappe.get_doc('SAP AR Invoice Detail',single_doc,cache=False)
            currency = frappe.get_doc('Currency', doc.doc_currency)
            # print(doc)
            nowdate_obj = datetime.strptime(Today, '%Y-%m-%d').date()
            difference = (nowdate_obj - doc.last_due_date).days
            # print(difference,'difference')
            # print(difference%5,'difference by 5')
            if difference%5 == 0:
                sales_personemail=doc.salesperson_email
                contact_email=[]
                if doc.contact_email is not None:
                    nonsplitemail = doc.contact_email
                    if ';' in nonsplitemail:
                        contact_email = nonsplitemail.split(';')
                    else:
                        contact_email = [nonsplitemail]
                recipients=[]
                if not sales_personemail and not contact_email:
                    # print('both empty')
                    pass  # do nothing
                elif not sales_personemail:
                    recipients=[contact_email,'ar@khanalfoods.com']
                elif not contact_email:
                    recipients=[sales_personemail,'ar@khanalfoods.com']
                else:
                    recipients=[sales_personemail,contact_email,'ar@khanalfoods.com']


                # print(recipients)
                if not recipients:
                    pass  # do nothing
                else:
                    new_date_str = datetime.strftime(doc.last_due_date, '%b %d %Y')
                    # print(new_date_str)
                    value = float(doc.bill_total) 
                    formatted_value = '{:,.2f}'.format(value)
                    # print(recipients[0],'1st')
                    for sentemailto in recipients:
                        # print(sentemailto,'sentemailto')
                        if sentemailto == sales_personemail:
                            customer_or_salesperson = doc.salesperson_name
                        else:
                            customer_or_salesperson = "Customer"

                        msg = """
                                <div style="margin:0 auto;background:#f2f5f7">
                                    <table style="margin:auto;background:#f2f5f7 url() top center no-repeat;padding:35px 0 20px;width:750px"
                                        cellpadding="0" cellspacing="0" border="0">
                                        <tbody>
                                            <tr>
                                                <td align="center" valign="middle" style="margin:0;padding:0">
                                                    <table width="750" border="0" cellpadding="0" cellspacing="0" style="width:750px;margin:auto">
                                                        <tbody>
                                                            <tr>
                                                                <td align="center" valign="middle" style="padding:0 0 24px;margin:0"><a href=""
                                                                        target="_blank" data-saferedirecturl="#">
                                                                        <img src="https://khanaltech.com/files/khanalfoods_logo.jpg" width="60"
                                                                            height="60" alt="" class="CToWUd" data-bit="iit">
                                                                    </a></td>
                                                            </tr>
                                                        </tbody>
                                                    </table>
                                                    <table width="750" border="0" cellpadding="0" cellspacing="0"
                                                        style="width:750px;margin:auto;background:url(https://ci4.googleusercontent.com/proxy/Ic7NVCs2Hj_DUbcW_VKD5QvRjPm2GWgt48QKJi4p_q_TwwHtaNtOUd4PVcqphtxPXNMQDPBpwtKKV8j66a1_vVo9p_9KaGNuw6eYmf36zKEmWv6w00ZEoep59VD08NHGsqUhTzzGjkXpAs91f5FZLAggHNgiejaDrJ8=s0-d-e1-ft) top center no-repeat;padding:0 0 21px">
                                                        <tbody>
                                                            <tr>
                                                                <td align="left" valign="top" style="padding:40px 54px 0;margin:0" colspan="2">
                                                                    <p style="font-size:17px;color:#666666;font-family:sans-serif;margin:0">Dear
                                                                        {customer_or_salesperson},</p>
                                                                        <p>We would like to remind you that payment of <b>{currency} {amount}/-.</b> is overdue. The outstanding amount  is overdue by <b>{difference}</b> days.</p>
                                                                        <p>Please disregard this message if you have already made the payment.</p>
                                                                    
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
                                                                        style="margin:0 0 0;font-size:18px;font-family:sans-serif;color:#000000;font-weight:bold">
                                                                        Payment Overdue Reminder</p>
                                                                </td>
                                                            </tr>
                                                        </tbody>
                                                    </table>
                                                </td>
                                            </tr>
                                            <tr>
                                            </tr>
                                            <tr>
                                                <td colspan="2" align="center" valign="top" style="padding:0 0px;margin:0">
                                                    <table width="750" border="0" cellpadding="0" cellspacing="0"
                                                        style="width:726px;margin:auto;padding:0 0 34px;background-color: #89b2b9;">
                                                        <tbody>
                                                            <tr>
                                                                <td colspan="2" align="center"
                                                                    style="padding:0;margin:0;background:#f3fdff;width:726px">
                                                                    <p style="font-size:13px;color:#00abc5;font-family:sans-serif;margin:20px 0 32px">In
                                                                        case of queries
                                                                        or more feedback, do reach out to your Point of Contacts below.</p>
                                                                </td>
                                                            </tr>
                                                            <tr>
                                                                <td align="left" valign="top"
                                                                    style="padding:0 54px 0;margin:0;width:50%;">
                                                                    <p style="margin:0;font-size:16px;color:white;font-family:sans-serif">
                                                                        {salesperson_name}</p>
                                                                    


                                                                    <p style="color:white;font-family:sans-serif;font-size:14px"><img
                                                                            src="https://ci4.googleusercontent.com/proxy/tjf-UpIQnqR3hn4aaT5B1SGYq-RXxF0Htb6EsMEbmnO2Nz-7RT6ejcjj3cFl26GrXakI64l_W1cOhTO_nuyjTqUl5iRROcvkqUGNtE6zOevlWtXxX4jOh4S6yTw0EdSvwcDAAXGqL3zYlceHCcmTftqLY_OFRRb4ZZ4=s0-d-e1-ft"
                                                                            alt="" style="vertical-align:middle;margin:0 10px 0 0" class="CToWUd"
                                                                            data-bit="iit"><a href="mailto:{sales_personemail}"
                                                                            target="_blank">{sales_personemail}</a></p>


                                                                    <p style="color:white;font-family:sans-serif;font-size:14px;margin:0 0 0"><img
                                                                            src="https://ci3.googleusercontent.com/proxy/YAYUsm_lCNlujSLRPunkqLhy1ZaER-PSInCVcgbUt4m9J1HcdMm5t4EKBH-osYn0JK52pvBF29Cg80sKhckTd2AyssrjT-alyRVuLnPXnAPeW5Fe77quU3XflIwcKoQiaR57hI_Y-sdLRXVHNWn8gxjRAlDezLPg8YM=s0-d-e1-ft"
                                                                            alt="" style="vertical-align:middle;margin:0 10px 0 0" class="CToWUd"
                                                                            data-bit="iit">NA</p>
                                                                </td>
                                                
                                                            </tr>
                                                        </tbody>
                                                    </table>
                                                </td>
                                            </tr>
                                        </tbody>
                                    </table>
                                    <table border="0" cellpadding="0" cellspacing="0" width="750" style="width:750px;margin:auto">
                                        <tbody>
                                            <tr>
                                                <td align="center" valign="top"
                                                    style="padding:0;margin:0;color:#666;font-size:13px;font-family:sans-serif">
                                                    <p style="font-size: 12px; color:#777;font-style: italic;">Note: This is a system generated email.
                                                        Please do
                                                        not reply to this email.</p><br>
                                                    Copyright © 2023 khanalFoods Pvt. Ltd. | All rights reserved.
                                                </td>
                                            </tr>

                                        </tbody>
                                    </table>
                                </div>
                            """.format(name=doc.customer_name,amount=formatted_value,customer_or_salesperson=customer_or_salesperson ,difference=difference ,salesperson_name=doc.salesperson_name,sales_personemail=doc.salesperson_email,currency=currency.symbol)
                            
                        seriesname=doc.series_name
                        docnum=doc.docnum
                        email_args = {
                                "recipients": sentemailto,
                                "message": msg,
                                "subject": 'Payment Overdue Reminder For  Invoice No.'+ seriesname +"/"+docnum,
                            }
                        # if attachments:email_args['attachments']=attachments
                        # frappe.enqueue(method=frappe.sendmail, queue='short', timeout=300, **email_args)

                        # print('Sending email to:', sentemailto)
            else:
                pass
    return
    



@frappe.whitelist()
def customer_email_update(deafult_email=""):
    created_datefilter=frappe.db.get_list('SAP AR Invoice Detail',filters={'contact_email': ['=', deafult_email] }, pluck="docentry")
    print(len(created_datefilter))
    for Single_Ar in created_datefilter:
        print(Single_Ar,'Single_Ar')
        doc = frappe.get_doc("SAP AR Invoice Detail", Single_Ar)
        # print(doc,'doc')
        session = AuthenticateSAPB1()
        doc_settings = frappe.get_doc('SAP Settings')
        reqUrl = doc_settings.sap_b1_url+"Invoices({docentry})"
        Modified_Url = reqUrl.format(docentry=Single_Ar)
        payload = ""
        response = session.request("GET", Modified_Url, data=payload,  headers=headersList,verify=False)
        SalesCode = dict(response.json())
        # print(SalesCode['ContactPersonCode'],'Internalcode')
        cardUrl      = doc_settings.sap_b1_url+"BusinessPartners('{cardCode}')"
        Modified_cardUrl = cardUrl.format(cardCode=doc.customer_code)
        cardresponse    = session.request("GET", Modified_cardUrl, data=payload,  headers=headersList,verify=False)
        Details  = dict(cardresponse.json())
        LineItems = Details['ContactEmployees']
        if Details.get('ContactEmployees') is not None:
            for SingleItem in LineItems:
                # print(SingleItem['InternalCode'])
                if SingleItem['InternalCode'] == SalesCode['ContactPersonCode']:
                    print(SingleItem['E_Mail'],'email')
                    doc.contact_name = SingleItem['Name']
                    doc.contact_phone = SingleItem['MobilePhone']
                    # doc.contact_email = 'shahilkhanarimbra@gmail.com'
                    doc.contact_email = SingleItem['E_Mail']
        try:
            doc.save()
            frappe.db.commit()
            print(doc,'saved')
        except frappe.DuplicateEntryError:
            print(doc,'duplicate')
            pass
        
    return None

# kumar.dilip@zomato.com




# EmailList=['shahil@khanalfoods.con','shahilkhan.7139@gmail.com']
# bench --site dev.localhost execute  --args "{ 'vyshali@khanalfoods.com' }"  khanal_tech_integrations.utils.logistics.alert_invoice.Change_SalespersonEmail
@frappe.whitelist()
def Change_SalespersonEmail(EmailList):
    list_of_EmailList = EmailList.split(',')
    Needed_toChangeList=frappe.db.get_list('SAP AR Invoice Detail',filters={'salesperson_email': ['in',list_of_EmailList],}, pluck="docentry")
    print(len(Needed_toChangeList))
    for docentry in Needed_toChangeList:
        doc = frappe.get_doc('SAP AR Invoice Detail',docentry)
        doc.salesperson_email   = ''
        doc.save()
        frappe.db.commit()
        print(doc,'saved')
        pass




# bench --site dev.localhost execute khanal_tech_integrations.utils.logistics.alert_invoice.fetch_ar_invoice
# bench --site dev.localhost execute khanal_tech_integrations.utils.logistics.ar_invoice.update
# bench --site dev.localhost execute khanal_tech_integrations.utils.logistics.alert_invoice.update_email
# bench --site dev.localhost execute khanal_tech_integrations.utils.logistics.alert_invoice.exceed_duedate
# bench --site dev.localhost execute khanal_tech_integrations.utils.logistics.alert_invoice.sent_alerts
# bench --site dev.localhost execute khanal_tech_integrations.utils.logistics.alert_invoice.change_wrong_email



# bench --site beta.khanaltech.com execute khanal_tech_integrations.utils.logistics.alert_invoice.fetch_ar_invoice
# bench --site khanaltech.com execute khanal_tech_integrations.utils.logistics.alert_invoice.exceed_duedate

# bench --site khanaltech.com execute khanal_tech_integrations.utils.logistics.alert_invoice.change_wrong_email

# bench --site khanaltech.com execute khanal_tech_integrations.utils.logistics.alert_invoice.customer_anil_update



# bench --site dev.localhost execute khanal_tech_integrations.utils.logistics.alert_invoice.customer_email_update
# bench --site dev.localhost execute  --args "{ 'anurodh.srivastav@bigbasket.com' }"  khanal_tech_integrations.utils.logistics.alert_invoice.customer_email_update
