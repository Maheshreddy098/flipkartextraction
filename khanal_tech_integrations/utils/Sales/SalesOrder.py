import requests
import json
import frappe
from frappe.utils import add_to_date, now, get_datetime, now_datetime
import pandas as pd
from datetime import datetime, timedelta
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
from khanal_tech_integrations.utils.logistics.alertList import SeriesName

payload=''


headersList = {
        "Accept": "*/*",
        "User-Agent": "Khanal Tech",
        "Content-Type": "application/json" ,
         "Prefer": "odata.maxpagesize=300",
    }


@frappe.whitelist()
def Bulk_Updation():
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    # item_master = sap.get_item_master()
    reqUrl = doc_settings.sap_b1_url+ "Orders" 
    response = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
    Orders_list = dict(response.json())
    while Orders_list.get('odata.nextLink', None):
        update_salesOrder(Orders_list)
        print (Orders_list['odata.nextLink'])
        next_url = doc_settings.sap_b1_url+Orders_list['odata.nextLink']
        response = session.request("GET", next_url, data=payload, headers=headersList, verify=False)
        Orders_list = dict(response.json())
        # update_salesOrder(item_master)

    update_salesOrder(Orders_list)
    # df_all.to_csv(Bulk_Data, index=False)

def update_salesOrder(Orders_data):
    
    # if Orders_data.get('value'):
    #     for Single_Order in Orders_data['value']:
            
    for i in range(len(Orders_data['value'])):
        DocEntry = Orders_data['value'][i]['DocEntry']
        # print (DocEntry)
        if frappe.db.exists("SAP Sales Order", DocEntry):
            doc = frappe.get_doc("SAP Sales Order",DocEntry)
            new_doc = False
        else:
            doc = frappe.new_doc("SAP Sales Order")
            new_doc = True

        doc.docentry            = Orders_data['value'][i]['DocEntry']
        doc.docnum              = Orders_data['value'][i]['DocNum']
        doc.customer_code       = Orders_data['value'][i]['CardCode']
        doc.customer_name       = Orders_data['value'][i]['CardName']
        doc.created_date        = Orders_data['value'][i]['DocDate']
        doc.sales_person_code   = Orders_data['value'][i]['SalesPersonCode']
        doc.cancellation_status = Orders_data['value'][i]['CancelStatus']
        doc.ref_number          = Orders_data['value'][i]['NumAtCard']
        doc.currency            = Orders_data['value'][i]['DocCurrency'] 
        doc.series_no           = Orders_data['value'][i]['Series'] 
        if Orders_data['value'][i]['DocCurrency'] == "INR":
            doc.doc_total           = Orders_data['value'][i]['DocTotal']
        else:
            doc.doc_total           = Orders_data['value'][i]['DocTotalFc']
        
        Single_whse             = None
        whse_list               = []
        for LineDetails in Orders_data['value'][i]['DocumentLines']:
        # for Single_line in Single_order['DocumentLines']:
            whse_list.append(LineDetails['WarehouseCode'])
        whse_set                = set(whse_list)
        if len(whse_set) == 1:
            # Single_whse         = whse_set.pop()
            doc.lineitem_from_warehouse = whse_set.pop()

        # print(SeriesName[Orders_data['value'][i]['Series']],'Series')
        series_key = str(Orders_data['value'][i]['Series'])
        # print(series_key,'series_key')

        if series_key in SeriesName:
            # print(SeriesName[series_key], 'Series')
            doc.series_name = SeriesName[series_key]
        else:
            # print(f"Series key {series_key} not found in SeriesName.")
            doc.series_name = ""

        salesperson = frappe.db.get_list('SAP Salesperson', filters={'salesperson_code': Orders_data['value'][i]['SalesPersonCode']}, fields=['salesperson_name','email'])
        for sale_person in salesperson:
            doc.sales_person_email   = sale_person['email']
            # doc.sales_person_email   = 'shahil@khanalfoods.com'
            doc.sales_person_name    = sale_person['salesperson_name']
        

        session = AuthenticateSAPB1()
        doc_settings = frappe.get_doc('SAP Settings')
        cardUrl      = doc_settings.sap_b1_url+"BusinessPartners('{cardCode}')"
        Modified_cardUrl = cardUrl.format(cardCode=Orders_data['value'][i]['CardCode'])
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
                if SingleItem['InternalCode'] == int(Orders_data['value'][i]['ContactPersonCode']):
                    doc.contact_person_code    = SingleItem['InternalCode']
                    doc.contact_person_name    = SingleItem['Name']
                    # doc.contact_person_email  = 'shahilkhanarimbra@gmail.com'
                    doc.contact_person_email   = SingleItem['E_Mail']
                else:
                    pass



        if new_doc:
            doc.save()
            # print(doc,'doc Saved')
        else:
            doc.save()
            # doc.submit()
            # print(doc,'doc Updated')

    frappe.db.commit()




@frappe.whitelist()
def delete():
    x = 'SAP Sales Order'
    print(len(frappe.get_list(x)))
    frappe.db.commit() 
    for documentt in frappe.get_list(x):
        documentt = frappe.get_doc( x , documentt.name)
        documentt.delete()



