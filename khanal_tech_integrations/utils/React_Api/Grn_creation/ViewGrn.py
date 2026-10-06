import frappe
import json
from frappe.utils import add_to_date
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
from khanal_tech_integrations.utils.React_Api.Grn_creation.Get_List_Purchase import GrnPayloadForSAP
from jinja2 import Template
import os
import datetime

headersList = {
                    "Accept": "*/*",
                    "User-Agent": "Khanal Tech",
                    "Content-Type": "application/json",
                    
                }
payload = ''


@frappe.whitelist()
def View_Submitted_Grn(page=1, limit=10):
    page = int(page)
    limit = int(limit)
    start = (page - 1) * limit

    DocList = frappe.db.get_list("SAP GRN Creation", pluck='name')[start:start + limit]
    print(len(DocList))

    CrateDeatails=View_Crate_Details()

    Result_dict = []

    for Single_Grn in DocList:
        single_list = frappe.get_doc("SAP GRN Creation", Single_Grn)
        Get_Purchase = frappe.get_doc("SAP Purchase Order", single_list.po_no)
        dict_response = json.loads(single_list.itemitems)
        document_lines = []  # Move inside the loop for each item

        for item in dict_response:
            
            for line in item.get('DocumentLines', []):

                non_crated_qty = 0  # Initialize non_crated_qty
                if line.get('InputValue') is not None and line['InputValue'] != '':
                    for CrateList in CrateDeatails:
                        if (CrateList["ItemCode"] == item['skuName'] and CrateList["BatchNumber"] == line.get('BatchNumber')):
                            non_crated_qty = line.get('InputValue') - CrateList["TotalCrateQty"]
                            break
                    else:  
                        non_crated_qty = line.get('InputValue')
                            
                    document_line = {
                        "id": line.get('id'),
                        "skuName": item['skuName'],
                        "skuDesc": item['skuDesc'],
                        "Quantity": item['Quantity'],
                        "Entered_Qty": line.get('InputValue'),
                        "BatchNumber": line.get('BatchNumber'),
                        "Non_Crated_Qty":non_crated_qty,
                        "Moisture":line.get('MoistureValue'),
                    }

                    document_lines.append(document_line)

        new_item = {
            "id": single_list.name,
            "Vendor_Name": single_list.vendor_name,
            "Invoice_Number": single_list.invoice_number,
            "Vendor_Code": single_list.vendor_code,
            "PO_No": Get_Purchase.docnum,
            "Invoice_Date": single_list.invoice_date,
            "Received_Date": single_list.received_date,
            "DocNum":single_list.grn_docnum,
            "DocumentLines": document_lines,
            "Moisture_Select": single_list.moist_select , 
            "Feedback": single_list.feedback ,
        }
        Result_dict.append(new_item)

    # print(len(Result_dict))
    # print(Result_dict)
        total_count = frappe.db.count('SAP GRN Creation')
    return{ 
         'message':{
                'data' : Result_dict, 
                'totalCount': total_count
                 } 
    }


# bench --site alpha.localhost execute khanal_tech_integrations.utils.React_Api.Grn_creation.ViewGrn.View_Submitted_Grn

# bench --site dev.localhost execute khanal_tech_integrations.utils.React_Api.Grn_creation.ViewGrn.View_Crate_Details

@frappe.whitelist()
def View_Crate_Details():
    DocList = frappe.db.get_list("Crate Assignment", pluck='name')
    result_list=[]
    for Single_Crate in DocList:
        doc = frappe.get_doc("Crate Assignment", Single_Crate)
        BasicDetails ={
        "id":doc.name,
        "BatchNumber":doc.batch_number,
        "ItemCode":doc.item_code,
        "ItemDescription":doc.item_description,
        "CrateConsumed":doc.crate_consumed,
        # "TotalCrateQty":sum(float(CrateChild.Quantity) for CrateChild in doc.crate_assignment_table)  ,
        "TotalCrateQty": sum(float(CrateChild.Quantity) for CrateChild in doc.crate_assignment_table if CrateChild.Quantity is not None),
        "Modified_on":doc.modified.strftime("%d %B %Y %I:%M:%S %p")
        }
        result_list.append(BasicDetails)
    


    return result_list






@frappe.whitelist()
def GetGr_List():
    # Assuming this function returns a list of strings
    GrList = frappe.db.get_list("SAP GRN Creation",pluck='name')
    return GrList


# bench --site beta.localhost execute  khanal_tech_integrations.utils.React_Api.Grn_creation.ViewGrn.Fetch_GrnWithProductionKey


@frappe.whitelist()
def Fetch_GrnWithProductionKey():
    Today = frappe.utils.nowdate()
    print(Today, 'today')  # Debugging statement
    FilterDate = add_to_date(Today, days=-5)
    print(FilterDate, 'FilterDate')  # Debugging statement
    GrnWithProductionKey_WithDatevalue=GrnWithProductionKey_WithDate(FilterDate)

    


