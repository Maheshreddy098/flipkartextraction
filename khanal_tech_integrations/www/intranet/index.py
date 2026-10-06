import frappe
import frappe.utils
from frappe.utils.dateutils import add_to_date
import re
import json
import requests
import collections 


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
def  get_salespersonsforsessiouser():
	logged_in = frappe.session.user 
	User_doc = frappe.get_doc("User", frappe.session.user)
	user_roles = []
	sales_persons = frappe.db.get_list('SAP Salesperson', filters={"email": User_doc.email  } ,fields=['salesperson_name', 'salesperson_code'])  
	# frappe.log_error('salesperson-get.db',sales_person)
	for i in User_doc.roles:
		user_roles.append(i.role)
	######################
	if  "Sales Logistics Master Viewer" in user_roles:
		result = frappe.db.get_list('SAP Salesperson'  ,fields=['salesperson_name', 'salesperson_code'])
	elif len(sales_persons) != 0:
		all_filteredchild_list  	= get_all_subordinates_ID(int(sales_persons[0]['salesperson_code'] )) #all subordinates for a code
		Filtered_Salespersons   	= tuple([ sales_persons[0]['salesperson_code']  ])
		if len(all_filteredchild_list) != 0:
			all_filteredchild_list  	= get_all_subordinates_ID(int(sales_persons[0]['salesperson_code'] )) #all subordinates for a code
			result = frappe.db.get_list('SAP Salesperson', filters={'salesperson_code': ('in', list(all_filteredchild_list))} ,fields=['salesperson_name', 'salesperson_code']) 

		else:
			pass
	
	else:
		result = None
		
	if len(result) ==0:
		result = None

	return result



def get_context(context):
	context.no_cache=True
	SelectedSalesPerson = []
	result = []
	if frappe.local.form_dict.endDate:
		endDate=frappe.local.form_dict.endDate
		if endDate=="null?":
			endDate = frappe.utils.nowdate()
		# frappe.log_error('url_endDate',endDate)
	else:
		endDate = frappe.utils.nowdate()
		# frappe.log_error('deafult_endDate',endDate)
	if frappe.local.form_dict.startDate:
		startDate=frappe.local.form_dict.startDate
		# frappe.log_error('url_startDate',startDate)
		if startDate=="null":
			startDate = add_to_date(endDate,days=-15)		
	else:
		startDate = add_to_date(endDate,days=-15)
		# frappe.log_error('deafult_startDate',startDate)

	if frappe.local.form_dict.SalesPersonCode:
		value=frappe.local.form_dict.SalesPersonCode
		SelectedSalesPerson = re.split(r',|-', value)
		
	
	else:
		pass
	#############DATE##############################
	default_query_result = get_data_userwise(startDate=startDate,endDate= endDate)
	for value in context:
		if value == "value":
			for listvalues in context.values():
				for singlevalue in listvalues:
					intvalue=int(singlevalue)
					SelectedSalesPerson.append(intvalue)
			
		else:
			pass	
	if len(SelectedSalesPerson) == 0:
		#default query result
		context['logistics_data']  = default_query_result
		pass
	else:
		for single_result in default_query_result:
			if single_result[12]  in SelectedSalesPerson:
				result.append(single_result)
			#######
		context['logistics_data']  = result
		
	# print(SelectedSalesPerson)
	
	
	User_doc = frappe.get_doc("User", frappe.session.user)
	# frappe.log_error('User_doc',User_doc)
	logged_in = frappe.session.user
	# frappe.log_error('logged_in',logged_in)
	# print(context.logistics_data)
	# final_sql_result=get_invoice_status_map()
	ALL_SO = len(context.logistics_data)
	if ALL_SO == 0:
		ALL_SO=1
	DN_count=0
	INV_count=0
	salesPerson_SO_list = []
	DN_Transporter_list=[]
	WareHouse_list=[]

	for full_list in context.logistics_data:
		salesPerson_SO_list.append({'SO_docnum':full_list[1],'Salesperson_Code':full_list[12]})

		# print(full_list[7])
		if full_list[4] is not None:
			DN_count +=1
			DN_Transporter_list.append(full_list[7])
			WareHouse_list.append(full_list[11])
		if full_list[9] is not None:
			INV_count +=1
	
	###############################################
	SalespersonList = [single_so['Salesperson_Code'] for single_so in salesPerson_SO_list]
	salesperson_withcounter = collections.Counter(SalespersonList)
	Salesperson_breakdown_count = dict(salesperson_withcounter)
	# print(Salesperson_breakdown_count)
	# print('list---------',list(Salesperson_breakdown_count))
	Finalresult = frappe.db.get_list('SAP Salesperson', filters={'salesperson_code': ('in', list(Salesperson_breakdown_count))} ,fields=['salesperson_name', 'salesperson_code'])
	# print(Finalresult)
	for single_salesperson1 in Finalresult:
		single_salesperson1['so_count'] = Salesperson_breakdown_count[single_salesperson1['salesperson_code']]
	# print('Final Finalresult ------------------------------',Finalresult)




	Stiil_in_SalesOrder 	= 	ALL_SO - DN_count
	Still_in_DeliveryNotes 	=	DN_count - INV_count
	DeliveryNotes_Invoiced 	=	INV_count

	DeliveryNotesPerCentage = Still_in_DeliveryNotes/ALL_SO*100
	Stiil_in_SalesOrderPerCentage = Stiil_in_SalesOrder/ALL_SO*100
	InvComplete =INV_count/ALL_SO*100


	conv = lambda i:i or 'None'

	# #######################################################
	DN_Transporter_list1 = [conv(i) for i in DN_Transporter_list]
	ALL_Lower_DN_Transporter_list = [x.lower() for x in DN_Transporter_list1]
	Unique_DN_Transporter = set(ALL_Lower_DN_Transporter_list)
	SingleListDn=[]
	for single_T in Unique_DN_Transporter:
		# print([single_T , ALL_Lower_DN_Transporter_list.count(single_T)])
		SingleListDn.append([single_T , ALL_Lower_DN_Transporter_list.count(single_T)])





	# #######################################################
	WareHouse_list1 = [conv(i) for i in WareHouse_list]
	ALL_Lower_WareHouse_list = [x.upper() for x in WareHouse_list1]
	Unique_WareHouse = set(ALL_Lower_WareHouse_list)
	WareSingleListDn=[]
	for single_Ware in Unique_WareHouse:
		WareSingleListDn.append([single_Ware , ALL_Lower_WareHouse_list.count(single_Ware)])




	
	# print(Finalresult)
	
	context={
		"Total_So":len(context.logistics_data),
		"DN_count":DN_count,
		"INV_count":INV_count,
		"Stiil_in_SalesOrder":Stiil_in_SalesOrder,
		"Still_in_DeliveryNotes":Still_in_DeliveryNotes,
		"DeliveryNotes_Invoiced":DeliveryNotes_Invoiced,
		"DeliveryNotesPerCentage":round(DeliveryNotesPerCentage),
		"Stiil_in_SalesOrderPerCentage":round(Stiil_in_SalesOrderPerCentage),
		"InvComplete":round(InvComplete),
		"SingleListDn":SingleListDn,
		"WareSingleListDn":WareSingleListDn,
		"Finalresult":Finalresult

	}
	
	
	return context


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
	# if len(final_sql_result) > 0:
	
	return final_sql_result

