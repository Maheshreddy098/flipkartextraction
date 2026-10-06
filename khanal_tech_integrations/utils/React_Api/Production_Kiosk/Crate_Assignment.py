
import frappe
import json
from frappe.utils import add_to_date
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
from khanal_tech_integrations.utils.React_Api.Grn_creation.emailalert import Sent_GRN_mail
from datetime import datetime
headersList = {
                "Accept": "*/*",
                "User-Agent": "Khanal Tech",
                "Content-Type": "application/json" 
            }


@frappe.whitelist()
def  Get_Single_BatchDetails(BatchNumber):
    # print(BatchNumber,'BatchNumber')
    doc_settings = frappe.get_doc('SAP Settings')
    Url                     = doc_settings.sap_b1_url+"BatchNumberDetails?$filter =Batch eq '{BatchNumber}'"
    reqUrl_modified         = Url.format(BatchNumber=BatchNumber) 
    session       = AuthenticateSAPB1()
    payload = ''
    response      = session.request("GET", reqUrl_modified, data=payload,  headers=headersList,verify=False)
    
    BatchNumberResponse  = dict(response.json())
    try:
        response = {}
        if BatchNumberResponse['value'] is not None:
            if len(BatchNumberResponse['value']) > 0:
                json_data_bp_associated = [{'Item_Code': record['ItemCode'], 'ItemDescription': record['ItemDescription']} for record in BatchNumberResponse['value']]
                # print(json_data_bp_associated, 'json_data_bp_associated')
                response['Status'] = 'Success'
                response['result'] = json_data_bp_associated
            else:
                response['Status'] = 'Error'
                response['result'] = []
        else:
            response['Status'] = 'Error'
            response['result'] = []
    except Exception as e:
        response['Status'] = 'Error'
        response['result'] = []
        print(f"An error occurred while processing DOCENTRY: {str(e)}")

    # Convert the response dictionary to a JSON string
    # result_json = json.dumps(response, indent=2)

    # Print or use the result JSON string as needed
    # print(response,'response')
    return response

    

# bench --site dev.localhost execute khanal_tech_integrations.utils.React_Api.Grn_creation.Production_Kiosk.Crate_CreateFrappe
# bench --site dev.localhost execute  --args "{ 'AfffAAA' }"  khanal_tech_integrations.utils.React_Api.Grn_creation.Production_Kiosk.Get_Single_BatchDetails


@frappe.whitelist()
def  Crate_CreateFrappe(SelectedData,rowsData):
    print('\n\n\n\n\n\n\n\n\n\n\n\n\n',SelectedData,'\n\n\n\n\n\n\n\n\n\n\n\n\n',rowsData,'\n\n\n\n\n\n\n\n\n\n\n\n\n')
    name = f"{SelectedData['inputValue']}-{SelectedData['ItemCode']['Item_Code']}"
    

    print('\n\n\n\n\n\n\n\n\n\n\n\n\n',SelectedData,'\n\n\n\n\n\n\n\n\n\n\n\n\n',name)

    if frappe.db.exists("Crate Assignment",name, cache=True):
        exists_doc = frappe.get_doc("Crate Assignment", name)
        # exists_doc.remove("crate_assignment_table")
        for row in exists_doc.get("crate_assignment_table"):
            row.delete()

        LineItem_list = []
        for singleRowData in rowsData:
            LineItem_list.append(
                {
                    "crate_no": singleRowData['batchnumber'],
                    "Quantity": singleRowData['Quantity'],
                    "consumed":singleRowData['Consumed'],
                    "metal_detected": singleRowData['isChecked'],
                    "unconsumable":singleRowData['isUnConsumable'],
                }
            )
        for LineItem in LineItem_list:
            exists_doc.append("crate_assignment_table", LineItem)

        exists_doc.save()
        frappe.db.commit()
        return {"status": "success", "message": "Document saved successfully"}
    else:
        doc = frappe.new_doc('Crate Assignment')
        doc.batch_number=SelectedData['inputValue']
        doc.created_date=datetime.now()
        doc.item_description=SelectedData['ItemCode']['ItemDescription']
        doc.item_code=SelectedData['ItemCode']['Item_Code']

        LineItem_list = []
        for singleRowData in rowsData:
            print(singleRowData['batchnumber'])
            LineItem_list.append(
                {
                    "crate_no":singleRowData['batchnumber'],
                    "Quantity":singleRowData['Quantity'],
                    "consumed":singleRowData['Consumed'],
                    "metal_detected":singleRowData['isChecked'],
                    "unconsumable":singleRowData['isUnConsumable'],
                }
            )
        for LineItem in LineItem_list:
            doc.append("crate_assignment_table",LineItem)

        doc.save()
        frappe.db.commit()
        return {"status": "success", "message": "Document saved successfully"}



