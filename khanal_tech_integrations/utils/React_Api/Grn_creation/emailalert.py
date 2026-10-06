import frappe
from frappe.utils import add_to_date
from datetime import datetime,date
from jinja2 import Template
import json
import os


@frappe.whitelist()
def Sent_GRN_mail(docName,DraftInvoice):
    doc = frappe.get_doc('SAP GRN Creation',docName)
    print('%'*10)
 
    resulted_List = []
    

    input_dict = json.loads(doc.itemitems)
    for item in input_dict:
        if 'DocumentLines' in item:
            for SingleLine in item['DocumentLines']:
                if SingleLine.get('InputValue') is not None and SingleLine['InputValue'] != '':
                    
                    new_item = {
                        'id': item['id'],
                        'skuName': item['skuName'],
                        'skuDesc': item['skuDesc'],
                        'Quantity': item['Quantity'],
                        'AccountCode': item['AccountCode'],
                        'WarehouseCode': item['WarehouseCode'],
                        'RemainingOpenQuantity': item['RemainingOpenQuantity'],
                        'Price': item['Price'],
                        'BatchNumber': SingleLine['BatchNumber'],
                        'InputValue': SingleLine['InputValue'],
                    }
                    if SingleLine.get('MoistureValue') is not None and SingleLine['MoistureValue'] != '':
                        new_item['MoistureValue'] = SingleLine['MoistureValue']
                    
                    # Append the new dictionary to the output list
                    resulted_List.append(new_item)
            


    

    file_path = os.path.join(os.path.dirname(__file__), 'emailalert.html')
    # print(file_path,'filepath')
    with open(file_path, 'r') as f:
        # contents = f.read()
        # print(contents)
        template_str = f.read()
    print(resulted_List)
    print(DraftInvoice)

    template = Template(template_str)

    rendered_message = template.render(
            resulted_List   =resulted_List,
            InvoiceNumber   =doc.invoice_number,
            InvoiceDate     = doc.invoice_date,
            ReceivedDate    = doc.received_date,
            DraftInvoice    =DraftInvoice
        )
   
    
    # recipients=['shahil@khanalfoods.com']
    recipients=['shivakumar@khanalfoods.com','rakesh.babu@khanalfoods.com ','mratyunjay@khanalfoods.com','harsha@khanalfoods.com','yogesha@khanalfoods.com']
    # recipients=['harsha@khanalfoods.com']
    email_args={
            "recipients":recipients,
            "message":rendered_message,
            "subject":'Notification: GRN Uploaded to Draft - Invoice #'+str(DraftInvoice), 
            # "subject":`Notification: GRN Uploaded to Draft - Invoice #+12342`,    
                    }
    frappe.enqueue(method=frappe.sendmail,queue='short',timeout=300, **email_args)
       

# # bench --site dev.localhost execute khanal_tech_integrations.utils.logistics.notification.daily_progress
# # bench --site beta.khanaltech.com execute khanal_tech_integrations.utils.logistics.notification.daily_progress
# # bench --site khanaltech.com execute khanal_tech_integrations.utils.logistics.notification.daily_progress