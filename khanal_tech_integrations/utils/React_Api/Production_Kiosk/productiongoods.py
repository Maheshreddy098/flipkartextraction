import frappe
import json
from frappe.utils import add_to_date
from datetime import datetime
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
from khanal_tech_integrations.utils.React_Api.Production_Kiosk.ApprovalPage import Production_Details, PATCH_Closed_ProductionOrders

headersList = {
    "Accept": "*/*",
    "User-Agent": "Khanal Tech",
    "Content-Type": "application/json"
}

@frappe.whitelist()
def Issue_productionList_InHooks():
    List_of_production_Order = frappe.db.get_list('Production Kiosk', filters={'sap_status': ['=',''] ,'sap_absoluteentry' :['=',''], 'error_message':['like','%Item already defined at a higher level in the product tree%'] ,'issue_for_production_docentry' :['=','']},pluck='name')

    print(List_of_production_Order,'Lenght Issue_productionList_InHooks')
    for SinglePo in List_of_production_Order:
    #     print(SinglePo,'SinglePo')
        singleissue=SingleIssue_for_Production(SinglePo)
    #     pass


def SingleIssue_for_Production(SinglePoID):
    doc = frappe.get_doc('Production Kiosk', SinglePoID)
    ProductionList = Production_Details(SinglePoID)
    
    total_wastage_loss = 0.0  # Initialize the total wastage loss
    input_quantity = 0.0  # Initialize input quantity
    total_output_quantity = 0.0  # Initialize output quantity

    # Loop through the entire production list
    for item in ProductionList[0]['Items']:
        # Sum PreProduction InputQuantity for all relevant items
        if 'PreProduction' in item:
            for pre_prod in item['PreProduction']:
                input_quantity += float(pre_prod.get('InputQuantity', 0))  # Ensure it's a float
                # This accumulates input quantities for all items
                
        # Sum PostProduction TotalOutputQuantity for all items
        if 'PostProduction' in item:
            for post_prod in item['PostProduction']:
                total_output_quantity += float(post_prod.get('TotalOutputQuantity', 0))  # Sum up output quantities
                
        # Sum Wasteage Loss for all items
        if 'Wasteage' in item:
            for waste in item['Wasteage']:
                wasteage_loss = float(waste.get('WasteageLoss', 0))  # Ensure it's a float
                total_wastage_loss += wasteage_loss  # Sum up the wastage loss

    # Total output quantity is the sum of all outputs and wasteage loss
    totalop = total_wastage_loss + total_output_quantity

    print(f"Total Output + Wasteage: {totalop}")
    print(input_quantity, 'input_quantity')

    # Check if input_quantity matches total output and wastage
    if float(input_quantity) == totalop:
        print('Next function')
        production_list = ProductionList[0]  
        Issue_for_Production(production_list, SinglePoID)  # Call the issue function
    else:
        # Display the mismatch error and the difference
        print("Mismatch error:", float(input_quantity) - totalop)

    
    # Pass the calculated values to the Issue_for_Production function
    # Issue_for_Production(ProductionList[0], SinglePoID, input_quantity, total_output_quantity, total_wastage_loss)

# production_list = ProductionList[0]  # Assuming first element is the relevant data
#         Issue_for_Production(production_list, SinglePoID)  # Call the issue function
#     else:
#         print(f"Mismatching error: InputQuantity - TotalOutputQuantity - Wasteage = {input_quantity - totalop}")

