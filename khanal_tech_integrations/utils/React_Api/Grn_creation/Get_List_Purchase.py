import frappe
import json
from frappe.utils import add_to_date
# from datetime import datetime,date
from datetime import datetime,date
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
from khanal_tech_integrations.utils.React_Api.Grn_creation.emailalert import Sent_GRN_mail

import os
from jinja2 import Template
import re
headersList = {
                "Accept": "*/*",
                "User-Agent": "Khanal Tech",
                "Content-Type": "application/json" 
            }
@frappe.whitelist()
def GetPo_List():
    # print(poNumber)
    DocList = frappe.db.get_list("SAP Purchase Order",filters={'status': 'Open'},fields=['docentry', 'docnum','cardname'])
    return DocList



# import datetime

@frappe.whitelist()
def GetSingle_LineItem(DocEntry):
    # print(DocEntry,'Data')
    # DocEntry=7678
    SingleDoc = frappe.get_doc("SAP Purchase Order",DocEntry)
    # print(SingleDoc,'SingleDoc')
    # print(len(SingleDoc.lineitem),'SingleDoc.lineitem')
    dict_response = json.loads(SingleDoc.lineitem)
    # print(dict_response,'dict_response')
    transformed_data = []
    current_date = datetime.now()
    day = current_date.strftime("%d")  # GH
    month_letter = current_date.strftime("%b").upper()  
    year_last_two_digits = current_date.strftime("%y")  # JK
    Monthmapping = {
            'JAN': 'A',
            'FEB': 'B',
            'MAR': 'C',
            'APR': 'D',
            'MAY': 'E',
            'JUN': 'F',
            'JUL': 'G',
            'AUG': 'H',
            'SEP': 'I',
            'OCT': 'J',
            'NOV': 'K',
            'DEC': 'L'
        }
    # print(Monthmapping[month_letter],'*'*10)
    vendorcode_mapping = {
    'V00151': 'DT',
    'V00719': 'TB',
    'VOO259': 'HB',
    'V00732': 'UP',
    'V00519': 'PE',
    'V00609': 'SE',
    'V01049': 'SH',
    'V00332': 'KI',
    'V01034': 'SF',
    'V00736': 'UF',
    'V01378': 'CI'
    }
    # print(vendorcode_mapping[SingleDoc.cardcode],'*'*10)
    cardcode = SingleDoc.cardcode

    # if cardcode in vendorcode_mapping:
    #     mappedvalue = vendorcode_mapping[cardcode]
    # else:
    #     mappedvalue = 'NA'
    
    if frappe.db.exists("SAP Vendor Mapping",cardcode):
        vendor_mapped = frappe.get_doc("SAP Vendor Mapping",cardcode)
        mappedvalue=vendor_mapped.vendor_short_code
    else:
        mappedvalue='NA'


    



    for item in dict_response:
        if frappe.db.exists("SAP Mapping",item["ItemCode"]):
            code_list = frappe.get_doc("SAP Mapping",item["ItemCode"])
            code_variant_code=code_list.variant_product_code
        else:
            code_variant_code='NA00'

        new_item = {
            "id": item["LineNum"],
            "skuName": item["ItemCode"],
            "skuDesc": item["ItemDescription"],
            "Quantity": item["Quantity"],
            "AccountCode":item["AccountCode"],
            "WarehouseCode":item["WarehouseCode"],
            "RemainingOpenQuantity":item["RemainingOpenQuantity"],
            "Price":item["Price"],
            "DocumentLines": [
                {
                    "id": "1",
                    "BatchNumber": f"{mappedvalue}{code_variant_code}{day}{Monthmapping[month_letter]}{year_last_two_digits}"
                }
            ]
        }
        transformed_data.append(new_item)

    return transformed_data


# @frappe.whitelist()
# def ProcurementAdding_To_SAP(input_dict,RequestData):
    
#     Today = frappe.utils.nowdate()
#     FilterDate = add_to_date(Today,days=+365)
    
