import frappe
import pandas as pd
from datetime import date

# DF_v2 = pd.read_csv('/home/frappe/frappe-bench/apps/khanal_tech_integrations/khanal_tech_integrations/utils/Khanalytics/Master_DF_ChannelWise.csv')
# DF_v3 = pd.read_csv('/home/frappe/frappe-bench/apps/khanal_tech_integrations/khanal_tech_integrations/utils/Khanalytics/Master_DF3.csv')
#/workspace/development/ape-bench/apps/khanal_tech_integrations/khanal_tech_integrations/utils/Khanalytics/Master_DF_ChannelWise.csv

# /Users/shahilkhan/Desktop/khanalFoods/frappe-bench/apps/khanal_tech_integrations/khanal_tech_integrations/utils/Khanalytics/Master_DF_ChannelWise.csv

DF_v2 = pd.read_csv('/Users/shahilkhan/Desktop/khanalFoods/frappe-bench/apps/khanal_tech_integrations/khanal_tech_integrations/utils/Khanalytics/Master_DF_ChannelWise.csv')
DF_v3 = pd.read_csv('/Users/shahilkhan/Desktop/khanalFoods/frappe-bench/apps/khanal_tech_integrations/khanal_tech_integrations/utils/Khanalytics/Master_DF3.csv')
DF_v3 = DF_v3.fillna(0)
@frappe.whitelist( allow_guest=True )
def Get_Api():
    doc = frappe.db.get_list('SAP Salesperson')
    return {'msg':doc}



month_dictionary = {
    1: 'January',
    2: 'February',
    3: 'March',
    4: 'April',
    5: 'May',
    6: 'June',
    7: 'July',
    8: 'August',
    9: 'September',
    10: 'October',
    11: 'November',
    12: 'December'
}
Current_Month = date.today().month
Current_MY = month_dictionary[date.today().month] +' '+ str(date.today().year)
###############################
def comma_formatting(input_num : float):
  """
  This Function takes a number round it off and add comma in 3 digit separation.
  """
  y   = round(input_num)
  res = ('{:,}'.format(y))
  return res

#! API End Ponit is 
#? {url and port }/api/method/khanal_tech_integrations.utils.Khanalytics.getApi.Get_Api
  


Month_list = ['January 2022',
              'February 2022',
              'March 2022',
              'April 2022',
              'May 2022',
              'June 2022',
              'July 2022', #---
              'August 2022',
              'September 2022',
              'October 2022',
              'November 2022',
              'December 2022',
              'January 2023',
              'February 2023',
              'March 2023', #---
              'April 2023',
              'May 2023',
              'June 2023',
              'July 2023',
              'August 2023',
              'September 2023',
              'October 2023',
              'November 2023',
              'December 2023'
              'January 2024',
              'February 2024',
              'March 2024',
              'April 2024',
              'May 2024',
              'June 2024',
              'July 2024',
              'August 2024',
              'September 2024',
               ]
@frappe.whitelist( allow_guest=True )
def core_filter(input_df=DF_v3,state=None,Start_MY=None,End_MY=None,category=None,brand=None,channel=None) -> dict:
  """
  Given some filters it modifies the core dataframe which will be passed to all other functions -- thus changing the data going to front-end.
  """
  input_df['Month_Year'] = input_df['Month'] +' '+ input_df['Year'].astype(str)

  if Start_MY and End_MY:
    start_index     = Month_list.index(Start_MY )
    end_index       = Month_list.index(End_MY)
    Filterd_Months  = Month_list[start_index : end_index+1]
    input_df        = input_df.loc[input_df['Month_Year'].isin(Filterd_Months)]

  if state:
    input_df = input_df[input_df['State'] == state]
  if category:
    input_df = input_df[input_df['Category'] == category]
  if brand:
    input_df = input_df[input_df['Brand Name'] == brand]
  if channel:
    input_df = input_df[input_df['Channel'] == channel]
  else:
    input_df = input_df.sort_values(by=['Revenue'], ascending=False).reset_index()
  input_df = input_df.sort_values(by=['Revenue'], ascending=False).reset_index()
  return input_df
