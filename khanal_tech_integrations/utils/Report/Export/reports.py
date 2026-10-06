import frappe
from jinja2 import Template
import json
from frappe.utils import nowdate, add_to_date, get_first_day, get_last_day
from datetime import datetime, timedelta

import pandas as pd
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
from khanal_tech_integrations.utils.Finance.AgeingReport import Make_AgeingReportForExport,ttJournalEntry_List,ttReceipt_List
from khanal_tech_integrations.utils.Finance.AgeingReport import Get_File
from khanal_tech_integrations.utils.Report.Ar_invoice import invoice_total
from khanal_tech_integrations.utils.Report.Ar_CreditNote import credit_note_total
from khanal_tech_integrations.utils.Report.IncomingPayment import incoming_total
from khanal_tech_integrations.utils.Report.GetSalesEmployee import ExportEmployeeList

from khanal_tech_integrations.utils.Report.Ecom.EcomCommonFile import currencyFormatInWords

headersList = {
    "Accept": "*/*",
    "User-Agent": "Khanal Tech",
    "Content-Type": "application/json",
    "Prefer": "odata.maxpagesize=10000",
}



#! bench --site dev.localhost execute   khanal_tech_integrations.utils.Report.Export.reports.Report_Generation_ForMonthly

def send_simple_email(template_name, recipient_name, recipient_email,sender_name, start_date, end_date, customer_data,Type):
    # Fetch the email template
    email_template = frappe.get_doc("Email Template", template_name)

    # Fetch the recipient email from the email template custom field
    external_poc_list = email_template.custom_external_poc
    external_poc_list = external_poc_list.split(',') if external_poc_list else []


    cc_list = list(set(external_poc_list))

    # Replace placeholders with dynamic variables using Jinja templating
    subject_template = Template(email_template.subject)
    body_template = Template(email_template.response_html)

    subject = subject_template.render(start_date=start_date, end_date=end_date)

    # Generate the customer rows for the table
    customer_rows = ""
    for customer in customer_data:
        customer_rows += f"""
        <tr>
            <td style="border-bottom: 1px solid #d89328; padding: 5px;"><span style="color:grey; font-weight:800;">{customer['customer_name']}<br> {customer['customer_code']}  </td>
            <td style="border-bottom: 1px solid #d89328; padding: 5px; text-align: right;">{customer['currency']}</td>
            <td style="border-bottom: 1px solid #d89328; padding: 5px; text-align: right;">{customer['opening_balance_due']}</td>
            <td style="border-bottom: 1px solid #d89328; padding: 5px; text-align: right;">{customer['invoice_total']}</td>
            <td style="border-bottom: 1px solid #d89328; padding: 5px; text-align: right;">{customer['return_total']}</td>
            <td style="border-bottom: 1px solid #d89328; padding: 5px; text-align: right;">{customer['revenue']}</td>
            <td style="border-bottom: 1px solid #d89328; padding: 5px; text-align: right;">{customer['payments_received']}</td>
            <td style="border-bottom: 1px solid #d89328; padding: 5px; text-align: right;">{customer['gst_receivable']}</td>
            <td style="border-bottom: 1px solid #d89328; padding: 5px; text-align: right;">{customer['closing_balance_due']}</td>
        </tr>
        """

    body = body_template.render(
        start_date=start_date,
        end_date=end_date,
        recipient_name=recipient_name,
        sender_name=sender_name,
        customer_rows=customer_rows
    )

    # Send the email
    # frappe.sendmail(recipients=[recipient_email], subject=subject, message=body)

    start_date = datetime.strptime(start_date, "%d %B %Y")
    end_date = datetime.strptime(end_date, "%d %B %Y")

    # Format the dates for the subject line
    subject_start_date = start_date.strftime("%B %-d")
    subject_end_date = end_date.strftime("%-d, %Y")

    if start_date.month == end_date.month:
        subject = f"{subject_start_date} to {subject_end_date}"
    else:
        subject_end_date = end_date.strftime("%b %-d, %Y")  # Use abbreviated month name for end date
        subject = f"{subject_start_date} to {subject_end_date}"



    # EmailSubject= email_template.subject + f' {subject} '
    if Type=='Monthly':
        EmailSubject= 'Sales Monthly Report - Export for' + f' {subject} '
    elif Type=='Weekly':
        EmailSubject= 'Sales Weekly Report - Export for' + f' {subject} '
    else:
        EmailSubject= 'Sales Quarterly Report - Export for' + f' {subject} '

    email_args={
        "recipients":recipient_email,
        "message":body,
        "cc": cc_list,
        "subject":EmailSubject,
    }

    frappe.enqueue(method=frappe.sendmail,queue='short',timeout=300, **email_args)




def Report_Generation_ForMonthly():
    Today = nowdate()
    StartDate = get_first_day(add_to_date(Today, months=-1)).strftime("%Y-%m-%d")
    EndDate = get_last_day(add_to_date(Today, months=-1)).strftime("%Y-%m-%d")
    # DayBeforeStartDate = get_last_day(add_to_date(Today, months=-2)).strftime("%Y-%m-%d")
    ReportGeneration(StartDate,EndDate,'Monthly')

    pass


# bench --site khanaltech.com execute   khanal_tech_integrations.utils.Report.Export.reports.Report_Generation_ForMonthly

