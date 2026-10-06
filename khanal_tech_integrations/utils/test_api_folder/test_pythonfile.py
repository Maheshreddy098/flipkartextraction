import os

import pandas as pd
import datetime
import frappe

csv_file_path = "MasterDF.csv"

# df = pd.read_csv('/workspace/development/ape-bench/apps/khanal_tech_integrations/khanal_tech_integrations/utils/test_api_folder/Master_DF.csv')
MASTER_DF_PATH = "/home/frappe/frappe-bench/apps/khanal_tech_integrations/khanal_tech_integrations/utils/test_api_folder/Master_DF.csv"
MASTER_DF_CHANNELWISE_PATH = "/home/frappe/frappe-bench/apps/khanal_tech_integrations/khanal_tech_integrations/utils/test_api_folder/Master_DF_ChannelWise.csv"

# `bench run-tests` imports this module during test discovery. Those CSV files
# are not available in all environments, so make import-time execution safe.
_MASTER_DF_COLUMNS = [
    "Item No.",
    "Item/Service Description",
    "Item Description",
    "Quantity",
    "Row Total",
    "Orders fulfilled / delivered",
    "Revenue",
    "Orders Raised",
    "Posting Date",
]
_DF_V2_COLUMNS = [
    "Item No.",
    "Item Description",
    "Orders fulfilled / delivered",
    "Revenue",
    "Orders Raised",
]

df = pd.read_csv(MASTER_DF_PATH) if os.path.exists(MASTER_DF_PATH) else pd.DataFrame(columns=_MASTER_DF_COLUMNS)
DF_v2 = (
    pd.read_csv(MASTER_DF_CHANNELWISE_PATH)
    if os.path.exists(MASTER_DF_CHANNELWISE_PATH)
    else pd.DataFrame(columns=_DF_V2_COLUMNS)
)
unique_item_count = df['Item No.'].nunique()
# Filter rows where "Item No." starts with "PM"
filtered_df = df[df['Item No.'].str.startswith('PM')]

filtered_df.head()

month_dict = {
    "1": "January",
    "2": "February",
    "3": "March",
    "4": "April",
    "5": "May",
    "6": "June",
    "7": "July",
    "8": "August",
    "9": "September",
    "10": "October",
    "11": "November",
    "12": "December"
}


def format_row_total(x):
    return f'{x:.2f}'  # Format as a float with 2 decimal places

result_df = df.groupby(['Item No.'])[['Quantity', 'Row Total']].sum().reset_index()
result_df = result_df.merge(df[['Item No.', 'Item/Service Description']].drop_duplicates(), on='Item No.', how='left')
result_df = result_df[['Item No.', 'Item/Service Description', 'Quantity', 'Row Total']]
result_sorted = result_df.sort_values(by='Row Total', ascending=False)
result_sorted['Row Total'] = result_sorted['Row Total'].apply(format_row_total)
#https://khanaltech.com/api/method/khanal_tech_integrations.utils.test_api_folder.test_pythonfile.get_all_items
@frappe.whitelist()
def get_all_items(new_df = DF_v2):
  filtered_df = new_df[new_df['Item No.'].str.startswith('FG')]
  result_df = filtered_df.groupby(['Item No.','Item Description'], as_index=False)[['Orders fulfilled / delivered', 'Revenue', 'Orders Raised']].sum()
  df_dict = result_df.to_dict('records')
  Output_dict = [{
            "skuName": i['Item No.'],
            "skuDesc": i['Item Description'],
            "ordered":  i[ 'Orders Raised'] ,
            "fulfilled":  i['Orders fulfilled / delivered'] ,
            "fulfillmentRate": round((i['Orders fulfilled / delivered']/ i[ 'Orders Raised'])*100,2),
            "revenue": i['Revenue'],
            "returns": 0 }  for i in df_dict]
  return Output_dict

@frappe.whitelist()
def get_sales_per_item(df_input = df,item_code = 'FGDC0031',year=2023):
    df['Posting Date'] = pd.to_datetime(df_input['Posting Date'], format='%d/%b/%Y')
    df['Month']       = df_input['Posting Date'].dt.month
    df['Year']        = df_input['Posting Date'].dt.year
    
    result_df = df.groupby(['Month', 'Year', 'Item No.'])[['Quantity', 'Row Total']].sum().reset_index()
    # Merge with the original DataFrame to get the "Item/Service Description" column
    result_df = result_df.merge(df[['Item No.', 'Item/Service Description']].drop_duplicates(), on='Item No.', how='left')
    # Reorder the columns as per your requirement
    result_df = result_df[['Item No.', 'Item/Service Description', 'Quantity', 'Row Total', 'Month', 'Year']]
    if item_code:
      result_df = result_df[result_df['Item No.'] == item_code]
      Raw_Dict = result_df.to_dict('records')
      
      Customized_Dict = {'SKU_Code' : Raw_Dict[0]['Item No.'],
                         'Item Name': Raw_Dict[0]['Item/Service Description']}
      Data = [{'Year':i['Year'],  'Month':month_dict[str( i['Month'])],'monthly_data':{ 'Ordered_Quantity':i['Quantity'], 'Revenue' :i['Row Total'], }} for i in Raw_Dict ]
      
      if year:
        Customized_Dict['Year'] = year
        Year_Filtered_Data = []
        for i in Data:
          if i['Year'] == year:
            i.pop('Year')
            Year_Filtered_Data.append(i)
            Customized_Dict[i['Month']] = i['monthly_data']
      else:
        Customized_Dict['Data'] = Data

      Rearranged_Item_Dict = Customized_Dict

    else:
      Raw_Dict = result_df.to_dict('records')
      Rearranged_Item_Dict = [{'SKU_Code':i['Item No.'],
                               'Item Name':i['Item/Service Description'],
                               'Year':i['Year'],
                               'Months':{i['Month']:{
                                                  'Ordered_Quantity':i['Quantity'],
                                                  'Revenue' :i['Row Total'], }} } for i in Raw_Dict ]
    
    return Rearranged_Item_Dict



def which_week(date_time):
  return date_time.isocalendar()[1]

df['Posting Date'] = pd.to_datetime(df['Posting Date'], format='%d/%b/%Y')
df['Month']       = df['Posting Date'].dt.month
df['Year']        = df['Posting Date'].dt.year
df['Week']        = df['Posting Date'].apply(which_week)

df_timely = df

result_df = df.groupby(['Month', 'Year', 'Item No.'])[['Quantity', 'Row Total']].sum().reset_index()
# Merge with the original DataFrame to get the "Item/Service Description" column
result_df = result_df.merge(df[['Item No.', 'Item/Service Description']].drop_duplicates(), on='Item No.', how='left')
# Reorder the columns as per your requirement
result_df = result_df[['Item No.', 'Item/Service Description', 'Quantity', 'Row Total', 'Month', 'Year']]
df_timely = result_df.copy()


@frappe.whitelist()
def get_sales_given_time_duration_per_item(df_input = df_timely):
    output_dict = df_input.to_dict('records')
    return output_dict
    
import frappe


@frappe.whitelist()
def get_Sales_ItemWise(sku_code = 'FGDC0031',Filtered_year =2023 ): #get_sales_per_item(df_input = df,item_code = 'FGDC0031',year=2023)
    result =  get_sales_per_item(df_input = df,item_code = sku_code,year=Filtered_year)
    return result #{'result':result}



#! API End Ponit is 
#? {url and port }/api/method/khanal_tech_integrations.utils.test_api_folder.test_pythonfile.get_Sales_ItemWise


# Print or use the resulting pivoted DataFrame as needed