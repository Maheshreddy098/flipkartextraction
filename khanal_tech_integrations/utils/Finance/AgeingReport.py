
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
from frappe.utils import add_to_date
import decimal

from datetime import datetime


# locale.setlocale(locale.LC_NUMERIC, 'en_IN')




# columns_to_select = ['ReferenceDate', 'Memo','Reference','Debit','Credit','Customer/Vendor Code','DueDate','TaxDate']
# df = pd.read_csv('/Users/shahilkhan/Desktop/WorkSpace/Aging Report/journalentry/JournalEntries.csv', usecols=columns_to_select)


# csv_filename = '/Users/shahilkhan/Desktop/WorkSpace/Aging Report/journalentry/APIResponse/MAY 20/'
# csv_filename = '/Users/shahilkhan/Desktop/WorkSpace/Export/'
# # https://dev.khanaltech.com/files/Bp Master.xlsx
def Get_File(url,sheetname):
    response = requests.get(url, verify=False)
    if response.status_code == 200:
        df = pd.read_excel(response.content,sheetname)
        return df
    else:
        print(f"Error: Unable to retrieve data from {url}")

# BpData=pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Aging Report/journalentry/BP Data.xlsx')
BpData=Get_File('https://dev.khanaltech.com/files/Bp Master.xlsx','Sheet1')

#! bench --site khanaltech.com execute  --args "( '2024-08-04','2024-07-28' )"  khanal_tech_integrations.utils.Finance.AgeingReport.Get_MasterData
# bench --site khanaltech.com execute  --args "( '2024-06-16','2024-06-09' )"  khanal_tech_integrations.utils.Finance.AgeingReport.Get_MasterData

table_css_style = """
            <style>
            body {
                    font-family: Arial, sans-serif;
                }

                p {
                    font-size: 8px;
                    font-weight: bold;
                    margin-bottom: 10px;
                }
                .custom-table {
                border-collapse: collapse;
                width: 100%;
                .noncustom-table{
                     border-collapse: collapse;
                width: 100%;
                }
            }

            .custom-table th, .custom-table td {
                border: 1px solid #dddddd;
                text-align: left;
                padding: 6px;
            }
            .custom-table h1{
               margin-top: -33px !important;
                font-size: 14px !important;
            }
             .noncustom-table h1{
               margin-top: -33px !important;
                font-size: 14px !important;
            }

            .custom-table th {
                background-color: #f2f2f2;
            }

            .noncustom-table th, .noncustom-table td {
                border: 1px solid #dddddd;
                text-align: left;
                padding: 6px;
            }

            .noncustom-table th {
                background-color: #f2f2f2;
            }

            .custom-table tr:last-child {
                    background-color: #ffffcc; 
                    color:'black';
                    font-weight: 900;
                }
            </style>
            """


#! bench --site dev.localhost execute   khanal_tech_integrations.utils.Finance.AgeingReport.weekly_Report

# bench --site dev.localhost execute  --args "( '2024-05-26','2024-05-19' )"  khanal_tech_integrations.utils.Finance.AgeingReport.Get_MasterData
# bench --site khanaltech.com execute  --args "( '2024-05-26','2024-05-19' )"  khanal_tech_integrations.utils.Finance.AgeingReport.Get_MasterData

# grouped_invoice_df.to_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/grouped_invoice_df part 1.xlsx')
@frappe.whitelist()
def weekly_Report():
    Today = frappe.utils.nowdate()
    FilterDate = add_to_date(Today,days=-7)
    Get_MasterData(CurrentDate=Today,PreviousDate=FilterDate)

    pass


@frappe.whitelist()
def Get_MasterData(CurrentDate,PreviousDate):
    # print(StartDate,CurrentDate,PreviousDate,'\n\n\n\n')
    # new_date_str = datetime.strftime(CurrentDate, '%b %d %Y')


    masterDf=Make_AgeingReport(CurrentDate)
    PayablesData_df=ExtractData(masterDf['VendorData'],'Vendor')
    Receivables_df=ExtractData(masterDf['CustomerData'],'Customer')

    # MasterForAdvancePayment=AdvancePaymentDatadf(CurrentDate)
    # MasterForAdvancePayment=AdvancePaymentDatadf(CurrentDate)
    AdvancePayment_df=AdvancePayment(masterDf['VendorData'])



    #! ----------------------------------
    TotalSum=GetTotalSum(PayablesData_df,Receivables_df)
    Consolidated_AdvPayments=AdvPayments_Consolidated(masterDf['VendorData'])
    Vendor_Consolidated=Master_Consolidated(masterDf['VendorData'],'Vendor')
    Customer_Consolidated=Master_Consolidated(masterDf['CustomerData'],'Customer')

    # !-------------------------------------
    # !? Previous Weak DATA 

    previousmasterDf=Make_AgeingReport(PreviousDate)
    Previous_PayablesData_df=ExtractData(previousmasterDf['VendorData'],'Vendor')
    Previous_Receivables_df=ExtractData(previousmasterDf['CustomerData'],'Customer')



    SummaryData_result=SummaryData(PayablesData_df,Receivables_df,Previous_PayablesData_df,Previous_Receivables_df)

    # !-------------------------------------

    CommonTabletructure=EmailFormat(PayablesData_df,Receivables_df,AdvancePayment_df,TotalSum,Consolidated_AdvPayments,Vendor_Consolidated,Customer_Consolidated,Previous_PayablesData_df,Previous_Receivables_df,SummaryData_result)


    EmailTemplate(CommonTabletructure,CurrentDate)

    # Item_master=Get_File("http://beta.khanaltech.com/files/List of Items.xlsx",'Sheet1')


#! bench --site dev.localhost execute    khanal_tech_integrations.utils.Finance.AgeingReport.DataFormJournalEntries


def DataFormJournalEntries():

    # print(StartDate,'StartDate')
    # print(EndDate,'EndDate')
    JournalEntriesList_List = frappe.get_list('SAP Journal Entries',
                        # filters={
                        #     # 'referencedate': ['between', [StartDate, EndDate]],
                        #     # 'referencedate': ['<=', EndDate],
                        #     'customervendor_code': 'C03353',
                        #     # 'duedate': ['<=', EndDate],
                        # },
                        fields=['referencedate', 'memo', 'duedate', 'taxdate', 'reference', 'lineitem.customervendor_code', 'lineitem.debit', 'lineitem.credit','lineitem.fcdebit', 'lineitem.fccredit'], as_list=True,order_by='referencedate asc',

                        )

    print(len(JournalEntriesList_List), 'Length of JournalEntriesList_List')

    formatted_entries = []
    for entry in JournalEntriesList_List:
        # print(entry)
        entry_date = entry[0]
        formatted_date = entry_date.strftime('%Y-%m-%d') if entry_date else None

        duedate = entry[2]
        formatted_duedate = duedate.strftime('%Y-%m-%d') if duedate else None

       
        formatted_entry = (formatted_date,  entry[6], entry[7],entry[5],formatted_duedate,entry[8], entry[9])
        formatted_entries.append(formatted_entry)
 

    columns_to_select = ['ReferenceDate', 'Debit', 'Credit', 'Customer/Vendor Code', 'DueDate','FCDebit', 'FCCredit',]

    # Create DataFrame
    df = pd.DataFrame(formatted_entries, columns=columns_to_select)
    # print(formatted_entries,'formatted_entries')
    # Convert date columns to datetime objects
    date_columns = ['ReferenceDate', 'DueDate',]
    df[date_columns] = df[date_columns].apply(pd.to_datetime)

    numeric_columns = ['Debit', 'Credit','FCDebit','FCCredit']
    df[numeric_columns] = df[numeric_columns].apply(pd.to_numeric, errors='coerce')

    # df.to_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/C03353 aga.xlsx')
    return df

