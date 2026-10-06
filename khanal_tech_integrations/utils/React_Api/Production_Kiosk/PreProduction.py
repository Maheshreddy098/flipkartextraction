import frappe
import json
from frappe.utils import add_to_date
from datetime import datetime
import pandas as pd
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
import os
from jinja2 import Template

headersList = {
                "Accept": "*/*",
                "User-Agent": "Khanal Tech",
                "Content-Type": "application/json" 
}



@frappe.whitelist()
def Get_Crate_Assignment():
    response_list = []

    docList = frappe.db.get_list('Crate Assignment', filters={'crate_consumed': '0'}, pluck='name')

    for SingleItem in docList:
        doc = frappe.get_doc("Crate Assignment", SingleItem)

        # Initialize an empty list for Lineitem within each document entry in response_list
        line_items = []

        for single_item in doc.crate_assignment_table:
            # if not single_item.consumed:
            # if not single_item.consumed and (not single_item.metal_detected or single_item.metal_detected != 1):
            if not single_item.consumed and (not single_item.unconsumable or single_item.unconsumable != 1):

                item_info = {
                    "batchnumber": single_item.crate_no,
                    "Quantity": single_item.Quantity,
                    #  "Quantity": single_item.quantity,
                    "Consumed": single_item.consumed,
                    "Key_Value": f'{doc.name}'+'_'+single_item.crate_no,
                    "isChecked": single_item.metal_detected if single_item.metal_detected else False
                }

                # Append the item_info dictionary to the line_items list
                line_items.append(item_info)

        # Check if line_items is not empty before adding to response_list
        if line_items:
            response_list.append({
                "batch_number": doc.batch_number,
                "item_code": doc.item_code,
                "item_description": doc.item_description,
                "name": doc.name,
                "Lineitem": line_items
            })

    # print(response_list, 'response_list')
    return response_list



# SAP Item Master




@frappe.whitelist()
def Get_item_Details():
    docList = frappe.db.get_list('Item', filters={'item_code': ['like', '%rmdc%']}, fields=['item_code','item_name'])
    return docList


# bench --site dev.localhost execute    khanal_tech_integrations.utils.React_Api.Production_Kiosk.PreProduction.Get_item_Details



    


@frappe.whitelist()
def Post_Pre_Production(CrateDetails,ProcessType,CountofEmp,UserEmail):
    # print(CrateDetails,'CrateDetails')
    # Extract relevant information from CrateDetails
    CrateDetailsneeded = [
        {
            'ItemCode': cd['ItemCode'],
            'ItemDescription': cd['ItemDescription'],
            'Frappe_key': cd['Frappe_key'],
            'CrateData': [
                {
                    'batchnumber': d['batchnumber'],
                    'Quantity': d['Quantity'],
                    'Consumed': d['Consumed'],
                    'Key_Value': d['Key_Value'],
                    'isChecked': d['isChecked'],
                    'EnteredInput': d['EnteredInput']
                }
                for d in cd['CrateData'] if 'EnteredInput' in d
            ]
        }
        for cd in CrateDetails
    ]
    
    # Create a new Production Kiosk document
    doc                 = frappe.new_doc('Production Kiosk')
    doc.created_date    = datetime.now()
    doc.process_type    =ProcessType['ProcessTyp']
    doc.employee_count  =CountofEmp
    doc.user_email      =UserEmail
    doc.status          ='Input Submitted'

    print(CrateDetailsneeded,'CrateDetailsneeded')

    # Loop through each CrateDetailsneeded
    for SingleCrateDetails in CrateDetailsneeded:
        docCreate = frappe.get_doc("Crate Assignment", SingleCrateDetails['Frappe_key'])
        LineItem_list = []

        # Loop through each item in crate_assignment_table
        for single_item in docCreate.crate_assignment_table:
            crate_no = single_item.crate_no

            # Loop through CrateData of SingleCrateDetails
            for LineDetails in SingleCrateDetails['CrateData']:
                if LineDetails['batchnumber'] == crate_no:
                    single_item.consumed = 1
                    LineItem_list.append({
                        "crate_assignment": SingleCrateDetails['Frappe_key'],
                        "crate_number": crate_no,
                        "input_quantity": LineDetails['EnteredInput'],
                        "crate_quantity": single_item.Quantity,
                        # "moisture_loss": int(single_item.Quantity) - int(LineDetails['EnteredInput']),
                    })

        # Append LineItem_list to pre_pro_associate_table_tab
        for LineItem in LineItem_list:
            doc.append("pre_pro_associate_table_tab", LineItem)

        docCreate.save()
    

    try:
        # Save documents and commit changes
        doc.save()
        docCreate.save()
        frappe.db.commit()
        print(doc, 'saved')
        issuemail=Sent_InitialMail(CrateDetailsneeded,doc)
        return {"status": "success", "message": "Document saved successfully","DocEntry":doc.name}
        
    except frappe.DuplicateEntryError:
        print(doc, 'duplicate')
        return {"status": "error", "message": str(frappe.DuplicateEntryError)}


