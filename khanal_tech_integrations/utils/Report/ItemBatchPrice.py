# import requests
# import json
# import frappe
# from frappe.utils import add_to_date, now, get_datetime, now_datetime
# import pandas as pd
# from datetime import datetime, timedelta
# from khanal_tech_integrations.utils.sap import AuthenticateSAPB1


# csv_filename = '/Users/shahilkhan/Desktop/WorkSpace/MTR/'

headersList = {
                    "Accept": "*/*",
                    "User-Agent": "Khanal Tech",
                    "Content-Type": "application/json",
                    # "Prefer": "odata.maxpagesize=1000",
                }
# payload = ''



# # bench --site dev.localhost execute  khanal_tech_integrations.utils.Report.ItemBatchPrice.GetbatchPrice

csv_filename = '/Users/shahilkhan/Desktop/WorkSpace/Export/'


# @frappe.whitelist()
# def GetbatchPrice():
#     session = AuthenticateSAPB1()
#     doc_settings = frappe.get_doc('SAP Settings')

#     reqUrl = doc_settings.sap_b1_url + "SQLQueries('ItemBatchPrice')/List"

#     response = session.request("GET", reqUrl, headers=headersList, verify=False)
#     print(response,'response')
#     itemList = dict(response.json())
#     print(itemList,'itemList')
    
#     all_data = []
    
    
#     while itemList.get('odata.nextLink', None):
#         all_data.extend(update_batchList(itemList))
#         print(itemList['odata.nextLink'])
#         next_url = doc_settings.sap_b1_url + itemList['odata.nextLink']
#         response = session.request("GET", next_url, headers=headersList, verify=False)
#         itemList = dict(response.json())

#     all_data.extend(update_batchList(itemList))
    
#     df = pd.DataFrame(all_data)



    
#     df.to_excel(f"{csv_filename}_BatchPrice Part 1.xlsx", index=False)
#     return 'File Saved'






# def update_batchList(itemList):
#     temp_list = []

#     if itemList.get('value'):
#         for SingleList in itemList['value']:
#             ItemCode = SingleList.get('ItemCode')
#             BatchNumber = SingleList.get('DistNumber')
#             CostTotal = SingleList.get('CostTotal')
#             Quantity = SingleList.get('Quantity')
            
#             if Quantity is not None and CostTotal is not None:
#                 try:
#                     quantity_float = float(Quantity)
#                     cost_total_float = float(CostTotal)
#                     if quantity_float != 0:
#                         UnitPrice = cost_total_float / quantity_float
#                     else:
#                         UnitPrice = None  # Or set to 0 or another value
#                 except ValueError:
#                     UnitPrice = None  # Handle cases where conversion to float fails
#             else:
#                 UnitPrice = None

#             data = {
#                 'ItemCode': ItemCode,
#                 'BatchNumber': BatchNumber,
#                 'CostTotal': CostTotal,
#                 'Quantity': Quantity,
#                 'UnitPrice': UnitPrice,
#             }

#             temp_list.append(data)
              
#     else:
#         print("No 'value' key found or it is empty")

#     return temp_list


import requests
import json
import frappe
from frappe.utils import add_to_date, now, get_datetime, now_datetime
import pandas as pd
from datetime import datetime, timedelta
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
import urllib3

from requests.exceptions import RequestException
import time

# @frappe.whitelist()
# def GetbatchPrice():
#     session = AuthenticateSAPB1()
#     doc_settings = frappe.get_doc('SAP Settings')

#     reqUrl = doc_settings.sap_b1_url + "SQLQueries('ItemBatchPrice')/List"

   

#     def make_request(url):
#         for attempt in range(5):  # Retry up to 5 times
            
#             try:
#                 response = session.request("GET", url, headers=headersList, verify=False)
#                 response.raise_for_status()  # Raise an HTTPError for bad responses
#                 # print(response.text,'\n\n')
#                 return response
#             except (RequestException, urllib3.exceptions.ProtocolError) as e:
#                 print(f"Attempt {attempt + 1} failed: {e} for url: {url}")
#                 time.sleep(10)  # Increased wait time to 10 seconds before retrying
#         return None