#! bench --site dev.localhost execute  --args "{ '2024-07-31' }"  khanal_tech_integrations.utils.Finance.AgeingReport.Make_AgeingReportForExport



def Make_AgeingReport(end_date):
    filtered_df=DataFormJournalEntries()
    # print(filtered_df,'Make_AgeingReport.Make_AgeingReportMake_AgeingReport')

    end_date = pd.to_datetime(end_date)

    filtered_df['ReferenceDate'] = pd.to_datetime(filtered_df['ReferenceDate'], format='%d/%m/%y', errors='coerce')
    filtered_df['DueDate'] = pd.to_datetime(filtered_df['DueDate'], format='%d/%m/%y', errors='coerce')


    # Filter data based on date range
    # filtered_df = df[(df['ReferenceDate'] <= end_date)]

    current_date = datetime.now()
    filtered_df['Age'] = (current_date - filtered_df['DueDate']).dt.days
    filtered_df = filtered_df.dropna(subset=['Customer/Vendor Code'])
    # filtered_df = filtered_df[filtered_df['Age'] >= 0]


    
    filtered_df = filtered_df[filtered_df['Customer/Vendor Code'].str[0].isin(['V', 'C', 'E'])]
    bins = [0, 30, 60, 90, 120, float('inf')]
    labels = ['0-30', '31-60', '61-90', '91-120', '120+']
    filtered_df['Age Group'] = pd.cut(filtered_df['Age'], bins=bins, labels=labels, right=False)
    filtered_df['Age Group'] = pd.Categorical(filtered_df['Age Group'], categories=labels, ordered=True)
  

    filtered_df['Total'] = filtered_df['Debit'] - filtered_df['Credit']

    
    grouped_totals = filtered_df.groupby('Customer/Vendor Code')[['Total']].sum()
    threshold = 10e-10  # Adjust the threshold as needed
    non_zero_groups = grouped_totals[abs(grouped_totals['Total']) > threshold]
    filtered_df = filtered_df[filtered_df['Customer/Vendor Code'].isin(non_zero_groups.index)]

    # filtered_df = filtered_df[(filtered_df['ReferenceDate'] <= end_date) & (filtered_df['DueDate'] <= end_date)]
    filtered_df = filtered_df[(filtered_df['ReferenceDate'] <= end_date)]

   




    aging_report = filtered_df.groupby(['Customer/Vendor Code', 'Age Group'], sort=False)[['Total']].sum().unstack(fill_value=0)

    # customer_totals = filtered_df.groupby('Customer/Vendor Code')[['Debit', 'Credit']].sum()
    customer_totals = filtered_df.groupby('Customer/Vendor Code')[['Debit', 'Credit']].sum()




    aging_report.columns = [' '.join(map(str, col)) for col in aging_report.columns]



    aging_report = aging_report.merge(customer_totals, how='left', on='Customer/Vendor Code')
    aging_report['Balance Due'] = aging_report['Debit'] - aging_report['Credit']
    # aging_report['FC Balance Due'] = aging_report['FCDebit'] - aging_report['FCCredit']
    aging_report.columns = labels + ['Total Debit', 'Total Credit', 'Balance Due']
    # aging_report.columns = labels + ['Total Debit', 'Total Credit', 'Balance Due']
    aging_report.index = aging_report.index.astype(str).fillna('')

    aging_report.reset_index(inplace=True)

  
    vendor_sheet = aging_report[aging_report['Customer/Vendor Code'].str.startswith('V')]
    customer_sheet = aging_report[aging_report['Customer/Vendor Code'].str.startswith('C')]
    employee_sheet = aging_report[aging_report['Customer/Vendor Code'].str.startswith('E')]
    excel_buffer = BytesIO()
    combined_sheet = pd.concat([vendor_sheet, employee_sheet])


    # Write the Excel file to the buffer
    with pd.ExcelWriter(excel_buffer) as writer:
        # vendor_sheet.to_excel(writer, sheet_name='Vendor', index=True)
        customer_sheet.to_excel(writer, sheet_name='Customer', index=True)
        combined_sheet.to_excel(writer, sheet_name='Vendor', index=True)
        # employee_sheet.to_excel(writer, sheet_name='Employee', index=True)

    
    vendor_data = combined_sheet.copy()
    customer_data = customer_sheet.copy()
    # employee_data = employee_sheet.copy()

    # with pd.ExcelWriter(csv_filename + '223part ' +'.xlsx') as writer:

    #     # Write vendor_data to 'Vendor' sheet
    #     vendor_data.to_excel(writer, sheet_name='Vendor', index=True)
        
    #     # Write customer_data to 'Customer' sheet
    #     customer_data.to_excel(writer, sheet_name='Customer', index=True)


    return {'VendorData': vendor_data,'CustomerData': customer_data}



# bench --site dev.localhost execute  --args "{ '2024-08-01' }"  khanal_tech_integrations.utils.Finance.AgeingReport.Make_AgeingReportForExport