# bench --site dev.localhost execute khanal_tech_integrations.utils.React_Api.Production_Kiosk.PreProduction.Get_Crate_Assignment
@frappe.whitelist()
def Sent_InitialMail(InputData,doc):
    
    result = []

    for item in InputData:
        item_code = item['ItemCode']
        batch_code = item['Frappe_key'].split('-')[0]  # Extracting the batch code
        total_entered_input = sum(float(cr['EnteredInput']) for cr in item['CrateData'])  # Calculating total EnteredInput
        result.append({'itemcode': item_code, 'batchnumber': batch_code, 'TotalQty': total_entered_input})

    print(result)

    print('\n\n\n\n\n\n\n\n\n\n\n',result,'result')
    current_directory = os.path.dirname(__file__)
    file_path = os.path.abspath(os.path.join(current_directory, '..', 'Ledger', 'Emailtemplate.html'))

    
    with open(file_path, 'r') as f:
        template_str = f.read()
   
    table = "<table style='border-collapse: collapse; margin-top: 10px;'><tr><th style='border: 1px solid black; padding: 5px;'>ItemCode</th><th style='border: 1px solid black; padding: 5px;'>BatchNumber</th><th style='border: 1px solid black; padding: 5px;'>Total Qty</th></tr>"
    for key in result:
        table += f"<tr><td style='border: 1px solid black; padding: 5px;'>{key['itemcode']}</td><td style='border: 1px solid black; padding: 5px;'>{key['batchnumber']}</td><td style='border: 1px solid black; padding: 5px;'>{key['TotalQty']}</td></tr>"
    table += "</table>"

    message_temp="Please verify that the item, along with its associated batch number and quantity, is present in the DC-WIP warehouse\n" + table


    # MessageContent=
    template = Template(template_str)
    rendered_message = template.render(
        message   =message_temp
    )    
    email_args={
            "recipients":['rakesh.babu@khanalfoods.com','shivakumar@khanalfoods.com','umesha@khanalfoods.com','srikanth@khanalfoods.com','harsha@khanalfoods.com','yogesha@khanalfoods.com'],
            "message":rendered_message,
            "subject":f'Confirmation of Item and Batch Number Presence in DC-WIP  {doc.name}'
                    }
    # if attachments:email_args['attachments']=attachments
    frappe.enqueue(method=frappe.sendmail,queue='short',timeout=300, **email_args)
    pass

#  [{'itemcode': 'RMDC0310', 'batchnumber': 'CUNA01D24', 'TotalQty': 28.44}, {'itemcode': 'RMDC0124', 'batchnumber': 'CUCA0401D24', 'TotalQty': 12.0}]