#     print(Today,'Today')
#     print(FilterDate,'FilterDate')
#     # print(RequestData['PoNumber'],'RequestData')
#     Single_Purchase_response=Get_Single_Purchase(RequestData['PoNumber'])
#     # input_dict = json.loads(storeData)
#     # print(type(storeData))
#     # print(Single_Purchase_response,'RequestData')
#     print('\n\n',input_dict,'\n\n',RequestData,'\n\n')
#     input_dictconverted = json.dumps(input_dict)
#     # print(type(input_dictconverted),'input_dictconverted Type')
#     # for i in storeData:
#     #     print(i)
#     # session       = AuthenticateSAPB1()
#     doc                                     = frappe.new_doc('SAP GRN Creation')
#     doc.vendor_code                         = Single_Purchase_response['CardCode']
#     doc.vendor_name                         = Single_Purchase_response['CardName']
#     doc.invoice_number                      = RequestData['InvoiceNumber']
#     doc.po_no                               = RequestData['PoNumber']
#     doc.invoice_date                        = RequestData['InvoiceDate']
#     doc.received_date                       = RequestData['ReceivedDate']
#     doc.itemitems                           = input_dictconverted
#     doc.type                                = 'GRN Creation'

#     doc.save()
#     frappe.db.commit()

#     purchase_payload = {    
#         "CardCode": Single_Purchase_response['CardCode'],
#         "CardName": Single_Purchase_response['CardName'],
#         # "Series": 210,
#         "NumAtCard": RequestData['InvoiceNumber'],
#         "DocObjectCode":20,
#         "DocDate" :RequestData['ReceivedDate'],
#         "TaxDate" :RequestData['ReceivedDate'],
#         "U_FrappeGRNKey" :doc.name,
#         "DocumentLines": [ ]
#                     }
#     # linenum_quantity = {i['skuName']:i['InputValue'] for i in input_dict}
    
#     # print(frappe.utils.nowdate(),'date')
#     # purchase_payload = {'DocumentLines': []}

#     # Iterate through each dictionary in the input_dict list
#     for single_dict in input_dict:
#         # Access the 'DocumentLines' key in the current dictionary
#         document_lines = single_dict.get('DocumentLines', [])
#         # print(document_lines,'document_lines')
#         # Iterate through each item in DocumentLines
#         for single_Lineitem in document_lines:
#             # Create a new dictionary for each item
#             # print(single_dict.get('skuName', ""),'single_Lineitem.get')
#             # print(single_Lineitem.get('InputValue', ""),'^'*10)
#             single_return_item = {
#                 "LineNum": int(single_dict.get('id', 0)),
#                 "ItemCode": single_dict.get('skuName', ""),
#                 "Quantity": float(single_Lineitem.get('InputValue', 0)),
#                 # "Price": single_dict.get('Price', 0),  
#                 "WarehouseCode": single_dict.get('WarehouseCode', ""),
#                 "AccountCode": single_dict.get('AccountCode', ""),
#                 "BaseType": 22,
#                 # "BaseEntry": data_dict['PonumberDocentry'],
#                 "BaseLine": int(single_dict.get('id', 0)),
#                 "BaseEntry":RequestData['PoNumber'],

#                 "BatchNumbers": []
#             }

#             # Get BatchNumber, Quantity, and ItemCode from the current item
#             batch_number = single_Lineitem.get('BatchNumber', "")
#             quantity = float(single_Lineitem.get('InputValue', 0))
#             item_code = single_Lineitem.get('skuName', "")

#             # Append BatchNumber to BatchNumbers list
#             single_return_item["BatchNumbers"].append({
#                 "BatchNumber": batch_number,
#                 "Quantity": float(quantity),
#                 "ItemCode": item_code,
#                 "BaseLineNumber": int(single_dict.get('id', 0)),  # Set the BaseLineNumber to the desired value
#                 "ExpiryDate":FilterDate,
#                 "ManufacturingDate": Today,
#                 "AddmisionDate": Today,
#             })

#             # Append the created item to DocumentLines list in purchase_payload
#             purchase_payload['DocumentLines'].append(single_return_item)

