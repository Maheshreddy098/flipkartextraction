
import frappe
import requests
import pandas as pd
from datetime import datetime
from khanal_tech_integrations.utils.React_Api.Ledger.EmailTemplate import Content_Email


# from khanal_tech_integrations.utils.React_Api.Ledger.ApprovalPage import Get_Filter_Journal

import json

# df = pd.read_csv('/Users/shahilkhan/Desktop/khanalFoods/frappe-bench/apps/khanal_tech_integrations/khanal_tech_integrations/utils/React_Api/Ledger/Ledger_Data.csv')
# df = pd.read_csv('/Users/shahilkhan/Desktop/WorkSpace/JournalEntries/Ledger/Vendor Master Data.csv')

# DF_v3 = pd.read_csv('/home/frappe/frappe-bench/apps/khanal_tech_integrations/khanal_tech_integrations/utils/Khanalytics/Master_DF3.csv')
#/Users/shahilkhan/Desktop/khanalFoods/frappe-bench/apps/khanal_tech_integrations/khanal_tech_integrations/utils/React_Api/Ledger/Ledger_Data.csv

def Get_File(url,sheetname):
    response = requests.get(url, verify=False)
    if response.status_code == 200:
        df = pd.read_excel(response.content,sheetname)
        return df
    else:
        print(f"Error: Unable to retrieve data from {url}")




@frappe.whitelist()
def Vendor_Details(UserEmail):
    print(UserEmail,'UserEmail')
    df = Get_File("https://khanaltech.com/files/Vendor-Master-Data.xlsx", 'Worksheet')
    # doc = frappe.get_list('SAP Salesperson',filters={'email':UserEmail})
    salesperson_exists = frappe.get_all('SAP Salesperson', filters={'email': UserEmail}, limit=1)
     

    if salesperson_exists:
    # Document exists, retrieve the value of 'bp__associated'
        doc_bp_associated_str = frappe.get_value('SAP Salesperson', {'email': UserEmail}, 'bp__associated')
    
    # Check if doc_bp_associated_str is not None
        if doc_bp_associated_str is not None:
            # Parse the JSON string into a Python object
            doc_bp_associated = json.loads(doc_bp_associated_str)
            # Convert 'bp__associated' to the desired structure
            json_data_bp_associated = [{'BP_Code': record['BP_Code'], 'BP_Name': record['BP_Name']} for record in doc_bp_associated]
            print(json_data_bp_associated,'json_data_bp_associated')
            return json_data_bp_associated

        else:
            print("bp__associated is null for SAP Salesperson with email:")
            filtered_df = df[df['BP Code'].str.startswith('V')]
            json_data = filtered_df[['BP Code', 'BP Name']].to_dict(orient='records')
            modified_json_data = [{'BP_Code': record['BP Code'], 'BP_Name': record['BP Name']} for record in json_data]   
            return modified_json_data
    else:
        print("SAP Salesperson document not found for email:")    
        filtered_df = df[df['BP Code'].str.startswith('V')]
        json_data = filtered_df[['BP Code', 'BP Name']].to_dict(orient='records')
        modified_json_data = [{'BP_Code': record['BP Code'], 'BP_Name': record['BP Name']} for record in json_data]   
        return modified_json_data
    # df = Get_File("http://beta.khanaltech.com/files/Vendor Master Data.xlsx", 'Sheet1')
    # json_data = df[['BP Code', 'BP Name']].to_dict(orient='records')
    





# bench --site dev.localhost execute  --args "{ 'shahil@khanalfoods.com' }"  khanal_tech_integrations.utils.React_Api.Ledger.RequestPage.Vendor_Details


@frappe.whitelist()
def Submitted_Result(RequestData):
    print('\n\n\n',RequestData,'RequestData')
    try:
        print(RequestData, 'RequestData')
        Today = frappe.utils.nowdate()
        print(Today, 'Today')

        doc = frappe.new_doc('Ledger Details')
        doc.start_date = RequestData['StartDate']
        doc.end_date = RequestData['EndDate']
        doc.vendor_code = RequestData['VendorCode']['BP_Code']
        doc.vendor_name = RequestData['VendorCode']['BP_Name']
        doc.user_comments = RequestData['Comments']
        doc.user_email = RequestData['UserEmail']
        doc.added_date = datetime.now()
        salesperson_exists = frappe.get_all('SAP Salesperson', filters={'email': RequestData['UserEmail']}, limit=1)
     

        if salesperson_exists:
            doc_bp_associated_str = frappe.get_value('SAP Salesperson', {'email': RequestData['UserEmail']}, 'bp__associated')
        
            if doc_bp_associated_str is not None:
                doc.status = "Approved"
                doc.save()
                frappe.db.commit()
                # Get_Filter_Journal(doc.name)
                return {"status": "success", "message": "Document saved successfully"}
            else:
                doc.save()
                frappe.db.commit()
                Content_Email()
                return {"status": "success", "message": "Document saved successfully"}
        else:
            doc.save()
            frappe.db.commit()
            Content_Email()
            return {"status": "success", "message": "Document saved successfully"}


    except Exception as e:
        # Return an error response
        return {"status": "error", "message": str(e)}

#  {'StartDate': '2024-01-19', 'EndDate': '2024-01-19', 'VendorCode': 'V00005', 'Comments': 'NA', 'UserEmail': 'procurement@gmail.com'}