# DataExistValue={'name': 'PID-0704', 'CreatedDate': '2024-03-06', 'EmployeeCount': '21', 'OutputCreatedData': '2024-03-05', 'ProcessType': 'Cutting'}
@frappe.whitelist()
def Post_Post_Production(ProdDocEntry,Expected_Output,LossesType,DataExistValue):
    print(ProdDocEntry,'\n\n\n\n\n' ,'\n\n\n\n\n',Expected_Output,'\n\n\n\n\n',LossesType,'\n\n\n\n\n',DataExistValue)

    print(DataExistValue['CreatedDate'],'CreatedDate')
    print(DataExistValue['OutputCreatedData'],'OutputCreatedData')
    doc = frappe.get_doc("Production Kiosk", ProdDocEntry)
    # doc.process_type=ProcessType['ProcessTyp']
    doc.output_created_data=datetime.now()
    
    # if 

    if DataExistValue:
        doc.output_created_data=datetime.now() if DataExistValue['OutputCreatedData'] is None else DataExistValue['OutputCreatedData']
        doc.created_date=DataExistValue['CreatedDate']


    print(doc.output_created_data,'doc.output_created_data')
    doc.status='Output Submitted'
    OutputItem_list=[]

    for SingleList in Expected_Output:
        # print(SingleList)
        OutputItem_list.append({
            "item_code":SingleList['item_code'],
            "item_name":SingleList['item_name'],
            "batch_number":SingleList['batchNumber'],
            "output_Quantity":SingleList['totalQuantity'],
            "line_items_deatils":json.dumps(SingleList['CreateDetails']),
        })
       
        name = f"{SingleList['batchNumber']}-{SingleList['item_code']}"
        
        if frappe.db.exists("Crate Assignment", name, cache=True):
            print('\n\n\n', 'IF')
            exists_doc = frappe.get_doc("Crate Assignment", name)
            Crate_List = []

            # for row in exists_doc.get("crate_assignment_table"):
            #     print(row.crate_no)

            for singleRowData in SingleList['CreateDetails']:
                crate_no = singleRowData['cratenumber']
                output_value = singleRowData['OutPutValue']
                found = False
                # Check if the crate number already exists in the document
                for row in exists_doc.get("crate_assignment_table"):
                    if row.crate_no == crate_no:
                        # print(row.crate_no,'\n\n\n')
                        # Update the quantity if the crate number exists
                        row.Quantity = output_value
                        found = True
                        break
                # If the crate number doesn't exist, append a new row
                if not found:
                    Crate_List.append({
                        "crate_no": crate_no,
                        "Quantity": output_value,
                    })

            # Append new rows for crates that didn't exist before
            for LineItemcrate in Crate_List:
                exists_doc.append("crate_assignment_table", LineItemcrate)

            exists_doc.save()
          
        else:
            print('\n\n\n','Else')
            crate_doc=frappe.new_doc('Crate Assignment')
            crate_doc.batch_number=SingleList['batchNumber']
            crate_doc.created_date=datetime.now()
            crate_doc.item_description=SingleList['item_name']
            crate_doc.item_code=SingleList['item_code']
            Crate_List_Else = []
            for singleRowData in SingleList['CreateDetails']:
                Crate_List_Else.append(
                    {
                        "crate_no":singleRowData['cratenumber'],
                        "Quantity":singleRowData['OutPutValue'],
                        # "quantity":singleRowData['OutPutValue'],
                        # "consumed":singleRowData['Consumed'],
                        # "metal_detected":singleRowData['isChecked'],
                    }
                )

            for LineItemcrate in Crate_List_Else:
                crate_doc.append("crate_assignment_table",LineItemcrate)
            
            crate_doc.save()



    for row in doc.get("expected_output_table"):
        row.delete()


    # print(OutputItem_list,'OutputItem_list')
    for OutputLineItem in OutputItem_list:
        doc.append("expected_output_table", OutputLineItem)

    loss_variants = [
            {'WASTE0001': 'Moisture loss'},
            {'WASTE0002': 'Production Wastage (DOGSEE)'},
            {'WASTE0003': 'Grinding Waste'},
    ]

    Losses_list=[]
    for single_loss in LossesType:
        if LossesType[single_loss]:
            matching_variant = next((variant[single_loss] for variant in loss_variants if single_loss in variant), None)
            Losses_list.append({
            "item_code":single_loss,
            "item_description":matching_variant,
            "loss_value":LossesType[single_loss],
        })




    for wastagerow in doc.get("wastage_loss"):
        wastagerow.delete()

    for Wastage_LineItem in Losses_list:
        doc.append("wastage_loss", Wastage_LineItem)



    try:
        # Save documents and commit changes
        doc.save()
        # crate_doc.save()
        frappe.db.commit()
        print(doc, 'saved')
        return {"status": "success", "message": "Document saved successfully","DocEntry":doc.name}
    except frappe.DuplicateEntryError:
        print(doc, 'duplicate')
        return {"status": "error", "message": str(frappe.DuplicateEntryError)}
    



