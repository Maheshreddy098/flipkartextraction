
import frappe
import requests
from datetime import datetime
import pandas as pd
# from khanal_tech_integrations.utils.React_Api.Ledger.EmailTemplate import Get_Ledger
# from khanal_tech_integrations.utils.React_Api.Ledger.RequestPage import Get_File
from khanal_tech_integrations.utils.React_Api.Ledger.EmailTemplate import Aprovel_Email,Reject_Email
import time
import io
import pdfkit
import json
import os

columns_to_select = ['ReferenceDate', 'Memo','Reference','Debit','Credit','Customer/Vendor Code','DueDate','TaxDate']

    
# df = pd.read_csv('/Users/shahilkhan/Desktop/khanalFoods/frappe-bench/apps/khanal_tech_integrations/khanal_tech_integrations/utils/React_Api/Ledger/JournalEntries.csv',usecols=columns_to_select) #!Test
# df = pd.read_csv('/home/frappe/frappe-bench/apps/khanal_tech_integrations/khanal_tech_integrations/utils/React_Api/Ledger/JournalEntries.csv',usecols=columns_to_select) ### *Live


# sites/dev.localhost/public/files/JournalEntries.csv
# /Users/shahilkhan/Desktop/khanalFoods/frappe-bench/sites/dev.localhost/public/files/JournalEntries.csv

# /Users/shahilkhan/Desktop/khanalFoods/ERPNext_AWS_Keypair.pem
# scp -i /Users/shahilkhan/Desktop/khanalFoods/ERPNext_AWS_Keypair.pem /Users/shahilkhan/Desktop/khanalFoods/frappe-bench/apps/khanal_tech_integrations/khanal_tech_integrations/utils/React_Api/Ledger/JournalEntries.csv ubuntu@172.31.2.168:/home/frappe/frappe-bench/apps/khanal_tech_integrations/khanal_tech_integrations/utils/React_Api/Ledger/


@frappe.whitelist()
def Get_List():
    ledger_details = frappe.db.get_list('Ledger Details', filters={'status': 'Not Seen'},order_by='added_date desc')
    # print(ledger_details)
    transformed_data=[]
    for item in ledger_details:
        doc=frappe.get_doc('Ledger Details',item)
        # print(doc)

        new_item = {
            "id": doc.name,
            "Start_Date": doc.start_date,
            "End_Date": doc.end_date,
            "Vendor_Code": doc.vendor_code,
            "Vendor_Name":doc.vendor_name,
            "User_Comments":doc.user_comments,
            "User_Name":doc.user_name,
            # "Added_Date":doc.added_date,
        }
        transformed_data.append(new_item)


    # print(transformed_data)

    return transformed_data
            



@frappe.whitelist()
def Action_Taken(id,additional_comments,action):
    print('Action_Taken',id)
    
    # print('\n\n\n\n',id,'\n\n\n\n',additional_comments,'\n\n\n\n',action)
    try:
        doc=frappe.get_doc('Ledger Details',id)
        doc.other_comments=additional_comments
        doc.status=action
        
        # doc.save()
        # frappe.db.commit()
        if action=='Approved':
            # Get_Ledger(doc)
            # Get_Selected_File(doc)
            doc.save()
            frappe.db.commit()
            # return {"status": "success", "message": "Document saved successfully"}
        else:
            Reject_Email(doc)

        return {"status": "success", "message": "Document saved successfully"}

    except Exception as e:
        # Return an error response
        return {"status": "error", "message": str(e)}





@frappe.whitelist()
def SentMail_ForApproved():
    ledger_details = frappe.db.get_list('Ledger Details', filters={'status':'Approved','attachment': ['=', '']},order_by='added_date desc',pluck='name')
    print("Lenght of Ledger Mail needed to Sent: ",len(ledger_details))
    for Single_Ledger in ledger_details:
        try:
            # Get_Selected_File(Single_Ledger)
            Get_Filter_Journal(Single_Ledger)
        except Exception as e:
            print(f"Error fetching document: {e}")
            frappe.log_error(frappe.get_traceback(), str(e))
            # frappe.throw(f"Error fetching document: {e}")



