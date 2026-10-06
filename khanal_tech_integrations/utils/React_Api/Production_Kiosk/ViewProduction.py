import frappe
import json
import requests
from frappe.utils import add_to_date
from datetime import datetime
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
import logging

headersList = {
                "Accept": "*/*",
                "User-Agent": "Khanal Tech",
                "Content-Type": "application/json",
                
}

@frappe.whitelist()
def View_Production_Details(page=1, limit=10, status=None, doc_id=None):
    page = int(page)
    limit = int(limit)
    start = (page - 1) * limit

    filters = {}
    if status:  # Apply the status filter if provided
        filters["status"] = status
    if doc_id:  # Apply the doc_id filter if provided
        filters["name"] = doc_id

    # Fetch documents matching the filters
    docList = frappe.db.get_list('Production Kiosk', filters=filters, pluck='name')[start:start + limit]

    response_list = []
    for Singledoc in docList:
        doc = frappe.get_doc('Production Kiosk', Singledoc)
        preproduction_list = []
        expecteddata_list = []
        wasteage_list = []

        for PreProductiondata in doc.pre_pro_associate_table_tab:
            crateDoc = frappe.get_doc("Crate Assignment", PreProductiondata.crate_assignment)
            preproduction_item_info = {
                "CrateAssignmentNumber": PreProductiondata.crate_assignment,
                "ItemCode": crateDoc.item_code,
                "ItemDescription": crateDoc.item_description,
                "BatchNumber": crateDoc.batch_number,
                "InputQuantity": PreProductiondata.input_quantity,
            }
            preproduction_list.append(preproduction_item_info)

        for ExpectedOutputdata in doc.expected_output_table:
            expectedoutput_item_info = {
                "ItemCode": ExpectedOutputdata.item_code,
                "ItemName": ExpectedOutputdata.item_name,
                "BatchNumber": ExpectedOutputdata.batch_number,
                "TotalOutputQuantity": ExpectedOutputdata.output_Quantity,
            }
            expecteddata_list.append(expectedoutput_item_info)

        for WasteageData in doc.wastage_loss:
            wastage_loss_item_info = {
                "ItemCode": WasteageData.item_code,
                "ItemName": WasteageData.item_description,
                "WasteageLoss": WasteageData.loss_value,
            }
            wasteage_list.append(wastage_loss_item_info)

        if preproduction_list or expecteddata_list or wasteage_list:
            response_dict = {
                'DocId': doc.name,
                'Employee Count': doc.employee_count,
                'SAP_DocNum': doc.sap_production_number,
                'Process Type': doc.process_type,
                "PreProductionDate": doc.created_date,
                "PostProductionDate": doc.output_created_data,
                "Status": doc.status,
                "Items": [{"PreProduction": preproduction_list}] + 
                         ([{"PostProduction": expecteddata_list}] if expecteddata_list else []) + 
                         ([{"Wasteage": wasteage_list}] if wasteage_list else [])
            }
            response_list.append(response_dict)

    # Combine Input Quantities for duplicate items in the same document
    response_list_combined_quantity = combine_input_quantities(response_list)

    # Return total count of all records in Production Kiosk
    total_count = frappe.db.count('Production Kiosk')

    # Return filtered total count (matching status if any)
    filtered_total_count = frappe.db.count('Production Kiosk', filters=filters)

    return {
        'data': response_list_combined_quantity,
        'totalCount': total_count,
        'filteredTotalCount': filtered_total_count
    }




def combine_input_quantities(response_list):
    combined_list = []

    for response_dict in response_list:
        combined_dict = response_dict.copy()
        items_combined_quantity = {}

        for item_info in response_dict["Items"][0]["PreProduction"]:
            key = (item_info["CrateAssignmentNumber"], item_info["ItemCode"])
            if key in items_combined_quantity:
                items_combined_quantity[key] += float(item_info["InputQuantity"])
            else:
                items_combined_quantity[key] = float(item_info["InputQuantity"])

        combined_items_list = []

        for key, quantity in items_combined_quantity.items():
            crate_assignment, item_code = key
            combined_item_info = {
                "CrateAssignmentNumber": crate_assignment,
                "ItemCode": item_code,
                "ItemDescription": next(
                    info["ItemDescription"]
                    for info in response_dict["Items"][0]["PreProduction"]
                    if info["CrateAssignmentNumber"] == crate_assignment and info["ItemCode"] == item_code
                ),
                "BatchNumber": next(
                    info["BatchNumber"]
                    for info in response_dict["Items"][0]["PreProduction"]
                    if info["CrateAssignmentNumber"] == crate_assignment and info["ItemCode"] == item_code
                ),
                "InputQuantity": str(quantity),
            }
            combined_items_list.append(combined_item_info)

        combined_dict["Items"][0]["PreProduction"] = combined_items_list
        combined_list.append(combined_dict)

    return combined_list












