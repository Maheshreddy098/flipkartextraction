import frappe
import frappe.utils
from frappe.utils import add_to_date

# frappe.utils.logger.set_log_level("DEBUG")
# logger = frappe.logger("api", allow_site=True, file_count=50)
# logger.info(f"{user} updated value to {value}")


def get_all_subordinates_ID(manager_SP_ID): #manager_SP_ID = None
	childreen_list = get_subordinates(manager_SP_ID)
	if len(get_subordinates(childreen_list)) != 0:
		childreen_list += get_subordinates(childreen_list)
	
	return childreen_list


def get_subordinates(manager_SP_ID): 
	if manager_SP_ID == [] or None:
		list_of_suboridinate = []
	elif isinstance(manager_SP_ID, list):
		list_of_suboridinate = frappe.db.get_list('SAP Salesperson', filters={  'reporting_manger_code':[ 'in' , manager_SP_ID ]}, fields=['salesperson_name','salesperson_code'],pluck='salesperson_code')  
	else:
		list_of_suboridinate = frappe.db.get_list('SAP Salesperson', filters={  'reporting_manger_code': manager_SP_ID }, fields=['salesperson_name','salesperson_code'],pluck='salesperson_code')
	
	return list_of_suboridinate

@frappe.whitelist()
def get_StartandEnd_Dates(startDate=None,endDate=None):

	User_doc = frappe.get_doc("User", frappe.session.user)
	logged_in = frappe.session.user
	sales_person = frappe.db.get_list('SAP Salesperson', filters={"email": User_doc.email  } ,fields=['salesperson_name', 'email','salesperson_code','brandwise'])  
	print(len(sales_person)) 

	dept = None
	if len(sales_person)>0:
		dept = sales_person[0].get('brandwise')

	# startDate = startDate
	# endDate = startDate
	# frappe.log_error('url_startDate',startDate)
	# frappe.log_error('url_endDate',endDate)
	if startDate is None and endDate is None:
		endDate = frappe.utils.nowdate()
		startDate = add_to_date(endDate,days=-15)


	if logged_in != 'Guest':
		if dept == "Corporate":# or dept is None:
			print('DEPT----',dept)
			print("Some Corporate Guys is the Session User.")
			# context['logistics_data'] 	= get_invoice_status_map(fromDate = startDate,toDate= endDate,salespersons= None) 
			context={
				"logistics_data":get_invoice_status_map(fromDate = startDate,toDate= endDate,salespersons= None)
			}          
		elif logged_in != 'Guest':
			check_point = []
			for i in User_doc.roles:
				if i.role == "Sales Logistics Master Viewer":
					check_point.append('YES')
					print('Sales Logistics Master Viewer-------')
			#########
			if len(check_point) > 0:
				print("Some Logistics Master Guy is the Session User.") #ex-Shubham,Shijo tech people etc
				# context['logistics_data'] 	= get_invoice_status_map(fromDate = startDate,toDate= endDate,salespersons= None)
				context={
					"logistics_data":get_invoice_status_map(fromDate = startDate,toDate= endDate,salespersons= None)
				}

			# context['logistics_data'] = get_invoice_status_map(fromDate='2022-04-01',toDate= frappe.utils.nowdate() )
		else:
			all_filteredchild_list  	= get_all_subordinates_ID(int(sales_person[0]['salesperson_code'] ))
			Filtered_Salespersons   	= tuple([ sales_person[0]['salesperson_code']  ])
			if len(all_filteredchild_list) != 0:
				all_filteredchild_list.append( sales_person[0]['salesperson_code']  )
				Filtered_Salespersons 	= tuple(all_filteredchild_list) 
				print("Filtered_Salespersons is ----------------------------------" , Filtered_Salespersons) 
			context={
				"logistics_data":get_invoice_status_map(fromDate=startDate,toDate= endDate, salespersons=Filtered_Salespersons)
			}
			# context['logistics_data'] 	= get_invoice_status_map(fromDate=startDate,toDate= endDate, salespersons=Filtered_Salespersons)
	# frappe.log_error('text',context['logistics_data'])
	# frappe.log_error('startDate',context['startDate'])
	# frappe.log_error('endDate',context['endDate'])
	# print(context['logistics_data'])
	# valuesdata=context['logistics_data']
	# for i in context['logistics_data']:
	# 	print(i[0])
	return context


