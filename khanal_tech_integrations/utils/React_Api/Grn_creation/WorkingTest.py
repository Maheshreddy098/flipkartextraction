
import frappe
import json

from khanal_tech_integrations.utils.sap import AuthenticateSAPB1

headersList = {
                "Accept": "*/*",
                "User-Agent": "Khanal Tech",
                "Content-Type": "application/json" 
            }


@frappe.whitelist()
def GetLineitem_Details(poNumber):
    # print(poNumber)
    SingleDoc = frappe.get_doc("SAP Purchase Order", poNumber)
    dict_response = json.loads(SingleDoc.lineitem)
    return {"docentry": SingleDoc.docentry, "PO_Dict": dict_response}



# utils.React_Api.Grn_creation.Get_PO_values.GetLineitem_Details



@frappe.whitelist()
def ProcurementAdding_To_SAP(data,inputData):
    
    # print(frappe.utils.nowdate(),'date')
    
    data_dict = json.loads(data)
    # print(data_dict,'data_dict')
    
    Get_Single_response = Get_Single_Purchase(data_dict['PonumberDocentry'])
    input_dict = json.loads(inputData)
    # print(input_dict,'input_dict')
    
    # reqUrl_modified         = Url.format(Docentry=data_dict['PonumberDocentry']) 
    session       = AuthenticateSAPB1()
    purchase_payload = {    
        "CardCode": Get_Single_response['CardCode'],
        "CardName": Get_Single_response['CardName'],
        "Series": 210,
        "NumAtCard": data_dict['invoice_number'],
        "DocObjectCode":20,

          "DocumentLines": [ ]
                    }
    
    linenum_quantity = {i['LineNum']:i['InputValue'] for i in input_dict}
    
    linenum_itemcode = {i['LineNum']:i['ItemCode'] for i in input_dict}

    linenum_WarehouseCode = {i['LineNum']:i['WarehouseCode'] for i in input_dict}
    linenum_Price = {i['LineNum']:i['Price'] for i in input_dict}
    linenum_AccountCode = {i['LineNum']:i['AccountCode'] for i in input_dict}

    linenum_BatchNumber = {i['LineNum']:i['BatchNumber'] for i in input_dict}

 
    for single_Lineitem in input_dict:
        single_return_item = {
                                "LineNum": 0,
                                "ItemCode": "PMHN0214",
                                "Quantity": 1.0,
                                "Price": 30,
                                "WarehouseCode": "DC-QA",
                                "AccountCode": "12500800",
                                "BaseType": 22,
                                "BaseEntry": data_dict['PonumberDocentry'],
                                "BaseLine": 0,
                                "BatchNumbers": []
                            }
        
        # print(linenum_itemcode[str(single_Lineitem['LineNum'])],'line')
        # print(linenum_quantity[str(single_Lineitem['LineNum'])],'qty')
        single_return_item["LineNum"]               = single_Lineitem["LineNum"]
        single_return_item["ItemCode"]              = linenum_itemcode[str(single_Lineitem["LineNum"])]
        single_return_item["Quantity"]              = linenum_quantity[str(single_Lineitem["LineNum"])]
        single_return_item["WarehouseCode"]         = linenum_WarehouseCode[str(single_Lineitem["LineNum"])]
        single_return_item["Price"]                 = linenum_Price[str(single_Lineitem["LineNum"])]
        single_return_item["AccountCode"]           = linenum_AccountCode[str(single_Lineitem["LineNum"])]
        # single_return_item["BaseLine"]              = int(single_Lineitem["LineNum"])+2
        single_return_item["BaseLine"]              = single_Lineitem["LineNum"]
        line_num = int(single_Lineitem["LineNum"])

        # Get BatchNumber based on LineNum from linenum_BatchNumber dictionary
        batch_number = linenum_BatchNumber.get(str(line_num), "")
        print(batch_number,"batch_number")
        # Append BatchNumber directly to BatchNumbers list
        single_return_item["BatchNumbers"].append({
            "BatchNumber": batch_number,
            "Quantity": linenum_quantity[str(single_Lineitem["LineNum"])],
            "ItemCode": single_Lineitem.get("ItemCode", ""),
            "BaseLineNumber":single_Lineitem['LineNum'],
            "ExpiryDate": "2023-11-17",
            "ManufacturingDate": "2023-11-10",
            "AddmisionDate": "2023-11-10",

        })
        purchase_payload['DocumentLines'].append(single_return_item)

    doc_settings = frappe.get_doc('SAP Settings')
    Url                     = doc_settings.sap_b1_url+"Drafts"
    json_string = json.dumps(purchase_payload, indent=2)
    # print(f"\n\n\n\n{json_string}\n\n\n")
    response      = session.request("POST", Url, data=json_string,  headers=headersList,verify=False)
    print(response)
    Draft_Response  = dict(response.json())
    # print(Draft_Response['DocEntry'])
    print(Draft_Response.text)
    return None


   
