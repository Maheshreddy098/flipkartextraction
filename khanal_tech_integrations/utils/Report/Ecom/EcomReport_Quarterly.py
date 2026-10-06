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
import numpy as np


# sap_df
Channel_Mapping={
    'C02574':'Snapdeal'       ,
    'C01186':'Amazon_IN_API'  ,
    'C03358':'CRED'           ,
    'C03121':'FLIPKART'       ,
    'C00623':'DOGSEE_SITE_IN' ,
    'C01026':'HN_SITE_IN'     ,
    'C03494':'ONDC_NSTORE'    ,
}

card_dict = {
    "C00127": "Amazon Seller Services Pvt Ltd",
    "C03358": "CRED",
    # "C03121": "Flipkart Internet Private Limited",
    "C03172": "JioMart Marketplace",
    # "C02574": "Snapdeal Private Limited",
    "C02836": "The North East Store",
    "C03170": "MOBIUSWORKS PRIVATE LIMITED",
    "C03174": "RK World Infocom Pvt Ltd",
    "C03311": "Amazon Retail India Pvt Ltd",
    "C03257": "Etrade Marketing Private Limited",
    "C03277": "Flipkart India Private Limited",
    "C03353": "Kiranakart Technologies Private Limited",
    "C03413": "Hands on trade Private limited",
    "C03275": "Innovative Retail Private Limited",
    "C03413": "Reliance Retail Limited",
    "C03267": "petfully yours private limited",
    "C03269": "Scootsy Logistics Private Limited",
    "C03412": "HalfCircleFull Ecommerce LLP",
    "C03161": "WINDLOCK PROJECT PRIVATE LIMITED",
    'C02574':'Snapdeal'       ,
    'C01186':'Amazon_IN_API'  ,
    'C03358':'CRED'           ,
    'C03121':'FLIPKART'       ,
    'C00623':'DOGSEE_SITE_IN' ,
    'C01026':'HN_SITE_IN'     ,
    'C03494':'ONDC_NSTORE'    ,
    'C03495':'MORE RETAIL PRIVATE LIMITED',
}
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