def Make_AgeingReportForExport(end_date):
    # print(end_date,'Make_AgeingReportForExport','\n\n\n')
    filtered_df=DataFormJournalEntries()
    # print(filtered_df,'Make_AgeingReport.Make_AgeingReportMake_AgeingReport')

    end_date = pd.to_datetime(end_date)

    filtered_df['ReferenceDate'] = pd.to_datetime(filtered_df['ReferenceDate'], format='%d/%m/%y', errors='coerce')
    filtered_df['DueDate'] = pd.to_datetime(filtered_df['DueDate'], format='%d/%m/%y', errors='coerce')


    # Filter data based on date range
    # filtered_df = df[(df['ReferenceDate'] <= end_date)]

    current_date = datetime.now()
    filtered_df['Age'] = (current_date - filtered_df['DueDate']).dt.days
    filtered_df = filtered_df.dropna(subset=['Customer/Vendor Code'])
    # filtered_df = filtered_df[filtered_df['Age'] >= 0]


    
    filtered_df['Total'] = filtered_df['Debit'] - filtered_df['Credit']

    # Filter the dataframe by 'ReferenceDate'
    grouped_totals = filtered_df.groupby('Customer/Vendor Code')[['Total']].sum()
    threshold = 10e-10  # Adjust the threshold as needed
    non_zero_groups = grouped_totals[abs(grouped_totals['Total']) > threshold]
    filtered_df = filtered_df[filtered_df['Customer/Vendor Code'].isin(non_zero_groups.index)]







    filtered_df = filtered_df[(filtered_df['ReferenceDate'] <= end_date)]

    # filtered_df.to_excel(csv_filename + 'Make_AgeingReportForExport part 6.xlsx')

    # Group by 'Customer/Vendor Code' and sum the 'Total', ensuring the result is a DataFrame
    aging_report = filtered_df.groupby(['Customer/Vendor Code'], sort=False).agg({'Total': 'sum'}).unstack(fill_value=0)

    # Compute totals for 'FCDebit' and 'FCCredit'
    customer_totals = filtered_df.groupby('Customer/Vendor Code')[['FCDebit', 'FCCredit']].sum()

    # Ensure aging_report is a DataFrame before merging
    if isinstance(aging_report, pd.Series):
        aging_report = aging_report.to_frame()

    # Merge aging_report with customer_totals
    aging_report = aging_report.merge(customer_totals, how='left', on='Customer/Vendor Code')

    # Calculate 'FC Balance Due'
    aging_report['FC Balance Due'] = aging_report['FCDebit'] - aging_report['FCCredit']

    # Rename columns and reset index
    # aging_report.columns = ['Total FCDebit', 'Total FCCredit', 'FC Balance Due']
    aging_report.index = aging_report.index.astype(str).fillna('')
    aging_report.reset_index(inplace=True)

    # Filter into separate sheets for vendors, customers, and employees
    vendor_sheet = aging_report[aging_report['Customer/Vendor Code'].str.startswith('V')]
    customer_sheet = aging_report[aging_report['Customer/Vendor Code'].str.startswith('C')]
    employee_sheet = aging_report[aging_report['Customer/Vendor Code'].str.startswith('E')]

    # Combine vendor and employee sheets
    combined_sheet = pd.concat([vendor_sheet, employee_sheet])

    # Output to an Excel buffer
    excel_buffer = BytesIO()


    # Write the Excel file to the buffer
    with pd.ExcelWriter(excel_buffer) as writer:
        # vendor_sheet.to_excel(writer, sheet_name='Vendor', index=True)
        customer_sheet.to_excel(writer, sheet_name='Customer', index=True)
        combined_sheet.to_excel(writer, sheet_name='Vendor', index=True)
        # employee_sheet.to_excel(writer, sheet_name='Employee', index=True)

    
    vendor_data = combined_sheet.copy()
    customer_data = customer_sheet.copy()
    # employee_data = employee_sheet.copy()

    # with pd.ExcelWriter(csv_filename + 'Make_AgeingReportForExport.xlsx') as writer:

    #     # Write vendor_data to 'Vendor' sheet
    #     vendor_data.to_excel(writer, sheet_name='Vendor', index=True)
        
    #     # Write customer_data to 'Customer' sheet
    #     customer_data.to_excel(writer, sheet_name='Customer', index=True)


    return {'VendorData': vendor_data,'CustomerData': customer_data}


# def AdvancePaymentDatadf(EndDate):

#     # print(StartDate,'StartDate')
#     print(EndDate,'EndDate')
#     JournalEntriesList_List = frappe.get_list('SAP Journal Entries Test',
#                         # filters={
#                         #     # 'referencedate': ['between', [StartDate, EndDate]],
#                         #     # 'referencedate': ['<=', EndDate],
#                         #     # 'referencedate': ['<=', EndDate],
#                         #     # 'duedate': ['<=', EndDate],
#                         # },
#                         fields=['referencedate', 'memo', 'duedate', 'taxdate', 'reference', 'lineitem.customervendor_code', 'lineitem.debit', 'lineitem.credit'], as_list=True,order_by='referencedate asc',

#                         )

#     print(len(JournalEntriesList_List), 'Length of JournalEntriesList_List')

#     formatted_entries = []
#     for entry in JournalEntriesList_List:
#         entry_date = entry[0]
#         formatted_date = entry_date.strftime('%Y-%m-%d') if entry_date else None

#         duedate = entry[2]
#         formatted_duedate = duedate.strftime('%Y-%m-%d') if duedate else None

       
#         formatted_entry = (formatted_date,  entry[6], entry[7],entry[5],formatted_duedate)
#         formatted_entries.append(formatted_entry)
 

#     columns_to_select = ['ReferenceDate', 'Debit', 'Credit', 'Customer/Vendor Code', 'DueDate']

#     # Create DataFrame
#     filtered_df = pd.DataFrame(formatted_entries, columns=columns_to_select)
#     # print(formatted_entries,'formatted_entries')
#     # Convert date columns to datetime objects
#     date_columns = ['ReferenceDate', 'DueDate',]
#     filtered_df[date_columns] = filtered_df[date_columns].apply(pd.to_datetime)

#     numeric_columns = ['Debit', 'Credit']
#     filtered_df[numeric_columns] = filtered_df[numeric_columns].apply(pd.to_numeric, errors='coerce')

#     filtered_df['ReferenceDate'] = pd.to_datetime(filtered_df['ReferenceDate'], format='%d/%m/%y', errors='coerce')
#     filtered_df['DueDate'] = pd.to_datetime(filtered_df['DueDate'], format='%d/%m/%y', errors='coerce')


#     # Filter data based on date range
#     # filtered_df = df[(df['ReferenceDate'] <= end_date)]

#     current_date = datetime.now()
#     filtered_df['Age'] = (current_date - filtered_df['DueDate']).dt.days
#     filtered_df = filtered_df.dropna(subset=['Customer/Vendor Code'])
#     # filtered_df = filtered_df[filtered_df['Age'] >= 0]


    
#     filtered_df = filtered_df[filtered_df['Customer/Vendor Code'].str[0].isin(['V', 'C', 'E'])]
#     bins = [0, 30, 60, 90, 120, float('inf')]
#     labels = ['0-30', '31-60', '61-90', '91-120', '120+']
#     filtered_df['Age Group'] = pd.cut(filtered_df['Age'], bins=bins, labels=labels, right=False)
#     filtered_df['Age Group'] = pd.Categorical(filtered_df['Age Group'], categories=labels, ordered=True)
#     # # print(filtered_df,'filtered_df')
#     # # Calculate document total and total
#     filtered_df['Total'] = filtered_df['Debit'] - filtered_df['Credit']

#     # threshold = 1e-10  # Adjust the threshold as needed
#     # grouped_totals = filtered_df.groupby('Customer/Vendor Code')[['Total']].sum()
#     # non_zero_groups = grouped_totals[abs(grouped_totals['Total']) > threshold]
#     # filtered_df = filtered_df[filtered_df['Customer/Vendor Code'].isin(non_zero_groups.index)]
   


#     # # Group by Customer/Vendor Code and Age Group, and calculate sum of Total
#     aging_report = filtered_df.groupby(['Customer/Vendor Code', 'Age Group'], sort=False)[['Total']].sum().unstack(fill_value=0)

#     # # Group by Customer/Vendor Code and calculate sum of Debit and Credit
#     customer_totals = filtered_df.groupby('Customer/Vendor Code')[['Debit', 'Credit']].sum()
#     # print('\n\n\n',aging_report)
#     # # Flatten the column index of aging_report
#     aging_report.columns = [' '.join(map(str, col)) for col in aging_report.columns]