# .SentMail_ForApproved
# bench --site khanaltech.com execute khanal_tech_integrations.utils.React_Api.Ledger.ApprovalPage.SentMail_ForApproved




# @frappe.whitelist()
# def Get_Selected_File(name):
#     doc=frappe.get_doc('Ledger Details',name)
#     print('Get_Selected_File',doc)
#     # columns_to_select = ['ReferenceDate', 'Memo','Reference','Debit','Credit','Customer/Vendor Code','DueDate','TaxDate']
#     # df = pd.read_csv('Ledger/JournalEntries.csv')
    
#     # df = pd.read_csv('/Users/shahilkhan/Desktop/WorkSpace/JournalEntries/Ledger/JournalEntries.csv',usecols=columns_to_select)

#     try:
#         # df = Get_File("http://beta.khanaltech.com/files/WorkingJournalEntries.xlsx", 'Sheet1')
#         # df = Get_File("http://beta.khanaltech.com/files/Live_AllComplete_JournalEntries_Dec_Jan.xlsx", 'Sheet1')
#         AccountCode = doc.vendor_code
#         df['ReferenceDate'] = pd.to_datetime(df['ReferenceDate'], format='%d/%m/%y', errors='coerce')
       
#         # Specify the start and end dates in datetime format
#         StartDate = pd.to_datetime(doc.start_date)
#         EndDate = pd.to_datetime(doc.end_date)

#         str_StartDate = StartDate.strftime('%d %B %Y')
#         str_EndDate = EndDate.strftime('%d %B %Y')
        


#         # Filter the DataFrame based on the given criteria
#         filtered_df = df[(df['ReferenceDate'] >= StartDate) & (df['ReferenceDate'] <= EndDate) & (df['Customer/Vendor Code'] == AccountCode)]
#         print(filtered_df, 'filtered_df')

#         previousData = df[(df['ReferenceDate'] < StartDate) & (df['Customer/Vendor Code'] == AccountCode)]
#         opening_balance = previousData['Debit'].sum() - previousData['Credit'].sum()
#         print(opening_balance,'opening_balance')
        
#         # total_balance = filtered_df['Debit'].sum() - filtered_df['Credit'].sum()
        
#         balanceFilter =filtered_df['Debit'].sum() - filtered_df['Credit'].sum()
#         print(balanceFilter,'balanceFilter')
#         caluclate_net = opening_balance + balanceFilter
#         print(caluclate_net,'caluclate_net')
#         TotalBalanceObtained= caluclate_net - opening_balance
#         print(TotalBalanceObtained,'TotalBalanceObtained')


#         filtered_df['CumulativeBalance'] = (filtered_df['Debit'] - filtered_df['Credit'])

#         total_balance=filtered_df['CumulativeBalance'].sum()
#         Net_Total = opening_balance+total_balance
#         print(Net_Total,'Net_Total')


#         Filter_result_df = filtered_df.rename(columns={'Memo': 'Remarks', 'Reference': 'Invoice Number'})

#         # Remove the 'ColumnToRemove' if it exists
#         Filter_result_df = Filter_result_df.drop(columns=['Customer/Vendor Code','CumulativeBalance'], errors='ignore')

#         # print(Filter_result_df,'Filter_result_df')
#         result_json = Filter_result_df.to_json(orient='records')

#         # Load JSON data
#         result_data = json.loads(result_json)

#         html_table = pd.json_normalize(result_data)
#         html_table = html_table.sort_values(by='ReferenceDate', ascending=True)
#         # Convert Unix timestamp to datetime for ReferenceDate
#         html_table['ReferenceDate'] = pd.to_datetime(html_table['ReferenceDate'], unit='ms')
#         html_table['ReferenceDate'] = html_table['ReferenceDate'].dt.strftime('%d %B %Y')

#         # Convert string to datetime for DueDate
#         html_table['DueDate'] = pd.to_datetime(html_table['DueDate'])
#         html_table['DueDate'] = html_table['DueDate'].dt.strftime('%d %B %Y')