def EcomReport(start_date,end_date):
    unicom_df = pd.read_csv('/Users/shahilkhan/Desktop/WorkSpace/Ecom/Unicom jan to June.csv')
    # print(unicom_df,'unicom_df')
    # unicom_df
    # sap_df =pd.read_excel('/content/SAP Ar Invoice.xlsx')
    batchprice_df =pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Ecom/BatchPricing.xlsx')
    invoice_df =pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Ecom/Complete All Ar Invoice FromJan To May part 1.xlsx')
    credit_df =pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Ecom/_with Credit Note FromJan To May.xlsx')
    invoice_df = invoice_df[invoice_df['CardCode'].isin(card_dict.keys())]
    credit_df = credit_df[credit_df['CardCode'].isin(card_dict.keys())]

    invoice_df = invoice_df[invoice_df['ProductionBaseType'] != 13]
    exclude_statuses = ['csYes', 'csCancellation']

    # Filter the DataFrame
    invoice_df = invoice_df[~invoice_df['CancelStatus'].isin(exclude_statuses)]

    # start_date = pd.to_datetime('2024-01-01').date()
    # end_date = pd.to_datetime('2024-01-31').date()
    
    # print(unicom_df.columns,'\n\n\n')
    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    unicom_df['Created'] = pd.to_datetime(unicom_df['Created']).dt.date
    unicom_df = unicom_df[(unicom_df['Created'] >= start_date) & (unicom_df['Created'] <= end_date)]


    
    
    invoice_df['DocDate'] = pd.to_datetime(invoice_df['DocDate']).dt.date
    credit_df['DocDate'] = pd.to_datetime(credit_df['DocDate']).dt.date

    # Filter invoice_df and credit_df
    invoice_df = invoice_df[(invoice_df['DocDate'] >= start_date) & (invoice_df['DocDate'] <= end_date)]
    credit_df = credit_df[(credit_df['DocDate'] >= start_date) & (credit_df['DocDate'] <= end_date)]

    new_invoice_df = invoice_df[invoice_df['CardCode'].isin(card_dict.keys())]
    credit_df = credit_df[credit_df['CardCode'].isin(card_dict.keys())]

    # Merge filtered_invoice_df with batchprice_df
    invoice_merged_df = pd.merge(new_invoice_df, batchprice_df, how='left', left_on=['ItemCode', 'BatchNumber'], right_on=['Item No.', 'Batch Number'])

    # Merge filtered_credit_df with batchprice_df
    credit_merged_df = pd.merge(credit_df, batchprice_df, how='left', left_on=['ItemCode', 'BatchNumber'], right_on=['Item No.', 'Batch Number'])

    # Select relevant columns and rename them if necessary
    invoice_final_df = invoice_merged_df[['DocEntry', 'DocNum', 'DocDate', 'Without Tax', 'CardCode', 'CardName', 'DocDueDate',
                                        'LineNumber', 'ItemCode', 'BaseQuantity', 'ProductionBaseEntry', 'ProductionBaseType',
                                        'BatchNumber', 'LineQuantity', 'UnitPrice']]


    credit_final_df = credit_merged_df[['DocEntry', 'DocNum', 'DocDate', 'Without Tax', 'CardCode', 'CardName', 'DocDueDate',
                                        'LineNumber', 'ItemCode', 'BaseQuantity', 'InvoiceBaseEntry', 'ProductionBaseType',
                                        'BatchNumber', 'LineQuantity', 'UnitPrice']]

    grouped_invoice_df = invoice_final_df.groupby(['DocEntry', 'CardCode']).agg({'Without Tax': 'first'}).reset_index()
    invoicecardcode_grouped_df = grouped_invoice_df.groupby('CardCode').agg({'Without Tax': 'sum'}).reset_index()
    invoicecardcode_grouped_df['CardName'] = invoicecardcode_grouped_df['CardCode'].map(card_dict)


    # Credit
    grouped_credit_df = credit_final_df.groupby(['DocEntry', 'CardCode']).agg({'Without Tax': 'first'}).reset_index()
    creditcardcode_grouped_df = grouped_credit_df.groupby('CardCode').agg({'Without Tax': 'sum'}).reset_index()
    creditcardcode_grouped_df['CardName'] = creditcardcode_grouped_df['CardCode'].map(card_dict)

    # Merge invoicecardcode_grouped_df with creditcardcode_grouped_df on 'CardCode'
    comparison_df = pd.merge(invoicecardcode_grouped_df, creditcardcode_grouped_df, how='left', on='CardCode', suffixes=('_Invoice', '_Credit'))
    # Fill NaN values in 'Without Tax_Credit' with 0 for calculations
    comparison_df['Without Tax_Credit'] = comparison_df['Without Tax_Credit'].fillna(0)

    comparison_df['Without Tax_Invoice']= comparison_df['Without Tax_Invoice'].fillna(0)
    # Calculate the difference between 'Without Tax' in invoice and credit
    comparison_df['Difference'] = comparison_df['Without Tax_Invoice'] - comparison_df['Without Tax_Credit']

    # Display the final comparison DataFrame
    # print("Comparison DataFrame:")
    # print(comparison_df[['CardCode', 'CardName_Invoice', 'Without Tax_Invoice', 'Without Tax_Credit', 'Difference']])
    filtered_df = unicom_df[unicom_df['Sale Order Status'] == 'COMPLETE']

    # Further filter out rows where Shipping Package Status Code is 'RETURN_EXPECTED'
    filtered_df = filtered_df[filtered_df['Shipping Package Status Code'] != 'RETURN_EXPECTED']

    # Ensure 'Created' column is in datetime format without time
    filtered_df['Created'] = pd.to_datetime(filtered_df['Created']).dt.date

    # Group by 'Vendor Batch Number', 'Item SKU Code', 'Channel Name', and 'Created'
    grouped_df = filtered_df.groupby(['Vendor Batch Number', 'Item SKU Code', 'Channel Name', 'Created']).size().reset_index(name='Count')


    # Merge the DataFrames on the specified columns
    merged_df = pd.merge(grouped_df, batchprice_df, how='left', left_on=['Vendor Batch Number', 'Item SKU Code'], right_on=['Batch Number', 'Item No.'])

    # Select relevant columns and rename them if necessary
    Unicom_final_df = merged_df[['Vendor Batch Number', 'Item SKU Code', 'Channel Name', 'Created', 'Count', 'UnitPrice']]

    # Display the final DataFrame
    # print("Final DataFrame:")


    Unicom_final_df['CardCode'] = Unicom_final_df['Channel Name'].str.lower().map({v.lower(): k for k, v in card_dict.items()})



    Unicom_final_df['Total Price'] = Unicom_final_df['Count'] * Unicom_final_df['UnitPrice']
    Unicom_final_df = Unicom_final_df[['CardCode', 'Channel Name', 'Count', 'UnitPrice', 'Total Price']]

    final_Unicomgrouped_df = Unicom_final_df.groupby('CardCode').agg({'Total Price': 'sum'}).reset_index()


    invoice_withBatchmerged_df = invoice_df.dropna(subset=['BatchNumber'])

    invoice_withBatchmerged_df = pd.merge(invoice_withBatchmerged_df, batchprice_df, how='left', left_on=['ItemCode', 'BatchNumber'], right_on=['Item No.','Batch Number'])
    invoice_withBatchmerged_df['Total Price'] = invoice_withBatchmerged_df['LineQuantity'] * invoice_withBatchmerged_df['UnitPrice']
    # print(invoice_withBatchmerged_df)

    grouped_invoicewithbatch_df = invoice_withBatchmerged_df.groupby('CardCode').agg({'Total Price': 'sum'}).reset_index()
    # grouped_invoicewithbatch_df['Total Price']= grouped_invoicewithbatch_df['Total Price'].fillna(0)
    # # Add CardName from card_dict to the grouped DataFrame
    grouped_invoicewithbatch_df['CardName'] = grouped_invoicewithbatch_df['CardCode'].map(card_dict)
    # print(grouped_invoicewithbatch_df)



    final_Unicomgrouped_df['CardName'] = final_Unicomgrouped_df['CardCode'].map(card_dict)
    grouped_invoicewithbatch_df['CardName'] = grouped_invoicewithbatch_df['CardCode'].map(card_dict)


    # print(final_Unicomgrouped_df,'final_Unicomgrouped_df')
    # print(grouped_invoicewithbatch_df,'grouped_invoicewithbatch_df')

    # # Step 2: Merge the two DataFrames on 'CardCode'
    combainUnicom_invoice = pd.merge(final_Unicomgrouped_df, grouped_invoicewithbatch_df, on='CardCode', how='outer', suffixes=('_Unicom', '_Invoice'))

    # # Step 3: Fill NaN values with 0 for Total Price columns
    combainUnicom_invoice['Total Price_Unicom'].fillna(0, inplace=True)
    combainUnicom_invoice['Total Price_Invoice'].fillna(0, inplace=True)
    # combainUnicom_invoice['Difference'].fillna(0, inplace=True)

    # # # Step 4: Compute the combined Total Price
    combainUnicom_invoice['Cogs Total Price'] = combainUnicom_invoice['Total Price_Unicom'] + combainUnicom_invoice['Total Price_Invoice']

    # # # Select relevant columns
    final_combainUnicom_invoice = combainUnicom_invoice[['CardCode', 'Cogs Total Price']]
    
    Final_withCogsandRevenue = pd.merge(final_combainUnicom_invoice, comparison_df, on='CardCode', how='left')
    Final_withCogsandRevenue = Final_withCogsandRevenue[Final_withCogsandRevenue['CardCode'].isin(card_dict.keys())]
    Final_withCogsandRevenue['CardName'] = Final_withCogsandRevenue['CardCode'].map(card_dict)
    Final_withCogsandRevenue['PNL'] = Final_withCogsandRevenue['Difference'] - Final_withCogsandRevenue['Cogs Total Price']
    Final_withCogsandRevenue = Final_withCogsandRevenue[['CardCode', 'CardName', 'Without Tax_Invoice', 'Without Tax_Credit', 'Difference','Cogs Total Price','PNL']]


    cols_to_format = Final_withCogsandRevenue.columns[~Final_withCogsandRevenue.columns.isin(['CardCode','CardName'])]
    Final_withCogsandRevenue[cols_to_format] = Final_withCogsandRevenue[cols_to_format].applymap(currencyInIndiaFormat)


    # cols_to_format = AdvancePayment_df.columns[~AdvancePayment_df.columns.isin(['Bucket','% of Total Adv Payments'])]
    Final_withCogsandRevenue[cols_to_format] = Final_withCogsandRevenue[cols_to_format].applymap(format_negative)

    # Final_withCogsandRevenue['Without Tax_Invoice'].fillna('Not Avaliable in sap', inplace=True)
    # Final_withCogsandRevenue['Without Tax_Invoice'].fillna('Not Available in SAP', inplace=True)
    # Final_withCogsandRevenue['Without Tax_Invoice'].replace('', 'Not Available in SAP', inplace=True)
    # Final_withCogsandRevenue['Without Tax_Invoice'].fillna('Not Available in SAP', inplace=True)
    # Final_withCogsandRevenue.fillna(0, inplace=True)

    Final_withCogsandRevenue.rename(columns={
        'CardCode': 'Card Code',
        'CardName': 'Card Name',
        'Without Tax_Invoice': 'Invoice Total (in Rs.)',
        'Without Tax_Credit': 'Return Total (in Rs.)',
        'Difference': 'Revenue (Invoice - Return)',
        'Cogs Total Price': 'COGS',
        'PNL': 'PNL (Rev - COGS)',
    }, inplace=True)
    # Display the merged DataFrame
    # Final_withCogsandRevenue.fillna(0, inplace=True)
    # print(Final_withCogsandRevenue.dtypes)
    # print(Final_withCogsandRevenue)
    # Final_withCogsandRevenue.replace(np.nan,0)
    
    # Final_withCogsandRevenue.fillna('Missing')
    Final_withCogsandRevenue.replace('nan', 'Not Available in SAP', inplace=True)

    # print(Final_withCogsandRevenue)
    # print(comparison_df.columns,'comparison_df')
    return Final_withCogsandRevenue






