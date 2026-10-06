import frappe
import pandas as pd
from datetime import date
from io import BytesIO
import requests

# DF_SalesOrder = pd.read_excel('/home/frappe/frappe-bench/apps/khanal_tech_integrations/khanal_tech_integrations/utils/Khanalytics/Dashboard/Analytics Dashbaord data.xlsx',"Sales Order")
# DF_v3 = pd.read_csv('/home/frappe/frappe-bench/apps/khanal_tech_integrations/khanal_tech_integrations/utils/Khanalytics/Master_DF3.csv')

# DF_SalesOrder = pd.read_excel('/Users/shahilkhan/Desktop/khanalFoods/frappe-bench/apps/khanal_tech_integrations/khanal_tech_integrations/utils/Khanalytics/Dashboard/Analytics Dashbaord data.xlsx',"Sales Order")
# /Users/shahilkhan/Desktop/khanalFoods/frappe-bench/apps/khanal_tech_integrations/khanal_tech_integrations/utils/Khanalytics/Dashboard/createfile.py", line 5

def Get_File(url,sheetname):
    response = requests.get(url, verify=False)
    if response.status_code == 200:
        df = pd.read_excel(response.content,sheetname)
        return df
    else:
        print(f"Error: Unable to retrieve data from {url}")



def trigger_function():
    Sales_df=Get_File("http://beta.khanaltech.com/files/Analytics Dashbaord data.xlsx",'Sales Order')
    Sales_df.rename(columns={'State.1': 'Country'}, inplace=True)
    Sales_df['State'].fillna(Sales_df['Country'], inplace=True)
    Bp_master=Get_File("http://beta.khanaltech.com/files/List of Business Partners Dashboard.xlsx",'Sheet1')
    merged_df = Sales_df.merge(Bp_master, left_on='Customer/Vendor Code', right_on='BP Code', how='left')
    merged_df['State'].fillna(merged_df['Ship-to State'], inplace=True)
    merged_df['State'] = merged_df['State'].replace(state_code_to_name)
    merged_df = merged_df.iloc[:, :8] 
    merged_df['Posting Date'] = pd.to_datetime(merged_df['Posting Date'], format='%d/%m/%Y')
    merged_df['Month'] = merged_df['Posting Date'].dt.month
    merged_df['Year'] = merged_df['Posting Date'].dt.year
    merged_df = merged_df[['Month', 'Year'] + [col for col in merged_df.columns if col not in ['Month', 'Year']]]
    Item_master=Get_File("http://beta.khanaltech.com/files/List of Items.xlsx",'Sheet1')
    # print(Item_master,'Item_master')
    columns_df = merged_df.merge(Item_master, left_on='Item Code', right_on='Item No.', how='left')
    # columns_df.columns

    # print(columns_df)
    return None


state_code_to_name = {
    "AP": "Andhra Pradesh",
    "ES_KT": "Karnataka",
    "NL_KT": "Karnataka",
    "GB_KT": "Karnataka",
    "TW_KT": "Karnataka",
    "US_KT": "Karnataka",
    "DL": "Delhi",
    "CA_DL": "Delhi",
    "NO_DL": "Delhi",
    "HR": "Haryana",
    "KT": "Karnataka",
    "MP": "Madhya Pradesh",
    "MH": "Maharashtra",
    "NL_MH": "Maharashtra",
    "UP": "Uttar Pradesh",
    "LN_UP": "Uttar Pradesh",
    "AN": "Andaman and Nicobar Islands",
    "AR": "Arunachal Pradesh",
    "AS": "Assam",
    "BR": "Bihar",
    "CH": "Chandigarh",
    "CG": "Chattisgarh",
    "DN": "Dadra and Nagar Haveli",
    "DD": "Daman and Diu",
    "GA": "Goa",
    "GJ": "Gujarat",
    "HP": "Himachal Pradesh",
    "JK": "Jammu and Kashmir",
    "JH": "Jharkhand",
    "KL": "Kerala",
    "LD": "Lakshadweep Islands",
    "MN": "Manipur",
    "ML": "Meghalaya",
    "MZ": "Mizoram",
    "NL": "Nagaland",
    "OD": "Odisha",
    "PY": "Pondicherry",
    "PB": "Punjab",
    "RJ": "Rajasthan",
    "SK": "Sikkim",
    "TN": "Tamil Nadu",
    "TS": "Telangana",
    "TR": "Tripura",
    "UK": "Uttarakhand",
    "WB": "West Bengal",
    "IN_PA": "USA",
    "WA": "USA",
    "HK_KT": "Karnataka",
    "FR_KT": "Maharashtra",
}