###################################
@frappe.whitelist( allow_guest=True )
def Top_Revenue_Items(df_input = DF_v3):
  Sorted_DF   = df_input.sort_values(by=['Revenue'], ascending=False)
  result_df   = Sorted_DF.groupby(['Item No.','Item Description'], as_index=False)[['Orders Raised','Orders fulfilled / delivered','Returned', 'Revenue', ]].sum().reset_index()
  result_df   = result_df.sort_values(by=['Revenue'], ascending=False).reset_index()
  if len(result_df['Item No.']) > 5:
    return result_df['Item No.'][:5]
#Saving the Top-Selling items in a Variable - Top 7 SKUs
Top_Selling = Top_Revenue_Items()

# DF_v3 =core_filter(input_df=DF_v3,state=None,Start_MY=None,End_MY=None,category=None,brand=None,channel=None)
@frappe.whitelist( allow_guest=True )
def get_sales_per_item(original_df=DF_v3,State=None,Category=None,Brand=None,Channel=None,
                       item_code1 = None,item_code2 = None ,item_code3 = None,item_code4 = None,item_code5 = None,
                       startMY = 'June 2022',endMY= Current_MY ):
    #for Amazon Revenue -- 7/10
    df_input      = core_filter(input_df=original_df,state=State,Start_MY=startMY,End_MY=endMY,category=Category,brand=Brand,channel=Channel)
    
    Top_Selling_Items = Top_Revenue_Items(df_input = df_input)
    
    if item_code1 == None and item_code2 == None and item_code3==None:
      item_code1 = Top_Selling_Items[0]
      item_code2 = Top_Selling_Items[1]
      item_code3 = Top_Selling_Items[2]
          
    result_df     = df_input.groupby(['Month', 'Year', 'Item No.'])[['Orders fulfilled / delivered', 'Orders Raised','Revenue','Returned']].sum().reset_index()
    result_df     = result_df.merge(df_input[['Item No.', 'Item Description']].drop_duplicates(), on='Item No.', how='left')
    
    result_df     = result_df[['Item No.', 'Item Description', 'Orders fulfilled / delivered', 'Orders Raised','Revenue', 'Returned','Month', 'Year']]
    result_df     = result_df.sort_values(by=['Revenue'], ascending=False)
    
    start_index   = Month_list.index(startMY )
    end_index     = Month_list.index(endMY)
    Filterd_Months = Month_list[start_index : end_index+1]
    final_output  = {}
    if item_code1:
      Item_df     = result_df[result_df['Item No.'] == item_code1]
      Raw_Dict    = Item_df.to_dict('records')

      Customized_Dict = {'SKU_Code' : Raw_Dict[0]['Item No.'],
                         'Item Name': Raw_Dict[0]['Item Description']}
      Monthly_Dict    = {}
      if Raw_Dict:
        Data = [{'Refer':str(i['Month'] + ' ' + str(i['Year'])),  'Month': i['Month'],'monthly_data':{ 'Unit_Order':i['Orders Raised'],'Unit_Sold':i['Orders fulfilled / delivered'], 'Returns':i['Returned'], 'Revenue' :round(i['Revenue'])}} for i in Raw_Dict ]
        Customized_Dict['Start Month_Year'] = startMY
        Customized_Dict['End Month_Year']   = endMY

        Month_Year_Filtered_Data = []
        for i in Data:
            if i['Refer'] in Filterd_Months:
                Month_Year_Filtered_Data.append(i)
                Monthly_Dict[i['Refer']] = i['monthly_data']
        Customized_Dict['Month'] = Monthly_Dict
        final_output[item_code1] = Customized_Dict
        
    if item_code2:
      Item_df = result_df[result_df['Item No.'] == item_code2]
      Raw_Dict = Item_df.to_dict('records')

      Customized_Dict = {'SKU_Code' : Raw_Dict[0]['Item No.'],
                         'Item Name': Raw_Dict[0]['Item Description']}
      Monthly_Dict = {}
      if Raw_Dict:
        Data = [{'Refer':str(i['Month'] + ' ' + str(i['Year'])),  'Month': i['Month'],'monthly_data':{ 'Unit_Order':i['Orders Raised'],'Unit_Sold':i['Orders fulfilled / delivered'], 'Returns':i['Returned'], 'Revenue' : round(i['Revenue']) }} for i in Raw_Dict ]
        Customized_Dict['Start Month_Year'] = startMY
        Customized_Dict['End Month_Year']   = endMY

        Month_Year_Filtered_Data = []
        for i in Data:
            if i['Refer'] in Filterd_Months:
                Month_Year_Filtered_Data.append(i)
                Monthly_Dict[i['Refer']] = i['monthly_data']
        Customized_Dict['Month'] = Monthly_Dict
        final_output[item_code2] = Customized_Dict
    ###############
    if item_code3:
      Item_df   = result_df[result_df['Item No.'] == item_code3]
      Raw_Dict  = Item_df.to_dict('records')

      Customized_Dict = {'SKU_Code' : Raw_Dict[0]['Item No.'],
                         'Item Name': Raw_Dict[0]['Item Description']}
      Monthly_Dict = {}
      if Raw_Dict:
        Data = [{'Refer':str(i['Month'] + ' ' + str(i['Year'])),  'Month': i['Month'],'monthly_data':{ 'Unit_Order':i['Orders Raised'],'Unit_Sold':i['Orders fulfilled / delivered'], 'Returns':i['Returned'], 'Revenue' :round(i['Revenue']) }} for i in Raw_Dict ]
        Customized_Dict['Start Month_Year'] = startMY
        Customized_Dict['End Month_Year']   = endMY

        Month_Year_Filtered_Data = []
        for i in Data:
            if i['Refer'] in Filterd_Months:
                Month_Year_Filtered_Data.append(i)
                Monthly_Dict[i['Refer']] = i['monthly_data']
        Customized_Dict['Month'] = Monthly_Dict
        final_output[item_code3] = Customized_Dict
    #######################
    if item_code4:
      Item_df   = result_df[result_df['Item No.'] == item_code4]
      Raw_Dict  = Item_df.to_dict('records')

      Customized_Dict = {'SKU_Code' : Raw_Dict[0]['Item No.'],
                         'Item Name': Raw_Dict[0]['Item Description']}
      Monthly_Dict = {}
      if Raw_Dict:
        Data = [{'Refer':str(i['Month'] + ' ' + str(i['Year'])),  'Month': i['Month'],'monthly_data':{ 'Unit_Order':i['Orders Raised'],'Unit_Sold':i['Orders fulfilled / delivered'], 'Returns':i['Returned'], 'Revenue' :round(i['Revenue']) }} for i in Raw_Dict ]
        Customized_Dict['Start Month_Year'] = startMY
        Customized_Dict['End Month_Year']   = endMY

        Month_Year_Filtered_Data = []
        for i in Data:
            if i['Refer'] in Filterd_Months:
                Month_Year_Filtered_Data.append(i)
                Monthly_Dict[i['Refer']] = i['monthly_data']
        Customized_Dict['Month'] = Monthly_Dict
        final_output[item_code4] = Customized_Dict
        
    if item_code5:
      Item_df   = result_df[result_df['Item No.'] == item_code5]
      Raw_Dict  = Item_df.to_dict('records')

      Customized_Dict = {'SKU_Code' : Raw_Dict[0]['Item No.'],
                         'Item Name': Raw_Dict[0]['Item Description']}
      Monthly_Dict = {}
      if Raw_Dict:
        Data = [{'Refer':str(i['Month'] + ' ' + str(i['Year'])),  'Month': i['Month'],'monthly_data':{ 'Unit_Order':i['Orders Raised'],'Unit_Sold':i['Orders fulfilled / delivered'], 'Returns':i['Returned'], 'Revenue' :round(i['Revenue']) }} for i in Raw_Dict ]
        Customized_Dict['Start Month_Year'] = startMY
        Customized_Dict['End Month_Year']   = endMY

        Month_Year_Filtered_Data = []
        for i in Data:
            if i['Refer'] in Filterd_Months:
                Month_Year_Filtered_Data.append(i)
                Monthly_Dict[i['Refer']] = i['monthly_data']
        Customized_Dict['Month'] = Monthly_Dict
        final_output[item_code5] = Customized_Dict    
    sample_output =   {'FGDC0031': {'SKU_Code': 'FGDC0031',
                                      'Item Name': 'Dogsee Chew Large bars - 130G India',
                                      'Start Month_Year': 'July 2022',
                                      'End Month_Year': 'May 2023',
                                      'Month': {'April 2023': {'Unit_Order': 2514.0,
                                                  'Unit_Sold': 2643.0,
                                                  'Returns': 0,
                                                  'Revenue': 490405.98},
                                                'October 2022': {'Unit_Order': 1479.0,
                                                  'Unit_Sold': 1524.0,
                                                  'Returns': 1,
                                                  'Revenue': 273696.89},
                                                'September 2022': {'Unit_Order': 2546.0,
                                                  'Unit_Sold': 2501.0,
                                                  'Returns': 7,
                                                  'Revenue': 428034.08}
                                      }
                                      },
                      'FGHN0015': {'SKU_Code': 'FGHN0015',
                                      'Item Name': 'HN Almond - 200G',
                                      'Start Month_Year': 'July 2022',
                                      'End Month_Year': 'May 2023',
                                      'Month': {'April 2023': {'Unit_Order': 8172.0,
                                                  'Unit_Sold': 3204.0,
                                                  'Returns': 0,
                                                  'Revenue': 476249.19},
                                                'January 2023': {'Unit_Order': 10217.0,
                                                  'Unit_Sold': 10277.0,
                                                  'Returns': 0,
                                                  'Revenue': 1497594.15},
                                                'July 2022': {'Unit_Order': 10306.0,
                                                  'Unit_Sold': 10406.0,
                                                  'Returns': 5143,
                                                  'Revenue': 1610421.34},
                                                }}}
    return final_output