# bench --site dev.localhost execute   khanal_tech_integrations.utils.Ecom.EcomReport.Get_MasterData


@frappe.whitelist()
def Get_MasterData():
    JanData=EcomReport('2024-01-01','2024-01-31')
    FebData=EcomReport('2024-02-01','2024-02-29')
    MarData=EcomReport('2024-03-01','2024-03-31')
    AprilData=EcomReport('2024-04-01','2024-04-30')
    MayData=EcomReport('2024-05-01','2024-05-31')
    
    EmailTemplate_Doc = frappe.get_doc('Email Template', 'Ecommerce Revenue Quarterly')
    

    
    CommonTabletructure=EmailFormat(JanData,FebData,MarData,AprilData,MayData,EmailTemplate_Doc)
    
    EmailTemplate(CommonTabletructure,EmailTemplate_Doc)



# def highlight_cogs(val):
#     # print(type(val),'val')
#     value = float(val.replace(',', ''))
#     print(value,'value')
#     try:
#         value = float(val.replace(',', ''))
#         color = 'red' if value > 6000 else 'black'
#     except ValueError:
#         color = 'black'


#     print(f'color: {color}')
#     return f'color: {color}'



# Function to generate HTML with conditional styling
def generate_html_with_styles(df):
    table_html = '<table class="noncustom-table">\n<thead>\n<tr>\n'
    
    # Add table headers
    for col in df.columns:
        table_html += f'  <th>{col}</th>\n'
    table_html += '</tr>\n</thead>\n<tbody>\n'
    
    # Add table rows
    for index, row in df.iterrows():
        table_html += '<tr>\n'
        for col in df.columns:
            value = row[col]
            if col == 'COGS':
                try:
                    numeric_value = float(value)
                    color = 'red' if numeric_value < 6000 else 'black'
                except ValueError:
                    color = 'black'
                table_html += f'  <td style="color: {color};">{value}</td>\n'
            else:
                table_html += f'  <td>{value}</td>\n'
        table_html += '</tr>\n'
    
    table_html += '</tbody>\n</table>'
    return table_html