@frappe.whitelist()
def Get_Single_ProductionDetails(ProdNum):
    print('$'*20)
    # print(ProdNum,'ProdNumProdNum')
    doc = frappe.get_doc("Production Kiosk", ProdNum)
    # print(doc)
    response_dict = {}

    for single_item in doc.pre_pro_associate_table_tab:
        createdoc = frappe.get_doc("Crate Assignment", single_item.crate_assignment)
        # print(createdoc, 'createdoc')
        item_info = {
            "batchnumber": single_item.crate_number,
            "input_quantity": single_item.input_quantity,
            "crate_quantity": single_item.crate_quantity,
            "Key_Value": f'{createdoc.name}'+'_'+single_item.crate_number,
        }

        key = (createdoc.batch_number, createdoc.item_code, createdoc.item_description)

        # if key in response_dict:
        #     response_dict[key]['Lineitem'].append(item_info)
        # else:
        #     response_dict[key] = {
        #         "batch_number": createdoc.batch_number,
        #         "item_code": createdoc.item_code,
        #         "item_description": createdoc.item_description,
        #         "name": createdoc.name,
        #         "Lineitem": [item_info]
        #     }
        input_quantity = float(single_item.input_quantity)

        if key in response_dict:
            response_dict[key]['Lineitem'].append(item_info)
            response_dict[key]['Total_Quantity'] += input_quantity
        else:
            response_dict[key] = {
                "batch_number": createdoc.batch_number,
                "item_code": createdoc.item_code,
                "item_description": createdoc.item_description,
                "name": createdoc.name,
                "Lineitem": [item_info],
                "Total_Quantity": input_quantity
            }

    expected_output_list = []


    for ExpectedOutputdata in doc.expected_output_table:
        # Check if line_items_deatils is not None before deserializing
        line_items_details_str = getattr(ExpectedOutputdata, 'line_items_deatils', '[]')
        if line_items_details_str is not None:
            try:
                # Deserialize the JSON string into a Python list
                line_items_details_list = json.loads(line_items_details_str)
                for item in line_items_details_list:
                    item["Item_Present"] = True
            except json.JSONDecodeError:
                # Handle the case where JSON decoding fails
                line_items_details_list = []
        else:
            line_items_details_list = []

        expectedoutput_item_info = {
            "item_code": getattr(ExpectedOutputdata, 'item_code', ''),
            "item_description": getattr(ExpectedOutputdata, 'item_name', ''),
            "batchNumber": getattr(ExpectedOutputdata, 'batch_number', ''),
            "totalQuantity": getattr(ExpectedOutputdata, 'output_Quantity', ''),
            "CreateDetails": line_items_details_list,

        }

        expected_output_list.append(expectedoutput_item_info)

    Wasteage_list = []
    for WasteageData in doc.wastage_loss:
        # print(WasteageData.loss_value,'WasteageData.loss_value')
        if WasteageData.loss_value:
            wastage_loss_item_info = {
                WasteageData.item_code:WasteageData.loss_value
            }
            Wasteage_list.append(wastage_loss_item_info)

    
    # formatted_dateOutputDate = (
    # doc.output_created_data.strftime("%d %B %Y %I:%M:%S %p")
    # if doc.output_created_data
    # else ""
    # )

    # formatted_dateInputDate = (
    #     doc.created_date.strftime("%d %B %Y %I:%M:%S %p")
    #     if doc.created_date
    #     else ""
    # )
    BasicDetais ={
            "name":ProdNum,
            "CreatedDate":doc.created_date,
            "EmployeeCount":doc.employee_count,
            "OutputCreatedData":doc.output_created_data,
            "ProcessType":doc.process_type,
        }
    
    
    # Convert the dictionary values to a list
    response_list = [{"PreProduction": list(response_dict.values())}, {"PostProduction": expected_output_list},{"Wastage": Wasteage_list},{"BasicDetais":BasicDetais}]

    return response_list




@frappe.whitelist()
def Get_ItemBatchCode():
    response_list = []
    docList = frappe.db.get_list('SAP Mapping', pluck='name')
    for SingleItem in docList:
        doc = frappe.get_doc("SAP Mapping", SingleItem)
        response_list.append({
            "ItemCode": doc.item_code,
            "VariantProductCode": doc.variant_product_code,
        })
    # print(response_list)
    return response_list







@frappe.whitelist()
def CheckGrn_List(Item_Code,Batch_Number):
    doc_settings = frappe.get_doc('SAP Settings')
    # Url                     = doc_settings.sap_b1_url+"BatchNumberDetails?$filter =Batch eq '{BatchNumber}'"
    Url                     = doc_settings.sap_b1_url+"SQLQueries('DCWIP_BatchItemQuantity')/List?ItemCode='{Item_Code}'&BatchNumber='{Batch_Number}'"

    reqUrl_modified         = Url.format(Item_Code=Item_Code,Batch_Number=Batch_Number) 
    session       = AuthenticateSAPB1()
    payload = ''
    response      = session.request("GET", reqUrl_modified, data=payload,  headers=headersList,verify=False)
    
    BatchNumberResponse  = dict(response.json())
    total_quantity = 0  # Initialize total quantity
    if BatchNumberResponse['value']:
        # print('valuepresnt')
        # return BatchNumberResponse['value'][0]['Quantity']
        for item in BatchNumberResponse['value']:
            total_quantity += float(item['Quantity'])  # Accumulate quantity for each item
        
        return total_quantity  # Return the total quantit
    else:
        # print('Empty')
        return ''
        









# bench --site dev.localhost execute --args "{'ProdNum-0660'}"  khanal_tech_integrations.utils.React_Api.Production_Kiosk.PreProduction.Get_Single_ProductionDetails
# bench --site dev.localhost execute    khanal_tech_integrations.utils.React_Api.Production_Kiosk.PreProduction.Get_item_Details
# bench --site dev.localhost execute --args "{'RMDC0030','NANA03A24'}"     khanal_tech_integrations.utils.React_Api.Production_Kiosk.PreProduction.CheckGrn_List

# bench --site dev.localhost execute --args "('RMDC0036','TESTBATCH')"     khanal_tech_integrations.utils.React_Api.Production_Kiosk.PreProduction.CheckBAtchQty_SAP