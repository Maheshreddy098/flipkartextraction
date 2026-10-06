import frappe
import json
from frappe.utils import add_to_date
from datetime import datetime
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
import os
from jinja2 import Template
import re

headersList = {
                "Accept": "*/*",
                "User-Agent": "Khanal Tech",
                "Content-Type": "application/json" 
}


# @frappe.whitelist()
# def SingleErrorCorrection(SinglePoID):
#     # Your existing code for sending individual emails


# @frappe.whitelist()
# def Table_Structure(SinglePoID):
#     doc = frappe.get_doc('Production Kiosk', SinglePoID)
#     preproduction_list=[]
#     combined_data = {}
#     for PreProductiondata in doc.pre_pro_associate_table_tab:
#         crateDoc = frappe.get_doc("Crate Assignment", PreProductiondata.crate_assignment)
#         preproduction_item_info = {
#             "ItemCode": crateDoc.item_code,
#             "ItemDescription": crateDoc.item_description,
#             "BatchNumber": crateDoc.batch_number,
#             "InputQuantity": PreProductiondata.input_quantity,
#         }
#         preproduction_list.append(preproduction_item_info)

#     for item in preproduction_list:
#         key = (item['ItemCode'], item['BatchNumber'])  # Create a tuple as key
#         quantity = float(item['InputQuantity'])  # Convert InputQuantity to integer
#         combined_data[key] = combined_data.get(key, 0) + quantity

#     table = "<table style='border-collapse: collapse; margin-top: 10px;'><tr><th style='border: 1px solid black; padding: 5px;'>ItemCode</th><th style='border: 1px solid black; padding: 5px;'>BatchNumber</th><th style='border: 1px solid black; padding: 5px;'>Total Qty</th></tr>"
#     for key,value in combined_data.items():
#         table += f"<tr><td style='border: 1px solid black; padding: 5px;'>{key[0]}</td><td style='border: 1px solid black; padding: 5px;'>{key[1]}</td><td style='border: 1px solid black; padding: 5px;'>{value}</td></tr>"
#     table += "</table>"


# @frappe.whitelist()
# def Error_MessageList():
#     List_of_production_Order = frappe.db.get_list('Production Kiosk', filters={'error_message':['!=',''],'sap_status':['!=','Production Cancelled'] },pluck='name')
#     print(len(List_of_production_Order))
#     for Single_List in List_of_production_Order:
#         # print (Single_List,'Single_List')
#         SingleErrorCorrection(Single_List)
#     pass



# @frappe.whitelist()
# def SingleErrorCorrection(SinglePoID):
#     doc = frappe.get_doc('Production Kiosk', SinglePoID)
#     current_directory = os.path.dirname(__file__)
#     file_path = os.path.abspath(os.path.join(current_directory, '..', 'Ledger', 'Emailtemplate.html'))

    
#     with open(file_path, 'r') as f:
#         template_str = f.read()
   

#     MessageContent=Content_Email(doc)
#     template = Template(template_str)
#     rendered_message = template.render(
#         message   =MessageContent
#     )    
#     email_args={
#             "recipients":['shahil@khanalfoods.com','shivakumar@khanalfoods.com','umesha@khanalfoods.com','srikanth@khanalfoods.com','mratyunjay@khanalfoods.com'],
#             "message":rendered_message,
#             "subject":f'Urgent: Error Message of  {doc.name}'
#                     }
#     # if attachments:email_args['attachments']=attachments
#     frappe.enqueue(method=frappe.sendmail,queue='short',timeout=300, **email_args)
#     doc.error_message=''
#     doc.save()
#     pass



# @frappe.whitelist()
# def Content_Email(doc):
#     message=''

    # if "10001153" in doc.error_message:
    #     Table_Data= Table_Structure(doc)
    #     message= doc.error_message+"\n"+Table_Data
    # elif "480000112" in doc.error_message:
    #     pattern = r'(?<=Batch/serial number\s)\b\w+\b'
    #     # Extracting the value using re.findall
    #     matches = re.findall(pattern, doc.error_message)
    #     # Printing the extracted value
    #     if matches:
    #         print("Extracted value:", matches[0])
    #         message=matches[0]  + ' is not present in DC-WIP kindly perform inventory transfer'
    #     else:
    #         print("No batch/serial number found in the string.")

    # elif "Quantity falls into negative inventory" in doc.error_message:    
    #     Table_Data= Table_Structure(doc)
    #     # result = "<p>\n".join([f"ItemCode: {key[0]}, BatchNumber: {key[1]}, Total Quantity Needed: {value}</p>" for key, value in combined_data.items()])
    #     message="Please review the inventory again as it appears that the quantity has fallen into negative levels\n" + Table_Data

    # else:
    #     message=doc.error_message


