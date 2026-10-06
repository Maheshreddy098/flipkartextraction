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

from khanal_tech_integrations.utils.Finance.AgeingReport import Make_AgeingReportForExport
from khanal_tech_integrations.utils.Report.Ar_invoice import Ar_Invoice_List
from khanal_tech_integrations.utils.Report.Ar_CreditNote import CreditNote_List
from khanal_tech_integrations.utils.Report.IncomingPayment import IncomingPayment_List

from khanal_tech_integrations.utils.Finance.AgeingReport import Get_File
from khanal_tech_integrations.utils.Report.GetSalesEmployee import ExportEmployeeList
from khanal_tech_integrations.utils.Report.Ecom.EcomCommonFile import currencyFormatInWords


from khanal_tech_integrations.utils.Report.Export.ExportCommonFile import EmailTemplate,EmailFormat,EcomReport

# from khanal_tech_integrations.utils.Report.Ecom.EcomCommonFile import EcomReport,currencyFormatInWords,EmailFormat,EmailTemplate


#! bench --site dev.localhost execute   khanal_tech_integrations.utils.Report.Export.ExportReport_Monthly.MonthlyReport


@frappe.whitelist()
def MonthlyReport():
    Today = nowdate()
    ThisMonthStarting = get_first_day(add_to_date(Today, days=-1)).strftime("%Y-%m-%d")

    MonthStarting = get_first_day(add_to_date(Today, months=-1)).strftime("%Y-%m-%d")
    MonthEnding = get_last_day(add_to_date(Today, months=-1)).strftime("%Y-%m-%d")

    PreviousMonthStarting = get_first_day(add_to_date(Today, months=-2)).strftime("%Y-%m-%d")
    PreviousMonthEnding = get_last_day(add_to_date(Today, months=-2)).strftime("%Y-%m-%d")

    

    LastMonthEnding=get_last_day(add_to_date(Today, months=-3)).strftime("%Y-%m-%d")

    # Print the dates for debugging
    data={
        "Today": Today,
        "ThisMonthStarting":ThisMonthStarting,
        "MonthStarting": MonthStarting,
        "MonthEnding": MonthEnding,
        "PreviousMonthStarting": PreviousMonthStarting,
        "PreviousMonthEnding": PreviousMonthEnding,
        "LastMonthEnding": LastMonthEnding
        
        }
    print(data,'data')

    To_Report=Get_MasterData(Today,MonthStarting,MonthEnding,PreviousMonthStarting,PreviousMonthEnding,LastMonthEnding,ThisMonthStarting)

    # Return the dates as a dictionary
    return {
        "Today": Today,
        "MonthStarting": MonthStarting,
        "MonthEnding": MonthEnding,
        "PreviousMonthStarting": PreviousMonthStarting,
        "PreviousMonthEnding": PreviousMonthEnding
    }



