import frappe
import json
from frappe.utils import add_to_date
from datetime import datetime
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
import urllib.parse

headersList = {
                "Accept": "*/*",
                "User-Agent": "Khanal Tech",
                "Content-Type": "application/json" 
}



# bench --site alpha.localhost execute --args "{'PID-0730'}"  khanal_tech_integrations.utils.React_Api.Production_Kiosk.ApprovalPage.Production_Order_UpdateTo_SAP

# bench --site khanaltech.com execute --args "{'PID-1379'}"  khanal_tech_integrations.utils.React_Api.Production_Kiosk.ApprovalPage.SingleIssue_for_Production

# bench --site khanaltech.com execute --args "{'PID-1379'}"  khanal_tech_integrations.utils.React_Api.Production_Kiosk.ApprovalPage.SingleReceipt_for_Production


# SingleIssue_for_Production
@frappe.whitelist()
def Production_Details(ProdID):
    doc = frappe.get_doc('Production Kiosk', ProdID)
    response_list=[]
    preproduction_list = []
    expecteddata_list = []
    wasteage_list = []

    for PreProductiondata in doc.pre_pro_associate_table_tab:
        # print(PreProductiondata.crate_assignment)
        crateDoc = frappe.get_doc("Crate Assignment", PreProductiondata.crate_assignment)
        preproduction_item_info = {
            "CrateAssignmentNumber": PreProductiondata.crate_assignment,
            "ItemCode": crateDoc.item_code,
            "ItemDescription": crateDoc.item_description,
            "BatchNumber": crateDoc.batch_number,
            "InputQuantity": PreProductiondata.input_quantity,
        }
        preproduction_list.append(preproduction_item_info)
        # print(preproduction_item_info)

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


    # Check if Items list is not empty before adding to response_list
    if preproduction_list or expecteddata_list or wasteage_list:
        response_dict = {
            'DocId': doc.name,
            'Employee Count': doc.employee_count,
            'Process Type': doc.process_type,
            "PreProductionDate": doc.creation,
            "PostProductionDate": doc.output_created_data,
            "Status": doc.status,
            "Items": [{"PreProduction": preproduction_list}] + ( [{"PostProduction": expecteddata_list}] if expecteddata_list else [] )  + ( [{"Wasteage": wasteage_list}] if wasteage_list else [] )
        }


    response_list.append(response_dict)

    # print(response_list,'response_listresponse_list')
    response_list_combined_quantity = combine_input_quantities(response_list)

    return response_list_combined_quantity





def combine_input_quantities(response_list):
    combined_list = []

    for response_dict in response_list:
        combined_dict = response_dict.copy()
        items_combined_quantity = {}

        # print('\n\n\n',combined_dict,'combined_dict')
        

        # Group by ItemCode
        for item_info in response_dict["Items"][0]["PreProduction"]:
            key = item_info["ItemCode"]
            if key in items_combined_quantity:
                items_combined_quantity[key].append(item_info)
            else:
                items_combined_quantity[key] = [item_info]

        combined_items_list = []

        for item_code, item_info_list in items_combined_quantity.items():
            crate_assignment_quantities = {}

            # Calculate TotalQuantity and gather BatchDetails
            for info in item_info_list:
                crate_assignment = info["CrateAssignmentNumber"]
                if crate_assignment in crate_assignment_quantities:
                    crate_assignment_quantities[crate_assignment] += float(info["InputQuantity"])
                else:
                    crate_assignment_quantities[crate_assignment] = float(info["InputQuantity"])

            batch_details = []

            # print('\n\n\n\n\n',items_combined_quantity,'combined_items_list')
            # print('\n\n\n\n\n',crate_assignment_quantities)
            for crate_assignment, total_quantity in crate_assignment_quantities.items():
                # Fetching BatchNumber from items_combined_quantity
                batch_number = next((info['BatchNumber'] for info in items_combined_quantity[item_code] if info['CrateAssignmentNumber'] == crate_assignment), None)
                
                batch_details.append({
                    "CrateAssignmentNumber": crate_assignment,
                    "BatchNumber": batch_number,  
                    "InputQuantity": float(total_quantity)
                })

            combined_item_info = {
                "ItemCode": item_code,
                "ItemDescription": item_info_list[0]["ItemDescription"],  # Assuming ItemDescription is the same for all entries
                "InputQuantity": sum(crate_assignment_quantities.values()),
                "BatchDetails": batch_details
            }

            combined_items_list.append(combined_item_info)

        combined_dict["Items"][0]["PreProduction"] = combined_items_list
        combined_list.append(combined_dict)

    return combined_list


