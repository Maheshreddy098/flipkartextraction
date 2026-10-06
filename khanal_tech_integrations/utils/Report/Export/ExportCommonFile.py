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

from khanal_tech_integrations.utils.Finance.AgeingReport import Make_AgeingReport
from khanal_tech_integrations.utils.Report.Ar_invoice import Ar_Invoice_List
from khanal_tech_integrations.utils.Report.Ar_CreditNote import CreditNote_List
from khanal_tech_integrations.utils.Report.IncomingPayment import IncomingPayment_List

from khanal_tech_integrations.utils.Finance.AgeingReport import Get_File
# from khanal_tech_integrations.utils.Report.GetSalesEmployee import ExportEmployeeList
# from khanal_tech_integrations.utils.Report.EcomReport_Weekly import currencyFormatInWords


headersList = {
                    "Accept": "*/*",
                    "User-Agent": "Khanal Tech",
                    "Content-Type": "application/json",
                    "Prefer": "odata.maxpagesize=300",
                }
payload = ''

table_css_style = """
            <style>
            #weekly_table td,
            #weekly_table th {
                padding: 0.5em 1em;
                text-align: center;
            }

    #weekly_table {
        border: 3px solid black;
    }

    #weekly_table thead th {
        border-bottom: 2px solid black;
    }
    # #weekly_table td { 
    #         padding: 10px; 
    #         border: 2px solid black; 
  
    # } 
    #weekly_table tfoot td {
        border-top: 2px solid black;
    }
  
    #weekly_table tbody td {
        border-top: 1px solid black;
        border-right: 1px solid black;
    }

    #weekly_table tbody tr:first-child td {
        border-top: 0;
    }

    #weekly_table tbody td:last-child {
        border-right: 0;
    }
    
    </style>
    """




