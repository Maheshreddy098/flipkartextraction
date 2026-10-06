import requests
import json
import frappe
from frappe.utils import add_to_date, now, get_datetime, now_datetime
import pandas as pd
from datetime import datetime, timedelta
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
import numpy as np

from khanal_tech_integrations.utils.Report.Ar_invoice import GetBatchDetails

csv_filename = '/Users/shahilkhan/Desktop/WorkSpace/MTR/'

headersList = {
                    "Accept": "*/*",
                    "User-Agent": "Khanal Tech",
                    "Content-Type": "application/json",
                    "Prefer": "odata.maxpagesize=900",
                }
payload = ''



# bench --site dev.localhost execute  khanal_tech_integrations.utils.Report.GetSalesEmployee.ExportEmployeeList

# csv_filename = '/Users/shahilkhan/Desktop/WorkSpace/'


@frappe.whitelist()
def ExportEmployeeList():
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url + "BusinessPartners?$select=CardCode,CardName,SalesPersonCode,Currency,CardForeignName&$filter=GroupCode eq 105 and SalesPersonCode ne null and SalesPersonCode ne -1"

    # print(reqUrl,'modified_Url')
    response = session.request("GET", reqUrl, headers=headersList, verify=False)
    # print(response,'response')
    Bp_list = dict(response.json())
    # print(Bp_list,'Bp_list')
    
    all_data = []
    
    while Bp_list.get('odata.nextLink', None):
        all_data.extend(update_Bp(Bp_list))
        # print(Bp_list['odata.nextLink'])
        next_url = doc_settings.sap_b1_url + Bp_list['odata.nextLink']
        response = session.request("GET", next_url, headers=headersList, verify=False)
        Bp_list = dict(response.json())

    all_data.extend(update_Bp(Bp_list))
    
    df = pd.DataFrame(all_data)


    return df




def update_Bp(bp_data):
    # print(bp_data,'bp_data')
    temp_list = []

    if bp_data.get('value'):
        for Single_BP in bp_data['value']:
            SingleSalesperson = Get_SalesPerson(Single_BP.get('SalesPersonCode'))
            CardCode = Single_BP.get('CardCode')
            CardName = Single_BP.get('CardName')
            SalesPersonCode = Single_BP.get('SalesPersonCode')
            Currency= Single_BP.get('Currency')
            SalesEmployeeName = SingleSalesperson.get('SalesEmployeeName')
            Email = SingleSalesperson.get('Email')
            CardForeignName = Single_BP.get('CardForeignName')
            data = {
                'BP Code': CardCode,
                'CardName': CardName,
                'SalesPersonCode': SalesPersonCode,
                'SalesEmployeeName': SalesEmployeeName,
                'Email': Email,
                'Currency':Currency,
                'CardForeignName':CardForeignName
           
            }

            temp_list.append(data)
                   
              
    else:
        print("No 'value' key found or it is empty")

    return temp_list


# bench --site dev.localhost execute  khanal_tech_integrations.utils.Report.GetSalesEmployee.EcomEmployeeList

@frappe.whitelist()
def EcomEmployeeList():
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url + "BusinessPartners?$select=CardCode,SalesPersonCode,CardName,Currency,CardForeignName&$filter=GroupCode eq 103"

    # print(reqUrl,'modified_Url')
    response = session.request("GET", reqUrl, headers=headersList, verify=False)
    # print(response,'response')
    Bp_list = dict(response.json())
    # print(Bp_list,'Bp_list')
    
    all_data = []
    
    while Bp_list.get('odata.nextLink', None):
        all_data.extend(update_Bp(Bp_list))
        # print(Bp_list['odata.nextLink'])
        next_url = doc_settings.sap_b1_url + Bp_list['odata.nextLink']
        response = session.request("GET", next_url, headers=headersList, verify=False)
        Bp_list = dict(response.json())

    all_data.extend(update_Bp(Bp_list))
    
    # df = pd.DataFrame(all_data)

    # df = df.replace("", np.nan)  # Replace empty strings with NaN
    # df = df.fillna("NA")  # Replace NaN values with "NA"

    # if not df.empty:
    #     print(df, 'df')
    # else:
    #     print("The DataFrame is empty")

    return all_data









def Get_SalesPerson(SalesPersonCode):
    SAPsession =  AuthenticateSAPB1()
    doc_settings    = frappe.get_doc('SAP Settings')
    salesPersonUrl = doc_settings.sap_b1_url+"SalesPersons({Code})"
    modfified_Url = salesPersonUrl.format(Code=SalesPersonCode)   
    response        = SAPsession.request("GET", modfified_Url,   headers=headersList,verify=False)
    Single_Dict  = dict(response.json())
    return Single_Dict