@frappe.whitelist( allow_guest=True )
def get_contexts(in_DF=DF_v3,startMY = 'June 2022',endMY= Current_MY ,Brand=None,State=None,Category=None,Channel=None): #startMY = 'June 2022',endMY= Current_MY 
  df_input = core_filter(input_df=in_DF,state=State,Start_MY=startMY,End_MY=endMY,category=Category,brand=Brand,channel=Channel)
  filtered_df   = df_input[df_input['Item No.'].str.startswith('FG')]
  Dict_filters  = {}
  filtered_df['Month_Year']     = filtered_df['Month'] +' '+ filtered_df['Year'].astype(str) #.str[:3]
  Dict_filters['Month_Year']    = list(filtered_df['Month_Year'].unique())
  
  Dict_filters['Channels']      = list(filtered_df['Channel'].unique())
  Dict_filters['Categories']    = list(filtered_df['Category'].unique())
  Dict_filters['State']         = list(filtered_df['State'].unique())
  Dict_filters['Brands']        = list(filtered_df['Brand Name'].unique())
  #  Dict_filters['Country']       = list(filtered_df['Country'].unique())
  
  Example_output = {'Month_Year': ['January 2023', 'February 2023'],
                    'Categories': ['Pet Food and Treats','Pet Accessories'],
                    'State'     : ['Spain', 'Karnataka', 'Maharashtra' ],
                    'Brands'    : ['Churpi', 'Dogsee', 'Petello', 'Yakkas'],
                    'Country'   : ['Spain', 'India', 'USA']}
  return Dict_filters