#     # print(message)
#     # print(preproduction_list)
#     message_html = """
#     <p>While doing issue for production, the following error occurred</p>
#     <p>{template_message}</p>
#     <p>To fix this, perform an inventory transaction.</p>
#     """.format(template_message=message)

#     return message_html
    


# def Table_Structure(doc):
#     preproduction_list=[]
#     combined_data = {}
#     for PreProductiondata in doc.pre_pro_associate_table_tab:
#         crateDoc = frappe.get_doc("Crate Assignment", PreProductiondata.crate_assignment)
#         preproduction_item_info = {
#             "ItemCode": crateDoc.item_code,
#             "ItemDescription": crateDoc.item_description,
#             "BatchNumber": crateDoc.batch_number,
#             "InputQuantity": PreProductiondata.input_quantity,
#         }
#         preproduction_list.append(preproduction_item_info)

#     for item in preproduction_list:
#         key = (item['ItemCode'], item['BatchNumber'])  # Create a tuple as key
#         quantity = float(item['InputQuantity'])  # Convert InputQuantity to integer
#         combined_data[key] = combined_data.get(key, 0) + quantity

#     table = "<table style='border-collapse: collapse; margin-top: 10px;'><tr><th style='border: 1px solid black; padding: 5px;'>ItemCode</th><th style='border: 1px solid black; padding: 5px;'>BatchNumber</th><th style='border: 1px solid black; padding: 5px;'>Total Qty</th></tr>"
#     for key,value in combined_data.items():
#         table += f"<tr><td style='border: 1px solid black; padding: 5px;'>{key[0]}</td><td style='border: 1px solid black; padding: 5px;'>{key[1]}</td><td style='border: 1px solid black; padding: 5px;'>{value}</td></tr>"
#     table += "</table>"

#     return table



#! ------------------------------------------IN Single Shot--------------------------------------------------------



@frappe.whitelist()
def consolidate_error_msg_list():
    data_presentTable = ""  # Initialize empty string to accumulate tables
    value_presentTable = ""
    List_of_production_Order = frappe.db.get_list('Production Kiosk', filters={'error_message':['!=',''],'sap_status':['!=','Production Cancelled'] },pluck='name')
    for Single_List in List_of_production_Order:
        doc = frappe.get_doc('Production Kiosk', Single_List)
        if "10001153" in doc.error_message:
            data_presentTable += Table_Structure(Single_List)
       
        elif "480000112" in doc.error_message:
            pattern = r'(?<=Batch/serial number\s)\b\w+\b'
            # Extracting the value using re.findall
            matches = re.findall(pattern, doc.error_message)
            # Printing the extracted value
            if matches:
                print("Extracted value:", matches[0])
                message=matches[0]  + ' is not present in DC-WIP kindly perform inventory transfer'
                value_presentTable += Normal_Structure(doc,message)
            else:
                print("No batch/serial number found in the string.")

        elif "Quantity falls into negative inventory" in doc.error_message:    
            data_presentTable += Table_Structure(Single_List)
            # result = "<p>\n".join([f"ItemCode: {key[0]}, BatchNumber: {key[1]}, Total Quantity Needed: {value}</p>" for key, value in combined_data.items()])

        else:
            value_presentTable += Normal_Structure(doc,doc.error_message)
        
    email_content = ""


    email_content += """
    <p>Please find below the consolidated error details:</p>
    """

    if data_presentTable:
        
        TableDATA = "<p>These errors occur because of insufficient quantity for the item or when the quantity falls into negative levels:</p><table style='border-collapse: collapse; margin-top: 10px;'><tr><th style='border: 1px solid black; padding: 5px;'>Production Number</th><th style='border: 1px solid black; padding: 5px;'>ItemCode</th><th style='border: 1px solid black; padding: 5px;'>BatchNumber</th><th style='border: 1px solid black; padding: 5px;'>Total Qty</th></tr>"
        data_presentTable = TableDATA + data_presentTable + "</table>"  # Combining TableDATA with data_presentTable
        email_content += f"{data_presentTable}"

    if value_presentTable:
        Newdata = "<p>Errors due to some other reason:</p><table style='border-collapse: collapse; margin-top: 10px;'><tr><th style='border: 1px solid black; padding: 5px;'>Production Number</th><th style='border: 1px solid black; padding: 5px;'>Reason</th></tr>"
        value_presentTable = Newdata + value_presentTable + "</table>"
        email_content += f"{value_presentTable}"

   

    if data_presentTable or value_presentTable:
        send_email(email_content)

    pass