# !-------------------------------------------------Production_Order To SAP-------------------------------------------------------------------------------------


@frappe.whitelist()
def Production_Order_UpdateTo_SAP(ProdID):
    ProductionList = Production_Details(ProdID)
    print('\n\n\n\n\n',ProductionList,'ProductionList')
    doc = frappe.get_doc('Production Kiosk', ProdID)
    # print(doc.created_date,'created_date')
    # date_only = doc.created_date.strftime("%Y-%m-%d")
    # print(date_only,'date_only')

    # Initialize an empty list to store the converted Production_Order items
    production_orders = []
    comment = "Posted by {} by production kiosk tool".format('Srikanth')
    # Iterate through each item in the ProductionList
    for item in ProductionList:
        production_order = {
            "ItemNo": item["Items"][1]["PostProduction"][0]["ItemCode"],
            "PlannedQuantity": float(item["Items"][1]["PostProduction"][0]["TotalOutputQuantity"]),
            "PostingDate": doc.created_date.strftime("%Y-%m-%d"),
            "Warehouse": "DC-WIP",
            "Remarks":comment,
            "ProductionOrderLines": []
        }

        # Iterate through each sub-item in the Items list
        for sub_item in item["Items"]:
            # Check if it's a PostProduction item
            if "PostProduction" in sub_item:
                # Iterate through each PostProduction entry
                for post_production_entry in sub_item["PostProduction"]:
                    if post_production_entry != sub_item["PostProduction"][0]:
                        # Create a new production_order_line for additional PostProduction entries
                        production_order_line = {
                            "ItemNo": post_production_entry["ItemCode"],
                            "PlannedQuantity": -float(post_production_entry["TotalOutputQuantity"]),
                            "Warehouse": "DC-WIP",
                            "LocationCode": 2,
                            "ProductionOrderIssueType": "im_Manual"
                        }
                        # Append the production_order_line to ProductionOrderLines
                        production_order["ProductionOrderLines"].append(production_order_line)

            # Check if it's a PreProduction or Wasteage item
            if "PreProduction" in sub_item or "Wasteage" in sub_item:
                # Combine PreProduction and Wasteage handling
                for entry_type in ["PreProduction", "Wasteage"]:
                    if entry_type in sub_item:
                        # Loop through each entry in the entry_type list
                        for entry in sub_item[entry_type]:
                            production_order_line = {
                                "ItemNo": entry["ItemCode"],
                                "PlannedQuantity": float(entry["InputQuantity"]) if entry_type == "PreProduction" else -float(entry["WasteageLoss"]),
                                "Warehouse": "DC-WIP",
                                "LocationCode": 2,
                                "ProductionOrderIssueType": "im_Manual"
                            }
                            # Append the production_order_line to ProductionOrderLines
                            production_order["ProductionOrderLines"].append(production_order_line)

        # Append the final Production_Order to the list
        production_orders.append(production_order)
    # print(production_orders,'\n\n\n')
    # Further processing or return the production_orders list as needed

    # print(production_orders,'production_orders')
    post_ProductionOrder=POST_ProductionOrder_SAP(production_orders,ProdID)
    return post_ProductionOrder
     