@frappe.whitelist()
def Get_MasterData(Today,MonthStarting,MonthEnding,PreviousMonthStarting,PreviousMonthEnding,LastMonthEnding,ThisMonthStarting):
 
    date_objstarting = datetime.strptime(MonthStarting, '%Y-%m-%d')
    # print(date_objstarting,'date_objstarting')
    
    formatted_datestarted = date_objstarting.strftime('%d %B %Y')
    # print(formatted_datestarted,'formatted_datestarted')

    
    formatted_dateStarting = date_objstarting.strftime('%B %Y')
    # print(formatted_dateStarting,'formatted_dateStarting')

    date_objstarted = datetime.strptime(MonthStarting, '%Y-%m-%d')
    formatted_dateEnding= date_objstarted.strftime('%B %Y')
    print(formatted_dateEnding,'formatted_dateEnding')
    
    # formatted_dateEnded = date_objending.strftime('%d %B %Y')
    # print(formatted_dateEnded,'formatted_dateEnded','\n\n')


    lastmonthEndiing = datetime.strptime(MonthStarting, '%Y-%m-%d')
    # print(lastmonthEndiing,'lastmonthEndiing')
    # print(LastMonthEnding,'LastMonthEnding')
    # print(lastmonthEndiing,'lastmonthEndiing')
    
    formatted_datelastMonthEnding = lastmonthEndiing.strftime('%d %B %Y')
    print(formatted_datelastMonthEnding,'formatted_datelastMonthEnding')
    # print(formatted_datelastMonthEnding,'formatted_datelastMonthEnding')

    
    # formatted_datelastMonthEnding = lastmonthEndiing.strftime('%B %Y')
    # print(formatted_datelastMonthEnding,'formatted_datelastMonthEnding')



    

    date_objending = datetime.strptime(MonthEnding, '%Y-%m-%d')
    formatted_dateEnded = date_objending.strftime('%d %B %Y')
    print(formatted_dateEnded,'formatted_dateEnded')

    date_obj_thisStarting = datetime.strptime(ThisMonthStarting, '%Y-%m-%d')
    formatted_dateThisStarting = date_obj_thisStarting.strftime('%d %B %Y')



    

    # !---------
    channel_Mapping=ExportEmployeeList()
    # invoice_df =Ar_Invoice_List(PreviousMonthStarting,Today)
    # credit_df=CreditNote_List(PreviousMonthStarting,Today)
    # Incomingpayment_dflist= IncomingPayment_List(MonthStarting,Today)
    Incomingpayment_dflist =pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/_Incoming payments upto Aug 08 with DocCurrency Part 2.xlsx')
    credit_df =pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/June to Aug CNPart 1.xlsx')
    invoice_df=pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/June to Augpart 1.xlsx')

  
    if isinstance(MonthStarting, str):
        MonthStarting = datetime.strptime(MonthStarting, '%Y-%m-%d').date()
        print('\n\n', MonthStarting, 'MonthStarting strptime')
    
    if isinstance(ThisMonthStarting, str):
        ThisMonthStarting_str = datetime.strptime(ThisMonthStarting, '%Y-%m-%d').date()

    Incomingpayment_dflist['DocDate'] = pd.to_datetime(Incomingpayment_dflist['DocDate']).dt.date

 
    Incomingpayment_dflist = Incomingpayment_dflist[(Incomingpayment_dflist['DocDate'] >= MonthStarting) & (Incomingpayment_dflist['DocDate'] <= ThisMonthStarting_str)]

    # InComingPayment_df = Incomingpayment_dflist.groupby('CardCode')['FCTotal'].sum().reset_index()
    # InComingPayment_df.rename(columns={'FCTotal': 'PaymentsReceived'}, inplace=True)
    InComingPayment_df = Incomingpayment_dflist.groupby('CardCode')[['FCTotal', 'TransferSum']].sum().reset_index()
    InComingPayment_df.rename(columns={'FCTotal': 'PaymentsReceived FC', 'TransferSum': 'PaymentsReceived'}, inplace=True)





    
    weeklyData=EcomReport(MonthStarting,ThisMonthStarting,invoice_df,credit_df,channel_Mapping)
    # print(weeklyData,'weeklyData','\n\n\n')
    previousData=EcomReport(PreviousMonthStarting,MonthStarting,invoice_df,credit_df,channel_Mapping)
    MTDData=EcomReport(MonthStarting,Today,invoice_df,credit_df,channel_Mapping)
  
    EmailTemplate_Doc = frappe.get_doc('Email Template', 'Export Revenue')

    PreviousMonthEndinggAging=Make_AgeingReportForExport(MonthStarting)['CustomerData']

    LastWeakingAging=Make_AgeingReportForExport(ThisMonthStarting)['CustomerData']
 
    # merged_aging = pd.merge(PreviousMonthEndinggAging, LastWeakingAging, on='Customer/Vendor Code', suffixes=('_ThisMonth', '_LastMonth'))
    merged_aging = pd.merge(PreviousMonthEndinggAging, LastWeakingAging, how='right' ,left_on=['Customer/Vendor Code'],right_on=['Customer/Vendor Code'], suffixes=('_ThisMonth', '_LastMonth'))
    # how='left'
    #  merged_df = pd.merge(grouped_df, batchprice_df, how='left', left_on=['Vendor Batch Number', 'Item SKU Code'], right_on=['Batch Number', 'Item No.'])

    merged_aging.to_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/merged_aging pRT 3.xlsx')
    # Extract Balance Due columns
    merged_aging['FC Balance Due_ThisMonth'] = merged_aging['FC Balance Due_ThisMonth']
    merged_aging['FC Balance Due_LastMonth'] = merged_aging['FC Balance Due_LastMonth']

    # Select relevant columns if needed
    final_aging = merged_aging[['Customer/Vendor Code', 'FC Balance Due_ThisMonth', 'FC Balance Due_LastMonth']]

    # Example print statement to check the final merged data
    # print(final_aging,'final_aging','\n\n\n\n')






    result_df = pd.merge(weeklyData, previousData, on='Card Code', how='left',suffixes=('_Monthly', '_Prv'))
    result_df['percentage'] = (result_df['Revenue (Invoice - Return)_Monthly'] - result_df['Revenue (Invoice - Return)_Prv']) / result_df['Revenue (Invoice - Return)_Prv'] * 100
    

    result_df['Total Cogs']=result_df['Cogs Total Price_Invoice_Monthly'] - result_df['Cogs Total Price_Return_Monthly']
    result_df['Total Cogs_Prv']=result_df['Cogs Total Price_Invoice_Prv'] - result_df['Cogs Total Price_Return_Prv']

    # result_df.to_excel('/Users/shahilkhan/Desktop/WorkSpace/Ecom/percentageValue 1.xlsx')
    
    columns_to_rename = {col: col.replace('_Monthly', '') for col in result_df.columns if col.endswith('_Monthly')}

    # Step 2: Rename these columns
    result_df.rename(columns=columns_to_rename, inplace=True)

    

    merged_df = pd.merge(result_df, MTDData, on='Card Code', suffixes=('_Monthly', '_MTD'))
    
    # merged_df.to_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/merged_df result_df MTDData 1.xlsx')


    # print(merged_df.columns)
    # print(merged_df,'\n\n')


    merged_df['PNL'] = merged_df['Revenue (Invoice - Return)_Monthly'] - merged_df['Total Cogs'] 
    merged_df['PNL_Prv'] = merged_df['Revenue (Invoice - Return)_Prv'] - merged_df['Total Cogs_Prv'] 
    # merged_df['PNL percentage'] = (merged_df['Revenue (Invoice - Return)_Monthly'] - merged_df['Total Cogs'] )
    merged_df['PNL MoM'] = (merged_df['PNL'] - merged_df['PNL_Prv']) / merged_df['PNL_Prv'] * 100
    merged_df['PNL Percentage'] = merged_df['PNL'] / merged_df['Revenue (Invoice - Return)_Monthly'] * 100
    # merged_df = pd.merge(channel_Mapping, merged_df, on='CardCode', how='left')
    result = pd.merge(channel_Mapping, merged_df, left_on='CardCode', right_on='Card Code', how='left')

    # Optionally, drop the redundant 'Card Code' column after merging if it's no longer needed
    result.drop(columns=['Card Code'], inplace=True)




    result = result.sort_values(by='Revenue (Invoice - Return)_Monthly', ascending=False)
    # result.to_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/result 1.xlsx')
    FinalDf = pd.merge(result, final_aging, left_on=('CardCode'), right_on='Customer/Vendor Code', how='left')



    print(FinalDf,'before MergibngFinalDf','\n\n\n')
    # FinalDf.to_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/FinalDf 1.xlsx')
    # result_df.to_excel('/Users/shahilkhan/Desktop/WorkSpace/Ecom/percentageValue 1.xlsx')
    # Drop the 'Customer/Vendor Code' column as it is no longer needed
    FinalDf.drop(columns=['Customer/Vendor Code'], inplace=True)

    # Rename the merged column to fit the multi-level header structure
    # FinalDf[('Critical Outstanding (>60 days)')] = FinalDf.pop('Critical Outstanding (>60 days)')

    FinalDf = pd.merge(FinalDf, InComingPayment_df[['CardCode', 'PaymentsReceived','PaymentsReceived FC']], on='CardCode', how='left')

    columns_to_drop = [col for col in FinalDf.columns if col.endswith('_Prv')]

    # # Step 2: Drop these columns
    FinalDf.drop(columns=columns_to_drop, inplace=True)
    print(FinalDf,'FinalDf','\n\n\n\n\n')
    
    print(FinalDf.columns,'result_df.columns','\n\n')
    # cols_to_format = FinalDf.columns[~FinalDf.columns.isin(['CardName','CardCode','SalesEmployeeName','Email','Card Name_Monthly','Card Name_MTD','Currency'])]
    # print(cols_to_format,'cols_to_format')
    # FinalDf[cols_to_format] = FinalDf[cols_to_format].applymap(currencyFormatInWords)

    FinalDf.replace('nan', float(0), inplace=True)




    # weeklyColumn = pd.MultiIndex.from_tuples([
    # ('Channel/Customer',),
    # (f'Total Outstanding {formatted_datelastMonthEnding}',),
    # ('Invoiced',),
    # ('Cogs',),
    # ('Returns',),
    # ('Revenue',),
    # ('PNL',),
    # (f'Total Outstanding {formatted_dateEnded}',),
    # (f'Payments Received {formatted_dateEnding}',)
    # ('percentage',),
    # ('PNL percentage',)
    
    
    # ])

    # # Define the columns for the second DataFrame
    # MtdColumn = pd.MultiIndex.from_tuples([
    #     ('Channel/Customer',),
    #     (f'Total Outstanding {formatted_datelastMonthEnding}',),
    #     ('Invoiced',),
    #     ('Returns',),
    #     ('Revenue',),
    #     (f'Total Outstanding {formatted_dateEnded}',),
    #     (f'Payments Received {formatted_dateEnding}',)
    # ])
    weeklyColumn = pd.MultiIndex.from_tuples([
    ('Channel/Customer',),
    ('Currency',),
    (f'Total Outstanding {formatted_datelastMonthEnding}',),
    ('Invoiced',),
    ('FCInvoiced',),
    ('COGS',),
    ('Returns',),
    ('FCReturns',),
    ('Revenue',),
    ('FCRevenue',),
    ('P&L',),
    ('P&L Percentage',),
    (f'Payments Received {formatted_dateEnding} (INR)',),
    (f'Payments Received {formatted_dateEnding} (FC)',),
    (f'Total Outstanding {formatted_dateThisStarting}',),
    ('percentage',),
    ('PNL MoM',)
    ])

    weekly_df = pd.DataFrame(columns=weeklyColumn)
    weekly_df['Channel/Customer'] = FinalDf['CardName']
    weekly_df['Currency'] = FinalDf['Currency']
    weekly_df[f'Total Outstanding {formatted_datelastMonthEnding}'] = FinalDf['FC Balance Due_ThisMonth']
    weekly_df['Invoiced'] = FinalDf['Invoice Total (in Rs.)_Monthly']
    weekly_df['FCInvoiced'] = FinalDf['FCInvoiced_Monthly']
    weekly_df['COGS'] = FinalDf['Total Cogs']
    weekly_df['Returns'] = FinalDf['Return Total (in Rs.)_Monthly']
    weekly_df['FCReturns'] = FinalDf['FCReturns_Monthly']
    weekly_df['Revenue'] = FinalDf['Revenue (Invoice - Return)_Monthly']
    weekly_df['FCRevenue'] = FinalDf['FCRevenue_Monthly']
    weekly_df['P&L'] = FinalDf['PNL']
    weekly_df['P&L Percentage'] =FinalDf['PNL Percentage'].astype(str) + ' %'
    weekly_df[f'Payments Received {formatted_dateEnding} (INR)'] = FinalDf['PaymentsReceived']
    weekly_df[f'Payments Received {formatted_dateEnding} (FC)'] = FinalDf['PaymentsReceived FC']
    weekly_df[f'Total Outstanding {formatted_dateThisStarting}'] = FinalDf['FC Balance Due_LastMonth']
    weekly_df['percentage'] = FinalDf['percentage']
    weekly_df['PNL MoM'] = FinalDf['PNL MoM']


    # weekly_df.to_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/Monthlydata With FC Aug 09 part 6.xlsx')

        
    # Group by email and create DataFrames
    # for email, FinalDf in FinalDf.groupby('Email'):
    #     sales_employee_name = FinalDf['SalesEmployeeName'].iloc[0]
  
    #     weekly_df = pd.DataFrame(columns=weeklyColumn)
    #     weekly_df['Channel/Customer'] = FinalDf['CardName']
    #     weekly_df['Currency'] = FinalDf['Currency']
    #     weekly_df[f'Total Outstanding {formatted_datelastMonthEnding}'] = FinalDf['FC Balance Due_ThisMonth']
    #     weekly_df['Invoiced'] = FinalDf['Invoice Total (in Rs.)_Monthly']
    #     weekly_df['COGS'] = FinalDf['Total Cogs']
    #     weekly_df['Returns'] = FinalDf['Return Total (in Rs.)_Monthly']
    #     weekly_df['Revenue'] = FinalDf['Revenue (Invoice - Return)_Monthly']
    #     weekly_df['P&L'] = FinalDf['PNL']
    #     weekly_df['P&L Percentage'] =FinalDf['PNL Percentage'].astype(str) + ' %'
    #     weekly_df[f'Payments Received {formatted_dateEnding} (INR)'] = FinalDf['PaymentsReceived']
    #     weekly_df[f'Total Outstanding {formatted_dateThisStarting}'] = FinalDf['FC Balance Due_LastMonth']
    #     weekly_df['percentage'] = FinalDf['percentage']
    #     weekly_df['PNL MoM'] = FinalDf['PNL MoM']
        
       
    #     Mtd_df=''
    #     CommonTableStructure = EmailFormat(weekly_df,Mtd_df, EmailTemplate_Doc ,formatted_dateEnding, formatted_datestarted, formatted_dateEnded, channel_Mapping,sales_employee_name,Today,MonthStarting,'Monthly')
        
    #     # Send the email
    #     EmailTemplate(CommonTableStructure, EmailTemplate_Doc, formatted_datestarted, formatted_dateEnded,email,'Monthly')

        