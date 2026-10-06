import frappe



def get_context(context):
    vendoe_list = frappe.db.get_list('SAP Vendor Registration', filters={"status": "Not Seen"  } ,fields=['company_name', 'vendor_name','telephone_number','mobile_number','email','name']) 
    context={
        "vendoe_list":vendoe_list
    } 
    # print(vendoe_list,'vendoe_list')
    return context