@frappe.whitelist()
def POST_ProductionOrder_SAP(ProductionList,ProdID):
    doc = frappe.get_doc('Production Kiosk', ProdID)
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url                     = doc_settings.sap_b1_url+"ProductionOrders"
    payload = json.dumps(ProductionList[0])
    print(payload,'payload')
    
    session             = AuthenticateSAPB1()
    response = session.request("POST", Url, headers=headersList, data=payload,verify=False)
    if response.status_code == 400:
        response_data = json.loads(response.text)
        error_value = response_data['error']['message']['value']
        # frappe.msgprint(msg = error_value,title ='Error')
        print('\n\n\n',error_value,'\n\n\n')
        doc.error_message=error_value
        doc.save()
        frappe.db.commit() #
        return {"status": "Error", "message": error_value}
    else:
        response_data = json.loads(response.text)
        absoluteentry = response_data["AbsoluteEntry"]
        doc.sap_absoluteentry = absoluteentry
        doc.sap_production_number=response_data["DocumentNumber"]
        doc.sap_status ='Production Created'
        doc.status ='Output Approved'
        doc.error_message=''
        doc.save()
        frappe.db.commit() #
        print('\n\n\n\n',absoluteentry,'AbsoluteEntry','\n\n\n\n')
        PATCH_Released_ProductionOrders(absoluteentry,ProdID)
        # response_data = {"AbsoluteEntry": 12345}  # Example response_data, replace it with your actual data
        # Assuming this code is within a function or method
        message = f"Document saved successfully in SAP with production Id as {response_data['DocumentNumber']}"
        result = {"status": "success", "message": message}
        return result
        # return {"status": "success", "message": f"Document saved successfully in SAP with production Id as ${response_data["AbsoluteEntry"]} "}
     
 







    


def PATCH_Released_ProductionOrders(Docentry,ProdID):
    doc = frappe.get_doc('Production Kiosk', ProdID)
    # print('logistics_detail_PATCH')
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url                     = doc_settings.sap_b1_url+"ProductionOrders({Docentry})"
    reqUrl_modified         = Url.format(Docentry=Docentry)        
    payload = json.dumps({  "ProductionOrderStatus": "boposReleased"})
    
    session             = AuthenticateSAPB1()
    response = session.request("PATCH", reqUrl_modified, headers=headersList, data=payload,verify=False)
    print(response,'response')
    if response.status_code == 204:
        doc.sap_status ='Production Released'
        doc.save()
        frappe.db.commit() #
        print('created successfully')
        return 'ProductionOrder Patch'
    else: 
        response_data = json.loads(response.text)
        error_value = response_data['error']['message']['value']
        # frappe.msgprint(msg = error_value,title ='Error')
        print('\n\n\n',error_value,'\n\n\n')
        doc.error_message=error_value
        doc.save()
        frappe.db.commit() #   
        return 'Error'





# !-------------------------------------------------Issue_for_Production-------------------------------------------------------------------------------------


@frappe.whitelist()
def Issue_productionList_InHooks():
    List_of_production_Order = frappe.db.get_list('Production Kiosk', filters={'sap_status': 'Production Released', 'error_message':['=',''] ,'issue_for_production_docentry' :['=','']},pluck='name')

    # print(len(List_of_production_Order),'Lenght Issue_productionList_InHooks')
    for SinglePo in List_of_production_Order:
        print(SinglePo,'SinglePo')
        singleissue=SingleIssue_for_Production(SinglePo)
        pass


@frappe.whitelist()
def SingleIssue_for_Production(SinglePoID):
    doc = frappe.get_doc('Production Kiosk', SinglePoID)
    ProductionList=Production_Details(SinglePoID)
    print(ProductionList,'ProductionList')
    Get_Issue=Issue_for_Production(ProductionList[0],doc.sap_absoluteentry,SinglePoID)
    pass
    


