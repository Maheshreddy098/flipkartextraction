import frappe
import datetime
from frappe.utils import add_to_date, get_datetime, now_datetime, today
from frappe.utils import now

def get_context(context):
    so_count = frappe.db.count('SAP Sales Order')
    context['so_count1'] = so_count

    #return {"so_count1": so_count}


@frappe.whitelist()
def get_so_count():
    toDate                = str(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')) #"2022-08-26"
    fromDate              = add_to_date(datetime.datetime.now(),days=-50).strftime('%Y-%m-%dT%H:%M:%SZ') #"2022-08-26"
    so_count              = frappe.db.count('SAP Sales Order')
    so_count_last30days   = frappe.db.count('SAP Sales Order', filters=[['created_date', 'between', [ fromDate  , toDate ] ]] )
    inv_count             = frappe.db.count('SAP AR Invoice')
    non_invoiced_SO_count = 30
    non_shipped_SO_count  = 20

    return {    "so_count":so_count,
                "inv_count":inv_count,
                "so_count_last30days" : so_count_last30days
            }

def get_invoice_status_map(filters=None):
	
	return	frappe.db.sql(
			"""
			SELECT DISTINCT 
				SO.customer_name "Customer Name", SO.docnum "SO Number",
                DN.transporter_name"Logitics Name" , DN.shipped_date,  DN.tracking_id
				
				
			FROM `tabSAP Sales Order` SO 
			LEFT JOIN `tabSAP Delivery Notes` DN ON SO.docentry=DN.ref_sales_order AND DN.cancellation_status = 'csNo'

			LEFT JOIN `tabSAP AR Invoice` INV ON INV.ref_delivery_note=DN.docentry AND INV.cancellation_status = 'csNo'

			WHERE SO.created_date>'2022-03-31' AND SO.sales_person_code = 9
			ORDER BY SO.docnum ASC
			
			"""
		)