#     # Merge the two DataFrames
#     aging_report = aging_report.merge(customer_totals, how='left', on='Customer/Vendor Code')
#     aging_report['Balance Due'] = aging_report['Debit'] - aging_report['Credit']
#     aging_report.columns = labels + ['Total Debit', 'Total Credit', 'Balance Due']
#     aging_report.index = aging_report.index.astype(str).fillna('')
#     # print(aging_report,'aging_report','\n\n')
#     aging_report.reset_index(inplace=True)


#     # vendor_sheet = aging_report[aging_report.index.str.startswith('V')]
#     # customer_sheet = aging_report[aging_report.index.str.startswith('C')]
#     # employee_sheet = aging_report[aging_report.index.str.startswith('E')]

#     vendor_sheet = aging_report[aging_report['Customer/Vendor Code'].str.startswith('V')]
#     # customer_sheet = aging_report[aging_report['Customer/Vendor Code'].str.startswith('C')]
#     employee_sheet = aging_report[aging_report['Customer/Vendor Code'].str.startswith('E')]
#     # Create a BytesIO buffer to hold the Excel file
#     excel_buffer = BytesIO()
#     combined_sheet = pd.concat([vendor_sheet, employee_sheet])


#     # Write the Excel file to the buffer
#     with pd.ExcelWriter(excel_buffer) as writer:
#         combined_sheet.to_excel(writer, sheet_name='Vendor', index=True)

#     vendor_data = combined_sheet.copy()
#     # vendor_data.to_excel('')

#     # with pd.ExcelWriter(csv_filename + 'AdvanceData8' +'.xlsx') as writer:
#     # # Write vendor_data to 'Vendor' sheet
#     #     vendor_data.to_excel(writer, sheet_name='Vendor', index=True)
    

 

#     return {'VendorData': vendor_data}



def ExtractData(mater_df,Type):
    # print(mater_df,'\n\n','MasterDF')
    # print('\n\n\n',Type,'Type')
    columns = ["Balance Due", '0-30', '31-60', '61-90', '91-120', '120+']
    for col in columns:
        mater_df[col] = mater_df[col].replace('[^\d().-]', '', regex=True)
        mater_df[col] = mater_df[col].apply(lambda x: -float(x[1:-1]) if isinstance(x, str) and x.startswith('(') else float(x))
        mater_df[col] = pd.to_numeric(mater_df[col], errors='coerce')



    conditions = {}

    if Type == 'Vendor':
        conditions = {
            '>1CR': (mater_df['Balance Due'] > 10000000) | (mater_df['Balance Due'] <= -10000000),
            '50L-1CR': (mater_df['Balance Due'] >= -10000000) & (mater_df['Balance Due'] < -5000000),
            '10L-50L': (mater_df['Balance Due'] >= -5000000) & (mater_df['Balance Due'] < -1000000),
            '1L-10L': (mater_df['Balance Due'] < 0) & (mater_df['Balance Due'] >= -1000000) & (mater_df['Balance Due'] < -100000),
            '50K-1L': (mater_df['Balance Due'] < -50000) & (mater_df['Balance Due'] >= -100000),
            '10K-50K': (mater_df['Balance Due'] < -10000) & (mater_df['Balance Due'] >= -50000),
            '<10K': (mater_df['Balance Due'] > -10000) & (mater_df['Balance Due'] < 0),
            'Adv Payments': mater_df['Balance Due'].fillna(0) >= 0
        }

    else:
        conditions = {
            '>1CR': (mater_df['Balance Due'] > 10000000),
            '50L-1CR': (mater_df['Balance Due'] >= 5000000) & (mater_df['Balance Due'] <= 10000000),
            '10L-50L': (mater_df['Balance Due'] >= 1000000) & (mater_df['Balance Due'] < 5000000),
            '1L-10L': (mater_df['Balance Due'] >= 100000) & (mater_df['Balance Due'] < 1000000),
            '50K-1L': (mater_df['Balance Due'] >= 50000) & (mater_df['Balance Due'] < 100000),
            '10K-50K': (mater_df['Balance Due'] >= 10000) & (mater_df['Balance Due'] < 50000),
            '<10K': (mater_df['Balance Due'] < 10000) & (mater_df['Balance Due'] > 0),
            'Negative': mater_df['Balance Due'].fillna(0) <= 0
        }
    # Prepare to accumulate sums
    sums_per_condition = {}
    total_sums = {col: 0 for col in columns}

    # Iterate over conditions and calculate sums per row
    for condition, mask in conditions.items():
        filtered_data = mater_df[mask]
        filtered_data['Customer/Vendor Code'] = 1

        sums_per_row = filtered_data[columns + ['Customer/Vendor Code']].sum(axis=0)
        num_customers = filtered_data['Customer/Vendor Code'].sum()

        # Store sums in dictionary
        sums_per_condition[condition] = sums_per_row
        total_sums = {col: total_sums[col] + sums_per_row[col] for col in columns}

    # Convert sums_per_condition to DataFrame
    result_df = pd.DataFrame(sums_per_condition).transpose()
    result_df['Number of customers'] = result_df['Customer/Vendor Code']
    result_df.drop('Customer/Vendor Code', axis=1, inplace=True)


    # # Add the total row
    total_row = pd.Series(total_sums, name='Total')
    total_row['Number of customers'] = result_df['Number of customers'].sum()
    # result_df = result_df.append(total_row)
    result_df = pd.concat([result_df, total_row.to_frame().transpose()])

    
    # Format the DataFrame for output
    Resulted_df = result_df.copy()
    Resulted_df.index.name = 'Bucket'
    Resulted_df = Resulted_df.rename(columns={'Balance Due': 'Outstanding Amount'})
    

    # Apply formatting to numeric columns
    # def format_currency(x):
    #     if isinstance(x, (int, float)):
    #         return f"{x:,.2f}"
    #     else:
    #         return x


    cols_to_format = Resulted_df.columns[~Resulted_df.columns.isin(['Number of customers'])]
    Resulted_df[cols_to_format] = Resulted_df[cols_to_format].applymap(currencyInIndiaFormat)

    # Resulted_df = Resulted_df.applymap(format_currency)

    # Format negative values with parentheses
   

    Resulted_df = Resulted_df.applymap(format_negative)
    # Resulted_df.rename(columns={'Number of customers': }, inplace=True)
    Resulted_df.reindex(columns=['Number of customers','Outstanding Amount', '0-30', '31-60', '61-90', '91-120','120+'])
    Resulted_df.rename(columns={'Number of customers': 'No:of Vendor' if Type == 'Vendor' else 'No:of Customer'},inplace=True)
    Resulted_df.reset_index(inplace=True)


    return Resulted_df