#     # Print the resulting purchase_payload
#     # print(purchase_payload)
#     doc_settings = frappe.get_doc('SAP Settings')
#     Url                     = doc_settings.sap_b1_url+"Drafts"
#     json_string = json.dumps(purchase_payload, indent=2)
#     print(f"\n\n\n\n{json_string}\n\n\n",'NOrmal GRN')
#     session       = AuthenticateSAPB1()
#     response      = session.request("POST", Url, data=json_string,  headers=headersList,verify=False)
#     # print(response)
#     if response.status_code==201:
       
#         Draft_Response  = dict(response.json())
#         Sent_GRN_mail(input_dict,RequestData,Draft_Response['DocNum'])
#         # print(Draft_Response['DocEntry'])
#         return Draft_Response['DocNum']   
#     else:
#         error_response = response.json().get('error', {})
#         error_message = error_response.get('message', {}).get('value', 'Unknown error')
#         print(f"Error: {error_message}")
#         return error_message  # You may want to handle the error case accordingly in your code

@frappe.whitelist()
def ProcurementAdding_To_SAP(input_dict, RequestData, GrnName):
    print(input_dict, 'type input_dict')
    print(RequestData, 'type RequestData')
    
    Today = frappe.utils.nowdate()
    FilterDate = frappe.utils.add_to_date(Today, days=+365)
    
    print(GrnName, 'GrnName')
    print(FilterDate, 'FilterDate')

    Single_Purchase_response = Get_Single_Purchase(RequestData['PoNumber'])
    
    input_dictconverted = json.dumps(input_dict, indent=4)

    contains_pmdc = False
    
    for item in input_dict:
        for line in item.get('DocumentLines', []):
            if line.get('ItemCode', '').startswith('RMDC') and not line.get('MoistureValue'):
                contains_pmdc = True
                break
        if contains_pmdc:
            break

    print(f"contains_pmdc: {contains_pmdc}")

    if GrnName:
        doc = frappe.get_doc("SAP GRN Creation", GrnName)
        new_doc = False
    else:
        doc = frappe.new_doc("SAP GRN Creation")
        new_doc = True

    doc.vendor_code = Single_Purchase_response['CardCode']
    doc.vendor_name = Single_Purchase_response['CardName']
    doc.invoice_number = RequestData['InvoiceNumber']
    doc.po_no = RequestData['PoNumber']
    doc.invoice_date = RequestData['InvoiceDate']
    doc.received_date = RequestData['ReceivedDate']
    doc.itemitems = input_dictconverted
    
    doc.moist_select = "QA Approval Pending" if contains_pmdc else "Sent to SAP"
    doc.type = 'GRN Creation'

    if new_doc:
        doc.insert()
    else:
        doc.save()

    frappe.db.commit()

    if GrnName:
        # print(doc.moist_select,'doc.moist_select')
        value = GrnPayloadForSAP(doc.name)
        return value

    if contains_pmdc:
        print('if moisture')
        email = ForMoistureValue(doc.name)
        return 'Saved For approval'
    else:
        print('else moisture')
        value = GrnPayloadForSAP(doc.name)
        return value


        

    
  
        