@frappe.whitelist()
def Issue_for_Production(production_list, ProdID ):
    doc = frappe.get_doc('Production Kiosk', ProdID)
    try:
        pre_production_list = production_list['Items'][0]['PreProduction']
    except (KeyError, IndexError):
        print("Invalid document entry or missing PreProduction data.")
        return  # Added return to halt execution in case of missing data

    issue_json = {
        "JournalMemo": "Goods Issue",
        "DocObjectCode": "oInventoryGenExit",
        "DocDate": doc.created_date.strftime("%Y-%m-%d"),
        "DocumentLines": []
    }
    
    base_line_counter = 0
    input_quantities = []  # Store input quantities for printing later

    for single_list in pre_production_list:
        # Get the Input Quantity from each single_list, ensure it's a float
        input_quantity = float(single_list.get('InputQuantity', 0))  # Using .get() with default 0
        input_quantities.append(f"Input Quantity for {single_list['ItemCode']}: {input_quantity}")

        batch_numbers = []
        for batch_detail in single_list.get('BatchDetails', []):  # Ensure BatchDetails is handled safely
            batch_number = {
                "BatchNumber": batch_detail.get('BatchNumber'),
                "Quantity": float(batch_detail.get('InputQuantity', 0)),  # Ensure it's a float
                "ItemCode": single_list.get('ItemCode'),
            }
            batch_numbers.append(batch_number)

        issue_line = {
            "Quantity": input_quantity,
            "WarehouseCode": "DC-WIP",
            "AccountCode": "12500900",
            "UseBaseUnits": "tYES",
            "BaseLine": 0 if base_line_counter == 0 else base_line_counter,
            "BatchNumbers": batch_numbers,
            "ItemCode": single_list.get('ItemCode'),
        }
        base_line_counter += 1
        issue_json["DocumentLines"].append(issue_line)
    
    # Ensure total_output_quantity and total_wastage_loss are floats
   
        payload = json.dumps(issue_json, indent=4)
        print(payload, 'payload')

        # Authenticate and post to SAP B1
        session = AuthenticateSAPB1()
        doc_settings = frappe.get_doc('SAP Settings')
        Url = doc_settings.sap_b1_url + "InventoryGenExits"
        
        response = session.request("POST", Url, headers=headersList, data=payload, verify=False)
        # print(response.text, 'response')

        if response.status_code == 201:
            response_data = json.loads(response.text)
            doc.issue_for_production_docentry = response_data.get("DocEntry")
            doc.journalentry_docentry = response_data.get("TransNum")
            print(response_data.get("DocNum"),'DocNum')
            doc.sap_status = 'Issue For Production'
            # doc.status = "Input Submitted"
            doc.error_message = ''
            doc.save()
            frappe.db.commit()

            print('Posted successfully')
        else:
            response_data = json.loads(response.text)
            error_value = response_data['error']['message']['value']
            doc.error_message = error_value
            doc.save()
            frappe.db.commit()
            print(f"Error during posting: {error_value}")
    


     




@frappe.whitelist()
def Receipt_productionList_InHooks():
    List_of_production_Order = frappe.db.get_list(
        'Production Kiosk',
        filters={'sap_status': 'Issue For Production', 'error_message': ['=', ''], 'receipt_from_production_docentry': ['=', ''],'issue_for_production_docentry': ['!=', ''],'journalentry_docentry': ['!=', '']},
        pluck='name'
    )
    print((List_of_production_Order),'Lenght Issue_productionList_InHooks')


    for SinglePo in List_of_production_Order:
        
        SingleReceipt_for_Production(SinglePo)


#  bench --site alpha.localhost execute --args "{'PID-0077'}"  khanal_tech_integrations.utils.React_Api.Production_Kiosk.productiongoods.SingleReceipt_for_Production
#  bench --site alpha.localhost execute --args "{'PID-0077'}"  khanal_tech_integrations.utils.React_Api.Production_Kiosk.productiongoods.SingleIssue_for_Production


@frappe.whitelist()
def SingleReceipt_for_Production(SinglePoID):
    doc = frappe.get_doc('Production Kiosk', SinglePoID)
    ProductionList = Production_Details(SinglePoID)
    if ProductionList:
        Receipt_for_Production(ProductionList[0], SinglePoID)