def GrnWithProductionKey_WithDate(FilterDate):
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    # pr
    url = doc_settings.sap_b1_url + f"PurchaseDeliveryNotes?$select=DocEntry,DocNum,U_FrappeGRNKey&$filter=UpdateDate ge '{FilterDate}' and U_FrappeGRNKey ne ''"
    
    # Corrected line: Added verify=False to ignore SSL certificate verification
    # response = session.get(url=count_url,  headersList=headersList,verify=False)
    response=session.request("GET", url, headers=headersList, verify=False)
    
    PurchasedeliveryNote_json = response.json()
    # print('\n\n\n',PurchasedeliveryNote_json)

    found = False

    if 'value' in PurchasedeliveryNote_json:
        for SinglePurchaseDelivery in PurchasedeliveryNote_json['value']:
            # print(SinglePurchaseDelivery.get('DocEntry'),'DocEntry')
            # print(SinglePurchaseDelivery.get('U_FrappeGRNKey'),'U_FrappeGRNKey')
            if 'U_FrappeGRNKey' in SinglePurchaseDelivery:
                if  frappe.db.exists( "SAP GRN Creation",{'name': SinglePurchaseDelivery.get('U_FrappeGRNKey')}):
                    Grndoc = frappe.get_doc('SAP GRN Creation', SinglePurchaseDelivery.get('U_FrappeGRNKey'))
                    if not Grndoc.grn_docentry:
                        Grndoc.grn_docentry = SinglePurchaseDelivery.get('DocEntry')
                        Grndoc.grn_docnum = SinglePurchaseDelivery.get('DocNum')
                        Grndoc.moist_select="Approved"
                        Grndoc.save()
                        print(Grndoc,'Saved')
                        
                    else:
                        pass
                else:
                    print(f"SAP GRN Creation {SinglePurchaseDelivery.get('U_FrappeGRNKey')} not found")
                
       
    



    return None
    


@frappe.whitelist()
def submit_feedback(doc_name, feedback, feedback_type):
    try:
        # Print the received data to the command prompt
        print(f"Received doc_name: {doc_name}")
        print(f"Received {feedback_type} feedback: {feedback}")
        
        # Fetch the document using doc_name
        doc = frappe.get_doc("SAP GRN Creation", doc_name)
        
        # Add the feedback to the document based on feedback_type
        if feedback_type == 'approval':
            doc.feedback = feedback
            # Save the document
            doc.save()
            frappe.db.commit()
            # Process and send the payload to SAP only for approval feedback
            sap_response = GrnPayloadForSAP(doc_name)


        elif feedback_type == 'rejection':
            doc.feedback = feedback
            doc.moist_select = 'Rejected'
            # Save the document
            doc.save()
            frappe.db.commit()
            RejectionMail(doc.name)
            sap_response = None  # No need to process or send payload for rejection feedback
    
        return {
            "status": "success",
            "message": f"Feedback ({feedback_type}) submitted successfully",
            "sap_response": sap_response
        }
    except Exception as e:
        # Print the error message if an exception occurs
        print(f"Error: {e}")
        return {"status": "error", "message": str(e)}



# bench --site alpha.localhost execute  --args "{ 'GRN-24-00061-9312' }" khanal_tech_integrations.utils.React_Api.Grn_creation.ViewGrn.get_single_GRNDetails