def Report_Generation_ForWeekly():
    Today = nowdate()
    StartDate = (datetime.strptime(Today, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
    EndDate = (datetime.strptime(StartDate, "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%d")
    print(StartDate,EndDate)

    ReportGeneration(StartDate,EndDate,'Weekly')
    pass

def parse_balance(balance):
    balance = balance.replace(',', '')  # Remove commas
    if 'Cr' in balance:
        return float(balance.replace('Cr', '').strip()) * 1e7  # Convert Crores to numeric
    elif 'Lakh' in balance:
        return float(balance.replace('Lakh', '').strip()) * 1e5  # Convert Lakhs to numeric
    elif balance == '0':
        return float('-inf')  # Assign the lowest possible value to '0' to push it to the end in reverse sort
    else:
        return float(balance)  # Convert normal numbers and negative numbers



# bench --site khanaltech.com execute --args "('2024-09-16','2024-09-22','Weekly' )"     khanal_tech_integrations.utils.Report.Export.reports.ReportGeneration


@frappe.whitelist()
def ReportGeneration(StartDate, EndDate,Type):

    DayBeforeStartDate=add_to_date(StartDate,days=-1)
    # print(DayBeforeStartDate,'DayBeforeStartDate')
    # channel_Mapping = Get_File('https://dev.khanaltech.com/files/Channal Mapping.xlsx', 'Sheet1')
    channel_Mapping = ExportEmployeeList()

    StartDateAging = Make_AgeingReportForExport(DayBeforeStartDate)['CustomerData']
    StartDateAging = StartDateAging[StartDateAging['Customer/Vendor Code'].isin(channel_Mapping['BP Code'])]
    ob_cust_list = dict(zip(StartDateAging['Customer/Vendor Code'], StartDateAging['FC Balance Due']))

    EndDateAging = Make_AgeingReportForExport(EndDate)['CustomerData']
    EndDateAging = EndDateAging[EndDateAging['Customer/Vendor Code'].isin(channel_Mapping['BP Code'])]
    bd_cust_list = dict(zip(EndDateAging['Customer/Vendor Code'], EndDateAging['FC Balance Due']))

    currency_cust_list = dict(zip(channel_Mapping['BP Code'], channel_Mapping['Currency']))

    # Group the channel_Mapping by 'Email'
    grouped = channel_Mapping.groupby('Email')

    for email, group in grouped:
        customer_data = []
        for index, (bp_code, bp_name) in enumerate(zip(group['BP Code'], group['CardName'])):
            invoice_total_value = invoice_total(bp_code, StartDate, EndDate, 'Export')
            credit_total_value = credit_note_total(bp_code, StartDate, EndDate, 'Export')
            incoming_total_value = ttReceipt_List(StartDate, EndDate, bp_code)['TotalFC']
            gst_receivable_export = ttJournalEntry_List(StartDate, EndDate, bp_code)['TotalFC']

            opening_balance_due = ob_cust_list.get(bp_code, 0)
            closing_balance_due = bd_cust_list.get(bp_code, 0)
            
            # Create a dictionary for each customer
            # customer = {
            #     "customer_code": bp_code,
            #     "customer_name": bp_name,
            #     "currency": currency_cust_list[bp_code],
            #     "opening_balance_due": opening_balance_due,
            #     "invoice_total": invoice_total_value,
            #     "return_total": credit_total_value,
            #     "revenue": float(invoice_total_value) - float(credit_total_value),
            #     "payments_received": incoming_total_value,
            #     "gst_receivable": gst_receivable_export,
            #     "closing_balance_due": closing_balance_due,
            # }
            customer = {
                "customer_code": bp_code,
                "customer_name": bp_name,
                "currency": currency_cust_list[bp_code],
                "opening_balance_due": currencyFormatInWords(opening_balance_due),
                "invoice_total": currencyFormatInWords(invoice_total_value),
                "return_total": currencyFormatInWords(credit_total_value),
                "revenue": currencyFormatInWords(float(invoice_total_value) - float(credit_total_value)),
                "payments_received": currencyFormatInWords(incoming_total_value),
                "gst_receivable": currencyFormatInWords(gst_receivable_export),
                "closing_balance_due": currencyFormatInWords(closing_balance_due),
            }
            
            # Add the customer dictionary to the list
            customer_data.append(customer)


        # df = pd.DataFrame(customer_data)

        # # Save DataFrame to Excel
        # excel_filename = "/Users/shahilkhan/Desktop/WorkSpace/"
        # # df.to_excel(excel_filename+group['SalesEmployeeName'].iloc[0].xlsx, index=False)
        # df.to_excel(f"{excel_filename}_{group['SalesEmployeeName'].iloc[0]} part 5.xlsx", index=False)

        customer_data = sorted(customer_data, key=lambda x: parse_balance(x['closing_balance_due']), reverse=True)


    # Optionally, you can replace '-inf' back to '0' if needed
        for customer in customer_data:
            if parse_balance(customer['closing_balance_due']) == float('-inf'):
                customer['closing_balance_due'] = '0'


        customers_with_zero_values = []
        customers_with_non_zero_values = []

        for customer in customer_data:
            if all(customer[key] == '0' for key in customer if key not in ['customer_code', 'customer_name', 'currency']):
                customers_with_zero_values.append(customer)
            else:
                customers_with_non_zero_values.append(customer)



        sorted_customer_data = []

        # Append non-zero customers first
        sorted_customer_data.extend(customers_with_non_zero_values)

        # Append zero-value customers at the bottom
        sorted_customer_data.extend(customers_with_zero_values)


        # Send the email with the customer data specific to the group
        send_simple_email(
            template_name="Export Report Template",
            recipient_name=group['SalesEmployeeName'].iloc[0],
            recipient_email=email,
            sender_name="Khanal Foods Pvt. Ltd",
            start_date=convert_date(StartDate),
            end_date=convert_date(EndDate),
            customer_data=sorted_customer_data,
            Type=Type

        )

    # del StartDateAging
    # del EndDateAging
    # del StartDateAging



def convert_date(date_str):
    # Convert string to datetime object
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    # Format the date as 'DD Month YYYY'
    formatted_date = date_obj.strftime('%d %B %Y')
    return formatted_date