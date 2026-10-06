
import frappe
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
from frappe.utils import add_to_date, now, get_datetime, now_datetime
from khanal_tech_integrations.utils.Email_Notification.sentmail import Sent_Mail

from datetime import datetime,date

headersList = {
                "Accept": "*/*",
                "User-Agent": "Khanal Tech",
                "Content-Type": "application/json" 
            }



from itertools import groupby

@frappe.whitelist()
def exceed_duedate():
    Today = frappe.utils.nowdate()
    FromDate = add_to_date(Today, days=-1)
    HundredDaysBack = add_to_date(Today, days=-100)

    # Add 'contact_email' field to the list of fields to retrieve
    fields = ['docentry', 'contact_email']

    exceed_list = frappe.db.get_list(
        'SAP AR Invoice Detail',
        filters={
            'last_due_date': ['between', [HundredDaysBack, FromDate]],
            'doc_currency': 'INR'
        },
        fields=fields
    )

    # Process multiple email addresses separated by ";"
    for record in exceed_list:
        # Split the contact_email string by ";"
        nonsplitemail = record.get('contact_email')
        if nonsplitemail is not None:
            if ';' in nonsplitemail:
                contact_emails = nonsplitemail.split(';')
            else:
                contact_emails = [nonsplitemail]

            # Update the record with the list of contact_emails
            record['contact_emails'] = contact_emails

    # Flatten the list and sort it by 'contact_email'
    flattened_list = [
        {'docentry': record['docentry'], 'contact_email': email}
        for record in exceed_list
        for email in record.get('contact_emails', [])
    ]
    flattened_list.sort(key=lambda x: x.get('contact_email'))

    print(len(flattened_list), 'flattened_list')

    # Group the flattened results by 'contact_email'
    grouped_results = {}
    for key, group in groupby(flattened_list, key=lambda x: x.get('contact_email')):
        grouped_results[key] = list(group)

    # Now, grouped_results is a dictionary where keys are unique 'contact_email' values
    # and values are lists of records with the corresponding 'contact_email'
    
    # Example: Accessing the groups
    for contact_email, records in grouped_results.items():

        
        invoices_data = []
        recipients=[]
        greatest_last_due_date = None  # Initialize the variable before the loop

        for record in records:
            docentry = record.get('docentry')
            print(f"  DocEntry: {docentry}")
            session = AuthenticateSAPB1()
            doc_settings = frappe.get_doc('SAP Settings')
            reqUrl = doc_settings.sap_b1_url+"Invoices({docentry})?$filter=DocumentStatus eq 'bost_Open'"
            Modified_Url = reqUrl.format(docentry=docentry)
            payload = ""
            response = session.request("GET", Modified_Url, data=payload,  headers=headersList,verify=False)
            status_code = response.status_code
            if status_code == 200:
                doc = frappe.get_doc('SAP AR Invoice Detail',docentry,cache=False)
                # print(doc)
                nowdate_obj = datetime.strptime(Today, '%Y-%m-%d').date()
                difference = (nowdate_obj - doc.last_due_date ).days
                print(docentry,'&'*20)
                print(difference,'#'*20)
                
                # difference = (nowdate_obj - doc.last_due_date).days
                # send_email = difference % 5 == 0

                # nowdate_obj = datetime.strptime(Today, '%Y-%m-%d').date()

                if greatest_last_due_date is None or doc.last_due_date < greatest_last_due_date:
                    greatest_last_due_date = doc.last_due_date
                if difference == 0:
                    difference="Last"
                else:
                    difference=difference
                new_date_str = datetime.strftime(doc.last_due_date, '%b %d %Y')
                str_docDate = datetime.strftime(doc.doc_date, '%b %d %Y')
                value = float(doc.bill_total) 
                formatted_value = '{:,.2f}'.format(value)
                format_get_value=formatINR(value)
                print(format_get_value,'format_get_valueformat_get_value')

                # formatted_value_indian = locale.format('%0.2f', value, grouping=True)
                invoicenum=doc.docnum
                customer_name=doc.customer_name
                salesperson_email=doc.salesperson_email
                series_name=doc.series_name
                doc_date=doc.doc_date
                invoice_data = {
                'series_name':series_name,
                'invoicenum': invoicenum,
                'formatted_value': format_get_value,
                'due_date': new_date_str,
                'difference':difference,
                'customer_name':customer_name,
                'salesperson_email':salesperson_email,
                'docDate':str_docDate

                }
                
                invoices_data.append(invoice_data)

      
        # Check if send_email is True before calling Sent_Mail
        # print(send_email,'send_email')
        # if send_email:
        # Determine send_email based on the greatest last_due_date
        print(greatest_last_due_date,'greatest_last_due_date')
        if greatest_last_due_date is not None:
            send_email = (nowdate_obj - greatest_last_due_date).days % 5 == 0
        else:
            send_email = False

        # Check if send_email is True before calling Sent_Mail
        if send_email:
            Sent_Mail(invoices_data, contact_email)

                

            
# import locale
def formatINR(number):
    s, *d = str(number).partition(".")
    r = ",".join([s[x-2:x] for x in range(-3, -len(s), -2)][::-1] + [s[-3:]])
    return "".join([r] + d)
# # Define a custom grouping format for Indian numbering system
# def format_indian_number(number, decimal_places=2):
#     try:
#         locale.setlocale(locale.LC_NUMERIC, 'en_IN')
#     except locale.Error:
#         locale.setlocale(locale.LC_NUMERIC, ('en_US', 'UTF-8'))

#     formatted_number = '{:,.{prec}f}'.format(number, prec=decimal_places)

#     # Reset locale to the default
#     locale.setlocale(locale.LC_NUMERIC, '')

#     return formatted_number

# bench --site dev.localhost execute khanal_tech_integrations.utils.Email_Notification.reminder_mail.exceed_duedate


    