@frappe.whitelist( allow_guest=True )
def get_Tabular_items(in_DF=DF_v3, startMY = 'June 2022',endMY=Current_MY ,Brand=None,State=None,Category=None,Channel=None):
    # df['Month_Year']     = df['Month'] +' '+ df['Year'].astype(str) #.str[:3]
    df_input = core_filter(input_df=in_DF,state=State,Start_MY=startMY,End_MY=endMY,category=Category,brand=Brand,channel=Channel)
    df_input   = df_input.sort_values(by=['Revenue'], ascending=False)
    if Brand:
      df_input  = df_input[df_input['Brand Name'] == Brand]
    result_df   = df_input.groupby(['Item No.','Item Description'], as_index=False)[['Orders Raised','Orders fulfilled / delivered','Returned', 'Revenue', ]].sum()
    result_df   = result_df.sort_values(by=['Revenue'], ascending=False)
    #result_df['Revenue'] = result_df['Revenue'].apply(comma_formatting) 
    Output_Item_Dict  = result_df.to_dict('records')
    Total_Revenue     = result_df['Revenue'].sum()
    Output_dict = [{
            "skuName"   : i['Item No.'],
            "skuDesc"   : i['Item Description'],
            "Unit_Order": i[ 'Orders Raised'] ,
            "Unit_Sold" : i['Orders fulfilled / delivered'] ,
            "Fullfillment_Rate": round((i['Orders fulfilled / delivered']/ i[ 'Orders Raised'])*100 , 2),
            "Revenue"   :round( i['Revenue']),
            "Percentage_of_Revenue": round((i['Revenue']/ Total_Revenue)*100,1),
            "Returns"   : i[ 'Returned'] }  for i in Output_Item_Dict]

    if startMY and endMY:
      df_input['Month_Year']     = df_input['Month'] +' '+ df_input['Year'].astype(str) #.str[:3]
      start_index     = Month_list.index(startMY )
      end_index       = Month_list.index(endMY)
      Filterd_Months  = Month_list[start_index : end_index+1]

      filtered_DF     = df_input[ df_input['Month_Year'].isin(Filterd_Months) ]

      Total_Revenue   = filtered_DF['Revenue'].sum()
      result_df       = filtered_DF.groupby(['Item No.','Item Description'], as_index=False)[['Orders Raised','Orders fulfilled / delivered','Returned', 'Revenue', ]].sum()
      df_dict         = result_df.to_dict('records')
      Output_list = [{
            "skuName"           : i['Item No.'],
            "skuDesc"           : i['Item Description'],
            "Unit_Order"        :  i[ 'Orders Raised'] ,
            "Unit_Sold"         :  i['Orders fulfilled / delivered'] ,
             "Returns"          :  i[ 'Returned'],
            "Fullfillment_Rate" : round((i['Orders fulfilled / delivered']/ i[ 'Orders Raised'])*100,1),
            "Revenue"           : round( i['Revenue'] ),
            "Percentage_of_Revenue" : round((i['Revenue']/ Total_Revenue)*100,2),} 
                     for i in df_dict]
      Output_format = [{'skuName': 'FGDC0001',
                        'skuDesc': 'Bubimex Crunchies - 70G x 1P (8947)',
                                'Unit_Ordered': 2100.0,
                                'Unit_Sold': 1350.0,
                                
                                'Fullfillment_Rate': 64.29,
                                'Revenue': 246225.0,
                                'Percentage_of_Revenue': 0.02,
                                'Returns': 0},
                       
                      {'skuName': 'FGDC0002',
                        'skuDesc': 'Bubimex Dried Coconut - 150G x 1P (8986)',
                                'Unit_Ordered': 480.0,
                                'Unit_Sold': 240.0,
                                'Fullfillment_Rate': 50.0,
                                'Revenue': 125182.8,
                                
                                'Percentage_of_Revenue': 0.01,
                                'Returns': 0},]
      Sorted_list = sorted(Output_list, 
                 key=lambda d: d['Revenue'],
                 reverse=True)

    return Sorted_list
  
