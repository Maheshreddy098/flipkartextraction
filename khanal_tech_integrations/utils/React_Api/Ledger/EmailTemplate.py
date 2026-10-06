import frappe
from frappe.utils import add_to_date
from datetime import datetime,date
from jinja2 import Template
import os
import requests
import pandas as pd
from frappe import _
import pandas as pd
# from frappe.utils.xlsxutils import write_xlsx_file
# from khanal_tech_integrations.utils.React_Api.Ledger.RequestPage import Get_File


def Get_File(url,sheetname):
    response = requests.get(url, verify=False)
    if response.status_code == 200:
        df = pd.read_excel(response.content,sheetname)
        return df
    else:
        print(f"Error: Unable to retrieve data from {url}")



@frappe.whitelist()
def Content_Email():
    message_html="""
    <p>An urgent approval is needed for a ledger request. Please click on the following link to review and approve:</p>

        <p><a href="http://erp.khanaltech.com/Ledger/Approval">erp.khanaltech.com</a></p>
    """
    # recipients=['shahil@khanalfoods.com']
    
    recipients=['anand.tiwari@khanalfoods.com']
    subject='Ledger Approval Request'
    Notification_Email(message_html,recipients,subject)


@frappe.whitelist()
def Aprovel_Email(doc):
    message_html = """
    <p>Your ledger has been approved. You may download it using the provided pdf:</p>
    <p><a href="{Link}">Ledger pdf</a> which will expire after 48 hours</p>
    <p>{Approvel_Message}</p>
    """.format(Link=doc.attachment,Approvel_Message=doc.other_comments)
    recipients=[doc.user_email]
    subject='Requested Ledger Deatils of '+doc.vendor_name
    Notification_Email(message_html,recipients,subject)



@frappe.whitelist()
def Reject_Email(doc):
    message_html = """
    <p>Your ledger has been declined due to {reason}.</p>
    """.format(reason=doc.other_comments)
    recipients=[doc.user_email]
    subject='Declined Ledger Deatils of '+doc.vendor_name
    Notification_Email(message_html,recipients,subject)



@frappe.whitelist()
def Notification_Email(get_content,recipients,subject):
    print('%'*10)
    file_path = os.path.join(os.path.dirname(__file__), 'Emailtemplate.html')
    with open(file_path, 'r') as f:
        template_str = f.read()
    # print(template_str)
    # get_content=Content_Email()
    template = Template(template_str)
    rendered_message = template.render(
            message   =get_content,
            
    )    
    email_args={
            "recipients":recipients,
            "message":rendered_message,
            "subject":subject
                    }
    # if attachments:email_args['attachments']=attachments
    frappe.enqueue(method=frappe.sendmail,queue='short',timeout=300, **email_args)
        # print('sent')
       



# @frappe.whitelist()
# def Get_Ledger(doc):
#     df = Get_File("http://beta.khanaltech.com/files/WorkingJournalEntries.xlsx", 'Sheet1')
#     print(doc)
#     StartDate   =doc.start_date
#     EndDate     =doc.end_date
#     AccountCode =doc.vendor_code
#     df['ReferenceDate'] = pd.to_datetime(df['ReferenceDate'])

#     # Filter the DataFrame based on the given criteria
#     filtered_df = df[(df['ReferenceDate'] >= StartDate) & (df['ReferenceDate'] <= EndDate) & (df['BP/Account Code'] == AccountCode)]

#     # Display the resulting DataFrame
#     print(filtered_df)


@frappe.whitelist()
def Get_Ledger(doc):
    

    df = Get_File("http://beta.khanaltech.com/files/WorkingJournalEntries.xlsx", 'Sheet1')
    AccountCode = doc.vendor_code
    df['ReferenceDate'] = pd.to_datetime(df['ReferenceDate'])
    # print(df['ReferenceDate'])
    # Specify the start and end dates in datetime format
    StartDate = pd.to_datetime(doc.start_date)  # Replace 'your_start_date' with the actual start date
    print(StartDate,'StartDate')
    EndDate = pd.to_datetime(doc.end_date)  # Replace 'your_end_date' with the actual end date

    # Filter the DataFrame based on the given criteria
    # filtered_df = df[(df['ReferenceDate'] >= StartDate) & (df['ReferenceDate'] <= EndDate) & (df['BP/Account Code'] == AccountCode)]
    # print(filtered_df,'filtered_df')

    # attachment_path='/Users/shahilkhan/Desktop/WorkSpace/JournalEntries/Filter/Excel1.xlsx'

    attachments=[frappe.attach_print('SAP AR Invoice Detail',12009,file_name=12009 )]
    # get_file_path()
    print("\n\n\n\n",attachments,"\n\n\n\n")

    # filtered_df.to_excel(attachment_path, index=False)
    # if os.path.exists(attachment_path):
    #     filtered_df.to_excel(attachment_path, index=False)
    #     attachments = [attachment_path]
    #     recipients=['shahil@khanalfoods.com']
    #     email_args = {
    #         "recipients": recipients,
    #         "message": 'hello',
    #         "subject": 'Ledger Email 12341',
    #     }

    #     if attachments:
    #         email_args['attachments'] = attachments
        

    #     print("\n\n\n\n",email_args,"\n\n\n\n")

    #     frappe.enqueue(method=frappe.sendmail, queue='short', timeout=300, **email_args) 
    #     print(frappe.enqueue)
    #     # rest of your code
    # else:
    #     print(f"Attachment file not found at: {attachment_path}")
    # attachments = [attachment_path]
    
    # Notification_Email()
    # return message_html






# # bench --site dev.localhost execute khanal_tech_integrations.utils.logistics.notification.daily_progress
# # bench --site beta.khanaltech.com execute khanal_tech_integrations.utils.logistics.notification.daily_progress
# # bench --site khanaltech.com execute khanal_tech_integrations.utils.logistics.notification.daily_progress