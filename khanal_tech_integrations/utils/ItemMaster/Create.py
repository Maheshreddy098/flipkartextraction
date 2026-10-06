import frappe
import json
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
import pandas as pd
import requests


headersList = {
                "Accept": "*/*",
                "User-Agent": "Khanal Tech",
                "Content-Type": "application/json" 
            }



# !bench --site khanaltech.com execute  --args "{ 'RMDC0005' }"  khanal_tech_integrations.utils.ItemMaster.Create.Create_ItemMaster
# !bench --site dev.localhost execute  --args "{ 'RMDC00019.BR' }"  khanal_tech_integrations.utils.ItemMaster.Create.Create_ItemMaster



# bench --site dev.localhost execute  --args "{ 'RMDC0029' }"  khanal_tech_integrations.utils.ItemMaster.Create.Create_ItemMaster
# Define ProcessDetails with process codes and names
# ProcessDetails = [
#     {"Process Code": "BR", "Process Name": "Brushing"},
#     {"Process Code": "CU", "Process Name": "Cutting"},
#     {"Process Code": "DR", "Process Name": "Drying"},
#     {"Process Code": "MD", "Process Name": "Metal Detection"},
#     {"Process Code": "WA", "Process Name": "Washing"}
# ]

ProcessDetails = [
    # {"Process Code": "BR", "Process Name": "Brushing"},
    # {"Process Code": "CU", "Process Name": "Cutting"},
    # {"Process Code": "DR", "Process Name": "Drying"},
    # {"Process Code": "MD", "Process Name": "Metal Detection"},
    # {"Process Code": "WA", "Process Name": "Washing"},
    # {"Process Code": "NHDR", "Process Name": "NandiHills Drying"},
    # {"Process Code": "MDR", "Process Name": "Malur Drying"},
  
]

# Function to create Item Master in SAP

#!Test bench --site dev.localhost execute khanal_tech_integrations.utils.ItemMaster.Create.GetDataFrom_ExcelForNHDR


@frappe.whitelist()
def GetDataFrom_ExcelForNHDR():
    # File_url = f"https://beta.khanaltech.com/files/{FileName}"
    # df=Get_File(File_url,'Sheet')
    df = pd.read_excel('/Users/shahilkhan/Downloads/For NHDR (1).xlsx','Sheet1')

    df.head()
    print(df)
    itemFiltered = df.loc[~df['Item No.'].str.contains('\.')]

    # for Single_itemDesc in itemFiltered['ItemName']:
    for index, row in itemFiltered.iterrows():
        print(row['Item No.'],row['ShelfLife (In Days)'],'************')
        itemcode=Create_ItemMaster(row['Item No.'],row['ShelfLife (In Days)'])
        pass


# bench --site dev.localhost execute  --args "{ 'RMDC0224' }"  khanal_tech_integrations.utils.ItemMaster.Create.Create_ItemMaster

@frappe.whitelist()
def Create_ItemMaster(ItemCode):

    print('\n\n\n',ItemCode)
    # Get details of the item
    
    for SingleProcess in ProcessDetails:
        itemDeatils=Single_ItemDetails(ItemCode)
        itemDeatils.pop('@odata.metadata', None)
        itemDeatils.pop('@odata.etag', None)

        # print(ItemPayload_payload,'ItemPayload_payload')
        itemDeatils['ItemCode'] = f"{itemDeatils['ItemCode']}.{SingleProcess['Process Code']}"
        itemDeatils['ItemName'] = f"{itemDeatils['ItemName']}.{SingleProcess['Process Name']}"
        itemDeatils['Series']   = 3 
        # itemDeatils['SWW']       =
        # itemDeatils['U_GstTax']   ="GST@18"
        # itemDeatils['U_IgstTax']    ="IGST@18"
        itemDeatils['TreeType']    ="iProductionTree"
        # "U_GstTax": "GST@12",
        # "U_IgstTax": "IGST@12",

        # Authenticate to SAP B1
        SAPsession =  AuthenticateSAPB1()
        doc_settings = frappe.get_doc('SAP Settings')
        item_url = doc_settings.sap_b1_url + "Items"

        # print('\n\n\n',itemDeatils['ItemCode'],'itemcode')
        
        # Send POST request to create item
        response = SAPsession.request("POST", item_url, data=json.dumps(itemDeatils), headers=headersList, verify=False)
        
        # Check response status
        if response.status_code == 400:
            # If error, print error message
            response_data = json.loads(response.text)
            error_value = response_data['error']['message']['value']
            print('\n\n',error_value,'\n\n')
        else:
            # If successful, print success message
            response_data = json.loads(response.text)
            # print('\n\n\n',response_data["ItemCode"],'response_data')
            ItemCode_value = response_data["ItemCode"]
            print('\n\n',ItemCode_value+' created successfully in SAP ','\n\n')
           