# bench --site alpha.localhost execute  --args "{ 'GRN-24-00061-9312' }" khanal_tech_integrations.utils.React_Api.Grn_creation.Get_List_Purchase.GrnPayloadForSAP

   
def GrnPayloadForSAP(docName):
    doc = frappe.get_doc('SAP GRN Creation',docName)

    # input_dict, RequestData, doc_name
    headersList = {"Content-Type": "application/json"}

    Single_Purchase_response = Get_Single_Purchase(doc.po_no)
    Today = frappe.utils.nowdate()
    FilterDate = frappe.utils.add_to_date(Today, days=+365)

    comment = "Posted Production kiosk tool"
    purchase_payload = {
        "CardCode": Single_Purchase_response['CardCode'],
        "CardName": Single_Purchase_response['CardName'],
        # "Series": 210,
        "NumAtCard": doc.invoice_number,
        "DocObjectCode": 20,
        "DocDate": doc.received_date.strftime('%Y-%m-%d'),
        "TaxDate": doc.received_date.strftime('%Y-%m-%d'),
        "U_FrappeGRNKey" :doc.name,
        "Comments":comment,
        "DocumentLines": []
    }
    input_dict = json.loads(doc.itemitems)
    print(input_dict,'input_dict','\n\n\n\n')

    # DocumentLines
    # linesingle_return_item = []
    filtered_data = []

    for item in input_dict:
        new_document_lines = [line for line in item['DocumentLines'] if 'InputValue' in line]
        if new_document_lines:
            new_item = item.copy()
            new_item['DocumentLines'] = new_document_lines
            filtered_data.append(new_item)

    print(filtered_data,'\n\n\n','filtered_data')

    # Process each single_dict in input_dict
    for single_dict in filtered_data:
        # print('single_dict', single_dict)
        if isinstance(single_dict, dict):
            document_lines = single_dict.get('DocumentLines', [])
        single_return_item = {
            "LineNum": int(single_dict.get('id', 0)),
            "ItemCode": single_dict.get('skuName', ""),
            "Quantity": single_dict.get('RemainingOpenQuantity', 0),
            "WarehouseCode": single_dict.get('WarehouseCode', ""),
            "AccountCode": single_dict.get('AccountCode', ""),
            "BaseType": 22,
            "BaseLine": int(single_dict.get('id', 0)),
            "BaseEntry": doc.po_no,
            "U_Moist_Qty":'',
            "BatchNumbers": []
        }

        for single_Lineitem in document_lines:
            # print('\n\n',float(single_Lineitem.get("MoistureValue")),'Moisture')
            # if 'MoistureValue' in single_Lineitem:  # Check if MoistureValue field exists
            if 'MoistureValue' in single_Lineitem and single_Lineitem['MoistureValue'] is not None and single_Lineitem['MoistureValue'] != "":
                single_return_item["U_Moist_Qty"] = float(single_Lineitem.get("MoistureValue",''))

            
            batch_number_detail = {
                "BatchNumber": single_Lineitem.get("BatchNumber"),
                "ExpiryDate": FilterDate,
                "ManufacturingDate": Today,
                "AddmisionDate": Today,
                "Quantity": single_Lineitem.get("InputValue"),
                "BaseLineNumber": single_Lineitem.get("LineID"),
                "ItemCode": single_Lineitem.get("ItemCode"),
                # "U_PrdAging": 0
           
            }

            # Append batch number detail to the BatchNumbers list
            single_return_item["BatchNumbers"].append(batch_number_detail)

        # Add to the list of processed items
        purchase_payload['DocumentLines'].append(single_return_item)



    # purchase_payload['DocumentLines'].append(linesingle_return_item)

    doc_settings = frappe.get_doc('SAP Settings')
    Url = doc_settings.sap_b1_url + "Drafts"

    # print('\n\n\n',purchase_payload,'\n\n\n')
    # print('\n\n\n',type(purchase_payload),'\n\n\n')
    json_string = json.dumps(purchase_payload)
    print('\n\n\n',json_string,'\n\n\n')
    # print('\n\n\n',type(json_string),'\n\n\n')
    session = AuthenticateSAPB1()
    response = session.request("POST", Url, data=json_string, headers=headersList, verify=False)
    print(response,'response')
    # print('response',response)
    if response.status_code == 201:
        Draft_Response = dict(response.json())
        doc.moist_select = "Sent to SAP"
        # doc.grn_docentry
        Sent_GRN_mail(docName, Draft_Response['DocNum'])
        doc.save()
        return Draft_Response['DocNum']
    else:
        error_response = response.json().get('error', {})
        error_message = error_response.get('message', {}).get('value', 'Unknown error')
        print(f"Error: {error_message}")
        return error_message


    

   
    


# [{'id': 0, 'skuName': 'PM000231', 'skuDesc': 'Essae-DS-252', 'Quantity': 3, 'DocumentLines': [{'id': '1', 'BatchNumber': 'GRN-PM000231-Essae-DS-252', 'InputValue': '32'}]}] 
# {'PoNumber': '7678', 'InvoiceNumber': '223', 'InvoiceDate': '2023-11-24T12:44:20.859Z', 'ReceivedDate': '2023-11-24T12:44:20.859Z'} 
    
    
   