#         html_table['TaxDate'] = pd.to_datetime(html_table['TaxDate'])
#         html_table['TaxDate'] = html_table['TaxDate'].dt.strftime('%d %B %Y')

#         # Format Credit column as Indian number system with commas
#         html_table['Credit'] = html_table['Credit'].apply(lambda x: "{:,}".format(x))
#         html_table['Debit'] = html_table['Debit'].apply(lambda x: "{:,}".format(x))


#         # Convert the column to integers and handle NaN values
#         # html_table['Invoice Number'] = html_table['Invoice Number'].fillna('').astype(int)
#         # print(html_table)

#         # Convert the DataFrame to HTML
#         html_table = html_table.to_html(index=False, classes='custom-table')
#         # Total_Balance=total_balance.apply(lambda x: "{:,}".format(x))
#         formatted_balance = "{:,.2f}".format(round(Net_Total, 2))
#         print(formatted_balance,'formatted_balance')
#         table_css_style = """
#             <style>
#             body {
#                     font-family: Arial, sans-serif;
#                 }

#                 p {
#                     font-size: 16px;
#                     font-weight: bold;
#                     margin-bottom: 10px;
#                 }
#                 .custom-table {
#                 border-collapse: collapse;
#                 width: 100%;
#             }

#             .custom-table th, .custom-table td {
#                 border: 1px solid #dddddd;
#                 text-align: left;
#                 padding: 8px;
#             }

#             .custom-table th {
#                 background-color: #f2f2f2;
#             }
#             </style>
#             """

#             # Rest of your existing CSS style
       

#         # Create HTML content with Opening Balance and the table, including style
#         # html_content = f"{css_style}<p>Bp Name: {doc.vendor_name}</p><br><p>Opening Balance: {total_balance}</p>{html_table}"
#         html_content=f"""{table_css_style}
#                     <div style="display: table-header-group">
#                 <h2 style="text-align: center; margin: 0">
#                     <b> Ledger Detail </b>
#                 </h2>

#                 <table style="width: 100%; table-layout: fixed">
#                     <tr>
#                         <td style="border-left: 1px solid #ddd; border-right: 1px solid #ddd">
#                             <div style="
#                     text-align: center;
#                     margin: auto;
#                     line-height: 1.5;
#                     font-size: 14px;
#                     color: #4a4a4a;
#                     ">
#                                 <img src="https://khanalfoods.com/wp-content/themes/khanalfoods/assets/img/khanalfoods/logo/Group.svg"
#                                     alt="" height="100" style="max-width: 100px; display: block; margin: auto;">
#                                 <span> Company ID : </span><br>
#                                 <span style="color: #00bb07">GST TIN :29AAFCK9270L1ZU</span>

#                             </div>
#                         </td>

#                         <td align="center" style="
#                     text-align: center;
#                     padding-left: 50px;
#                     line-height: 1.5;
#                     color: #323232;
#                 ">
#                             <div>
#                                 <h4 style="margin-top: 5px; margin-bottom: 5px">
#                                     Khanal Foods Pvt Ltd
#                                 </h4>

#                                 <p style="font-size: 14px">
#                                     NO 40, D M Nagappa,Garudachar palya,<br>
#                                     Mahadevapura,Bengaluru,560048 <br>
                                
#                                 </p>



#                             </div>
#                         </td>
#                         <td align="right" style="
                    
#                     border-left: 1px solid #ddd;
#                     border-right: 1px solid #ddd
#                 ">
#                             <div style="
#                     text-align: center;
#                     margin: auto;
#                     line-height: 1.5;
#                     font-size: 14px;
#                     color: #4a4a4a;
#                     ">
#                                 <b><span>Posting Period From</span>: <span>{str_StartDate}</span> </b><br>
#                                <b> <span>Posting Period To</span>: <span>{str_EndDate}</span> </b><br>
#                                <b> <span>Point of Contact</span>: <span>{doc.user_name}</span> </b>