def EcomReport(start_date,end_date,invoice_df,credit_df,ChannelMapping_df):
    # print('\n\n',start_date,'start_date')
    # print("start_date before conversion:", start_date, type(start_date))
    # print("end_date before conversion:", end_date, type(end_date))
    # batchprice_df=Get_File('https://dev.khanaltech.com/files/BatchPricing_July25.xlsx','Sheet1')
    batchprice_df=pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/Batch Pricing Aug 08.xlsx')
    
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        # print('\n\n', start_date, 'start_date strptime')
    
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

    invoice_df = invoice_df[invoice_df['CardCode'].isin(ChannelMapping_df['CardCode'])]
    credit_df = credit_df[credit_df['CardCode'].isin(ChannelMapping_df['CardCode'])]
    # invoice_df = pd.merge(ChannelMapping_df, invoiceWithoutMapping_df, on='CardCode', how='left')
    # credit_df = pd.merge(ChannelMapping_df, creditWithoutMapping_df, on='CardCode', how='left')

   


    invoice_df = invoice_df[invoice_df['ProductionBaseType'] != 13]
    exclude_statuses = ['csYes', 'csCancellation']

    # Filter the DataFrame
    invoice_df = invoice_df[~invoice_df['CancelStatus'].isin(exclude_statuses)]
    credit_df = credit_df[~credit_df['CancelStatus'].isin(exclude_statuses)]

    exclude_item = ['ECOMREVENUE']
    invoice_df = invoice_df[~invoice_df['ItemCode'].isin(exclude_item)]
    credit_df = credit_df[~credit_df['ItemCode'].isin(exclude_item)]

    
   
    
    invoice_df['DocDate'] = pd.to_datetime(invoice_df['DocDate']).dt.date
    credit_df['DocDate'] = pd.to_datetime(credit_df['DocDate']).dt.date

    # Filter invoice_df and credit_df
    invoice_df = invoice_df[(invoice_df['DocDate'] >= start_date) & (invoice_df['DocDate'] <= end_date)]
    credit_df = credit_df[(credit_df['DocDate'] >= start_date) & (credit_df['DocDate'] <= end_date)]

    # new_invoice_df = invoice_df[invoice_df['CardCode'].isin(ChannelMapping_df['CardCode'])]
    # credit_df = credit_df[credit_df['CardCode'].isin(ChannelMapping_df['CardCode'])]

    # Merge filtered_invoice_df with batchprice_df
    invoice_merged_df = pd.merge(invoice_df, batchprice_df, how='left', left_on=['ItemCode', 'BatchNumber'], right_on=['Item No.', 'Batch Number'])

    # Merge filtered_credit_df with batchprice_df
    credit_merged_df = pd.merge(credit_df, batchprice_df, how='left', left_on=['ItemCode', 'BatchNumber'], right_on=['Item No.', 'Batch Number'])

    # Select relevant columns and rename them if necessary
    invoice_final_df = invoice_merged_df[['DocEntry', 'DocNum', 'DocDate', 'Without Tax','DocTotalFc', 'CardCode', 'CardName', 'DocDueDate',
                                        'LineNumber', 'ItemCode', 'BaseQuantity', 'ProductionBaseEntry', 'ProductionBaseType',
                                        'BatchNumber', 'LineQuantity','UnitPrice']]


    credit_final_df = credit_merged_df[['DocEntry', 'DocNum', 'DocDate', 'Without Tax','DocTotalFc', 'CardCode', 'CardName', 'DocDueDate',
                                        'LineNumber', 'ItemCode', 'BaseQuantity', 'InvoiceBaseEntry', 'ProductionBaseType',
                                        'BatchNumber', 'LineQuantity','UnitPrice']]


    # print(invoice_final_df,'invoice_final_df')

    invoice_final_df['Cogs Total Price'] = invoice_final_df['LineQuantity'] * invoice_final_df['UnitPrice']
    credit_final_df['Cogs Total Price'] = credit_final_df['LineQuantity'] * credit_final_df['UnitPrice']

    grouped_invoice_df = invoice_final_df.groupby(['DocEntry', 'CardCode']).agg({'Without Tax': 'first','DocTotalFc': 'first', 'Cogs Total Price': 'sum'}).reset_index()

    invoicecardcode_grouped_df = grouped_invoice_df.groupby('CardCode').agg({'Without Tax': 'sum','DocTotalFc': 'sum', 'Cogs Total Price': 'sum'}).reset_index()
    # print(invoicecardcode_grouped_df,'invoicecardcode_grouped_df')

    # print(grouped_invoice_df)
    # print(invoicecardcode_grouped_df)
    # Credit
    grouped_credit_df = credit_final_df.groupby(['DocEntry', 'CardCode']).agg({'Without Tax': 'first','DocTotalFc': 'first', 'Cogs Total Price': 'sum'}).reset_index()
    creditcardcode_grouped_df = grouped_credit_df.groupby('CardCode').agg({'Without Tax': 'sum','DocTotalFc': 'sum', 'Cogs Total Price': 'sum'}).reset_index()
    # creditcardcode_grouped_df['CardName'] = creditcardcode_grouped_df['CardCode'].map(card_dict)

    # Merge invoicecardcode_grouped_df with creditcardcode_grouped_df on 'CardCode'
    comparison_df = pd.merge(invoicecardcode_grouped_df, creditcardcode_grouped_df, how='left', on='CardCode', suffixes=('_Invoice', '_Credit'))
    # print(grouped_credit_df,'\n\n\n')
    # Fill NaN values in 'Without Tax_Credit' with 0 for calculations
    comparison_df['Without Tax_Credit'] = comparison_df['Without Tax_Credit'].fillna(0)
    comparison_df['Without Tax_Invoice']= comparison_df['Without Tax_Invoice'].fillna(0)
    comparison_df['DocTotalFc_Credit'] = comparison_df['DocTotalFc_Credit'].fillna(0)
    comparison_df['DocTotalFc_Invoice']= comparison_df['DocTotalFc_Invoice'].fillna(0)
    comparison_df['Cogs Total Price_Invoice'] = comparison_df['Cogs Total Price_Invoice'].fillna(0)
    comparison_df['Cogs Total Price_Return'] = comparison_df['Cogs Total Price_Credit'].fillna(0)
    comparison_df['Difference'] = comparison_df['Without Tax_Invoice'] - comparison_df['Without Tax_Credit']
    comparison_df['FC Difference'] = comparison_df['DocTotalFc_Invoice'] - comparison_df['DocTotalFc_Credit']
    # comparison_df['Cogs Difference'] = comparison_df['Cogs Total Price_Invoice'] - comparison_df['Cogs Total Price_Credit']

    bp_name_mapping = dict(zip(ChannelMapping_df['CardCode'], ChannelMapping_df['CardName']))

    comparison_df['CardName'] = comparison_df['CardCode'].map(bp_name_mapping)



    comparison_df.rename(columns={
        'CardCode': 'Card Code',
        'CardName': 'Card Name',
        'Without Tax_Invoice': 'Invoice Total (in Rs.)',
        'Without Tax_Credit': 'Return Total (in Rs.)',
        'DocTotalFc_Invoice':'FCInvoiced',
        'DocTotalFc_Credit':'FCReturns',
        'FC Difference':'FCRevenue',
        'Difference': 'Revenue (Invoice - Return)',
        'Cogs Total Price_Invoice':'Cogs Total Price_Invoice',
        'Cogs Total Price_Return':'Cogs Total Price_Return',
        # 'Cogs Total Price_Credit': 'Cogs Return Total (in Rs.)',
        # 'Cogs Difference': 'Cogs Revenue (Invoice - Return)',
    }, inplace=True)

    comparison_df.replace('nan', 'Not Available in SAP', inplace=True)

    # print(comparison_df,'comparison_df')

    # # print(Final_withCogsandRevenue)
    # # print(comparison_df.columns,'comparison_df')
    return comparison_df