def  Get_Single_Purchase(DocEntry):
    doc_settings = frappe.get_doc('SAP Settings')
    Url           = doc_settings.sap_b1_url+"PurchaseOrders({Docentry})"
    reqUrl_modified         = Url.format(Docentry=DocEntry) 
    session       = AuthenticateSAPB1()
    payload = ''
    response      = session.request("GET", reqUrl_modified, data=payload,  headers=headersList,verify=False)
    
    PurchaseorderOrder  = dict(response.json())
    return PurchaseorderOrder








# bench --site alpha.localhost execute khanal_tech_integrations.utils.React_Api.Grn_creation.Get_List_Purchase.GrnStillNotProcess
@frappe.whitelist()
def GrnStillNotProcess():
    # toDate                = str(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')) #"2022-08-26"
    fromDate              = add_to_date(datetime.now(),days=-5).strftime('%Y-%m-%d') #"2022-08-26"
    print(fromDate,'fromDate')
    # modified
    sap_grnList = frappe.db.get_list('SAP GRN Creation', filters={'modified': ['<=', fromDate] ,'grn_docnum':['=','']},pluck='name')
    print(len(sap_grnList))
    
    for SingleGrn in sap_grnList:
        SentMail=AlertEmail(SingleGrn)
        break
        
        





def AlertEmail(SingleGrn):
    doc = frappe.get_doc('SAP GRN Creation',SingleGrn)

    content=EmailContent(doc)
    current_directory = os.path.dirname(__file__)
    file_path = os.path.abspath(os.path.join(current_directory, '..', 'Ledger', 'Emailtemplate.html'))
    # print(file_path,'file_path')
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
        "recipients": ['shivakumar@khanalfoods.com','rakesh.babu@khanalfoods.com '],
        "message": rendered_message,
        "cc": ['shahil@khanalfoods.com','mratyunjay@khanalfoods.com','harsha@khanalfoods.com','yogesha@khanalfoods.com'],
        # "subject": 'Urgent: GRN Still Not Processed - Immediate Attention Required',
        "subject": f'Urgent: GRN Still Not Processed - Immediate Attention Required as of {new_date_str}'
        }
    # if attachments:email_args['attachments']=attachments
    frappe.enqueue(method=frappe.sendmail, queue='short', timeout=300, **email_args)
    pass


def EmailContent(doc):

    Today = frappe.utils.nowdate()
   
    modified_date_only_str = doc.modified.date().strftime('%Y-%m-%d')
    modified_date = datetime.datetime.strptime(modified_date_only_str, "%Y-%m-%d")
    today_date = datetime.datetime.strptime(Today, "%Y-%m-%d")

    # Calculate the difference in days
    difference_in_days = (today_date - modified_date).days

    print("Difference in days:", difference_in_days)

    # new_date_str = datetime.strftime(Today, '%b %d %Y')
    new_date = datetime.datetime.strptime(modified_date_only_str, "%Y-%m-%d")
    formatted_date = new_date.strftime("%b %d %Y")

    email_content = f"""
    <p>The GRN was updated on {formatted_date}, but it still hasn't been created in SAP after {difference_in_days} days. Could you please look into this</p>
    """
    return email_content






# bench --site alpha.localhost execute  --args "{ 'GRN-24-00751-9241' }" khanal_tech_integrations.utils.React_Api.Grn_creation.Get_List_Purchase.ForMoistureValue