@frappe.whitelist()
def Issue_for_Production(production_list, DocEntry,ProdID):
    doc = frappe.get_doc('Production Kiosk', ProdID)
    # Assuming doc_entry is an index for accessing the relevant data in ProductionList
    try:
        pre_production_list = production_list['Items'][0]['PreProduction']
    except (KeyError, IndexError):
        print("Invalid document entry or missing PreProduction data.")
        

    # Printing the first item's PreProduction for reference
    # print(pre_production_list[0])

    issue_json = {
        "JournalMemo": "Issue for Production",
        "DocObjectCode": "oInventoryGenExit",
        "DocDate":doc.created_date.strftime("%Y-%m-%d"),
        "DocumentLines": []
    }
    base_line_counter = 0 
    for single_list in pre_production_list:
        print(single_list,'single_listsingle_list')
        batch_numbers = []
        for batch_detail in single_list['BatchDetails']:
            batch_number = {
                "BatchNumber": batch_detail['BatchNumber'],
                "Quantity": float(batch_detail['InputQuantity']),  # Convert to float
                "ItemCode": single_list['ItemCode'],
            }
            batch_numbers.append(batch_number)

        issue_line = {
            # "ItemCode": single_list['ItemCode'],
            "Quantity": single_list['InputQuantity'],
            "WarehouseCode": "DC-WIP",
            "AccountCode": "12500900",
            "UseBaseUnits": "tYES",
            "BaseEntry": DocEntry,
            # "BaseLine": 0,
            "BaseLine": 0 if base_line_counter == 0 else base_line_counter,
            "BatchNumbers": batch_numbers
        }
        base_line_counter += 1
        issue_json["DocumentLines"].append(issue_line)

    # Converting to JSON for payload
    payload = json.dumps(issue_json, indent=4)
    # print(payload,'payload')
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url                     = doc_settings.sap_b1_url+"InventoryGenExits"
    print(payload,'payload')
    
    session             = AuthenticateSAPB1()
    response = session.request("POST", Url, headers=headersList, data=payload,verify=False)
    if response.status_code == 201:

        response_data = json.loads(response.text)
        doc.issue_for_production_docentry = response_data["DocEntry"]
        doc.journalentry_docentry = response_data["TransNum"]
        doc.sap_status ='Issue For Production'
        doc.error_message=''
        doc.save()
        frappe.db.commit() #
        print('Posted successfully')
    else:
        response_data = json.loads(response.text)
        error_value = response_data['error']['message']['value']
        # frappe.msgprint(msg = error_value,title ='Error')
        print('\n\n\n',error_value,'\n\n\n')
        doc.error_message=error_value
        doc.save()
        frappe.db.commit() #
        
    




# !-------------------------------------------------Receipt_for_Production-------------------------------------------------------------------------------------



@frappe.whitelist()
def Receipt_productionList_InHooks():
    List_of_production_Order = frappe.db.get_list('Production Kiosk', filters={'sap_status': 'Issue For Production', 'error_message':['=',''],'receipt_from_production_docentry' :['=',''] },pluck='name')

    # print(len(List_of_production_Order),'Lenght Issue_productionList_InHooks')
    for SinglePo in List_of_production_Order:
        singlereceipt=SingleReceipt_for_Production(SinglePo)
        pass
    # ProductionList=Production_Details('ProdNum-0659')
    # Get_Receipt=Receipt_for_Production(ProductionList[0],'14979','ProdNum-0659')
    pass


@frappe.whitelist()
def SingleReceipt_for_Production(SinglePoID):
    doc = frappe.get_doc('Production Kiosk', SinglePoID)
    ProductionList=Production_Details(SinglePoID)
    Get_Receipt=Receipt_for_Production(ProductionList[0],doc.sap_absoluteentry,SinglePoID)
    pass