def AdvancePayment(VendorData_df):
    VendorData_df['Balance Due'] = VendorData_df['Balance Due'].replace('[^\d.]', '', regex=True).astype(float)

    # with pd.ExcelWriter(csv_filename + 'AdvanceData045' +'.xlsx') as writer:
    # # Write vendor_data to 'Vendor' sheet
    #     VendorData_df.to_excel(writer, sheet_name='Vendor', index=True)
    



    # Define conditions for different balance ranges
    conditions = {
        '>5L': (VendorData_df['Balance Due'] > 500000),
        '1L-5L': (VendorData_df['Balance Due'] >= 100000) & (VendorData_df['Balance Due'] <= 500000),
        '50K-1L': (VendorData_df['Balance Due'] >= 50000) & (VendorData_df['Balance Due'] < 100000),
        '10K-50K': (VendorData_df['Balance Due'] >= 10000) & (VendorData_df['Balance Due'] < 50000),
        '<10K': (VendorData_df['Balance Due'].fillna(0) < 10000) & (VendorData_df['Balance Due'].fillna(0) > 0) | VendorData_df['Balance Due'].isna()
    }

    # Initialize dictionaries to store sums and total counts
    sums_per_condition = {}
    total_customers = 0

    # Iterate over conditions and calculate sums per condition
    for condition, mask in conditions.items():
        filtered_data = VendorData_df[mask]

        # Calculate sum of 'Balance Due' for this condition excluding NaN values
        filtered_balance_due = filtered_data['Balance Due'].dropna()
        sums_per_condition[condition] = filtered_balance_due.sum()

        # Calculate number of customers in this category
        num_customers = filtered_data.shape[0]
        total_customers += num_customers  # Accumulate total number of customers

    # Calculate total outstanding amount (excluding NaN)
    
    # total_outstanding_amount = VendorData_df['Balance Due'].dropna().sum()
    VendorData_df = VendorData_df[VendorData_df['Balance Due'] > 0]  # Filter the DataFrame
    # print(VendorData_df,'AdvancePayment_df[Outstanding Amount]','\n\n\n\n')
    total_outstanding_amount = VendorData_df['Balance Due'].sum()  # Calculate the sum
    # print(total_outstanding_amount,'total_outstanding_amounttotal_outstanding_amount','\n\n\n\n')
    # Append 'Total' row to the result DataFrame
    AdvancePayment_df = pd.DataFrame(list(sums_per_condition.items()), columns=['Bucket', 'Outstanding Amount'])
    AdvancePayment_df['Customer/Vendor Code'] = [VendorData_df[mask].shape[0] for _, mask in conditions.items()]
    
    # Calculate percentage contribution of each 'Total Amount' to the total
    AdvancePayment_df['Percentage'] = (AdvancePayment_df['Outstanding Amount'] / total_outstanding_amount) * 100
    # print( AdvancePayment_df['Percentage'],'\n\n\n','################')

    # Append 'Total' row with total outstanding amount and total customers
    total_row = pd.DataFrame({'Bucket': ['Total'], 'Outstanding Amount': [AdvancePayment_df['Outstanding Amount'].sum()], 'Customer/Vendor Code': [total_customers]})
    total_row['Percentage'] = AdvancePayment_df['Percentage'].sum()  # Calculate total percentage


    # print(total_row,'\n\n\n\n','!!!!!!!!!!!!!!!!!!!')
    # AdvancePayment_df = AdvancePayment_df.append(total_row, ignore_index=True)

    AdvancePayment_df = pd.concat([AdvancePayment_df, total_row], ignore_index=True)

    # Format the 'Outstanding Amount' and 'Percentage' columns
    # AdvancePayment_df['Outstanding Amount'] = AdvancePayment_df['Outstanding Amount'].apply(lambda x: f"{x:,.2f}")
    # AdvancePayment_df['Percentage'] = AdvancePayment_df['Percentage'].apply(lambda x: f"{x:.2f}%")

    # print(AdvancePayment_df,'*'*10)





    # Calculate percentage for 'Total' row
    total_percentage = AdvancePayment_df.loc[AdvancePayment_df['Bucket'] != 'Total', 'Percentage'].sum()  # Sum of individual percentages
    AdvancePayment_df.loc[AdvancePayment_df['Bucket'] == 'Total', 'Percentage'] = total_percentage

    # Format the 'Outstanding Amount' and 'Percentage' columns
    AdvancePayment_df['Outstanding Amount'] = AdvancePayment_df['Outstanding Amount'].apply(currencyInIndiaFormat)

    # AdvancePayment_df['Outstanding Amount'] = AdvancePayment_df['Outstanding Amount'].apply(lambda x: f"{x:,.2f}")
    AdvancePayment_df['Percentage'] = AdvancePayment_df['Percentage'].apply(lambda x: f"{x:.2f}%")

    AdvancePayment_df.rename(columns={'Customer/Vendor Code': 'Number of Vendor','Outstanding Amount': 'Total Amount','Percentage': '% of Total Adv Payments'}, inplace=True)

 
    cols_to_format = AdvancePayment_df.columns[~AdvancePayment_df.columns.isin(['Bucket','% of Total Adv Payments'])]
    AdvancePayment_df[cols_to_format] = AdvancePayment_df[cols_to_format].applymap(format_negative)


    return AdvancePayment_df






def GetTotalSum(PayablesData_df,Receivables_df):
    outstanding_amount_receivables = float(Receivables_df['Outstanding Amount'].iloc[-1].replace(',', ''))
    outstanding_amount_payables = float(PayablesData_df['Outstanding Amount'].iloc[-1].replace(',', ''))

    # Calculate total outstanding amount
    total_outstanding_amount = outstanding_amount_receivables + outstanding_amount_payables


    # Sum of each bucket range
    total_0_30 = float(str(Receivables_df['0-30'].iloc[-1]).replace(',', '')) + float(str(PayablesData_df['0-30'].iloc[-1]).replace(',', ''))
    total_31_60 = float(str(Receivables_df['31-60'].iloc[-1]).replace(',', '')) + float(str(PayablesData_df['31-60'].iloc[-1]).replace(',', ''))
    total_61_90 = float(str(Receivables_df['61-90'].iloc[-1]).replace(',', '')) + float(str(PayablesData_df['61-90'].iloc[-1]).replace(',', ''))
    total_91_120 = float(str(Receivables_df['91-120'].iloc[-1]).replace(',', '')) + float(str(PayablesData_df['91-120'].iloc[-1]).replace(',', ''))
    total_120_plus = float(str(Receivables_df['120+'].iloc[-1]).replace(',', '')) + float(str(PayablesData_df['120+'].iloc[-1]).replace(',', ''))

    # Create a DataFrame for the sum
    data = {
        '': ['AR+AP'],
        'Outstanding Amount': [total_outstanding_amount],
        '0-30': [total_0_30],
        '31-60': [total_31_60],
        '61-90': [total_61_90],
        '91-120': [total_91_120],
        '120+': [total_120_plus]
    }

    sum_df = pd.DataFrame(data)
    # # Apply formatting to numeric columns
    # def format_currency(x):
    #     if isinstance(x, (int, float)):
    #         return f"{x:,.2f}"
    #     else:
    #         return x

    # sum_df = sum_df.applymap(format_currency)

    # # Format negative values with parentheses
   
    # def format_negative_non(x):

    #     if isinstance(x, float) and x < 0:
    #         return f"({abs(x):,.2f})"
    #     else:
    #         return format_currency(x)

    # sum_df = sum_df.applymap(format_negative_non)

    # sum_df['Value'] = sum_df['Value'].apply(currencyInIndiaFormat)


    # Format negative values with parentheses
   
    cols_to_format = sum_df.columns[~sum_df.columns.isin([''])]
    sum_df[cols_to_format] = sum_df[cols_to_format].applymap(currencyInIndiaFormat)
    sum_df[cols_to_format] = sum_df[cols_to_format].applymap(format_negative)


    # print(sum_df,'\n\n\n\n')
    return sum_df

