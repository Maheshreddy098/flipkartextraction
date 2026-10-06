import frappe
import json
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
import pandas as pd
import requests
from khanal_tech_integrations.utils.React_Api.Ledger.EmailTemplate import Notification_Email


headersList = {
                "Accept": "*/*",
                "User-Agent": "Khanal Tech",
                "Content-Type": "application/json" 
            }





#!Test bench --site dev.localhost execute  --args "( 'New itemSKU.xlsx','RMDC0353' )"  khanal_tech_integrations.utils.ItemMaster.Create.GetDataFrom_Excel


def Get_File(url,sheetname):
    response = requests.get(url, verify=False)
    if response.status_code == 200:
        df = pd.read_excel(response.content,sheetname)
        return df
    else:
        print(f"Error: Unable to retrieve data from {url}")


# Function to create Item Master in SAP
@frappe.whitelist()
def GetDataFrom_Excel(FileName,SampleItemCode):
    File_url = f"https://beta.khanaltech.com/files/{FileName}"
    df=Get_File(File_url,'Sheet')
    df.head()
    print(df)
    

    # print('\n\n\n',itemDeatils['ItemCode'],'itemcode')
    pass



# utils/React_Api/Ledger/EmailAutomation.py
# bench --site dev.localhost execute   khanal_tech_integrations.utils.React_Api.Ledger.EmailAutomation.Email_template

@frappe.whitelist()
def Email_template():
    message_html = """
    <div>
    <p>This is a request for a detailed ledger of all transactions between  Khanal Foods and your company for the 2023-24 fiscal year, from April 1, 2023 through March 31, 2024.</p>
    <p>The ledger should include the following information for each transaction:</p>
    <ul>
        <li>Date of transaction</li>
        <li>Invoice number</li>
        <li>Description of goods/services</li>
        <li>Quantity</li>
        <li>Rate</li>
        <li>Total amount</li>
    </ul>
    <p>Please include any outstanding credits, debits, or balances due to either party as of March 31, 2024.</p>
    <p>This ledger is required for accounting and auditing purposes. Please provide the ledger in Excel or CSV format.</p>
    <p>Thank you in advance for your cooperation. If any additional information is needed to fulfill this request, please respond to this email.</p>
    </div>
    """.format()
    recipients=['shahil@khanalfoods.com','harsha@khanalfoods.com','yogesha@khanalfoods.com']
    subject='Request for Ledger - Fiscal Year 2023-24'
    Notification_Email(message_html,recipients,subject)