#                             </div>
#                         </td>
#                     </tr>

#                 </table>
#             </div>
#             <table class="table table-bordered h4-14" style="width: 100%; -fs-table-paginate: paginate; margin-top: 15px">
#                 <thead style="display: table-header-group">

#                     <tr style="
#                 margin: 0;
#                 background: #cebd811f;
#                 padding: 15px;
#                 padding-left: 20px;
#                 -webkit-print-color-adjust: exact;
#                 ">

#                     </tr>
#                     <tr style="
#                 margin: 0;
#                 background: #c7c3b51f;
#                 padding: 15px;
#                 padding-left: 20px;
#                 -webkit-print-color-adjust: exact;
#                 ">
#                         <td colspan="5">
                                
#                             <h4 style="margin: 0">Net Balance:</h4>
#                             <p style="margin: 5px 0">{formatted_balance}</p><br>



#                         </td>
#                         <td colspan="5">

#                             <h4 style="margin: 0">Bp Name:</h4>
#                             <p style="margin: 5px 0">{doc.vendor_name}</p>

#                         </td>
#                     </tr>



#                 </thead>
#               <div style="margin-top: 15px;">
                      
#                 {html_table}
#         </div>
#                 <tfoot></tfoot>
#             </table>
#             """

       


        
#         html_filename = 'table.html'
#         timestamp = str(int(time.time()))
#         pdf_filename = f"LedgerDetail_{timestamp}.pdf"
#         # pdf_filename = 'output_styled.pdf'

#         with open(html_filename, 'w') as f:
#             f.write(html_content)

#         # print(html_content,'html_content')

#         # Convert HTML to PDF using pdfkit
#         pdfkit.from_file(html_filename, pdf_filename)
#         # Read PDF content
#         # with open(pdf_filename, 'rb') as pdf_file:
#         #     pdf_content = pdf_file.read()
#         aws_upload_url = "https://tg31l9q380.execute-api.us-west-1.amazonaws.com/dev/khanalfoods-fileupload-bucket/"+pdf_filename #!Live
#         headers = {
#             'pdf': 'application/pdf',
#             }
#         # aws_response = requests.put(aws_upload_url, headers=headers, data=pdf_content)
#         with open(pdf_filename, 'rb') as pdf_file:
#             files = {'file': (pdf_filename, pdf_file, 'application/pdf')}
#             aws_response = requests.put(aws_upload_url, headers=headers, files=files)

#         aws_response.raise_for_status()

#         file_url = 'https://khanalfoods-fileupload-bucket.s3.us-west-1.amazonaws.com/' + pdf_filename
#         doc.attachment = file_url
#         doc.save()
#         frappe.db.commit()
#         Aprovel_Email(doc)
#         os.remove(html_filename)
#         os.remove(pdf_filename)

#     except Exception as e:
#         frappe.throw(f"Error fetching document: {e}")



# bench --site dev.localhost execute khanal_tech_integrations.utils.React_Api.Ledger.ApprovalPage.Get_List


# C01200-615

# bench --site dev.localhost execute  --args "{ 'C01200-615' }"  khanal_tech_integrations.utils.React_Api.Ledger.ApprovalPage.Get_Filter_Journal

