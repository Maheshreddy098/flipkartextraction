import frappe
import json
from datetime import datetime,timedelta

def get_context(context):
    # print('worked')
    # print(f"\n\n\n\n{frappe.form_dict}\n\n\n")
    doc = frappe.get_doc('SAP Delivery Notes', frappe.form_dict.docentry)
    json_shipment = json.loads(doc.shipping_details)
    tracking=json_shipment['shipment']['tracking']
    # print(tracking)
    sales_order_details = frappe.get_doc('SAP Sales Order', doc.ref_sales_order)
    
    def parse_date(date_str):
        return datetime.strptime(date_str, '%d-%b-%Y %I:%M:%S %p')

    sorted_tracking = sorted(tracking, key=lambda x: (parse_date(x['date']) + timedelta(days=1) if x['status'] == 'DELIVERED' and x['date'].endswith('12:00:00 am') else parse_date(x['date'])))




    invoice = frappe.db.get_list('SAP AR Invoice', filters={'ref_delivery_note': doc.docentry},pluck="docentry")
    print(invoice)
    for docentry in invoice:
        invoice_details = frappe.get_doc('SAP AR Invoice', docentry)

    context={
        "shipping_details":sorted_tracking,
        "sales_order":sales_order_details,
        "doc":doc,
        "invoice":invoice_details,
        "status":doc.delivery_status
    }
    return context