@frappe.whitelist( allow_guest=True )
def get_Tabular_categories(in_DF=DF_v3,startMY = 'June 2022',endMY=Current_MY ,Brand=None,State=None,Category=None,Channel=None):
    # df['Month_Year']     = df['Month'] +' '+ df['Year'].astype(str) #.str[:3]
    df_input = core_filter(input_df=in_DF,state=State,Start_MY=startMY,End_MY=endMY,category=Category,brand=Brand,channel=Channel)
    result_df = df_input.groupby(['Category'], as_index=False)[['Orders Raised','Orders fulfilled / delivered','Returned', 'Revenue', ]].sum()
    result_df = result_df.sort_values(by=['Revenue'], ascending=False)
    #result_df['Revenue'] = result_df['Revenue'].apply(comma_formatting) 
    Output_Item_Dict = result_df.to_dict('records')
    Total_Revenue = result_df['Revenue'].sum()
    Output_dict = [{
                "Category Name"     :  i['Category'],
                "Unit_Order"        :  i[ 'Orders Raised'] ,
                "Unit_Sold"         :  i['Orders fulfilled / delivered'] ,
                "Fullfillment_Rate" :  round((i['Orders fulfilled / delivered']/ i[ 'Orders Raised'])*100,1),
                "Revenue"           :  round( i['Revenue'] ),
                "Percentage_of_Revenue" : round((i['Revenue']/ Total_Revenue)*100,2),
                "Returns"           :  i[ 'Returned'] }  for i in Output_Item_Dict
                   ]
    return Output_dict
  