def get_context(context):
	# result = get_StartandEnd_Dates(startDate=None,endDate=None)
	# print(context.logistics_data)
	# print(context['logistics_data'])
	return 


def get_invoice_status_map(fromDate=None,toDate=None,salespersons=None):
	
	query_text_corporate = """
			SELECT DISTINCT 
				SO.created_date, 					
				SO.docnum "SO Number",	 
				SO.customer_code "Customer Code",
				SO.customer_name "Customer Name", 
				DN.docnum "DN #",
				DN.created_date "DN Created On", 
				DN.shipped_date, 
				DN.transporter_name, 
				DN.tracking_id,
				INV.docnum,
				INV.bill_total,
				SO.lineitem_from_warehouse,
				SO.sales_person_code
				
			FROM `tabSAP Sales Order` SO 
			LEFT JOIN `tabSAP Delivery Notes` DN ON SO.docentry=DN.ref_sales_order AND DN.cancellation_status = 'csNo'
			LEFT JOIN `tabSAP AR Invoice` INV ON INV.ref_delivery_note=DN.docentry AND INV.cancellation_status = 'csNo'
			WHERE SO.created_date>= '{FromDate}' AND SO.created_date<= '{ToDate}' 
			ORDER BY SO.docnum DESC
			
			""" 
	############

	query_text_child_salespersons = """
			SELECT DISTINCT 
				SO.created_date,
				SO.docnum "SO Number",
				SO.customer_code "Customer Code",
				SO.customer_name "Customer Name", 
				DN.docnum "DN #",
				DN.created_date "DN Created On", 
				DN.shipped_date, 
				DN.transporter_name, 
				DN.tracking_id,
				INV.docnum,
				INV.bill_total,
				SO.lineitem_from_warehouse,
				SO.sales_person_code
				
			FROM `tabSAP Sales Order` SO 
			LEFT JOIN `tabSAP Delivery Notes` DN ON SO.docentry=DN.ref_sales_order AND DN.cancellation_status = 'csNo'
			LEFT JOIN `tabSAP AR Invoice` INV ON INV.ref_delivery_note=DN.docentry AND INV.cancellation_status = 'csNo'
			WHERE SO.created_date>= '{FromDate}' AND SO.created_date<= '{ToDate}'  AND SO.sales_person_code IN {filtered_salesperson}
			ORDER BY SO.docnum DESC
			
			"""

	query_text_single_salesperson = """
			SELECT DISTINCT 
				SO.created_date, 
				SO.docnum "SO Number",	 
				SO.customer_code "Customer Code",
				SO.customer_name "Customer Name", 
				DN.docnum "DN #",
				DN.created_date "DN Created On", 
				DN.shipped_date, 
				DN.transporter_name, 
				DN.tracking_id,
				INV.docnum,
				INV.bill_total,
				SO.lineitem_from_warehouse,
				SO.sales_person_code
				
				
			FROM `tabSAP Sales Order` SO 
			LEFT JOIN `tabSAP Delivery Notes` DN ON SO.docentry=DN.ref_sales_order AND DN.cancellation_status = 'csNo'
			LEFT JOIN `tabSAP AR Invoice` INV ON INV.ref_delivery_note=DN.docentry AND INV.cancellation_status = 'csNo'
			WHERE SO.created_date>= '{FromDate}' AND SO.created_date<= '{ToDate}'  AND SO.sales_person_code = {single_salesperson}
			ORDER BY SO.docnum DESC
			
			"""

	if fromDate and toDate and salespersons == None:
		modified_query_text = query_text_corporate.format(FromDate = fromDate,ToDate = toDate)
		final_sql_result =	frappe.db.sql(modified_query_text)
		
	if fromDate and toDate and salespersons != None:
		if len(salespersons) != 1:
			modified_query_text = query_text_child_salespersons.format(FromDate = fromDate,ToDate = toDate,filtered_salesperson = salespersons)
			final_sql_result =	frappe.db.sql(modified_query_text)
		else:
			modified_query_text = query_text_single_salesperson.format(FromDate = fromDate,ToDate = toDate,single_salesperson = salespersons[0])
			final_sql_result =	frappe.db.sql(modified_query_text)
			#print(modified_query_text)
	# print(len(final_sql_result))
	# if len(final_sql_result) > 0:
	# 	print(final_sql_result[1])
	# 	print('Query single result length-',len(final_sql_result[0]))
	return final_sql_result