@frappe.whitelist()
def Receipt_for_Production(production_list, doc_entry, prod_id):
    doc = frappe.get_doc('Production Kiosk', prod_id)
    # print(doc,'doc')
    print(doc.journalentry_docentry,'doc.journalentry_docentry')
    JournalEntryPriceAmount=JournalEntryPrice(doc.journalentry_docentry)
    Get_Production=Get_Production_Data(doc_entry)
    print(JournalEntryPriceAmount,'JournalEntryPrice')
    try:
        production_item_list = production_list.get('Items', [])
    except (KeyError, IndexError):
        print("Invalid document entry or missing PreProduction data.")
        return

    receipt_json = {
        "JournalMemo": "Receipt from Production",
        "DocObjectCode": "oInventoryGenEntry",
        "DocDate":doc.output_created_data.strftime("%Y-%m-%d"),
        "DocumentLines": []
    }

    
    production_orders = []
    # post_production_items = set()
    Total_QtyPresent=0
    for sub_item in production_item_list:
        if "PostProduction" in sub_item:
            # post_production_items.update(entry['TotalOutputQuantity'] for entry in sub_item['PostProduction'])
            for entry in sub_item['PostProduction']:
                try:
                    total_output_quantity = float(entry['TotalOutputQuantity'])  # or float if they are not integers
                    Total_QtyPresent +=float(total_output_quantity)
                except ValueError:
                    print(f"Invalid TotalOutputQuantity value: {entry['TotalOutputQuantity']}")





    print(Total_QtyPresent,'Total_QtyPresent','\n\n')
    # num_production_order_lines = sum(int(post_production_items))

    # print(num_production_order_lines,'num_production_order_lines','\n\n')
    
    # !-----
    for sub_item in production_item_list:
        if "PostProduction" in sub_item or "Wasteage" in sub_item:
            for entry_type in ["PostProduction", "Wasteage"]:
                if entry_type in sub_item:
                    for entry_index, entry in enumerate(sub_item[entry_type]):
                        # matched_production_item = next((prod_item for prod_item in Get_Production if prod_item["ItemNo"] == entry["ItemCode"]), None)
                        matched_production_item = [prod_item for prod_item in Get_Production if prod_item["ItemNo"] == entry["ItemCode"]]
                        tolerance = 0.001
                        # print(matched_production_item,'matched_production_item')
                        
                        if matched_production_item:
                            for matched_production_item in matched_production_item:
                                # print('\n\n\n\n',abs(float(entry["TotalOutputQuantity"]) if entry_type == "PostProduction" else float(entry["WasteageLoss"])),'EnterQty')
                                # print('\n\n\n\n',abs(matched_production_item['PlannedQuantity']),'Item Qty')
                                if abs(float(entry["TotalOutputQuantity"]) if entry_type == "PostProduction" else float(entry["WasteageLoss"]) - abs(matched_production_item['PlannedQuantity'])) < tolerance:
                                    base_line = matched_production_item["LineNumber"]
                                else:
                                    base_line = matched_production_item["LineNumber"]
                        else:
                            base_line = None

                        # print(entry_index,'entry_index')

                    
                        
                        # Append the production_order_line to production_orders list
                        production_order_line = {
                            "Quantity": float(entry["TotalOutputQuantity"]) if entry_type == "PostProduction" else float(entry["WasteageLoss"]),
                            "WarehouseCode": "DC-WIP",
                            "AccountCode": "12500900",
                            "UseBaseUnits": "tYES",
                            "BaseEntry": doc_entry,
                            "BaseLine": base_line,
                            "LocationCode": 2,
                            "BatchNumbers": [
                                {
                                    "BatchNumber": entry["BatchNumber"] if entry_type == "PostProduction" else entry["ItemCode"],
                                    "Quantity": float(entry["TotalOutputQuantity"]) if entry_type == "PostProduction" else float(entry["WasteageLoss"]),
                                    "ItemCode": entry["ItemCode"] if entry_type == "PostProduction" else entry["ItemCode"],
                                }
                            ],
                        }
                        if entry_type == "PostProduction" and entry_index > 0:
                            production_order_line["UnitPrice"] = JournalEntryPriceAmount / Total_QtyPresent if Total_QtyPresent > 0 else 0

                      
                        production_orders.append(production_order_line)

  
    receipt_json["DocumentLines"].extend(production_orders)



    # Convert to JSON for payload
    payload = json.dumps(receipt_json, indent=4)
    print(payload)

    # print(payload,'payloadpayload')
    
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url                     = doc_settings.sap_b1_url+"InventoryGenEntries"
    # print(payload,'payload')
    
    session             = AuthenticateSAPB1()
    response = session.request("POST", Url, headers=headersList, data=payload,verify=False)
    print(response,'response')
    if response.status_code == 201:
        response_data = json.loads(response.text)
        # absoluteentry = response_data["receipt_from_production_docentry"]
        doc.receipt_from_production_docentry = response_data["DocEntry"]
        
        doc.sap_status ='Receipt From Production'
        doc.error_message=''
        doc.save()
        frappe.db.commit() #
        PATCH_Closed_ProductionOrders(doc_entry,prod_id)
        print('Posted successfully')
    else:
        response_data = json.loads(response.text)
        error_value = response_data['error']['message']['value']
        # frappe.msgprint(msg = error_value,title ='Error')
        print('\n\n\n',error_value,'\n\n\n')
        doc.error_message=error_value
        doc.save()
        frappe.db.commit() #


    return payload
    


