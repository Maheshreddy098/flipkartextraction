import requests
import json
import frappe
from frappe.utils import add_to_date, now, get_datetime, now_datetime
import re
from datetime import datetime,date

from khanal_tech_integrations.utils.sap import AuthenticateSAPB1

from khanal_tech_integrations.utils.Finance.AgeingReport import currencyInIndiaFormat
import locale
import re


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


# utils/logistics/SaleOrderReport.py

#! bench --site alpha.localhost  execute  --args "{ '24450' }" khanal_tech_integrations.utils.Sales.SaleOrderReport.SingleSalesOrder

@frappe.whitelist()
def SingleSalesOrder(DocEntry):
    SalesSO = SingleSO(DocEntry)
    CogsTotal = 0
    
    for line in SalesSO.get('DocumentLines', []):
        # print(line.get('LineNum'), line.get('ItemCode'))
        batchPrice = Get_BatchPrice(line.get('ItemCode'))
        # batchPrice=''
        if batchPrice:
            TotalPrice = line.get('Quantity') * batchPrice
            # print(batchPrice,line.get('Quantity'),line.get('Quantity')*batchPrice ,'\n\n')
            CogsTotal += TotalPrice
        else:
            print('batchPrice not found',line.get('ItemCode'),DocEntry,'Docentry')
            getBOM=SingleBOM(line.get('ItemCode'))
            # print(getBOM,'getBOM')
            if isinstance(getBOM, (int, float)):
            # if getBOM:
                # print('Type of ', type(line.get('Quantity')),'Typeof Quantity')
                # print('Type of ', type(getBOM),'Typeof batchPrice')
                TotalPrice = line.get('Quantity') * getBOM
                CogsTotal += TotalPrice
            else:
                # CogsTotal = 'Cogs Cannot be Estimated because it has never been Produced'
                CogsTotal=getBOM

                # print('Cogs Cannot be Estimated ')


    DocTotal = SalesSO.get('DocTotal')

    PNL_value = None
    PNL_percentage = None

    if isinstance(CogsTotal, (int, float)):
        PNL_value = DocTotal - CogsTotal
        PNL_percentage = (DocTotal - CogsTotal) / DocTotal * 100

        print(DocTotal, 'DocTotal')
        print(CogsTotal, 'Final Cogs')
        print(PNL_value, 'PNL_value')
        print(PNL_percentage, 'PNL_percentage')
    else:
        print(CogsTotal)  # Printing the error message in CogsTotal

    return {
        'CogsTotal': currencyInIndiaFormat(CogsTotal) if isinstance(CogsTotal, (int, float)) else CogsTotal,
        'DocTotal': currencyInIndiaFormat(DocTotal),
        'PNL_value': currencyInIndiaFormat(PNL_value) if PNL_value is not None else None,
        'PNL_percentage': round(PNL_percentage, 2) if PNL_percentage is not None else None
    }
    # return {'CogsTotal':CogsTotal,'DocTotal':DocTotal,'PNL_value':PNL_value,'PNL_percentage':PNL_percentage}




def SingleSO(SO_DocEntry):
    SAPsession =  AuthenticateSAPB1()
    doc_settings    = frappe.get_doc('SAP Settings')
    invoice_Url = doc_settings.sap_b1_url+"Orders({DocEntry})"
    modfified_Url = invoice_Url.format(DocEntry=SO_DocEntry)   
    response        = SAPsession.request("GET", modfified_Url,   headers=headersList,verify=False)
    Single_Dict  = dict(response.json())
    return Single_Dict




def SingleBOM(ItemCode):
    SAPsession =  AuthenticateSAPB1()
    doc_settings    = frappe.get_doc('SAP Settings')
    invoice_Url = doc_settings.sap_b1_url+"ProductTrees('{ItemCode}')"
    modfified_Url = invoice_Url.format(ItemCode=ItemCode)   
    # print(modfified_Url,'modfified_Url')

    response        = SAPsession.request("GET", modfified_Url,   headers=headersList,verify=False)
    sumOfBatch=0
    if response.status_code == 200:
        Single_Dict  = dict(response.json())
        # print(Single_Dict,'Single_Dict')
        ProductTreeLines=Single_Dict.get('ProductTreeLines', [])

        if ProductTreeLines:
            for line in ProductTreeLines:
                print(line.get('ItemCode'),'In BOM')
                batchPrice = Get_BatchPrice(line.get('ItemCode'))
                sumOfBatch +=batchPrice
                # return batchPrice
    else:
        sumOfBatch='BOM not created, so COGS cannot be estimated'
       


    # print(sumOfBatch,'sumOfBatch')
    return sumOfBatch
        # return ''

    # return Single_Dict



def Get_BatchPrice(ItemCode):
    SAPsession = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    invoice_Url = doc_settings.sap_b1_url + "SQLQueries('PriceList_API')/List?ItemCode='{ItemCode}'"
    modified_Url = invoice_Url.format(ItemCode=ItemCode)
    response = SAPsession.request("GET", modified_Url, headers=headersList, verify=False)
    single_dict = dict(response.json())
    
    # List to store SingleList items
    single_list = single_dict.get('value', [])
    if single_list:

    
        # Convert CreateDate to datetime and sort in descending order
        for item in single_list:
            item['CreateDate'] = datetime.strptime(item['CreateDate'], '%Y%m%d')
        
        sorted_list = sorted(single_list, key=lambda x: x['CreateDate'], reverse=True)
        
        # Find the first item with CostTotal not equal to 0.0 and calculate UnitPrice
        for item in sorted_list:
            if item['CostTotal'] != 0.0:
                unit_price = item['CostTotal'] / item['Quantity']
                print(f"ItemCode: {item['ItemCode']}, CreateDate: {item['CreateDate']}, UnitPrice: {unit_price}")
                return unit_price
            
            if all(item['CostTotal'] == 0.0 for item in sorted_list):
                print("All items have CostTotal of 0.0. No valid UnitPrice can be calculated.")
                return None

    else:

        # If no valid item is found
        print("No valid item found with CostTotal not equal to 0.0")
        return ''