def AdvPayments_Consolidated(AdvPayments_df):
    
    AdvPayments_df.reset_index(inplace=True)
    # print(AdvPayments_df['Customer/Vendor Code'],'\n\n\n\n','AdvPayments_df')
    AdvPayments_df['Balance Due'] = AdvPayments_df['Balance Due'].replace('[^\d.]', '', regex=True).astype(float)

    # AdvPayments_df = AdvPayments_df.loc[AdvPayments_df['Balance Due'] > 500000]
    AdvPayments_df = AdvPayments_df[AdvPayments_df['Balance Due'] > 500000]
    sorted_AdvPayments_df = AdvPayments_df.sort_values(by='Balance Due', ascending=False)

    # print(sorted_AdvPayments_df)
    mergedAdvPayments_df = sorted_AdvPayments_df.merge(BpData[['BP Code', 'BP Name']], 
                                        left_on='Customer/Vendor Code', 
                                        right_on='BP Code', 
                                        how='left')


    columns_to_drop = ['Customer/Vendor Code', '0-30', '31-60', '61-90', '91-120', '120+', 'Total Debit','Total Credit','BP Code']
    mergedAdvPayments_df.drop(columns=columns_to_drop, inplace=True)
    # Reorder the columns
    mergedAdvPayments_df = mergedAdvPayments_df.reindex(columns=['BP Name', 'Balance Due'])
    mergedAdvPayments_df['Balance Due'] = mergedAdvPayments_df['Balance Due'].apply(currencyInIndiaFormat)


    cols_to_format = mergedAdvPayments_df.columns[~mergedAdvPayments_df.columns.isin(['BP Name'])]
    mergedAdvPayments_df[cols_to_format] = mergedAdvPayments_df[cols_to_format].applymap(format_negative)


    return mergedAdvPayments_df


def Master_Consolidated(Commondf_1cr,Type):
    Commondf_1cr.reset_index(inplace=True)
    Commondf_1cr['Balance Due'] = Commondf_1cr['Balance Due'].replace('[^\d.]', '', regex=True).astype(float)

    # AdvPayments_df = AdvPayments_df.loc[AdvPayments_df['Balance Due'] > 500000]
    # AdvPayments_df = AdvPayments_df[AdvPayments_df['Balance Due'] > 500000]
    Commondf_1cr = Commondf_1cr[((Commondf_1cr['Balance Due'] > 10000000) | (Commondf_1cr['Balance Due'] <= -10000000))]

    # sorted_Commondf_1cr = Commondf_1cr.sort_values(by='Balance Due', ascending=False)
    if Type == 'Vendor':
        sorted_Commondf_1cr = Commondf_1cr.sort_values(by='Balance Due', ascending=True)
    else:
        sorted_Commondf_1cr = Commondf_1cr.sort_values(by='Balance Due', ascending=False)

    # print(sorted_AdvPayments_df)
    mergedsorted_Commondf_1cr = sorted_Commondf_1cr.merge(BpData[['BP Code', 'BP Name']], 
                                        left_on='Customer/Vendor Code', 
                                        right_on='BP Code', 
                                        how='left')


    columns_to_drop = ['Customer/Vendor Code', '0-30', '31-60', '61-90', '91-120', '120+', 'Total Debit','Total Credit','BP Code']
    mergedsorted_Commondf_1cr.drop(columns=columns_to_drop, inplace=True)
    # Reorder the columns
    mergedsorted_Commondf_1cr = mergedsorted_Commondf_1cr.reindex(columns=['BP Name', 'Balance Due'])
    # Apply formatting to numeric columns
    # def format_currency(x):
    #     if isinstance(x, (int, float)):
    #         return f"{x:,.2f}"
    #     else:
    #         return x

    # print(mergedsorted_Commondf_1cr,'\n\n\n\n','mergedsorted_Commondf_1cr')
    # mergedsorted_Commondf_1cr = mergedsorted_Commondf_1cr.applymap(currencyInIndiaFormat)
    mergedsorted_Commondf_1cr['Balance Due'] = mergedsorted_Commondf_1cr['Balance Due'].apply(currencyInIndiaFormat)

    # Format negative values with parentheses
   

    # mergedsorted_Commondf_1cr = mergedsorted_Commondf_1cr.applymap(format_negative)
    cols_to_format = mergedsorted_Commondf_1cr.columns[~mergedsorted_Commondf_1cr.columns.isin(['BP Name'])]
    mergedsorted_Commondf_1cr[cols_to_format] = mergedsorted_Commondf_1cr[cols_to_format].applymap(format_negative)

    return mergedsorted_Commondf_1cr



def SummaryData(PayablesData_df,Receivables_df,Previous_PayablesData_df,Previous_Receivables_df):
    outstanding_amount_receivables = float(Receivables_df['Outstanding Amount'].iloc[-1].replace(',', ''))
    outstanding_amount_payables = float(PayablesData_df['Outstanding Amount'].iloc[-1].replace(',', ''))
    outstanding_amount_previous_receivables = float(Previous_Receivables_df['Outstanding Amount'].iloc[-1].replace(',', ''))
    outstanding_amount_previous_payables = float(Previous_PayablesData_df['Outstanding Amount'].iloc[-1].replace(',', ''))

    # print(outstanding_amount_previous_payables,outstanding_amount_payables,'\n\n\n\n')
    # print(outstanding_amount_receivables,outstanding_amount_previous_receivables,'\n\n\n\n')

    ap_value = outstanding_amount_previous_payables - outstanding_amount_payables
    ar_value = outstanding_amount_receivables - outstanding_amount_previous_receivables
    # formatted_ap_value = locale.format('%0.2f', ap_value, grouping=True)
    # formatted_ar_value = locale.format('%0.2f', ar_value, grouping=True)
   
    # print(formatted_ap_value)

    more_less_ap = "More" if ap_value > 0 else "Less"
    more_less_ar = "More" if ar_value > 0 else "Less"

    # Create the DataFrame
    data = {
        "Change From Prev Week": ["AP", "AR"],
        "Value": [ap_value, ar_value],
        "More/Less": [more_less_ap, more_less_ar]
    }

    result_Summary = pd.DataFrame(data)

    result_Summary['Value'] = result_Summary['Value'].apply(currencyInIndiaFormat)


    # Format negative values with parentheses
   
    cols_to_format = result_Summary.columns[~result_Summary.columns.isin(['Change From Prev Week','More/Less'])]
    result_Summary[cols_to_format] = result_Summary[cols_to_format].applymap(format_negative)

    # result_Summary = result_Summary.applymap(format_negative)


    return result_Summary




