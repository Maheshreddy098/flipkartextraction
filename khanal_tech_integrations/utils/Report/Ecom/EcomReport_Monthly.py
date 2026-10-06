import requests
import json
import pandas as pd
# import datetime
import re
import frappe
import os
from io import BytesIO
import os
from jinja2 import Template
import locale
# from frappe.utils import add_to_date
import decimal
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1

# from datetime import datetime
from frappe.utils import nowdate, add_to_date, get_first_day, get_last_day
from datetime import datetime, timedelta
import numpy as np
from bs4 import BeautifulSoup

import numpy as np
from khanal_tech_integrations.utils.Finance.AgeingReport import Make_AgeingReport
from khanal_tech_integrations.utils.Report.Ar_invoice import Ar_Invoice_List
from khanal_tech_integrations.utils.Report.Ar_CreditNote import CreditNote_List
from khanal_tech_integrations.utils.Report.IncomingPayment import IncomingPayment_List

from khanal_tech_integrations.utils.Finance.AgeingReport import Get_File
from khanal_tech_integrations.utils.Report.GetSalesEmployee import ExportEmployeeList
from khanal_tech_integrations.utils.Report.Ecom.EcomCommonFile import currencyFormatInWords


from khanal_tech_integrations.utils.Report.Ecom.EcomCommonFile import EcomReport,currencyFormatInWords,EmailFormat,EmailTemplate


#! bench --site dev.localhost execute   khanal_tech_integrations.utils.Report.Ecom.EcomReport_Monthly.MonthlyReport



@frappe.whitelist()
def MonthlyReport():
    Today = nowdate()
    ThisMonthStarting = get_first_day(add_to_date(Today, days=-1)).strftime("%Y-%m-%d")


    # Today="2024-07-04"
    # MonthStarting = "2024-06-01"
    # MonthEnding =  "2024-06-30"
    # PreviousMonthStarting='2024-05-01'
    # PreviousMonthEnding='2024-05-31'
    # LastMonthEnding="2024-04-30"
    MonthStarting = get_first_day(add_to_date(Today, months=-1)).strftime("%Y-%m-%d")
    MonthEnding = get_last_day(add_to_date(Today, months=-1)).strftime("%Y-%m-%d")

    PreviousMonthStarting = get_first_day(add_to_date(Today, months=-2)).strftime("%Y-%m-%d")
    PreviousMonthEnding = get_last_day(add_to_date(Today, months=-2)).strftime("%Y-%m-%d")

    

    LastMonthEnding=get_last_day(add_to_date(Today, months=-3)).strftime("%Y-%m-%d")



    # Print the dates for debugging
    print("Today:", Today)
    print("ThisMonthStarting:", ThisMonthStarting)
    print("Month Starting:", MonthStarting)
    print("This Week Starting:", MonthEnding)
    print("Previous Week Starting:", PreviousMonthStarting)
    print("Previous Week Ending:", PreviousMonthEnding)
    print('LastMonthEnding',LastMonthEnding)

    To_Report=Get_MasterData(Today,MonthStarting,MonthEnding,PreviousMonthStarting,PreviousMonthEnding,LastMonthEnding,ThisMonthStarting)

    # Return the dates as a dictionary
    return {
        "Today": Today,
        "MonthStarting": MonthStarting,
        "MonthEnding": MonthEnding,
        "PreviousMonthStarting": PreviousMonthStarting,
        "PreviousMonthEnding": PreviousMonthEnding
    }



# @frappe.whitelist()
# def Get_MasterData(Today,MonthStarting,ThisWeekStarting,ThisWeekEnding,PreviousWeekStarting,PreviousWeekEnding,LastMonthEnding):
 
#     date_objstarting = datetime.strptime(ThisWeekStarting, '%Y-%m-%d')
#     formatted_datestarted = date_objstarting.strftime('%d %B %Y')


#     formatted_dateStarting = date_objstarting.strftime('%B %Y')

