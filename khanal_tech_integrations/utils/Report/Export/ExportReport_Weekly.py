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
from khanal_tech_integrations.utils.Finance.AgeingReport import Make_AgeingReport
from khanal_tech_integrations.utils.Report.Ar_invoice import Ar_Invoice_List
from khanal_tech_integrations.utils.Report.Ar_CreditNote import CreditNote_List
from khanal_tech_integrations.utils.Report.IncomingPayment import IncomingPayment_List

from khanal_tech_integrations.utils.Finance.AgeingReport import Get_File
from khanal_tech_integrations.utils.Report.GetSalesEmployee import ExportEmployeeList
from khanal_tech_integrations.utils.Report.Ecom.EcomCommonFile import currencyFormatInWords

from khanal_tech_integrations.utils.Report.Export.ExportCommonFile import EmailTemplate,EcomReport,EmailFormat



#! bench --site dev.localhost execute   khanal_tech_integrations.utils.Report.Export.ExportReport_Weekly.WeeklyReport

#! bench --site khanaltech.com execute   khanal_tech_integrations.utils.Report.Export.ExportReport_Weekly.WeeklyReport


@frappe.whitelist()
def WeeklyReport():
    Today = nowdate()
    # Today='2024-06-17'
    # Get the first day of the current month
    MonthStarting = get_first_day(Today)

   
    # Calculate the start and end dates for the current week
    ThisWeekStarting = (datetime.strptime(Today, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
    ThisWeekEnding = (datetime.strptime(ThisWeekStarting, "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%d")

    # ThisWeekStarting='2024-06-01'
    # ThisWeekEnding='2024-06-30'
    # Calculate the start and end dates for the previous week
    PreviousWeekStarting = (datetime.strptime(ThisWeekStarting, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
    PreviousWeekEnding = (datetime.strptime(ThisWeekStarting, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")

    # PreviousWeekStarting='2024-05-01'
    # PreviousWeekEnding='2024-05-31'
    LastMonthEnding= (MonthStarting - timedelta(days=1)).strftime("%Y-%m-%d")


    # Print the dates for debugging
    print("Today:", Today)
    print("Month Starting:", MonthStarting)
    print("Last Month Ending:", LastMonthEnding)
    print("This Week Starting:", ThisWeekStarting)
    print("This Week Ending:", ThisWeekEnding)
    print("Previous Week Starting:", PreviousWeekStarting)
    print("Previous Week Ending:", PreviousWeekEnding)

    To_Report=Get_MasterData(Today,MonthStarting,ThisWeekStarting,ThisWeekEnding,PreviousWeekStarting,PreviousWeekEnding,LastMonthEnding)

    # Return the dates as a dictionary
    return {
        "Today": Today,
        "MonthStarting": MonthStarting,
        "ThisWeekStarting": ThisWeekStarting,
        "ThisWeekEnding": ThisWeekEnding,
        "PreviousWeekStarting": PreviousWeekStarting,
        "PreviousWeekEnding": PreviousWeekEnding
    }





@frappe.whitelist()
def Get_MasterData(Today,MonthStarting,ThisWeekStarting,ThisWeekEnding,PreviousWeekStarting,PreviousWeekEnding,LastMonthEnding):
 
    date_objstarting = datetime.strptime(ThisWeekStarting, '%Y-%m-%d')
    # print(date_objstarting,'date_objstarting')
    
    formatted_datestarted = date_objstarting.strftime('%d %B %Y')
    # print(formatted_datestarted,'formatted_datestarted')

    
    formatted_dateStarting = date_objstarting.strftime('%B %Y')
    # print(formatted_dateStarting,'formatted_dateStarting')

    date_objending = datetime.strptime(ThisWeekEnding, '%Y-%m-%d')
    formatted_dateEnding= date_objending.strftime('%B %Y')
    
    formatted_dateEnded = date_objending.strftime('%d %B %Y')
    # print(formatted_dateEnded)


    lastmonthEndiing = datetime.strptime(LastMonthEnding, '%Y-%m-%d')
    formatted_datelastMonthEnding = lastmonthEndiing.strftime('%d %B %Y')
    # print(formatted_datelastMonthEnding,'formatted_datelastMonthEnding')




    # !----------
    channel_Mapping=ExportEmployeeList()
    invoice_df =Ar_Invoice_List(PreviousWeekStarting,Today)
    credit_df=CreditNote_List(PreviousWeekStarting,Today)
    Incomingpayment_dflist= IncomingPayment_List(MonthStarting,Today)
    # Incomingpayment_dflist =pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/_May To July IncomingPayments For Monthly Report.xlsx')
    # credit_df =pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/May To July COMPLETE CreditNotes For Monthly Report.xlsx')
    # invoice_df=pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/all data from June to Augpart 2.xlsx')

    if isinstance(MonthStarting, str):
        MonthStarting = datetime.strptime(MonthStarting, '%Y-%m-%d').date()
        print('\n\n', MonthStarting, 'MonthStarting strptime')
    
    if isinstance(Today, str):
        Today_str = datetime.strptime(Today, '%Y-%m-%d').date()

    Incomingpayment_dflist['DocDate'] = pd.to_datetime(Incomingpayment_dflist['DocDate']).dt.date

    # Incomingpayment =pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Ecom/_Incoming Payment From Jan To July.xlsx')
    Incomingpayment_dflist = Incomingpayment_dflist[(Incomingpayment_dflist['DocDate'] >= MonthStarting) & (Incomingpayment_dflist['DocDate'] <= Today_str)]
    InComingPayment_df = Incomingpayment_dflist.groupby('CardCode')['TransferSum'].sum().reset_index()
    InComingPayment_df.rename(columns={'TransferSum': 'PaymentsReceived'}, inplace=True)



    weeklyData=EcomReport(ThisWeekStarting,ThisWeekEnding,invoice_df,credit_df,channel_Mapping)
    # print(weeklyData,'weeklyData','\n\n\n')
    previousData=EcomReport(PreviousWeekStarting,PreviousWeekEnding,invoice_df,credit_df,channel_Mapping)
    MTDData=EcomReport(MonthStarting,Today,invoice_df,credit_df,channel_Mapping)
    # weeklyData.to_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/weeklyData 4.xlsx')
    # previousData.to_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/previousData 1.xlsx')

    # MTDData.to_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/ MTDData 1.xlsx')



    # print(MTDData,'\n\n\n','MTDData')
   
    EmailTemplate_Doc = frappe.get_doc('Email Template', 'Export Revenue')

    LastMonthEndingAging=Make_AgeingReport(LastMonthEnding)['CustomerData']

    LastWeakingAging=Make_AgeingReport(ThisWeekEnding)['CustomerData']
 
    merged_aging = pd.merge(LastMonthEndingAging, LastWeakingAging, on='Customer/Vendor Code', suffixes=('_LastMonth', '_ThisWeek'))

    # Extract Balance Due columns
    merged_aging['Balance Due_LastMonth'] = merged_aging['Balance Due_LastMonth']
    merged_aging['Balance Due_ThisWeek'] = merged_aging['Balance Due_ThisWeek']

    # Select relevant columns if needed
    final_aging = merged_aging[['Customer/Vendor Code', 'Balance Due_LastMonth', 'Balance Due_ThisWeek']]

    # Example print statement to check the final merged data
    print(final_aging,'final_aging','\n\n\n\n')





    result_df = pd.merge(weeklyData, previousData, on='Card Code', how='left',suffixes=('_Weekly', '_Prv'))
    result_df['percentage'] = (result_df['Revenue (Invoice - Return)_Weekly'] - result_df['Revenue (Invoice - Return)_Prv']) / result_df['Revenue (Invoice - Return)_Prv'] * 100

    result_df['Total Cogs']=result_df['Cogs Total Price_Invoice_Weekly'] - result_df['Cogs Total Price_Return_Weekly']
    result_df['Total Cogs_Prv']=result_df['Cogs Total Price_Invoice_Prv'] - result_df['Cogs Total Price_Return_Prv']

    # result_df.to_excel('/Users/shahilkhan/Desktop/WorkSpace/Ecom/percentageValue 1.xlsx')
    # columns_to_drop = [col for col in result_df.columns if col.endswith('_Prv')]

    # # Step 2: Drop these columns
    # result_df.drop(columns=columns_to_drop, inplace=True)
    columns_to_rename = {col: col.replace('_Weekly', '') for col in result_df.columns if col.endswith('_Weekly')}

    # Step 2: Rename these columns
    result_df.rename(columns=columns_to_rename, inplace=True)

    

    merged_df = pd.merge(result_df, MTDData, on='Card Code', suffixes=('_Weekly', '_MTD'))
    
    # merged_df.to_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/merged_df result_df MTDData 1.xlsx')


    # print(merged_df.columns)
    # print(merged_df,'\n\n')


    merged_df['PNL'] = merged_df['Revenue (Invoice - Return)_Weekly'] - merged_df['Total Cogs'] 
    merged_df['PNL_Prv'] = merged_df['Revenue (Invoice - Return)_Prv'] - merged_df['Total Cogs_Prv'] 
    # merged_df['PNL WoW'] = (merged_df['Revenue (Invoice - Return)_Monthly'] - merged_df['Total Cogs'] )
    merged_df['PNL WoW'] = (merged_df['PNL'] - merged_df['PNL_Prv']) / merged_df['PNL_Prv'] * 100

    # merged_df['PNL percentage'] = (merged_df['Revenue (Invoice - Return)_Weekly'] - merged_df['Cogs Invoice Total (in Rs.)_Weekly']) / merged_df['Revenue (Invoice - Return)_Weekly'] * 100
    merged_df['PNL Percentage'] = merged_df['PNL'] / merged_df['Revenue (Invoice - Return)_Weekly'] * 100

    columns_to_drop = [col for col in merged_df.columns if col.endswith('_Prv')]

    # # Step 2: Drop these columns
    merged_df.drop(columns=columns_to_drop, inplace=True)

    # merged_df = pd.merge(channel_Mapping, merged_df, on='CardCode', how='left')
    result = pd.merge(channel_Mapping, merged_df, left_on='CardCode', right_on='Card Code', how='left')

    # Optionally, drop the redundant 'Card Code' column after merging if it's no longer needed
    result.drop(columns=['Card Code'], inplace=True)




    result = result.sort_values(by='Revenue (Invoice - Return)_Weekly', ascending=False)
    # result.to_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/result 1.xlsx')
    FinalDf = pd.merge(result, final_aging, left_on=('CardCode'), right_on='Customer/Vendor Code', how='left')



    print(FinalDf,'before MergibngFinalDf','\n\n\n')
    # FinalDf.to_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/FinalDf 1.xlsx')
    # result_df.to_excel('/Users/shahilkhan/Desktop/WorkSpace/Ecom/percentageValue 1.xlsx')
    # Drop the 'Customer/Vendor Code' column as it is no longer needed
    FinalDf.drop(columns=['Customer/Vendor Code'], inplace=True)

    # Rename the merged column to fit the multi-level header structure
    # FinalDf[('Critical Outstanding (>60 days)')] = FinalDf.pop('Critical Outstanding (>60 days)')

    FinalDf = pd.merge(FinalDf, InComingPayment_df[['CardCode', 'PaymentsReceived']], on='CardCode', how='left')


    print(FinalDf,'FinalDf','\n\n\n\n\n')
    

    cols_to_format = FinalDf.columns[~FinalDf.columns.isin(['CardName','CardCode','SalesEmployeeName','Email','Card Name_Weekly','Card Name_MTD'])]
    # print(cols_to_format,'cols_to_format')
    FinalDf[cols_to_format] = FinalDf[cols_to_format].applymap(currencyFormatInWords)

    FinalDf.replace('nan', float(0), inplace=True)




    weeklyColumn = pd.MultiIndex.from_tuples([
    ('Channel/Customer',),
    ('Invoiced',),
    ('COGS',),
    ('Returns',),
    ('Revenue',),
    ('P&L',),
    ('P&L Percentage',),
    ('percentage',),
    ('PNL WoW',),
    ])

    # Define the columns for the second DataFrame
    MtdColumn = pd.MultiIndex.from_tuples([
        ('Channel/Customer',),
        (f'Total Outstanding {formatted_datelastMonthEnding}',),
        ('Invoiced',),
        ('Returns',),
        ('Revenue',),
        (f'Total Outstanding {formatted_dateEnded}',),
        (f'Payments Received {formatted_dateEnding}',)
    ])

    # Group by email and create DataFrames
    for email, FinalDf in FinalDf.groupby('Email'):
        sales_employee_name = FinalDf['SalesEmployeeName'].iloc[0]
        
        # Create the first DataFrame
        weekly_df = pd.DataFrame(columns=weeklyColumn)
        weekly_df['Channel/Customer'] = FinalDf['CardName']
        weekly_df['Invoiced'] = FinalDf['Invoice Total (in Rs.)_Weekly']
        weekly_df['COGS'] = FinalDf['Total Cogs']
        weekly_df['Returns'] = FinalDf['Return Total (in Rs.)_Weekly']
        weekly_df['Revenue'] = FinalDf['Revenue (Invoice - Return)_Weekly']
        weekly_df['P&L'] = FinalDf['PNL']
        weekly_df['P&L Percentage'] = FinalDf['PNL Percentage'].astype(str) + ' %'
        weekly_df['percentage'] = FinalDf['percentage']
        weekly_df['PNL WoW'] = FinalDf['PNL WoW']
        
        # Create the second DataFrame
        Mtd_df = pd.DataFrame(columns=MtdColumn)
        Mtd_df['Channel/Customer'] = FinalDf['CardName']
        Mtd_df[f'Total Outstanding {formatted_datelastMonthEnding}'] = FinalDf['Balance Due_LastMonth']
        Mtd_df['Invoiced'] = FinalDf['Invoice Total (in Rs.)_MTD']
        Mtd_df['Returns'] = FinalDf['Return Total (in Rs.)_MTD']
        Mtd_df['Revenue'] = FinalDf['Revenue (Invoice - Return)_MTD']
        Mtd_df[f'Total Outstanding {formatted_dateEnded}'] = FinalDf['Balance Due_ThisWeek']
        Mtd_df[f'Payments Received {formatted_dateEnding}'] = FinalDf['PaymentsReceived']


        CommonTableStructure = EmailFormat(weekly_df,Mtd_df, EmailTemplate_Doc, formatted_dateEnding, formatted_datestarted, formatted_dateEnded, channel_Mapping,sales_employee_name,Today,MonthStarting,'Weekly')
        EmailTemplate(CommonTableStructure, EmailTemplate_Doc, formatted_datestarted, formatted_dateEnded,email,'Weekly')

        