def Table_Structure(SinglePoID):
    doc = frappe.get_doc('Production Kiosk', SinglePoID)
    preproduction_list = []
    combined_data = {}
    production_number = doc.name  # Get the production number

    for PreProductiondata in doc.pre_pro_associate_table_tab:
        crateDoc = frappe.get_doc("Crate Assignment", PreProductiondata.crate_assignment)
        preproduction_item_info = {
            "ItemCode": crateDoc.item_code,
            "ItemDescription": crateDoc.item_description,
            "BatchNumber": crateDoc.batch_number,
            "InputQuantity": PreProductiondata.input_quantity,
        }
        preproduction_list.append(preproduction_item_info)

    for item in preproduction_list:
        key = (item['ItemCode'], item['BatchNumber'])  # Create a tuple as key
        quantity = float(item['InputQuantity'])  # Convert InputQuantity to integer
        combined_data[key] = combined_data.get(key, 0) + quantity

   
    rowspan = len(combined_data) if len(combined_data) > 0 else 1  # Calculate rowspan for production number
    table = f"<tr><td rowspan='{rowspan}' style='border: 1px solid black; padding: 5px;'>{production_number}</td>"  # Add production number cell
    for index, (key, value) in enumerate(combined_data.items()):
        if index > 0:
            table += "</tr><tr>"  # Start new row for subsequent items
        table += f"<td style='border: 1px solid black; padding: 5px;'>{key[0]}</td><td style='border: 1px solid black; padding: 5px;'>{key[1]}</td><td style='border: 1px solid black; padding: 5px;'>{value}</td>"

    return table

def Normal_Structure(doc,message):
    
    table = f"<tr><td  style='border: 1px solid black; padding: 5px;'>{doc.name}</td><td  style='border: 1px solid black; padding: 5px;'>{message}</td></tr>"  # Add production number cell
    # Start new row for subsequent items
   

    return table


def send_email(content):
    current_directory = os.path.dirname(__file__)
    file_path = os.path.abspath(os.path.join(current_directory, '..', 'Ledger', 'Emailtemplate.html'))
    with open(file_path, 'r') as f:
        template_str = f.read()

    template = Template(template_str)
    rendered_message = template.render(
        message=content
    )


    Today = frappe.utils.nowdate()
    Yesterday = add_to_date(Today,days=-1)
    nowdate_obj = datetime.strptime(Yesterday, '%Y-%m-%d').date()
    new_date_str = datetime.strftime(nowdate_obj, '%b %d %Y')
    email_args = {
        "recipients": ['shivakumar@khanalfoods.com','umesha@khanalfoods.com','srikanth@khanalfoods.com'],
        "message": rendered_message,
        "cc": ['shahil@khanalfoods.com','mratyunjay@khanalfoods.com','harsha@khanalfoods.com','yogesha@khanalfoods.com'],
        "subject": f'Urgent: Consolidate Error Messages up to {new_date_str}'
    }
    frappe.enqueue(method=frappe.sendmail, queue='short', timeout=300, **email_args)

# /Users/shahilkhan/Desktop/khanalFoods/frappe-bench/apps/khanal_tech_integrations/khanal_tech_integrations/utils/React_Api/Production_Kiosk/Error_Correction.py

# bench --site dev.localhost execute khanal_tech_integrations.utils.React_Api.Production_Kiosk.Error_Correction.consolidate_error_msg_list