def EmailFormat(JanData,FebData,MarData,AprilData,MayData,EmailTemplate_Doc):
    
    JanData_json_data = JanData.to_json(orient='records')
    FebData_json_data = FebData.to_json(orient='records')
    MarData_json_data = MarData.to_json(orient='records')
    AprilData_json_data = AprilData.to_json(orient='records')
    MayData_json_data = MayData.to_json(orient='records')



    JanData_html_table = pd.json_normalize(json.loads(JanData_json_data))
    FebData_html_table = pd.json_normalize(json.loads(FebData_json_data))
    MarData_html_table = pd.json_normalize(json.loads(MarData_json_data))
    AprilData_html_table = pd.json_normalize(json.loads(AprilData_json_data))
    MayData_html_table = pd.json_normalize(json.loads(MayData_json_data))

    # styled_JanData = JanData_html_table.style.applymap(highlight_cogs, subset=['COGS'])

    # print(styled_JanData,'\n\n')

    # JanData_html_table = styled_JanData.to_html(index=False, classes='noncustom-table')

    # styled_df = JanData_html_table.style.applymap(highlight_cogs, subset=['COGS'])
    # JanData_html_table = styled_df.to_html(index=False, classes='noncustom-table')


    JanData_html_table = generate_html_with_styles(JanData_html_table)

    FebData_html_table = FebData_html_table.to_html(index=False, classes='noncustom-table')
    MarData_html_table = MarData_html_table.to_html(index=False, classes='noncustom-table')
    AprilData_html_table = AprilData_html_table.to_html(index=False, classes='noncustom-table')
    MayData_html_table = MayData_html_table.to_html(index=False, classes='noncustom-table')

    style = """
    <style type="text/css">
    .noncustom-table {
    border-collapse: collapse;
    width: 100%;
    }
    .noncustom-table th, .noncustom-table td {
    border: 1px solid black;
    padding: 8px;
    text-align: left;
    }
    </style>
    """

    # Combine style and HTML
    full_html = f"{style}\n{JanData_html_table}"

    # Save to an HTML file (optional)
    with open("styled_table.html", "w") as file:
        file.write(full_html)

    # Print the HTML for viewing (optional)
    print(full_html)


    # EmailTemplate_Doc123 = type('EmailTemplate_Doc', (object,), {'response_html': '<html><body>{JanData_html_table}</body></html>'})
    # print('\n\n\n',JanData_html_table)


    html_content=EmailTemplate_Doc.response_html.format(JanData_html_table=full_html,FebData_html_table=FebData_html_table,MarData_html_table=MarData_html_table,AprilData_html_table=AprilData_html_table,MayData_html_table=MayData_html_table )


    # html_filename = 'table.html'
    # # pdf_filename = 'output_styled.pdf'

    # with open(html_filename, 'w') as f:
    #     f.write(html_content)


    return html_content



 

@frappe.whitelist()
def EmailTemplate(Tabletructure,EmailTemplate_Doc):
        
  
    current_directory = os.path.dirname(__file__)
    file_path = os.path.abspath(os.path.join(current_directory, '..','React_Api', 'Ledger', 'Emailtemplate.html'))

    
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

    recipients_list = list(set(internalPerson_email_list))
   

    external_poc_list = EmailTemplate_Doc.custom_external_poc
    external_poc_list = external_poc_list.split(',') if external_poc_list else []


    cc_list = list(set(external_poc_list))


    print(recipients_list,'recipients_list')
    print(cc_list,'cc_list')
    
    
    email_args={
        "recipients":recipients_list,
        "message":rendered_message,
        "cc": cc_list,
        "subject":EmailTemplate_Doc.subject
    }

    frappe.enqueue(method=frappe.sendmail,queue='short',timeout=300, **email_args)