# !--------------------1st response------------------------------------------------------------------------------------------------------------

# @frappe.whitelist()
# def  Check_Crate_Assignment(SelectedData):
#     print('\n\n\n\n\n\n',SelectedData,'\n\n\n\n\n\n')
#     # name = f"{SelectedData['inputValue']}-{SelectedData['ItemCode']['Item_Code']}"
#     name = f"{SelectedData['inputValue']}-"

#     if isinstance(SelectedData['ItemCode'], dict):
#         item_code = SelectedData['ItemCode'].get('Item_Code', '')
#     else:
#         item_code = SelectedData['ItemCode']

#     name += item_code
#     response_list = []

#     print('\n\n\n\n\n\n\n\n\n\n\n\n\n',SelectedData,'\n\n\n\n\n\n\n\n\n\n\n\n\n',name)

#     if frappe.db.exists("Crate Assignment",name, cache=True):
#         print('Exist')
#         doc=frappe.get_doc('Crate Assignment',name)
#         print(doc.crate_assignment_table,'crate_assignment_table')
#         for single_item in doc.crate_assignment_table:
#             # print(single_item.crate_no,'single_item.crate_no')
#             item_info = {
#             "batchnumber": single_item.crate_no,
#             "Consumed": single_item.consumed,
#             "Quantity": single_item.Quantity,
#             # "Quantity": single_item.quantity,
#             "isUnConsumable":single_item.unconsumable,
#             "isChecked": single_item.metal_detected if single_item.metal_detected else False,
#             "Value_Present":True
#             }
        
#             response_list.append(item_info)

#     else:
#         print("Not Exixt")

#     print(response_list,'response_listresponse_listresponse_list')

#     return response_list



# !-----------------------2&3 response---------------------------------------------------------------------------------------------------------
# @frappe.whitelist()
# def Check_Crate_Assignment(SelectedData):
#     print('\n\n\n\n\n\n', SelectedData, '\n\n\n\n\n\n')
#     response_list = []

#     input_values = SelectedData['inputValue'].split()  # Split inputValue into a list
#     item_codes = SelectedData['ItemCode'].split()  # Split ItemCode into a list

#     # Pair each inputValue with its corresponding ItemCode
#     data_pairs = zip(input_values, item_codes)


#     for input_value, item_code in data_pairs:
#         name = f"{input_value}-{item_code}"
#         print( '\n\n\n\n\n\n\n\n\n\n\n\n\n', name)

#         if frappe.db.exists("Crate Assignment", name, cache=True):
#             print('Exist')
#             doc = frappe.get_doc('Crate Assignment', name)
#             print(doc.crate_assignment_table, 'crate_assignment_table')
#             for single_item in doc.crate_assignment_table:
#                 item_info = {
                    