def  Get_Single_Purchase(DocEntry):
    doc_settings = frappe.get_doc('SAP Settings')
    Url                     = doc_settings.sap_b1_url+"PurchaseOrders({Docentry})"
    reqUrl_modified         = Url.format(Docentry=DocEntry) 
    session       = AuthenticateSAPB1()
    payload = ''
    response      = session.request("GET", reqUrl_modified, data=payload,  headers=headersList,verify=False)
    
    PurchaseorderOrder  = dict(response.json())
    print(PurchaseorderOrder['CardCode'])
    return PurchaseorderOrder



# {'CardCode': 'V00002', 'CardName': 'A&D Instruments India Pvt. Ltd.', 'Series': 210, 'NumAtCard': '12345678923456787962212', 'DocumentLines': [{'LineNum': '0', 'ItemCode': 'PMHN0149', 'Quantity': '333', 'Price': '5', 'WarehouseCode': 'HN-QA', 'AccountCode': '12500400', 'BaseType': 22, 'BaseEntry': 7659, 'BaseLine': 0, 'BatchNumbers': [{'LineNum': 0, 'BatchNumber': 'G3H102F04G', 'Quantity': 1, 'ItemCode': ''}, {'BatchNumber': 'GRN-23-5428-0', 'Quantity': '2100', 'ItemCode': 'PMHN0149'}]}, {'LineNum': '2', 'ItemCode': 'PMHN0105', 'Quantity': '323', 'Price': '5', 'WarehouseCode': 'HN-QA', 'AccountCode': '12500400', 'BaseType': 22, 'BaseEntry': 7659, 'BaseLine': 0, 'BatchNumbers': [{'LineNum': 0, 'BatchNumber': 'G3H102F04G', 'Quantity': 1, 'ItemCode': ''}, {'BatchNumber': 'GRN-23-5428-2', 'Quantity': '2100', 'ItemCode': 'PMHN0105'}]}]}




# for single_Lineitem in input_dict:
#         single_return_item = {
#                                 "LineNum": 0,
#                                 "ItemCode": "PMHN0214",
#                                 "Quantity": 1.0,
#                                 "Price": 30,
#                                 "WarehouseCode": "DC-QA",
#                                 "AccountCode": "12500800",
#                                 "BaseType": 22,
#                                 "BaseEntry": data_dict['PonumberDocentry'],
#                                 "BaseLine": 0,
#                                 "BatchNumbers": []
#                             }
        

#         single_return_item["LineNum"]               = 
#         single_return_item["ItemCode"]              = 
#         single_return_item["Quantity"]              = 
#         single_return_item["WarehouseCode"]         = 
#         single_return_item["Price"]                 = 
#         single_return_item["AccountCode"]           = 
#         # single_return_item["BaseLine"]              = 

#         line_num = int(single_Lineitem["LineNum"])

#         # Get BatchNumber based on LineNum from linenum_BatchNumber dictionary
#         batch_number = linenum_BatchNumber.get(str(line_num), "")
#         print(batch_number,"batch_number")
#         # Append BatchNumber directly to BatchNumbers list
#         single_return_item["BatchNumbers"].append({
#             "BatchNumber": ,
#             "Quantity": ,
#             "ItemCode": ,
#             "BaseLineNumber":,
#             "ExpiryDate": "2023-11-17",
#             "ManufacturingDate": "2023-11-10",
#             "AddmisionDate": "2023-11-10",

#         })
#         purchase_payload['DocumentLines'].append(single_return_item)