#     response = make_request(reqUrl)
#     if response is None:
#         print("Failed to retrieve data after multiple attempts")
#         return "Failed to retrieve data"

#     itemList = dict(response.json())
#     all_data = []
    
#     while itemList.get('odata.nextLink', None):
#         all_data.extend(update_batchList(itemList))
#         print(itemList['odata.nextLink'])
#         next_url = doc_settings.sap_b1_url + itemList['odata.nextLink']
#         response = make_request(next_url)
#         if response is None:
#             print("Failed to retrieve data after multiple attempts")
#             return "Failed to retrieve data"
#         itemList = dict(response.json())

#     all_data.extend(update_batchList(itemList))
    
#     df = pd.DataFrame(all_data)

#     csv_filename = "BatchPrice"  # You should define csv_filename somewhere in your code
#     df.to_excel(f"{csv_filename}_BatchPrice Part 1.xlsx", index=False)
#     return 'File Saved'
def GetbatchPrice():
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url + "SQLQueries('ItemBatchPrice')/List"

    def make_request(url):
        for attempt in range(5):  # Retry up to 5 times
            try:
                response = session.request("GET", url, headers=headersList, verify=False)
                response.raise_for_status()  # Raise an HTTPError for bad responses
                return response
            except (RequestException, urllib3.exceptions.ProtocolError) as e:
                print(f"Attempt {attempt + 1} failed: {e} for url: {url}")
                time.sleep(10)  # Increased wait time to 10 seconds before retrying
        return None

    response = make_request(reqUrl)
    if response is None:
        print("Failed to retrieve data after multiple attempts")
        return "Failed to retrieve data"

    itemList = dict(response.json())
    all_data = []
    
    part_number = 1
    while itemList.get('odata.nextLink', None):
        all_data.extend(update_batchList(itemList))
        print(itemList['odata.nextLink'])
        next_url = doc_settings.sap_b1_url + itemList['odata.nextLink']
        response = make_request(next_url)
        if response is None:
            print("Failed to retrieve data after multiple attempts")
            return "Failed to retrieve data"
        itemList = dict(response.json())

        # Save part if data gets large
        if len(all_data) > 10000:  # Example threshold, adjust as needed
            df = pd.DataFrame(all_data)
            # df.to_excel(f"{csv_filename}_BatchPrice Part {part_number}.xlsx", index=False)
            part_number += 1
            all_data = []  # Clear data for the next batch

    # Save the remaining data
    if all_data:
        df = pd.DataFrame(all_data)
        # df.to_excel(f"{csv_filename}_BatchPrice Part {part_number}.xlsx", index=False)
        
    return 'File Saved'

def update_batchList(itemList):
    temp_list = []

    if itemList.get('value'):
        for SingleList in itemList['value']:
            ItemCode = SingleList.get('ItemCode')
            BatchNumber = SingleList.get('DistNumber')
            CostTotal = SingleList.get('CostTotal')
            Quantity = SingleList.get('Quantity')
            
            # if Quantity is not None and CostTotal is not None:
            #     try:
            #         quantity_float = float(Quantity)
            #         cost_total_float = float(CostTotal)
            #         if quantity_float != 0:
            #             UnitPrice = cost_total_float / quantity_float
            #         else:
            #             UnitPrice = None  # Or set to 0 or another value
            #     except ValueError:
            #         UnitPrice = None  # Handle cases where conversion to float fails
            # else:
            #     UnitPrice = None

            data = {
                'ItemCode': ItemCode,
                'BatchNumber': BatchNumber,
                'CostTotal': CostTotal,
                'Quantity': Quantity,
                # 'UnitPrice': UnitPrice,
            }

            temp_list.append(data)
              
    else:
        print("No 'value' key found or it is empty")

    return temp_list