@frappe.whitelist()
def get_single_GRNDetails(doc_name):
    doc = frappe.get_doc('SAP GRN Creation', doc_name)
    Get_Purchase = frappe.get_doc("SAP Purchase Order", doc.po_no)
    # print(doc)
    Get_Purchase_dict_response = json.loads(Get_Purchase.lineitem)
    doc_dict_response = json.loads(doc.itemitems)

    result = []
    
    # Iterate through Get_Purchase_dict_response and doc_dict_response
    for purchase_item in Get_Purchase_dict_response:
        # Flag to track if DocumentLines need to be appended
        append_document_lines = False
        
        for doc_item in doc_dict_response:
            # Check if 'LineNum' in purchase_item matches 'id' in doc_item
            if 'LineNum' in purchase_item and 'ItemCode' in purchase_item and 'id' in doc_item and 'skuName' in doc_item:
                # Combine values from purchase_item and doc_item
                purchase_combination = f"{purchase_item['ItemCode']}_{purchase_item['LineNum']}"
                doc_combination = f"{doc_item['skuName']}_{doc_item['id']}"

                # print(purchase_combination,doc_combination,'\n\n\n','purchase_combination')
                # print(doc_combination,'\n\n\n','doc_combination')
                if purchase_combination == doc_combination:

                    # Extract required fields from purchase_item with DocumentLines
                    item_info = {
                        "id": purchase_item.get("LineNum"),
                        "skuName": purchase_item.get("ItemCode"),
                        "skuDesc": purchase_item.get("ItemDescription"),
                        "AccountCode": purchase_item.get("AccountCode"),
                        "WarehouseCode": purchase_item.get("WarehouseCode"),
                        "Quantity": purchase_item.get("Quantity"),
                        "RemainingOpenQuantity": purchase_item.get("RemainingOpenQuantity"),
                        "Price": purchase_item.get("Price"),
                        "DocumentLines": doc_item.get("DocumentLines", [])
                    }
                    # Set the flag to True to indicate DocumentLines need to be appended
                    append_document_lines = True
                    break  # Stop further iterations for this purchase_item
        
        # If append_document_lines is False, add item_info without DocumentLines
        if not append_document_lines:
            current_date = datetime.datetime.now()
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
         
    
            if frappe.db.exists("SAP Vendor Mapping",doc.vendor_code):
                vendor_mapped = frappe.get_doc("SAP Vendor Mapping",doc.vendor_code)
                mappedvalue=vendor_mapped.vendor_short_code
            else:
                mappedvalue='NA'

            if frappe.db.exists("SAP Mapping",purchase_item.get("ItemCode")):
                code_list = frappe.get_doc("SAP Mapping",purchase_item.get("ItemCode"))
                code_variant_code=code_list.variant_product_code
            else:
                code_variant_code='NA00'
            item_info = {
                "id": purchase_item.get("LineNum"),
                "skuName": purchase_item.get("ItemCode"),
                "skuDesc": purchase_item.get("ItemDescription"),
                "AccountCode": purchase_item.get("AccountCode"),
                "WarehouseCode": purchase_item.get("WarehouseCode"),
                "Quantity": purchase_item.get("Quantity"),
                "RemainingOpenQuantity": purchase_item.get("RemainingOpenQuantity"),
                "Price": purchase_item.get("Price"),
                "DocumentLines":
                [
                   {
                    "id": "1",
                    "BatchNumber": f"{mappedvalue}{code_variant_code}{day}{Monthmapping[month_letter]}{year_last_two_digits}"
                }
                ]
                
            }
        
        # Append the item_info to the result list
        result.append(item_info)
  
  
    BasicDetails = {
        "PoNumber": doc.po_no,
        "PoValue":Get_Purchase.docnum,
        "InvoiceNumber": doc.invoice_number,
        "InvoiceDate": doc.invoice_date,
        "ReceivedDate": doc.received_date,
        "Feedback": doc.feedback,
        "Lineitem": result,
    } 

    # Print the details to the command prompt
    # print("Basic Details:",type(BasicDetails))

    return BasicDetails



# bench --site dev.localhost execute  --args "{ 'GRN-24-00751-9241' }" khanal_tech_integrations.utils.React_Api.Grn_creation.ViewGrn.RejectionMail


def RejectionMail(docName):
    doc = frappe.get_doc('SAP GRN Creation',docName)
    content=RejectionContent(doc)
    current_directory = os.path.dirname(__file__)
    file_path = os.path.abspath(os.path.join(current_directory, '..', 'Ledger', 'Emailtemplate.html'))
    # print(file_path,'file_path')
    with open(file_path, 'r') as f:
        template_str = f.read()

    template = Template(template_str)
    
    rendered_message = template.render(
        message=content
    )
    email_args = {
        "recipients": ['shivakumar@khanalfoods.com','rakesh.babu@khanalfoods.com '],
        "cc": ['shahil@khanalfoods.com','mratyunjay@khanalfoods.com','shivakumar@khanalfoods.com','bhaskar@khanalfoods.com','bharathks@khanalfoods.com','harsha@khanalfoods.com','yogesha@khanalfoods.com'],
        # "recipients": ['shahil@khanalfoods.com'],
        # "cc": ['harsha@khanalfoods.com'],
        "message": rendered_message,
        "subject": 'Action Required: Goods Receipt Note (GRN) Rejected by QA',
        }
    # if attachments:email_args['attachments']=attachments
    frappe.enqueue(method=frappe.sendmail, queue='short', timeout=300, **email_args)





def RejectionContent(doc):
    Purchase_doc = frappe.get_doc('SAP Purchase Order',doc.po_no)

    template_str = """
    <table id="tablestyle">
        <tr>
            <td colspan="8" valign="top" style="padding:40px 54px 0;margin:0;border: none;">
<p>The QA team has rejected the Goods Receipt Note (GRN) due to <b><em>{{ Feedback }}</em></b> To correct it, it has been sent again for correction. You can visit <a href="http://106.51.78.108/Production/GrnCreation?docName={{ ID }}">this link</a> to make the necessary corrections.</p>

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
        "Feedback": doc.feedback,
        "ID": doc.name,
    }

    # Render the template with the context data
    rendered_html = template.render(context)


    return rendered_html




# bench --site khanaltech.com execute  --args "{ '2024-05-20' }" khanal_tech_integrations.utils.React_Api.Grn_creation.ViewGrn.GrnWithProductionKey_WithDate