@frappe.whitelist()
def Get_Filter_Journal(name):
    doc=frappe.get_doc('Ledger Details',name)
    print('Get_Selected_File',doc)
    try:
        StartDate=doc.start_date
        EndDate=doc.end_date
        print(StartDate,'StartDate')
        print(EndDate,'EndDate')
        JournalEntriesList_List = frappe.get_list('SAP Journal Entries',
                            filters={
                                'referencedate': ['between', [StartDate, EndDate]],
                                'customervendor_code': doc.vendor_code
                            },
                            fields=['referencedate', 'memo', 'duedate', 'taxdate', 'reference', 'lineitem.customervendor_code', 'lineitem.debit', 'lineitem.credit'], as_list=True,order_by='referencedate asc',

                            )

        print(len(JournalEntriesList_List), 'Length of JournalEntriesList_List')
        # print(JournalEntriesList_List,'JournalEntriesList_List')
        str_StartDate = StartDate.strftime('%d %B %Y')
        str_EndDate = EndDate.strftime('%d %B %Y')
        formatted_entries = []
        for entry in JournalEntriesList_List:
            entry_date = entry[0]
            formatted_date = entry_date.strftime('%Y-%m-%d') if entry_date else None

            duedate = entry[2]
            formatted_duedate = duedate.strftime('%Y-%m-%d') if duedate else None

            taxdate = entry[3]
            formatted_taxdate = taxdate.strftime('%Y-%m-%d') if taxdate else None

            formatted_entry = (formatted_date, entry[1], entry[4],  entry[6], entry[7],entry[5],formatted_duedate, formatted_taxdate)
            formatted_entries.append(formatted_entry)
            # print(formatted_entry)
        # print(formatted_entries)


        columns_to_select = ['ReferenceDate', 'Memo', 'Reference', 'Debit', 'Credit', 'Customer/Vendor Code', 'DueDate', 'TaxDate']

        # Create DataFrame
        df = pd.DataFrame(formatted_entries, columns=columns_to_select)
        # print(formatted_entries,'formatted_entries')
        


        # Convert date columns to datetime objects
        date_columns = ['ReferenceDate', 'DueDate', 'TaxDate']
        df[date_columns] = df[date_columns].apply(pd.to_datetime)

        numeric_columns = ['Debit', 'Credit']
        df[numeric_columns] = df[numeric_columns].apply(pd.to_numeric, errors='coerce')
        # print(df)

        # # Sort DataFrame by 'ReferenceDate' in ascending order
        # df_sorted = df.sort_values(by='ReferenceDate')

        # print(df_sorted)
        df['CumulativeBalance'] = (df['Debit'] - df['Credit'])

        Filter_Data_Sum=df['CumulativeBalance'].sum()
        print(Filter_Data_Sum,'CumulativeBalance')


        # !--------------------To Calulate Opening Balance--------------------------------------------
        OpeningBalanceJournalEntriesList_List = frappe.get_list('SAP Journal Entries',
                            filters={
                                'referencedate': ['<', StartDate],
                                'customervendor_code': doc.vendor_code
                            },
                            fields=['referencedate', 'memo', 'duedate', 'taxdate', 'reference', 'lineitem.customervendor_code', 'lineitem.debit', 'lineitem.credit'], as_list=True, order_by='referencedate asc'
                            )

        # print(OpeningBalanceJournalEntriesList_List,'OpeningBalanceJournalEntriesList_List')
        str_StartDate = StartDate.strftime('%d %B %Y')
        str_EndDate = EndDate.strftime('%d %B %Y')
        OpeningBalanceformatted_entries = []
        for entry in OpeningBalanceJournalEntriesList_List:
            entry_date = entry[0]
            formatted_date = entry_date.strftime('%Y-%m-%d') if entry_date else None

            duedate = entry[2]
            formatted_duedate = duedate.strftime('%Y-%m-%d') if duedate else None

            taxdate = entry[3]
            formatted_taxdate = taxdate.strftime('%Y-%m-%d') if taxdate else None

            formatted_entry = (formatted_date, entry[1], entry[4],  entry[6], entry[7],entry[5],formatted_duedate, formatted_taxdate)
            OpeningBalanceformatted_entries.append(formatted_entry)
            # print(formatted_entry)
        # print(OpeningBalanceformatted_entries)


        columns_to_select = ['ReferenceDate', 'Memo', 'Reference', 'Debit', 'Credit', 'Customer/Vendor Code', 'DueDate', 'TaxDate']

        # Create DataFrame
        OpeningBalancedf = pd.DataFrame(OpeningBalanceformatted_entries, columns=columns_to_select)

        numeric_columns = ['Debit', 'Credit']
        OpeningBalancedf[numeric_columns] = OpeningBalancedf[numeric_columns].apply(pd.to_numeric, errors='coerce')
        OpeningBalaceTotal = OpeningBalancedf['Debit'].sum() - OpeningBalancedf['Credit'].sum()
        print(OpeningBalaceTotal,'OpeningBalaceTotal')
        # !--------------------To Calulate Opening Balance--------------------------------------------
        Net_Total = OpeningBalaceTotal+Filter_Data_Sum
        print(Net_Total,'Net_Total')
        Filter_result_df = df.rename(columns={'Memo': 'Remarks', 'Reference': 'Invoice Number'})

        # # Remove the 'ColumnToRemove' if it exists
        Filter_result_df = Filter_result_df.drop(columns=['Customer/Vendor Code','CumulativeBalance'], errors='ignore')
        print(Filter_result_df)
        
        # print(Filter_result_df,'Filter_result_df')
        result_json = Filter_result_df.to_json(orient='records')

        # Load JSON data
        result_data = json.loads(result_json)

        html_table = pd.json_normalize(result_data)
        html_table = html_table.sort_values(by='ReferenceDate', ascending=True)
        # Convert Unix timestamp to datetime for ReferenceDate
        html_table['ReferenceDate'] = pd.to_datetime(html_table['ReferenceDate'], unit='ms')
        html_table['ReferenceDate'] = html_table['ReferenceDate'].dt.strftime('%d %B %Y')

        # Convert string to datetime for DueDate
        html_table['DueDate'] = pd.to_datetime(html_table['DueDate'])
        html_table['DueDate'] = html_table['DueDate'].dt.strftime('%d %B %Y')

        html_table['TaxDate'] = pd.to_datetime(html_table['TaxDate'])
        html_table['TaxDate'] = html_table['TaxDate'].dt.strftime('%d %B %Y')

        # Format Credit column as Indian number system with commas
        html_table['Credit'] = html_table['Credit'].apply(lambda x: "{:,}".format(x))
        html_table['Debit'] = html_table['Debit'].apply(lambda x: "{:,}".format(x))


        # Convert the column to integers and handle NaN values
        # html_table['Invoice Number'] = html_table['Invoice Number'].fillna('').astype(int)
        # print(html_table)

        # Convert the DataFrame to HTML
        html_table = html_table.to_html(index=False, classes='custom-table')
        # Total_Balance=total_balance.apply(lambda x: "{:,}".format(x))
        Opening_Balance_Formated = "{:,.2f}".format(round(OpeningBalaceTotal, 2))
        formatted_balance = "{:,.2f}".format(round(Net_Total, 2))
        print(formatted_balance,'formatted_balance')
        table_css_style = """
            <style>
            body {
                    font-family: Arial, sans-serif;
                }

                p {
                    font-size: 16px;
                    font-weight: bold;
                    margin-bottom: 10px;
                }
                .custom-table {
                border-collapse: collapse;
                width: 100%;
            }

            .custom-table th, .custom-table td {
                border: 1px solid #dddddd;
                text-align: left;
                padding: 8px;
            }

            .custom-table th {
                background-color: #f2f2f2;
            }
            </style>
            """

            # Rest of your existing CSS style
        

        # Create HTML content with Opening Balance and the table, including style
        # html_content = f"{css_style}<p>Bp Name: {doc.vendor_name}</p><br><p>Opening Balance: {total_balance}</p>{html_table}"
        html_content=f"""{table_css_style}
                    <div style="display: table-header-group">
                    <h2 style="text-align: center; margin: 0">
                        <b> Ledger Detail </b>
                    </h2>

                    <table style="width: 100%; table-layout: fixed">
                        <tr>
                            <td style="border-left: 1px solid #ddd; border-right: 1px solid #ddd">
                                <div style="
                        text-align: center;
                        margin: auto;
                        line-height: 1.5;
                        font-size: 14px;
                        color: #4a4a4a;
                        ">
                                    <img src="https://khanalfoods.com/wp-content/themes/khanalfoods/assets/img/khanalfoods/logo/Group.svg"
                                        alt="" height="100" style="max-width: 100px; display: block; margin: auto;">
                                    <span> Company ID : </span><br>
                                    <span style="color: #00bb07">GST TIN :29AAFCK9270L1ZU</span>

                                </div>
                            </td>

                            <td align="center" style="
                        text-align: center;
                        padding-left: 50px;
                        line-height: 1.5;
                        color: #323232;
                    ">
                                <div>
                                    <h4 style="margin-top: 5px; margin-bottom: 5px">
                                        Khanal Foods Pvt Ltd
                                    </h4>

                                    <p style="font-size: 14px">
                                        NO 40, D M Nagappa,Garudachar palya,<br>
                                        Mahadevapura,Bengaluru,560048 <br>
                                    
                                    </p>



                                </div>
                            </td>
                            <td align="right" style="
                        
                        border-left: 1px solid #ddd;
                        border-right: 1px solid #ddd
                    ">
                                <div style="
                        text-align: center;
                        margin: auto;
                        line-height: 1.5;
                        font-size: 14px;
                        color: #4a4a4a;
                        ">
                                    <b><span>Posting Period From</span>: <span>{str_StartDate}</span> </b><br>
                                    <b> <span>Posting Period To</span>: <span>{str_EndDate}</span> </b><br>
                                    <b> <span>Point of Contact</span>: <span>{doc.user_name}</span> </b>


                                </div>
                            </td>
                        </tr>

                    </table>
                </div>
                <table class="table table-bordered h4-14" style="width: 100%; -fs-table-paginate: paginate; margin-top: 15px">
                    <thead style="display: table-header-group">

                        <tr style="
                    margin: 0;
                    background: #cebd811f;
                    padding: 15px;
                    padding-left: 20px;
                    -webkit-print-color-adjust: exact;
                    ">

                        </tr>
                        <tr style="
                    margin: 0;
                    background: #c7c3b51f;
                    padding: 15px;
                    padding-left: 20px;
                    -webkit-print-color-adjust: exact;
                    ">
                            <td colspan="5">
                                    
                             
                                <h4 style="margin: 0">Net Balance:</h4>
                                <p style="margin: 5px 0">{formatted_balance}</p><br>



                            </td>
                            <td colspan="5">

                                <h4 style="margin: 0">Bp Name:</h4>
                                <p style="margin: 5px 0">{doc.vendor_name}</p>

                            </td>
                        </tr>



                    </thead>
                    <div style="margin-top: 15px;">
                            
                    {html_table}
            </div>
                    <tfoot></tfoot>
                </table>
                """

    


    
        html_filename = 'table.html'
        timestamp = str(int(time.time()))
        pdf_filename = f"LedgerDetail_{timestamp}.pdf"
        # pdf_filename = 'output_styled.pdf'

        with open(html_filename, 'w') as f:
            f.write(html_content)

        # print(html_content,'html_content')

        # Convert HTML to PDF using pdfkit
        pdfkit.from_file(html_filename, pdf_filename)
        # Read PDF content
        # with open(pdf_filename, 'rb') as pdf_file:
        #     pdf_content = pdf_file.read()
        aws_upload_url = "https://tg31l9q380.execute-api.us-west-1.amazonaws.com/dev/khanalfoods-fileupload-bucket/"+pdf_filename #!Live
        headers = {
            'pdf': 'application/pdf',
            }
        # aws_response = requests.put(aws_upload_url, headers=headers, data=pdf_content)
        with open(pdf_filename, 'rb') as pdf_file:
            files = {'file': (pdf_filename, pdf_file, 'application/pdf')}
            aws_response = requests.put(aws_upload_url, headers=headers, files=files)

        aws_response.raise_for_status()

        file_url = 'https://khanalfoods-fileupload-bucket.s3.us-west-1.amazonaws.com/' + pdf_filename
        doc.attachment = file_url
        doc.save()
        frappe.db.commit()
        Aprovel_Email(doc)
        os.remove(html_filename)
        os.remove(pdf_filename)

    except Exception as e:
        frappe.throw(f"Error fetching document: {e}")