# bench --site dev.localhost execute khanal_tech_integrations.www.intranet.myorder.get_salespersonsforsessiouser

# 

def get_data_userwise(startDate=None, endDate=None):
    ############# DATE ##############################
    User_doc = frappe.get_doc("User", frappe.session.user)
    logged_in = frappe.session.user
    sales_person = frappe.db.get_list('SAP Salesperson', filters={"email": User_doc.email}, fields=['salesperson_name', 'email', 'salesperson_code', 'brandwise'])
    
    dept = None
    result = []  # Initialize result to an empty list as a default value

    if len(sales_person) > 0:
        dept = sales_person[0].get('brandwise')
    
    if len(sales_person) == 0:
        check_point = []
        for i in User_doc.roles:
            if i.role == "Sales Logistics Master Viewer":
                check_point.append('YES')

        if len(check_point) > 0:
            result = get_invoice_status_map(fromDate=startDate, toDate=endDate, salespersons=None)
    else:
        if dept == "Corporate":  # or dept is None:
            result = get_invoice_status_map(fromDate=startDate, toDate=endDate, salespersons=None)
        else:
            all_filteredchild_list = get_all_subordinates_ID(int(sales_person[0]['salesperson_code']))  # All subordinates for a code
            Filtered_Salespersons = tuple([sales_person[0]['salesperson_code']])

            if len(all_filteredchild_list) != 0:
                all_filteredchild_list.append(sales_person[0]['salesperson_code'])
                Filtered_Salespersons = tuple(all_filteredchild_list)
                result = get_invoice_status_map(fromDate=startDate, toDate=endDate, salespersons=Filtered_Salespersons)
            else:
                empty_salespersons = [sales_person[0]['salesperson_code']]
                Filtered_Salespersons = tuple(empty_salespersons)
                result = get_invoice_status_map(fromDate=startDate, toDate=endDate, salespersons=Filtered_Salespersons)

    return result


#test#