@frappe.whitelist()
def Receipt_for_Production(production_list, prod_id):
    doc = frappe.get_doc('Production Kiosk', prod_id)
    
    # Fetch the journal entry price amount
    JournalEntryPriceAmount = JournalEntryPrice(doc.journalentry_docentry)
    print(JournalEntryPriceAmount, 'JournalEntryPriceAmount')

    try:
        production_item_list = production_list.get('Items', [])
    except (KeyError, IndexError):
        print("Invalid document entry or missing PreProduction data.")
        return

    # Initialize the receipt JSON payload
    receipt_json = {
        "JournalMemo": "Receipt from Production",
        "DocObjectCode": "oInventoryGenEntry",
        "DocDate": doc.output_created_data.strftime("%Y-%m-%d"),
        "DocumentLines": []
    }

    Total_QtyPresent = 0
    # Calculate the total output quantity
    for sub_item in production_item_list:
        if "PostProduction" in sub_item:
            for entry in sub_item['PostProduction']:
                try:
                    total_output_quantity = float(entry['TotalOutputQuantity'])
                    Total_QtyPresent += total_output_quantity
                except ValueError:
                    print(f"Invalid TotalOutputQuantity value: {entry['TotalOutputQuantity']}")

    print(Total_QtyPresent, 'Total_QtyPresent', '\n\n')

    # Ensure we don't divide by zero
    if Total_QtyPresent == 0:
        print("Total output quantity is zero, cannot calculate unit price.")
        return

    production_orders = []

    # Process PostProduction and Wasteage entries
    for sub_item in production_item_list:
        if "PostProduction" in sub_item or "Wasteage" in sub_item:
            for entry_type in ["PostProduction", "Wasteage"]:
                if entry_type in sub_item:
                    for entry_index, entry in enumerate(sub_item[entry_type]):
                        
                        production_order_line = {
                            "ItemCode": entry["ItemCode"],
                            "Quantity": float(entry["TotalOutputQuantity"]) if entry_type == "PostProduction" else float(entry["WasteageLoss"]),
                            "WarehouseCode": "DC-WIP",
                            "AccountCode": "12500900",
                            "UseBaseUnits": "tYES",
                            "LocationCode": 2,
                            "BatchNumbers": [
                                {
                                    "BatchNumber": entry["BatchNumber"] if entry_type == "PostProduction" else entry["ItemCode"],
                                    "Quantity": float(entry["TotalOutputQuantity"]) if entry_type == "PostProduction" else float(entry["WasteageLoss"]),
                                    "ItemCode": entry["ItemCode"],
                                }
                            ],
                        }

                        # Apply UnitPrice for PostProduction after the first entry
                        if entry_type == "PostProduction" :
                            production_order_line["UnitPrice"] = JournalEntryPriceAmount / Total_QtyPresent

                        production_orders.append(production_order_line)

        # Add document lines to the receipt_json
        receipt_json["DocumentLines"] = production_orders

    # Serialize the payload
    payload = json.dumps(receipt_json, indent=4)
    print(payload, 'payload')

    # Authenticate and send the request to SAP
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url = doc_settings.sap_b1_url + "InventoryGenEntries"

    response = session.request("POST", Url, headers=headersList, data=payload, verify=False)
    print(response, 'response')

    if response.status_code == 201:
        response_data = json.loads(response.text)
        print(response_data.get("DocNum"), 'DocNum')
        doc.sap_status = 'Production Completed'
        doc.status='Output Approved'
        doc.receipt_from_production_docentry = response_data.get("DocNum")
        doc.save()
        frappe.db.commit()
        return 'ProductionOrder Closed'
    else:
        response_data = json.loads(response.text)
        error_value = response_data['error']['message']['value']
        print('\n\n\n', error_value, '\n\n\n')
        doc.error_message = error_value
        doc.save()
        frappe.db.commit()
        return 'Error'


    



@frappe.whitelist()
def Get_Production_Data(DocEntry):
    session = AuthenticateSAPB1()
    payload = ''
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = f"{doc_settings.sap_b1_url}ProductionOrders({DocEntry})"
    response = session.request("GET", reqUrl, data=payload, headers=headersList, verify=False)
    ProductionOrdersList = response.json()
    return ProductionOrdersList['ProductionOrderLines']


@frappe.whitelist()
def JournalEntryPrice(DocEntry):
    session = AuthenticateSAPB1()
    payload = ''
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = f"{doc_settings.sap_b1_url}JournalEntries({DocEntry})"
    response = session.request("GET", reqUrl, data=payload, headers=headersList, verify=False)
    JournalEntries = response.json()
    
    CreditList = list({line.get('Credit') for line in JournalEntries.get('JournalEntryLines', []) if line.get('Credit') and line.get('Credit') != 0})
    return CreditList[0] if CreditList else 0

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
       