# def GetIncomingdf(start_date,end_date,Incomingpayment_df):
#     print(start_date,end_date)
#     if isinstance(start_date, str):
#         start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
#         print('\n\n', start_date, 'start_date strptime')
    
#     if isinstance(end_date, str):
#         end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

#     Incomingpayment_df['DocDate'] = pd.to_datetime(Incomingpayment_df['DocDate']).dt.date

#     # Incomingpayment =pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Ecom/_Incoming Payment From Jan To July.xlsx')
#     Incomingpayment_df = Incomingpayment_df[(Incomingpayment_df['DocDate'] >= start_date) & (Incomingpayment_df['DocDate'] <= end_date)]
#     Incomingpayment_df_result = Incomingpayment_df.groupby('CardCode')['TransferSum'].sum().reset_index()
#     Incomingpayment_df_result.rename(columns={'TransferSum': 'PaymentsReceived'}, inplace=True)

#     return Incomingpayment_df_result








def EmailFormat(weekly_df,Mtd_df,EmailTemplate_Doc,formatted_dateEnding,formatted_datestarted,formatted_dateEnded,ChannelMapping_df,sales_employee_name,Today,MonthStarting,Type):
    # ChannelMapping_df =pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Ecom/Channal Mapping.xlsx')
   
    # print(weekly_df.columns)

   


    start_date = datetime.strptime(formatted_datestarted, "%d %B %Y")
    end_date = datetime.strptime(formatted_dateEnded, "%d %B %Y")
    print(start_date,end_date,'\n\n','start_date,end_date')

    # Format the dates for the subject line
    subject_start_date = start_date.strftime("%B %-d")
    subject_end_date = end_date.strftime("%-d, %Y")

    # Create the subject line
    # subject = f"{subject_start_date} to {subject_end_date}"
    if start_date.month == end_date.month:
        subject = f"{subject_start_date} to {subject_end_date}"
    else:
        subject_end_date = end_date.strftime("%b %-d, %Y")  # Use abbreviated month name for end date
        subject = f"{subject_start_date} to {subject_end_date}"


    # Create a mapping from BP Name to Channel Name
    # channel_mapping = dict(zip(ChannelMapping_df['BP Name'], ChannelMapping_df['Channel Name']))

    weekly_df_html_table = weekly_df.to_html(border=0, index=False, justify='center', classes='dataframe', table_id='weekly_table')

    soup = BeautifulSoup(weekly_df_html_table, 'html.parser')

    
    print(weekly_df_html_table,'weekly_df_html_table')

    # Iterate over rows and update the table
    for row in soup.find_all('tr'):
        cells = row.find_all('td')
    
        if len(cells) >= 5:
            # percentage_text = cells[9].text.strip()
            percentage_text = cells[7].text.strip() if Type == 'Weekly' else cells[10].text.strip()

            if percentage_text:
                # print(float(percentage_text.replace('%', '').replace(',', '').strip()),'value')
                if percentage_text:
                    # Remove commas and convert the text to a float for comparison
                    try:
                        percentage_value = float(percentage_text.replace('%', '').replace(',', '').strip())
                    except ValueError:
                        continue  # Skip rows where percentage_text is not a valid number
                    
                    # Determine the arrow direction based on the percentage value
                    if percentage_value < 0:
                        arrow = '⬇'
                    else:
                        arrow = '⬆'
                    
                    # Create the span tag with the arrow and percentage value
                    cellappend =cells[4] if Type == 'Weekly' else cells[5]
                    cellappend.append(soup.new_tag('br'))
                    span_tag = soup.new_tag('span', **{'class': 'percentage'},style='font-size: 0.7em;')
                    span_tag.string = f' ({arrow}{percentage_value}% )'
                    
                    # Append the new line and span tag to the cell
                    # cells[3].append(soup.new_tag('br'))
                    cellappend.append(span_tag)

            

            pnlmom = cells[8].text.strip() if Type == 'Weekly' else cells[11].text.strip()
            
            if pnlmom:
                # print(float(percentage_text.replace('%', '').replace(',', '').strip()),'value')
                if pnlmom:
                    # Remove commas and convert the text to a float for comparison
                    try:
                        pnl_mom = float(pnlmom.replace('%', '').replace(',', '').strip())
                    except ValueError:
                        continue  # Skip rows where pnlmom is not a valid number
                    
                    # Determine the arrow direction based on the percentage value
                    if pnl_mom < 0:
                        arrow = '⬇'
                    else:
                        arrow = '⬆'
                    
                    # Create the span tag with the arrow and percentage value
                    cellappendval =cells[5] if Type == 'Weekly' else cells[6]
                    cellappendval.append(soup.new_tag('br'))
                    span_tag = soup.new_tag('span', **{'class': 'percentage'},style='font-size: 0.7em;')
                    span_tag.string = f' ({arrow}{pnl_mom}% )'
                    
                    # Append the new line and span tag to the cell
                    # cells[3].append(soup.new_tag('br'))
                    cellappendval.append(span_tag)

            # percentage_textpnl =cells[7].text.strip() if Type == 'Weekly' else cells[7].text.strip()
            # percentage_textpnl =cells[6].text.strip() 
            # print('\n\n',percentage_textpnl)
            # if percentage_textpnl:
            #     # Remove commas and convert the text to a float for comparison
            #     try:
            #         pnl_percentage_value = float(percentage_textpnl.replace('%', '').replace(',', '').strip())
            #     except ValueError:
            #         continue  # Skip rows where percentage_textpnl is not a valid number
                
            #     cells[6].clear()
            #     print(pnl_percentage_value,'pnl_percentage_value')
            #     # Append the new span tag
            #     span_tag = soup.new_tag('span', **{'class': 'percentage'}, style='font-size: 0.9em;')
            #     span_tag.string = f'{pnl_percentage_value} %'
            #     cells[6].append(soup.new_tag('br'))
            #     cells[6].append(span_tag)
        # if len(cells) >= 4:
        #     percentage_text = cells[6].text.strip()
        #     if percentage_text:
        #         # print(float(percentage_text.replace('%', '').replace(',', '').strip()),'value')
        #         if percentage_text:
        #             # Remove commas and convert the text to a float for comparison
        #             try:
        #                 percentage_value = float(percentage_text.replace('%', '').replace(',', '').strip())
        #             except ValueError:
        #                 continue  # Skip rows where percentage_text is not a valid number
                    
        #             # Determine the arrow direction based on the percentage value
        #             if percentage_value < 0:
        #                 arrow = '⬇'
        #             else:
        #                 arrow = '⬆'
                    
        #             # Create the span tag with the arrow and percentage value
        #             cells[4].append(soup.new_tag('br'))
        #             span_tag = soup.new_tag('span', **{'class': 'percentage'},style='font-size: 0.7em;')
        #             span_tag.string = f' ({arrow}{percentage_value}% )'
                    
        #             # Append the new line and span tag to the cell
        #             # cells[3].append(soup.new_tag('br'))
        #             cells[4].append(span_tag)

        #     percentage_textpnl = cells[7].text.strip()
        #     if percentage_textpnl:
        #         # print(float(percentage_text.replace('%', '').replace(',', '').strip()),'value')
        #         if percentage_textpnl:
        #             # Remove commas and convert the text to a float for comparison
        #             try:
        #                 pnl_percentage_value = float(percentage_textpnl.replace('%', '').replace(',', '').strip())
        #             except ValueError:
        #                 continue  # Skip rows where percentage_textpnl is not a valid number
                    
        #             # Determine the arrow direction based on the percentage value
        #             if pnl_percentage_value < 0:
        #                 arrow = '⬇'
        #             else:
        #                 arrow = '⬆'
                    
        #             # Create the span tag with the arrow and percentage value
        #             cells[5].append(soup.new_tag('br'))
        #             span_tag = soup.new_tag('span', **{'class': 'percentage'},style='font-size: 0.7em;')
        #             span_tag.string = f' ({arrow}{pnl_percentage_value}% )'
                    
        #             # Append the new line and span tag to the cell
        #             # cells[3].append(soup.new_tag('br'))
        #             cells[5].append(span_tag)


  
    header_cells = soup.find_all('th')
    if len(header_cells) > 0:
        # Decompose the last two header cells
        header_cells[-2].decompose()
        header_cells[-1].decompose()

    # Iterate over each row to decompose the last two cells
    for row in soup.find_all('tr'):
        cells = row.find_all('td')
        if cells:
            # Decompose the last two cells
            cells[-2].decompose()
            cells[-1].decompose()

    # Remove the header for the 8th column
    


    headers = soup.find_all('th')
    if len(headers) > 0:
        headers[0]['colspan'] = 1
        headers[0]['style'] = "background-color: #F1F1F1;"
        for i in range(1, len(headers)):
            headers[i]['style'] = "background-color: #F1F1F1;"
            if headers[i].text == f'Week of {formatted_dateEnding}':
                headers[i]['colspan'] = 5
            # elif headers[i].text == 'MTD':
            #     headers[i]['colspan'] = 3

    

    if Type=='Weekly':
        MTd_html_table = Mtd_df.to_html(border=0, index=False, justify='center', classes='dataframe', table_id='weekly_table')
        # Parse the HTML with BeautifulSoup
        Mtd_df_soup = BeautifulSoup(MTd_html_table, 'html.parser')

        Mtdheaders = Mtd_df_soup.find_all('th')
        if len(Mtdheaders) > 0:
            Mtdheaders[0]['colspan'] = 1
            Mtdheaders[0]['style'] = "background-color: #F1F1F1;"
            for i in range(1, len(Mtdheaders)):
                Mtdheaders[i]['style'] = "background-color: #F1F1F1;"
                if Mtdheaders[i].text == f'Week of {formatted_dateEnding}':
                    Mtdheaders[i]['colspan'] = 6

        Final_Html_MTDtemplate = str(Mtd_df_soup)
    else:
        Final_Html_MTDtemplate=''

    



    Final_Html_weeklytemplate = str(soup)

    
    Today_date = datetime.strptime(Today, "%Y-%m-%d").date()

    subject_MonthStarting = MonthStarting.strftime("%B %-d")
    print(subject_MonthStarting)
    subject_Today = Today_date.strftime("%-d, %Y")


    if Type=='Monthly':
        subjectname='Monthly'
        MTDsubject=''
    elif Type=='Weekly':
        subjectname='Weekly'
        MTDsubject = f"MTD Report ({subject_MonthStarting} to {subject_Today})"  
    else:
        subjectname='Quarterly'


    html_content=EmailTemplate_Doc.response_html.format(WeeklyReport=Final_Html_weeklytemplate,Subject=subject,sales_employee_name=sales_employee_name,MTDReport=Final_Html_MTDtemplate,MTDsubject=MTDsubject,subjectname=subjectname)


   
    return table_css_style+html_content



 