# Function to retrieve details of a single item from SAP

def Single_ItemDetails(ItemCode):
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl=doc_settings.sap_b1_url+"Items('{ItemCode}')"
    modfified_Url = reqUrl.format(ItemCode=ItemCode)
    session = AuthenticateSAPB1()
    itemDetails = session.request("GET", modfified_Url, headers=headersList, verify=False)
    itemDetails_json = itemDetails.json()
    # print(itemDetails_json['Series'])
    return itemDetails_json



def Single_ItemDetails_byItemName(ItemName):
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl=doc_settings.sap_b1_url+"Items?$filter=ItemName eq '{ItemName}'"
    # BatchNumberDetails?$filter=Batch eq 'BR16D24NL06'
    modfified_Url = reqUrl.format(ItemName=ItemName)
    session = AuthenticateSAPB1()
    itemDetails = session.request("GET", modfified_Url, headers=headersList, verify=False)
    itemDetails_json = itemDetails.json()
    # print(itemDetails_json['Series'])
    return itemDetails_json




# !RMDC0411


# *RMDC0353

#!Test bench --site dev.localhost execute  --args "{'RMDC0353' }"  khanal_tech_integrations.utils.ItemMaster.Create.GetDataFrom_Excel

# SAP Item File.xlsx
#?Live bench --site dev.localhost execute  --args "{'RMDC0411' }"  khanal_tech_integrations.utils.ItemMaster.Create.GetDataFrom_Excel
# 
def Get_File(url,sheetname):
    response = requests.get(url, verify=False)
    if response.status_code == 200:
        df = pd.read_excel(response.content,sheetname)
        return df
    else:
        print(f"Error: Unable to retrieve data from {url}")


# Function to create Item Master in SAP
@frappe.whitelist()
def GetDataFrom_Excel(SampleItemCode):
    # File_url = f"https://beta.khanaltech.com/files/{FileName}"
    # df=Get_File(File_url,'Sheet')
    df = pd.read_excel('/Users/shahilkhan/Downloads/New Item_SKU Code (3).xlsx','Sheet3')

    df.head()
    print(df)
    itemFiltered = df.loc[~df['ItemName'].str.contains('\.')]

    # for Single_itemDesc in itemFiltered['ItemName']:
    for index, row in itemFiltered.iterrows():
        NewItemDeatils=Single_ItemDetails(SampleItemCode)
        NewItemDeatils['ItemName'] = row['ItemName']
        NewItemDeatils['Series']   = 108,
        NewItemDeatils['SWW']       =730,
        
        SAPsession =  AuthenticateSAPB1()
        doc_settings = frappe.get_doc('SAP Settings')
        item_url = doc_settings.sap_b1_url + "Items"

        itemExist=Single_ItemDetails_byItemName(row['ItemName'])
        # print(itemExist,'itemExist')
        if 'value' in itemExist and itemExist['value']:
            print(f"{row['ItemName']} is present in SAP")
            # Do something with itemDetails_json['value']
            pass
        else:
            # Handle the case where 'value' is not present
            # Send POST request to create item
            response = SAPsession.request("POST", item_url, data=json.dumps(NewItemDeatils), headers=headersList, verify=False)
            
            # Check response status
            if response.status_code == 400:
                # If error, print error message
                response_data = json.loads(response.text)
                error_value = response_data['error']['message']['value']
                print('\n\n',error_value,'\n\n')
            else:
                # If successful, print success message
                response_data = json.loads(response.text)
                # print('\n\n\n',response_data["ItemCode"],'response_data')
                ItemCode_value = response_data["ItemCode"]
                print('\n\n',ItemCode_value+' created successfully in SAP ','\n\n')
                if row['ChildNeeded'] == 'Y':
                    Create_ItemMaster(ItemCode_value)
                # break
            pass

        # print('\n\n\n',itemDeatils['ItemCode'],'itemcode')
        
        



    pass