@frappe.whitelist()
def Get_Production_Data(DocEntry):
    session = AuthenticateSAPB1()
    payload = ''
    # INITIALIZATION
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url + "ProductionOrders({DocEntry})"
    modified_Url = reqUrl.format(DocEntry=DocEntry) 
    session = AuthenticateSAPB1()
    response = session.request("GET", modified_Url, data=payload, headers=headersList, verify=False)
    ProductionOrdersList = dict(response.json()) 
    # print(ProductionOrdersList['ProductionOrderLines'])
    return ProductionOrdersList['ProductionOrderLines']
    
@frappe.whitelist()
def JournalEntryPrice(DocEntry):
    session = AuthenticateSAPB1()
    payload = ''
    # INITIALIZATION
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url + "JournalEntries({DocEntry})"
    modified_Url = reqUrl.format(DocEntry=DocEntry) 
    session = AuthenticateSAPB1()
    response = session.request("GET", modified_Url, data=payload, headers=headersList, verify=False)
    JournalEntries = dict(response.json()) 
    CreditList = list({line.get('Credit') for line in JournalEntries.get('JournalEntryLines', []) if line.get('Credit') and line.get('Credit') != 0})
    print(CreditList, 'CreditList without duplicates and zeros')

    # print(CreditList[0],'CreditList')
    return CreditList[0]
    

    
# bench --site dev.localhost execute --args "('15042','PID-0713')"  khanal_tech_integrations.utils.React_Api.Production_Kiosk.ApprovalPage.PATCH_Closed_ProductionOrders

#bench --site alpha.localhost execute --args "('PID-0713')"  khanal_tech_integrations.utils.React_Api.Production_Kiosk.ApprovalPage.handle_error_and_process_goods
def PATCH_Closed_ProductionOrders(Docentry,ProdID):
    doc = frappe.get_doc('Production Kiosk', ProdID)
    # print('logistics_detail_PATCH')
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url                     = doc_settings.sap_b1_url+"ProductionOrders({Docentry})"
    reqUrl_modified         = Url.format(Docentry=Docentry)        
    payload = json.dumps({  "ProductionOrderStatus": "boposClosed"})
    
    session             = AuthenticateSAPB1()
    response = session.request("PATCH", reqUrl_modified, headers=headersList, data=payload,verify=False)
    print(response,'response')
    if response.status_code == 204:
        doc.sap_status ='Production Completed'
        doc.save()
        frappe.db.commit() #
        print('created successfully')
        return 'ProductionOrder Closed'
    else: 
        response_data = json.loads(response.text)
        error_value = response_data['error']['message']['value']
        # frappe.msgprint(msg = error_value,title ='Error')
        print('\n\n\n',error_value,'\n\n\n')
        doc.error_message=error_value
        doc.save()
        frappe.db.commit() #   
        return 'Error'
       


# bench --site dev.localhost execute   khanal_tech_integrations.utils.React_Api.Production_Kiosk.ApprovalPage.Issue_productionList_InHooks
# bench --site dev.localhost execute   khanal_tech_integrations.utils.React_Api.Production_Kiosk.ApprovalPage.Receipt_productionList_InHooks


# bench --site dev.localhost execute --args "{'PID-0713'}"  khanal_tech_integrations.utils.React_Api.Production_Kiosk.ApprovalPage.PATCH_Closed_ProductionOrders




# bench --site dev.localhost execute --args "{'141699'}"  khanal_tech_integrations.utils.React_Api.Production_Kiosk.ApprovalPage.JournalEntryPrice
# 14953


# bench --site khanaltech.com execute   khanal_tech_integrations.utils.React_Api.Production_Kiosk.ApprovalPage.Issue_productionList_InHooks
# bench --site khanaltech.com execute   khanal_tech_integrations.utils.React_Api.Production_Kiosk.ApprovalPage.Receipt_productionList_InHooks
# handle_error_and_process_goods
#bench --site alpha.localhost execute   khanal_tech_integrations.utils.React_Api.Production_Kiosk.ApprovalPage.