def currencyInIndiaFormat(n):
    # Convert n to Decimal
    # print(n,'\n\n\n\n')
    d = decimal.Decimal(str(n))
    # Round to two decimal places
    rounded = round(d, 2)
    # Convert to string
    s = '{0:.2f}'.format(rounded)
    l = len(s)
    i = l - 1
    res = ''
    flag = 0
    k = 0
    while i >= 0:
        if flag == 0:
            res = res + s[i]
            if s[i] == '.':
                flag = 1
        elif flag == 1:
            k = k + 1
            res = res + s[i]
            if k == 3 and i - 1 >= 0:
                res = res + ','
                flag = 2
                k = 0
        else:
            k = k + 1
            res = res + s[i]
            if k == 2 and i - 1 >= 0:
                res = res + ','
                flag = 2
                k = 0
        i = i - 1

    return res[::-1]




def format_negative(x):
    if isinstance(x, float) and x < 0:
        return '-{:,.2f}'.format(abs(x))
    elif isinstance(x, str) and '-' in x:
        # Removing extra comma after the minus sign if exists
        if '-,' in x:
            x = x.replace('-,', '-')
        # Keeping commas and '-' sign and formatting as string
        return '-{}'.format(x.replace('-', ''))
    elif isinstance(x, str) and ',' in x:
        # Keeping commas and formatting as string
        return '{}'.format(x)
    else:
        # Formatting positive numbers or non-string values
        return '{:,.0f}'.format(float(x))

def EmailFormat(PayablesData_df,Receivables_df,AdvancePayment_df,TotalSum_df,Consolidated_AdvPayments,Vendor_Consolidated,Customer_Consolidated,Previous_PayablesData_df,Previous_Receivables_df,SummaryData):
    #! Convert DataFrames to JSON
    payables_json_data = PayablesData_df.to_json(orient='records')
    Receivables_json_data = Receivables_df.to_json(orient='records')
    AdvancePayment_json_data = AdvancePayment_df.to_json(orient='records')
    TotalSum_json_data = TotalSum_df.to_json(orient='records')
    Consolidated_AdvPayments_json_data = Consolidated_AdvPayments.to_json(orient='records')
    Vendor_Consolidated_json_data = Vendor_Consolidated.to_json(orient='records')
    Customer_Consolidated_json_data = Customer_Consolidated.to_json(orient='records')
    Previous_PayablesData_df_json_data = Previous_PayablesData_df.to_json(orient='records')
    Previous_Receivables_df_json_data = Previous_Receivables_df.to_json(orient='records')
    SummaryData_json_data = SummaryData.to_json(orient='records')


    

    #! Load JSON data
    payables_html_table = pd.json_normalize(json.loads(payables_json_data))
    Receivables_html_table = pd.json_normalize(json.loads(Receivables_json_data))
    AdvancePayment_html_table = pd.json_normalize(json.loads(AdvancePayment_json_data))
    TotalSum_html_table = pd.json_normalize(json.loads(TotalSum_json_data))
    Consolidated_AdvPayments_html_table = pd.json_normalize(json.loads(Consolidated_AdvPayments_json_data))
    Vendor_Consolidated_html_table = pd.json_normalize(json.loads(Vendor_Consolidated_json_data))
    Customer_Consolidated_html_table = pd.json_normalize(json.loads(Customer_Consolidated_json_data))
    Previous_PayablesData_df_html_table = pd.json_normalize(json.loads(Previous_PayablesData_df_json_data))
    Previous_Receivables_df_html_table = pd.json_normalize(json.loads(Previous_Receivables_df_json_data))
    SummaryData_df_html_table = pd.json_normalize(json.loads(SummaryData_json_data))


    #! Convert DataFrames to HTML tables
    payables_html_table = payables_html_table.to_html(index=False, classes='custom-table')
    Receivables_html_table = Receivables_html_table.to_html(index=False, classes='custom-table')
    AdvancePayment_html_table = AdvancePayment_html_table.to_html(index=False, classes='custom-table')
    TotalSum_html_table = TotalSum_html_table.to_html(index=False, classes='custom-table')
    Consolidated_AdvPayments_html_table = Consolidated_AdvPayments_html_table.to_html(index=False, classes='noncustom-table')
    Vendor_Consolidated_html_table = Vendor_Consolidated_html_table.to_html(index=False, classes='noncustom-table')
    Customer_Consolidated_html_table = Customer_Consolidated_html_table.to_html(index=False, classes='noncustom-table')
    Previous_PayablesData_df_html_table = Previous_PayablesData_df_html_table.to_html(index=False, classes='custom-table')
    Previous_Receivables_df_html_table = Previous_Receivables_df_html_table.to_html(index=False, classes='custom-table')
    SummaryData_df_html_table = SummaryData_df_html_table.to_html(index=False,classes='noncustom-table')


    html_content=f"""{table_css_style}
        <table >
            <thead >

                <tr>

                </tr>
                



            </thead>


            
             <div>
               <h1>Summary</h1>     
                {SummaryData_df_html_table}
            </div>

            <div>
               <h1>Account Payables</h1>     
                {payables_html_table}
            </div>

            <div>
               <h1>Account Receivables</h1>     
                {Receivables_html_table}
            </div>

             <div>
                 <h1></h1>     
                {TotalSum_html_table}
            </div>
            <div style="display: flex; justify-content: space-between;">
                <div>
                    <h1> >1CR vendors with dues</h1>
                    {Vendor_Consolidated_html_table}
                </div>
                <div>
                    <h1> >1CR customers with receivables due</h1>
                    {Customer_Consolidated_html_table}
                </div>
            </div>
            
             <div>
                <h1>Advance Payment</h1>     
                {AdvancePayment_html_table}
            </div>
             <div>
                <h1>Vendor With Adv Payment > 5L</h1>     
                {Consolidated_AdvPayments_html_table}
            </div>

             
           

            
            
            <tfoot></tfoot>
        </table>
        """
    
    return html_content
# <div>
# <h1>PREV WEEK Account Payables</h1>     
# {Previous_PayablesData_df_html_table}
# </div>


# <div>
# <h1>PREV WEEK Account Receivables</h1>     
# {Previous_Receivables_df_html_table}
# </div>



@frappe.whitelist()
def EmailTemplate(Tabletructure,CurrentDate):
        
    date_object = datetime.strptime(CurrentDate, "%Y-%m-%d")

    # Formatting the date object to the desired format
    formatted_date = date_object.strftime("%B %d")

    
    print(formatted_date,'formatted_date')
    current_directory = os.path.dirname(__file__)
    file_path = os.path.abspath(os.path.join(current_directory, '..','React_Api', 'Ledger', 'Emailtemplate.html'))

    
    with open(file_path, 'r') as f:
        template_str = f.read()
   

    MessageContent=Tabletructure
    template = Template(template_str)
    rendered_message = template.render(
        message   =MessageContent
    )    
    # email_args={
    #         "recipients":['shahil@khanalfoods.com'],
    #         "message":rendered_message,
    #         "cc": ['harsha@khanalfoods.com','shahil.7139@gmail.com'],
    #         "subject":f'{formatted_date} AP/AR, Advance Payments Weekly Reports'
    #  }

    email_args={
        "recipients":['bhupendra@khanalfoods.com','finance@khanalfoods.com'],
        "message":rendered_message,
        "cc": ['mratyunjay@khanalfoods.com','lian@khanalfoods.com','shahil@khanalfoods.com'],
        "subject":f'{formatted_date} AP/AR, Advance Payments Weekly Reports'
    }

    frappe.enqueue(method=frappe.sendmail,queue='short',timeout=300, **email_args)

    # pass