#                     "batchnumber": single_item.crate_no,
#                     "Consumed": single_item.consumed,
#                     "Quantity": single_item.Quantity,
#                     "isUnConsumable": single_item.unconsumable,
#                     "isChecked": single_item.metal_detected if single_item.metal_detected else False,
#                     "Value_Present": True,
#                     "item_code":item_code
#                 }
#                 response_list.append(item_info)
#         else:
#             print("Not Exist")

#     print(response_list, 'response_listresponse_listresponse_list')

#     return response_list




#*{'inputValue': 'AAAA', 'ItemCode': {'Item_Code': 'RMDC0310', 'ItemDescription': 'Hardened Cheese Carrot Powder'}} 
#*{'inputValue': 'CUCA0420C24', 'ItemCode': 'RMDC0124.CU'} 
#*{'inputValue': 'CUCA0420C24 CUNA20C24', 'ItemCode': 'RMDC0124.CU RMDC0310'} 


@frappe.whitelist()
def Check_Crate_Assignment(SelectedData):
    print('\n\n\n\n\n\n', SelectedData, '\n\n\n\n\n\n')
    response_list = []

    # Check the structure of SelectedData and proceed accordingly
    if 'ItemCode' in SelectedData and isinstance(SelectedData['ItemCode'], dict):
        # Case 1: SelectedData contains 'ItemCode' as a dictionary
        input_value = SelectedData['inputValue']
        item_code = SelectedData['ItemCode'].get('Item_Code', '')

        name = f"{input_value}-{item_code}"
        print( '\n\n\n\n\n\n\n\n\n\n\n\n\n', name)

        if frappe.db.exists("Crate Assignment", name, cache=True):
            print('Exist')
            doc = frappe.get_doc('Crate Assignment', name)
            print(doc.crate_assignment_table, 'crate_assignment_table')
            for single_item in doc.crate_assignment_table:
                item_info = {
                    "batchnumber": single_item.crate_no,
                    "Consumed": single_item.consumed,
                    "Quantity": single_item.Quantity,
                    "isUnConsumable": single_item.unconsumable,
                    "isChecked": single_item.metal_detected if single_item.metal_detected else False,
                    "Value_Present": True,
                    "item_code": item_code
                }
                response_list.append(item_info)
        else:
            print("Not Exist")
    
    else:
        # Case 2 & 3: SelectedData contains 'ItemCode' as a string or multiple codes
        input_values = SelectedData['inputValue'].split()  # Split inputValue into a list
        item_codes = SelectedData['ItemCode'].split()  # Split ItemCode into a list

        # Pair each inputValue with its corresponding ItemCode
        data_pairs = zip(input_values, item_codes)

        for input_value, item_code in data_pairs:
            name = f"{input_value}-{item_code}"
            print( '\n\n\n\n\n\n\n\n\n\n\n\n\n', name)

            if frappe.db.exists("Crate Assignment", name, cache=True):
                print('Exist')
                doc = frappe.get_doc('Crate Assignment', name)
                print(doc.crate_assignment_table, 'crate_assignment_table')
                for single_item in doc.crate_assignment_table:
                    item_info = {
                        "batchnumber": single_item.crate_no,
                        "Consumed": single_item.consumed,
                        "Quantity": single_item.Quantity,
                        "isUnConsumable": single_item.unconsumable,
                        "isChecked": single_item.metal_detected if single_item.metal_detected else False,
                        "Value_Present": True,
                        "item_code": item_code
                    }
                    response_list.append(item_info)
            else:
                print("Not Exist")

    print(response_list, 'response_listresponse_listresponse_list')

    return response_list


@frappe.whitelist()
def Crate_delete():
    x = 'Crate Assignment'
    print(len(frappe.get_list(x)))
    for documentt in frappe.get_list(x):
        documentt = frappe.get_doc( x , documentt.name)
        # print(documentt,'documentt')
        documentt.delete()
        print(documentt,'documentt Delected')


# bench --site dev.localhost execute khanal_tech_integrations.utils.React_Api.Production_Kiosk.Crate_Assignment.Crate_delete