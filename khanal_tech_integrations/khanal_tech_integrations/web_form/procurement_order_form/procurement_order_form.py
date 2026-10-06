import frappe
import json
def get_context(context):
	# do your magic here
	# print(context,'context')
    context.title='Shahil'




@frappe.whitelist()
def ProcurementAdding_To_SAP(data,inputData):
    print(data,'dataaaaaaaaa')
    print(inputData,'inputData')
    # print(type(data))
    # print(data['location'])
    data_dict = json.loads(data)
    print(data_dict['location'])
    print(type(data_dict))
    pass




@frappe.whitelist()
def GetLineitem_Details(poNumber):
    print(poNumber)
    SingleDoc = frappe.get_doc("SAP Purchase Order", poNumber)
    
    # SAP Purchase Order
    dict_response = json.loads(SingleDoc.lineitem)
    print(type(dict_response))
    return dict_response