def ForMoistureValue(SingleGrn):
    doc = frappe.get_doc('SAP GRN Creation',SingleGrn)

    content=MoistureValueContent(doc)
    current_directory = os.path.dirname(__file__)
    file_path = os.path.abspath(os.path.join(current_directory, '..', 'Ledger', 'Emailtemplate.html'))
    # print(file_path,'file_path')
    with open(file_path, 'r') as f:
        template_str = f.read()

    template = Template(template_str)
    
    rendered_message = template.render(
        message=content
    )
    Today = frappe.utils.nowdate()
    nowdate_obj = datetime.strptime(Today, '%Y-%m-%d').date()
    new_date_str = datetime.strftime(nowdate_obj, '%b %d %Y')
    email_args = {
        # "recipients": ['harsha@khanalfoods.com'],
        "recipients": ['bhaskar@khanalfoods.com','bharathks@khanalfoods.com','gunalan@khanalfoods.com','navaneeth@khanalfoods.com','priyanka@khanalfoods.com'],
        "cc": ['shahil@khanalfoods.com','mratyunjay@khanalfoods.com','shivakumar@khanalfoods.com','harsha@khanalfoods.com','yogesha@khanalfoods.com'],
        # "recipients": ['shahil@khanalfoods.com'],
        "message": rendered_message,
        "subject": f'Approval Needed: Goods Receipt Note (GRN) Pending QA Approval as of {new_date_str}',
        }
    # if attachments:email_args['attachments']=attachments
    frappe.enqueue(method=frappe.sendmail, queue='short', timeout=300, **email_args)





def MoistureValueContent(doc):
    Purchase_doc = frappe.get_doc('SAP Purchase Order',doc.po_no)
    resulted_List = []
    input_dict = json.loads(doc.itemitems)
    for item in input_dict:
        if 'DocumentLines' in item:
            # document_line = item['DocumentLines'][0]
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
                    
                    # Append the new dictionary to the output list
                    resulted_List.append(new_item)
          

    template_str = """
    <table id="tablestyle">
        <tr>
            <td colspan="8" valign="top" style="padding:40px 54px 0;margin:0;border: none;">
            <p>We are pleased to inform you that the Goods Receipt Note (GRN) has been sent to the QA team for approval due to moisture content. Once it has been approved, it will be uploaded to Draft with the following details. You can visit <a href="http://106.51.78.108/Production/ViewDetails">erp.khanaltech.com</a> to view and approve it:</p>
                <ul>
                <li><strong>Vendor Name:</strong> {{ VendorName }}</li>
                <li><strong>Vendor Code:</strong> {{ VendorCode }}</li>
                <li><strong>PurchaseNumber:</strong> {{ PurchaseNumber }}</li>
                <li><strong>Vendor Invoice Number:</strong> {{ InvoiceNumber }}</li>
                <li><strong>Invoice Date:</strong> {{ InvoiceDate }}</li>
                <li><strong>Received Date:</strong> {{ ReceivedDate }}</li>
                </ul>
                <p>Thank you for your attention to these important details.</p>
            </td>
        </tr>
        <tr>
            <th style="background-color: white;border: none;"></th>
            <th>Item Code</th>
            <th>Item Name</th>
            <th>PO Qty</th>
            <th>Received Qty</th>
            <th>Batch Number</th>
            <th style="background-color: white;border: none;"></th>
        </tr>
        {% for item in resulted_List %}
        <tr style="margin-bottom: 10px; padding-bottom:20px;">
            <td style="background-color: white;border: none;"></td>
            <td style="text-align: center; font-size: 9px;"><b>{{ item.skuName }}</b></td>
            <td style="text-align: center; font-size: 9px;"> <b>{{ item.skuDesc }}</b></td>
            <td style="text-align: center; font-size: 9px;"> <b>{{ item.Quantity }}</b> </td>
            <td style="text-align: center; font-size: 9px;"> <b>{{ item.InputValue }}</b> </td>
            <td style="text-align: center; font-size: 9px;"> <b>{{ item.BatchNumber }}</b> </td>
            <td style="background-color: white;border: none;"></td>
        </tr>
        {% endfor %}
        <tr>
            <td colspan="8" valign="top" style="padding:40px 54px 0;margin:0;border: none;"></td>
        </tr>
    </table>
    """

    # Create a template object
    template = Template(template_str)

    # Context data to render the template
    context = {
        "VendorName": doc.vendor_name,
        "VendorCode": doc.vendor_code,
        "PurchaseNumber": Purchase_doc.docnum,
        "InvoiceNumber": doc.invoice_number,
        "InvoiceDate": doc.invoice_date,
        "ReceivedDate": doc.received_date,
        "resulted_List": resulted_List
    }

    # Render the template with the context data
    rendered_html = template.render(context)


    return rendered_html