# bench --site alpha.localhost execute    khanal_tech_integrations.utils.React_Api.Production_Kiosk.ViewProduction.View_Production_Details







@frappe.whitelist()
def View_Crate_Details(page=1, limit=10):
    page = int(page)
    limit = int(limit)
    start = (page - 1) * limit


    docList = frappe.db.get_list('Crate Assignment', pluck='name')[start:start + limit]

    result_list=[]

    for SingleDoc in docList:

        Cratedoc = frappe.get_doc('Crate Assignment', SingleDoc)
        
        preproduction_list=[]

        for CrateChild in Cratedoc.crate_assignment_table:
            
            Kioskdoc = frappe.db.get_list('Production Kiosk',filters={  'crate_assignment':[ '=' , Cratedoc.name ],'crate_number':CrateChild.crate_no}, fields='name')
            print(Kioskdoc,'Kioskdoc')
            Kioskdoc_List = [item['name'] for item in Kioskdoc]


            
            preproduction_item_info = {
                    "CrateNo": CrateChild.crate_no,
                    "metal_detected": CrateChild.metal_detected,
                    "QuantityPresent": CrateChild.Quantity,
                    "consumed": CrateChild.consumed,
                    "AssociatedProductionOrder":Kioskdoc_List

                    }
            preproduction_list.append(preproduction_item_info)

        
        BasicDetails ={
            "id":Cratedoc.name,
            "BatchNumber":Cratedoc.batch_number,
            "ItemCode":Cratedoc.item_code,
            "ItemDescription":Cratedoc.item_description,
            "CrateConsumed":Cratedoc.crate_consumed,
            "ItemDetails":preproduction_list,
            "Modified_on":Cratedoc.modified.strftime("%d %B %Y %I:%M:%S %p")
        }
        result_list.append(BasicDetails)

        total_count = frappe.db.count('Crate Assignment')

    return {
        'message':{
                'data' : result_list, 
                'totalCount': total_count
                 } 
    }



  




















# # Dummy API endpoint URLs
# GOODS_ISSUE_API_URL = "https://localhost:50000/b1s/v1/GoodsReturnRequestService_HandleApprovalRequest"
# POST_PRODUCTION_ORDER_API_URL = "https://localhost:50000/b1s/v1/ProductionOrders"
# GOODS_RECEIPT_API_URL = "https://localhost:50000/b1s/v1/GoodsReturnRequest"

# def handle_production_errors_and_post_order(production_order_id):
#     try:
#         # Step 1: Detect the error in the production process
#         production_doc = frappe.get_doc("Production Kiosk", production_order_id)
        
#         # Simulating error checking (you might have more complex logic here)
#         if production_doc.status == 'Error':
#             # Step 2: Create Goods Issue
#             goods_issue_response = create_api_call(GOODS_ISSUE_API_URL, production_order_id)
            
#             if goods_issue_response['status_code'] == 200:
#                 frappe.msgprint(f"Goods Issue created for {production_order_id}")
                
#                 # Step 3: Post the Production Order
#                 post_order_response = create_api_call(POST_PRODUCTION_ORDER_API_URL, production_order_id)
                
#                 if post_order_response['status_code'] == 200:
#                     frappe.msgprint(f"Production Order {production_order_id} posted successfully")
                    
#                     # Step 4: Create Goods Receipt
#                     goods_receipt_response = create_api_call(GOODS_RECEIPT_API_URL, production_order_id)
                    
#                     if goods_receipt_response['status_code'] == 200:
#                         frappe.msgprint(f"Goods Receipt created for {production_order_id}")
#                     else:
#                         frappe.throw(f"Failed to create Goods Receipt: {goods_receipt_response['text']}")
#                 else:
#                     frappe.throw(f"Failed to post Production Order: {post_order_response['text']}")
#             else:
#                 frappe.throw(f"Failed to create Goods Issue: {goods_issue_response['text']}")
#     except Exception as e:
#         frappe.throw(f"Error handling production order {production_order_id}: {str(e)}")

# def create_api_call(api_url, production_order_id):
#     """
#     Creates a goods issue, posts a production order, or creates a goods receipt by calling the external SAP API.
#     """
#     data = {
#         "production_order_id": production_order_id,
#         # Add other relevant data required by the API
#     }
    
#     # Replace this with the session handling logic similar to CheckGrn_List
#     doc_settings = frappe.get_doc('SAP Settings')  # Get SAP settings for URL
#     session = AuthenticateSAPB1()  # Assume this is your custom function to authenticate

#     # Make the API call using the authenticated session
#     headers = {"Authorization": "Bearer YOUR_SAP_API_KEY"}
#     response = session.request("POST", api_url, json=data, headers=headers)

#     # Return response details
#     return {
#         'status_code': response.status_code,
#         'text': response.text
#     }