#########
@frappe.whitelist( allow_guest=True )
def Manual_Insights(in_DF=DF_v3,startMY = 'June 2022',endMY= Current_MY ,Brand=None,State=None,Category=None,Channel=None): # startMY = 'July 2022',endMY='September 2023'
    """
    1 - Top Selling Category
    2 - Top Revenue Generation Customer 
    3 - Channelwise Top-selling category. and Items 
    4 - 
    """
    Output_Dict = {}
    df_input  = core_filter(input_df=in_DF,state=State,Start_MY=startMY,End_MY=endMY,category=Category,brand=Brand,channel=Channel)
    Sorted_DF = df_input.sort_values(by=['Revenue'], ascending=False)
    Item_df   = Sorted_DF.groupby(['Item No.','Item Description'], as_index=False)[['Orders Raised','Orders fulfilled / delivered','Returned', 'Revenue', ]].sum().reset_index()
    Item_df   = Item_df.sort_values(by=['Revenue'], ascending=False).reset_index()
    Output_Dict['Filtered_DateRange'] = [startMY , endMY]
    if Brand :
      Output_Dict['Filtered_Brand'] = Brand
    if Category:
      Output_Dict['Filtered_Category'] = Category
      
    
    Output_Dict['BestSellingItem']    = {Item_df['Item No.'][0]:Item_df['Item Description'][0]}
    Output_Dict['WorstSellingItem']   = {Item_df['Item No.'][len(Item_df['Item No.'])-1]:Item_df['Item Description'][len(Item_df['Item Description'])-1]}


    Category_df   = Sorted_DF.groupby(['Category'], as_index=False)[['Orders Raised','Orders fulfilled / delivered','Returned', 'Revenue', ]].sum().reset_index()
    Category_df   = Category_df.sort_values(by=['Revenue'], ascending=False).reset_index()
    Total_Revenue = Category_df['Revenue'].sum()
    Output_Dict['BestSellingCategory']    = { Category_df['Category'][0] : round((Category_df['Revenue'][0]/ Total_Revenue)*100,2) }
    Output_Dict['WorstSellingCategory']   = { Category_df['Category'][len(Category_df['Category'])-1] :round((Category_df['Revenue'][len(Category_df['Category'])-1]/ Total_Revenue)*100,2) }
    
    Channel_df    = Sorted_DF.groupby(['Channel'], as_index=False)[['Orders Raised','Orders fulfilled / delivered','Returned', 'Revenue', ]].sum().reset_index()
    Channel_df    = Channel_df.sort_values(by=['Revenue'], ascending=False).reset_index()
    Output_Dict['BestSellingChannel']     = { Channel_df['Channel'][0] : round((Channel_df['Revenue'][0]/ Total_Revenue)*100,2) }
    Output_Dict['WorstSellingChannel']    = { Channel_df['Channel'][len(Channel_df['Channel'])-1] :round((Channel_df['Revenue'][len(Channel_df['Channel'])-1]/ Total_Revenue)*100,2) }

    Customer_df   = Sorted_DF.groupby(['Customer/Vendor Code','Customer Code'], as_index=False)[['Orders Raised','Orders fulfilled / delivered','Returned', 'Revenue', ]].sum().reset_index()
    Customer_df   = Customer_df.sort_values(by=['Revenue'], ascending=False).reset_index()
    Output_Dict['BestSellingCustomer']    = { Customer_df['Customer Code'][0] : round((Customer_df['Revenue'][0]/ Total_Revenue)*100,2)}
    Output_Dict['WorstSellingCustomer']   =  { Customer_df['Customer Code'][len(Customer_df['Customer Code'])-1] : round((Customer_df['Revenue'][len(Customer_df['Customer Code'])-1]/ Total_Revenue)*100,2)}

    return Output_Dict