#     date_objending = datetime.strptime(ThisWeekEnding, '%Y-%m-%d')
#     formatted_dateEnding= date_objending.strftime('%B %Y')
#     # print(formatted_date)
#     formatted_dateEnded = date_objending.strftime('%d %B %Y')
@frappe.whitelist()
def Get_MasterData(Today,MonthStarting,MonthEnding,PreviousMonthStarting,PreviousMonthEnding,LastMonthEnding,ThisMonthStarting):
    
    
    date_objstarting = datetime.strptime(MonthStarting, '%Y-%m-%d')
    # print(date_objstarting,'date_objstarting')
    
    formatted_datestarted = date_objstarting.strftime('%d %B %Y')
    # print(formatted_datestarted,'formatted_datestarted')

    
    formatted_dateStarting = date_objstarting.strftime('%B %Y')
    # print(formatted_dateStarting,'formatted_dateStarting')


    lastmonthEndiing = datetime.strptime(MonthStarting, '%Y-%m-%d')
    # print(lastmonthEndiing,'lastmonthEndiing')
    
    formatted_datelastMonthEnding = lastmonthEndiing.strftime('%d %B %Y')

    print(formatted_datelastMonthEnding,'formatted_datelastMonthEnding')



    date_objstarted = datetime.strptime(MonthStarting, '%Y-%m-%d')
    formatted_dateEnding= date_objstarted.strftime('%B %Y')
    print(formatted_dateEnding,'formatted_dateEnding')
    


    date_objending = datetime.strptime(MonthEnding, '%Y-%m-%d')
    formatted_dateEnded = date_objending.strftime('%d %B %Y')
    print(formatted_dateEnded,'formatted_dateEnded')



    date_obj_thisStarting = datetime.strptime(ThisMonthStarting, '%Y-%m-%d')
    formatted_dateThisStarting = date_obj_thisStarting.strftime('%d %B %Y')
    print(formatted_dateThisStarting,'formatted_dateEnded')







    channel_Mapping=Get_File('https://dev.khanaltech.com/files/Channal Mapping.xlsx','Sheet1')
    # !--------
    invoice_df =Ar_Invoice_List(PreviousMonthStarting,Today)
    credit_df=CreditNote_List(PreviousMonthStarting,Today)
    # Incomingpayment_dflist= IncomingPayment_List(MonthStarting,Today)
    # Incomingpayment_dflist =pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Export_Incoming payments upto Aug 08 with DocCurrency Part 2.xlsx.xlsx')
    # credit_df =pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/June to Aug CNPart 1.xlsx')
    # invoice_df=pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/June to Augpart 1.xlsx')

    # !--------


    print(MonthStarting,ThisMonthStarting,PreviousMonthStarting,MonthStarting,MonthStarting,Today,'MonMonthStarting,ThisMonthStarting,PreviousMonthStarting,MonthStarting,MonthStarting,Todayy','\n\n\n\n')
    MonthlyData=EcomReport(MonthStarting,ThisMonthStarting,invoice_df,credit_df,channel_Mapping)
    previousData=EcomReport(PreviousMonthStarting,MonthStarting,invoice_df,credit_df,channel_Mapping)
    MTDData=EcomReport(MonthStarting,Today,invoice_df,credit_df,channel_Mapping)
   
    # EmailTemplate_Doc = frappe.get_doc('Email Template', 'Ecommerce Revenue')



    
  
    if isinstance(MonthStarting, str):
        MonthStarting = datetime.strptime(MonthStarting, '%Y-%m-%d').date()
        print('\n\n', MonthStarting, 'MonthStarting strptime')
    
    if isinstance(ThisMonthStarting, str):
        ThisMonthStarting_str = datetime.strptime(ThisMonthStarting, '%Y-%m-%d').date()

    # Incomingpayment_dflist['DocDate'] = pd.to_datetime(Incomingpayment_dflist['DocDate']).dt.date

 
    # Incomingpayment_dflist = Incomingpayment_dflist[(Incomingpayment_dflist['DocDate'] >= MonthStarting) & (Incomingpayment_dflist['DocDate'] <= ThisMonthStarting_str)]

    # InComingPayment_df = Incomingpayment_dflist.groupby('CardCode')['TransferSum'].sum().reset_index()
    # InComingPayment_df.rename(columns={'TransferSum': 'PaymentsReceived'}, inplace=True)

    print(MonthStarting,ThisMonthStarting,'\n\n\n\n','****')
    PreviousMonthEndingAging=Make_AgeingReport(MonthStarting)['CustomerData']
    LastWeakingAging=Make_AgeingReport(ThisMonthStarting)['CustomerData']
    # LastWeakingAging.to_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/LastWeakingAging.xlsx')
    # LastWeakingAging.to_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/LastWeakingAging.xlsx')
    merged_aging = pd.merge(PreviousMonthEndingAging, LastWeakingAging, on='Customer/Vendor Code', suffixes=('_LastMonth', '_ThisWeek'))

    # Extract Balance Due columns
    merged_aging['Balance Due_LastMonth'] = merged_aging['Balance Due_LastMonth']
    merged_aging['Balance Due_ThisWeek'] = merged_aging['Balance Due_ThisWeek']
    # Select relevant columns if needed
    final_aging = merged_aging[['Customer/Vendor Code', 'Balance Due_LastMonth', 'Balance Due_ThisWeek']]
    # Example print statement to check the final merged data
    # print(final_aging,'final_aging','\n\n\n\n')




    # withAgeing = pd.merge(MonthlyData, final_aging, left_on=('Card Code'), right_on='Customer/Vendor Code', how='left')

    # Drop the 'Customer/Vendor Code' column as it is no longer needed
    # withAgeing.drop(columns=['Customer/Vendor Code'], inplace=True)

    # Rename the merged column to fit the multi-level header structure




    result_df = pd.merge(MonthlyData, previousData, on='Card Code', how='left',suffixes=('_Monthly', '_Prv'))
    result_df['percentage'] = (result_df['Revenue (Invoice - Return)_Monthly'] - result_df['Revenue (Invoice - Return)_Prv']) / result_df['Revenue (Invoice - Return)_Prv'] * 100

    
    result_df['Total Cogs']=result_df['Cogs Total Price_Invoice_Monthly'] - result_df['Cogs Total Price_Return_Monthly']
    result_df['Total Cogs_Prv']=result_df['Cogs Total Price_Invoice_Prv'] - result_df['Cogs Total Price_Return_Prv']

    
    # columns_to_drop = [col for col in result_df.columns if col.endswith('_Prv')]

    # Step 2: Drop these columns
    # result_df.drop(columns=columns_to_drop, inplace=True)
    columns_to_rename = {col: col.replace('_Monthly', '') for col in result_df.columns if col.endswith('_Monthly')}

    # Step 2: Rename these columns
    result_df.rename(columns=columns_to_rename, inplace=True)

    merged_df = pd.merge(result_df, MTDData, on='Card Code', suffixes=('_Monthly', '_MTD'))
    
    print(merged_df.columns,'merged_df.columns','\n\n\n')

    merged_df['PNL'] = merged_df['Revenue (Invoice - Return)_Monthly'] - merged_df['Total Cogs'] 
    merged_df['PNL_Prv'] = merged_df['Revenue (Invoice - Return)_Prv'] - merged_df['Total Cogs_Prv'] 
    # merged_df['PNL MoM'] = (merged_df['Revenue (Invoice - Return)_Monthly'] - merged_df['Total Cogs'] )
    merged_df['PNL MoM'] = (merged_df['PNL'] - merged_df['PNL_Prv']) / merged_df['PNL_Prv'] * 100

    merged_df['PNL Percentage'] = merged_df['PNL'] / merged_df['Revenue (Invoice - Return)_Monthly'] * 100

    columns_to_drop = [col for col in merged_df.columns if col.endswith('_Prv')]

    # Step 2: Drop these columns
    merged_df.drop(columns=columns_to_drop, inplace=True)

    # FinalDf = pd.merge(merged_df, InComingPayment_df[['CardCode', 'PaymentsReceived']], left_on='Card Code', right_on='CardCode', how='left')
    # FinalDf = FinalDf.sort_values(by='Revenue (Invoice - Return)_Monthly', ascending=False)
    # print(FinalDf)
    # print(FinalDf,'FinalDf')
    

    FinalDf = pd.merge(merged_df, final_aging, left_on=('Card Code'), right_on='Customer/Vendor Code', how='left')

    # Drop the 'Customer/Vendor Code' column as it is no longer needed
    FinalDf.drop(columns=['Customer/Vendor Code'], inplace=True)

    FinalDf.to_excel('/Users/shahilkhan/Desktop/WorkSpace/July Datawith COGS.xlsx')
    cols_to_format = FinalDf.columns[~FinalDf.columns.isin(['Channel/Customer','Card Code','Card Name_Monthly','Card Name_MTD','CardCode'])]
    # print(cols_to_format,'cols_to_format')
    FinalDf[cols_to_format] = FinalDf[cols_to_format].applymap(currencyFormatInWords)


    lastmonthEndiing = datetime.combine(MonthStarting, datetime.min.time())

    print(lastmonthEndiing,'***************')
    
    formatted_datelastMonthEnding = lastmonthEndiing.strftime('%d %B %Y')
    # lastmonthEndiing = datetime.strptime(MonthStarting, '%Y-%m-%d')


    print('\n\n',FinalDf,'FinalDf','\n\n')
    print('\n\n',FinalDf.columns,'FinalDf.columns','\n\n')

    print(formatted_dateEnded,'formatted_dateEnded')
    print(formatted_dateEnding,'formatted_dateEndingformatted_dateEnding')

    weeklyColumn = pd.MultiIndex.from_tuples([
    ('Channel/Customer',),
    (f'Total Outstanding {formatted_datelastMonthEnding}',),
    ('Invoiced',),
    ('COGS',),
    ('Returns',),
    ('Revenue',),
    ('P&L',),
    ('P&L Percentage',),
    (f'Payments Received {formatted_dateEnding}',),
    (f'Total Outstanding {formatted_dateThisStarting}',),
    ('percentage',),
    ('PNL MoM',)
    ])

    # Define the columns for the second DataFrame
    # MtdColumn = pd.MultiIndex.from_tuples([
    #     ('Channel/Customer',),
    #     (f'Total Outstanding {formatted_datelastMonthEnding}',),
    #     ('Invoiced',),
    #     ('Returns',),
    #     ('Revenue',),
    #     (f'Total Outstanding {formatted_dateEnded}',),
    #     (f'Payments Received {formatted_dateEnding}',)
    # ])

    # # # # # Create the final DataFrame with the multi-level columns
    weekly_df = pd.DataFrame(columns=weeklyColumn)
    weekly_df['Channel/Customer'] = FinalDf['Card Name_Monthly']
    weekly_df[f'Total Outstanding {formatted_datelastMonthEnding}'] = FinalDf['Balance Due_LastMonth']
    weekly_df['Invoiced'] = FinalDf['Invoice Total (in Rs.)_Monthly']
    weekly_df['COGS'] = FinalDf['Total Cogs']
    weekly_df['Returns'] = FinalDf['Return Total (in Rs.)_Monthly']
    weekly_df['Revenue'] = FinalDf['Revenue (Invoice - Return)_Monthly']
    weekly_df['P&L'] = FinalDf['PNL']
    weekly_df['P&L Percentage'] = FinalDf['PNL Percentage'].astype(str) + ' %'
    weekly_df[f'Payments Received {formatted_dateEnding}'] = FinalDf['PaymentsReceived']
    weekly_df[f'Total Outstanding {formatted_dateThisStarting}'] = FinalDf['Balance Due_ThisWeek']
    weekly_df['percentage'] = FinalDf['percentage']
    weekly_df['PNL MoM'] = FinalDf['PNL MoM']
        
    

    # Mtd_df = pd.DataFrame(columns=MtdColumn)
    # Mtd_df['Channel/Customer'] = FinalDf['Card Name_Monthly']
    # Mtd_df[f'Total Outstanding {formatted_datelastMonthEnding}'] = FinalDf['Balance Due_LastMonth']
    # Mtd_df['Invoiced'] = FinalDf['Invoice Total (in Rs.)_MTD']
    # Mtd_df['Returns'] = FinalDf['Return Total (in Rs.)_MTD']
    # Mtd_df['Revenue'] = FinalDf['Revenue (Invoice - Return)_MTD']
    # Mtd_df[f'Total Outstanding {formatted_dateEnded}'] = FinalDf['Balance Due_ThisWeek']
    # Mtd_df[f'Payments Received {formatted_dateEnding}'] = FinalDf['PaymentsReceived']



 

    # Mtd_df=''
    # CommonTabletructure=EmailFormat(weekly_df,Mtd_df,EmailTemplate_Doc,formatted_dateEnding,formatted_datestarted,formatted_dateEnded,channel_Mapping,Today,MonthStarting,'Monthly')
    # print(formatted_datestarted,formatted_dateEnded,'&&&&&&&&&&&&&&&************')
    # EmailTemplate(CommonTabletructure,EmailTemplate_Doc,formatted_datestarted,formatted_dateEnded,'Monthly')