# bench --site dev.localhost execute  --args "( '2024-08-01','2024-08-18','C03495' )"  khanal_tech_integrations.utils.Finance.AgeingReport.JournalEntriesList_List

# bench --site dev.localhost execute  --args "( '2024-01-01','2024-08-18','C03269' )"  khanal_tech_integrations.utils.Finance.AgeingReport.JournalEntriesList_List


def JournalEntriesList_List(StartDate, EndDate,CardCode):
    JournalEntriesList_List = frappe.get_list('SAP Journal Entries',
        filters={
            'referencedate': ['between', [StartDate, EndDate]],
            'customervendor_code': CardCode,
            # 'originaljournal': 'ttJournalEntry',
        },
        pluck='name'
        )
    # print(JournalEntriesList_List,'JournalEntriesList_List')
    # response_list = []
    result = []
    for SingleJournalEntries in  JournalEntriesList_List:
        doc = frappe.get_doc("SAP Journal Entries", SingleJournalEntries)
        
        for single_JE in doc.lineitem:

            item_List = {
                "customervendor_code": single_JE.customervendor_code,
                "accountcode": single_JE.accountcode,
                "linememo": single_JE.linememo,
                "debit": single_JE.debit,
                "credit": single_JE.credit,
                "fcdebit": single_JE.fcdebit,
                "fccredit": single_JE.fccredit,
            }

            # Append the item_List dictionary to the line_items list
            result.append(item_List)
    
    # print(result,'result')
    # if 
    total_difference_FC = 0.0
    total_difference_LC = 0.0
    for item in result:
        if item['accountcode'] == '12300201':
            difference_fc = float(item['fcdebit']) - float(item['fccredit'])
            total_difference_FC += difference_fc
            # difference_lc = float(item['debit']) - float(item['credit'])
            # total_difference_LC += difference_lc

        if (
            item['accountcode'] == '51203500' or #Promo
            item['accountcode'] == '52131000' or #Round off
            item['accountcode'] == '13200301' or  #TDS
            item['accountcode'] == '13200302' or #TDS
            item['customervendor_code'] == 'V01095'
            
            # (
            #     item['linememo'] and 
            #     "promo" in item['linememo'].lower() and 
            #     item['customervendor_code'] == CardCode
            # )
            ):
            


            difference_lc = float(item['debit']) - float(item['credit'])
            total_difference_LC += difference_lc

     
    print({'TotalLC':total_difference_LC,'TotalFC':total_difference_FC},'\n\n')
    return  {'TotalLC': abs(total_difference_LC),'TotalFC': abs(total_difference_FC)}





# bench --site dev.localhost execute  --args "( '2024-01-01','2024-08-18','C01765' )"  khanal_tech_integrations.utils.Finance.AgeingReport.ttJournalEntry_List


def ttJournalEntry_List(StartDate, EndDate,CardCode):
    JournalEntriesList_List = frappe.get_list('SAP Journal Entries',
        filters={
            'referencedate': ['between', [StartDate, EndDate]],
            'customervendor_code': CardCode,
            'originaljournal': 'ttJournalEntry',
        },
        # pluck='name',
        fields=['referencedate', 'memo', 'duedate', 'taxdate', 'reference', 'lineitem.customervendor_code', 'lineitem.debit', 'lineitem.credit','lineitem.fcdebit', 'lineitem.fccredit','lineitem.accountcode'], as_list=True,order_by='referencedate asc',

        )

    total_difference_FC = 0.0
    total_difference_LC = 0.0
    for SingleList in JournalEntriesList_List:
        difference_lc=float(SingleList[6]) - float(SingleList[7])
        total_difference_LC += difference_lc


        difference_fc=float(SingleList[8]) - float(SingleList[9])
        total_difference_FC += difference_fc



    # print({'TotalLC':total_difference_LC,'TotalFC':total_difference_FC},'\n\n')
    return  {'TotalLC': abs(total_difference_LC),'TotalFC': abs(total_difference_FC)}




# bench --site dev.localhost execute  --args "( '2024-01-01','2024-08-18','C03353' )"  khanal_tech_integrations.utils.Finance.AgeingReport.ttReceipt_List

# bench --site dev.localhost execute  --args "( '2024-01-01','2024-08-18','C03516' )"  khanal_tech_integrations.utils.Finance.AgeingReport.ttReceipt_List

def ttReceipt_List(StartDate, EndDate,CardCode):
    JournalEntriesList_List = frappe.get_list('SAP Journal Entries',
        filters={
            'referencedate': ['between', [StartDate, EndDate]],
            'customervendor_code': CardCode,
            'originaljournal': 'ttReceipt',
        },
        # pluck='name',
        fields=['referencedate', 'memo', 'duedate', 'taxdate', 'reference', 'lineitem.customervendor_code', 'lineitem.debit', 'lineitem.credit','lineitem.fcdebit', 'lineitem.fccredit','lineitem.accountcode'], as_list=True,order_by='referencedate asc',

        )

    total_difference_FC = 0.0
    total_difference_LC = 0.0
    for SingleList in JournalEntriesList_List:
        difference_lc=float(SingleList[6]) - float(SingleList[7])
        total_difference_LC += difference_lc


        difference_fc=float(SingleList[8]) - float(SingleList[9])
        total_difference_FC += difference_fc



    # print({'TotalLC':total_difference_LC,'TotalFC':total_difference_FC},'\n\n')
    return  {'TotalLC': abs(total_difference_LC),'TotalFC': abs(total_difference_FC)}

# bench --site dev.localhost execute  --args "( '2022-01-01','2024-08-18','C03414' )"  khanal_tech_integrations.utils.Finance.AgeingReport.ttBalance_Report

def ttBalance_Report(StartDate, EndDate,CardCode):
    JournalEntriesList_List = frappe.get_list('SAP Journal Entries',
        filters={
            'referencedate': ['between', [StartDate, EndDate]],
            'customervendor_code': CardCode,
        },
        # pluck='name',
        fields=['referencedate', 'memo', 'duedate', 'taxdate', 'reference', 'lineitem.customervendor_code', 'lineitem.debit', 'lineitem.credit','lineitem.fcdebit', 'lineitem.fccredit','lineitem.accountcode'], as_list=True,order_by='referencedate asc',

        )

    total_difference_FC = 0.0
    total_difference_LC = 0.0
    for SingleList in JournalEntriesList_List:
        difference_lc=float(SingleList[6]) - float(SingleList[7])
        total_difference_LC += difference_lc


        difference_fc=float(SingleList[8]) - float(SingleList[9])
        total_difference_FC += difference_fc


    total_difference_LC = abs(total_difference_LC)
    total_difference_FC = abs(total_difference_FC)

    threshold = 10e-10

    if total_difference_LC < threshold:
        total_difference_LC = 0.0
        total_difference_FC = 0.0

    return {'TotalLC': total_difference_LC, 'TotalFC': total_difference_FC}