@frappe.whitelist()
def EmailTemplate(Tabletructure,EmailTemplate_Doc,formatted_datestarted,formatted_dateEnded,SaleEmployeeEmail,Type):
    print(SaleEmployeeEmail,'\n\n')
  
    current_directory = os.path.dirname(__file__)
    # print(SaleEmployeeEmail,'\n\n')
    # file_path = os.path.abspath(os.path.join(current_directory, 'EmailTemplate.html'))
    file_path = os.path.abspath(os.path.join(current_directory, '..','EmailTemplate.html'))
    # print(file_path)
    
    with open(file_path, 'r') as f:
        template_str = f.read()
   

    MessageContent=Tabletructure
    template = Template(template_str)
    rendered_message = template.render(
        message   =MessageContent
    )    

    internalPerson_email_list = []

    for SingleEmail in EmailTemplate_Doc.custom_internal_email_recipients:
        # Append each email address to the list
        internalPerson_email_list.append(SingleEmail.employee_email)

    # recipients_list = list(set(internalPerson_email_list)) + [SaleEmployeeEmail]
    recipients_list = list(set(internalPerson_email_list)) 
   

    external_poc_list = EmailTemplate_Doc.custom_external_poc
    external_poc_list = external_poc_list.split(',') if external_poc_list else []


    cc_list = list(set(external_poc_list))


    # print(recipients_list,'recipients_list')
    # print(cc_list,'cc_list')
    # print(formatted_datestarted,formatted_dateEnded)
    start_date = datetime.strptime(formatted_datestarted, "%d %B %Y")
    end_date = datetime.strptime(formatted_dateEnded, "%d %B %Y")

    # Format the dates for the subject line
    subject_start_date = start_date.strftime("%B %-d")
    subject_end_date = end_date.strftime("%-d, %Y")

    if start_date.month == end_date.month:
        subject = f"{subject_start_date} to {subject_end_date}"
    else:
        subject_end_date = end_date.strftime("%b %-d, %Y")  # Use abbreviated month name for end date
        subject = f"{subject_start_date} to {subject_end_date}"

    # print(recipients_list,'recipients_list')
    # print(subject,'subject')
    if Type=='Monthly':
        EmailSubject= 'Sales Monthly Report - Export for' + f' {subject} '
    elif Type=='Weekly':
        EmailSubject= 'Sales Weekly Report - Export for' + f' {subject} '
    else:
        EmailSubject= 'Sales Quarterly Report - Export for' + f' {subject} '
        # EmailSubject='Quarterly'

    # formatted_datestarted,formatted_dateEnded
    email_args={
        "recipients":recipients_list,
        "message":rendered_message,
        "cc": cc_list,
        "subject": EmailSubject
        # subject = EmailTemplate_Doc.subject + f' From {formatted_dateStarting} to {formatted_dateEnding}'

    }

    frappe.enqueue(method=frappe.sendmail,queue='short',timeout=300, **email_args)




