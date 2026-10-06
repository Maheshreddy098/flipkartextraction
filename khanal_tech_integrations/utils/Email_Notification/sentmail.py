
import frappe
import os
from jinja2 import Template
from collections import Counter
from datetime import datetime,date

def Sent_Mail(invoices_data,contact_email):
    # print(invoices_data,'invoices_data')
    # print(contact_email,'contact_email')
    # Count occurrences of customer names and salesperson emails
    # from collections import Counter
    print(f"\n\n\n\n{invoices_data}\n\n\n",'invoices_data')
  

        # Count occurrences of customer names and salesperson emails
        # Count occurrences of customer names and salesperson emails
    customer_name_counts = Counter(item['customer_name'] for item in invoices_data)
    salesperson_counts = Counter(item['salesperson_email'] for item in invoices_data if item['salesperson_email'])

    # Find the most common customer name
    try:
        most_common_customer_name, occurrences_customer = customer_name_counts.most_common(1)[0]
    except IndexError:
        most_common_customer_name, occurrences_customer = None, 0

    # Find the most common salesperson email
    try:
        most_common_salesperson, occurrences_salesperson = salesperson_counts.most_common(1)[0]
    except IndexError:
        most_common_salesperson, occurrences_salesperson = None, 0

    # Handle the case where the most_common_customer_name is None or Empty
    if not most_common_customer_name:
        try:
            most_common_customer_name, occurrences_customer = next((name, count) for name, count in customer_name_counts.most_common() if name)
        except StopIteration:
            most_common_customer_name, occurrences_customer = None, 0

    # Handle the case where the most_common_salesperson is None or Empty
    if not most_common_salesperson:
        try:
            most_common_salesperson, occurrences_salesperson = next((email, count) for email, count in salesperson_counts.most_common() if email)
        except StopIteration:
            most_common_salesperson, occurrences_salesperson = None, 0

    print("Most common customer name:", most_common_customer_name)
    print("Occurrences of most common customer name:", occurrences_customer)
    print("Most common salesperson:", most_common_salesperson)
    print("Occurrences of most common salesperson:", occurrences_salesperson)

    file_path = os.path.join(os.path.dirname(__file__), 'sentmail.html')
    # print(file_path,'filepath')
    with open(file_path, 'r') as f:
        # contents = f.read()
        # print(contents)
        template_str = f.read()
    template = Template(template_str)
    rendered_message = template.render(
       invoices_data=sorted(invoices_data, key=lambda x: x['difference'], reverse=True),
       customer_name=most_common_customer_name,
       most_common_salesperson=most_common_salesperson
            
        )

    recipient=[contact_email,most_common_salesperson,'ar@khanalfoods.com']
    Today = frappe.utils.nowdate()
    nowdate_obj = datetime.strptime(Today, '%Y-%m-%d').date()
    new_date_str = datetime.strftime(nowdate_obj, '%b %d %Y')
    print(recipient,'recipient')
    print(nowdate_obj,'nowdate_obj')
    print(new_date_str,'new_date_str')
    email_args={
            "recipients":recipient,
            "message":rendered_message,
            "subject": f'Gentle Reminder: Outstanding Payments for {most_common_customer_name} as of {new_date_str}',
            # "subject":`Notification: GRN Uploaded to Draft - Invoice #+12342`,    
                    }
    # # print(email_args,'email_args')
    frappe.enqueue(method=frappe.sendmail,queue='short',timeout=300, **email_args)
        # print('sent')
   
    pass