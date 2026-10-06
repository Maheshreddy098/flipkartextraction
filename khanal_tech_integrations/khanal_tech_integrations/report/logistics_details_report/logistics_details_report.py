# # Copyright (c) 2022, Khanal Tech and contributors
# # For license information, please see license.txt
import html
import functools
import frappe
import datetime
from frappe import _
from frappe.utils import add_to_date, get_datetime, now_datetime, today
from frappe.utils import now


# Detailed Tutorial
# https://discuss.erpnext.com/t/tutorial-script-report-chart/79873

def get_count(data,columnvalues):
	is_countt  = 0
	none_count = 0
	for item in data:
		if item[columnvalues] !=None:
			is_countt  		  += 1
		else:
			none_count 		  += 1
	return [is_countt,none_count]
        

def execute(filters=None):
	filters		   = frappe._dict(filters or { })
	columns, data  = get_columns(filters), get_data(filters)
	message 	   = ["This is a dashboard showing orders and their logistics details for a salesperson."] #
	Session_user   = frappe.get_doc("User", frappe.session.user)
	if filters.From_Date and filters.To_Date:
		message    = ["This is a dashboard showing orders and their logistics details for  : " + Session_user.full_name + " from " + str(filters.From_Date) + " to " + str(filters.To_Date)  ]

	report_summary = [ 
						{"label":"Dashboard Viewer",			 "value": Session_user.full_name      ,							   'indicator':'Black'  },
						{"label":"Orders Placed",				 "value": get_count(data,"so_number")[0] , 					 	   'indicator': get_color( get_count(data,"so_number")[0] )   		   }, 
						#{"label":"Delivery Note Not Created",   "value": get_count(data,"DN_No")[1] , 				    		   'indicator': get_color( get_count(data,"DN_No")[1]     )    		   },
						{"label":"Invoiced Orders",				 "value": get_count(data,"INV_no")[0],  		  			       'indicator': get_color( get_count(data,"INV_no")[0]    )    		   },
						{"label":"Shipped",						 "value": get_count(data,"DN_transporter_name")[0],  		  	   'indicator': get_color( get_count(data, "DN_transporter_name")[0] ) },
					  ]
	

	return columns, data, message ,None , report_summary

def get_salesperson_from_session_user():
	User_doc 					= frappe.get_doc("User", frappe.session.user)
	Required_Salespersons 		= [ ]
	
	for person in frappe.db.get_list('SAP Salesperson', fields=['salesperson_name', 'email','salesperson_code']):
		if person['email'] 	== User_doc.email:
			print("Dashboard to be filtered for :: " , person['salesperson_name'])  
			Required_Salespersons.append(person['salesperson_code'])
		else:
			pass
	
	return Required_Salespersons #list of salesperson code

def get_all_subordinates_ID(manager_SP_ID): 
	childreen_list 		= get_subordinates(manager_SP_ID)
	if len(get_subordinates(childreen_list)) != 0:
		childreen_list += get_subordinates(childreen_list)
	
	return childreen_list


def get_subordinates(manager_SP_ID): 
	if manager_SP_ID 		 == [] or None:
		list_of_suboridinate = []
	elif isinstance(manager_SP_ID, list):
		list_of_suboridinate = frappe.db.get_list('SAP Salesperson', filters={  'reporting_manger_code':[ 'in' , manager_SP_ID ]}, fields=['salesperson_name','salesperson_code'],pluck='salesperson_code')  
	
	else:
		list_of_suboridinate = frappe.db.get_list('SAP Salesperson', filters={  'reporting_manger_code': manager_SP_ID }, fields=['salesperson_name','salesperson_code'],pluck='salesperson_code')

	return list_of_suboridinate



def get_color(count_data):
	color         = "Green"
	if count_data == 0:
		color     = "Red"
	return color

def get_data(filters=None):
	data  			   		= [ ]
	hyperlink_format   		= '<a href="{link}" target="_blank">{text}</a>'
	red_color_format 	    = "<span style='color:red!important;font-weight:normal'>{value}</span>"
	Salesperson_codes       = get_salesperson_from_session_user()	
	#print("Salesperson code is " , Salesperson_codes, type(Salesperson_codes))
	if isinstance(Salesperson_codes, list):
		grandparent = int(Salesperson_codes[0])
		print("*********/n Query execution is successful /n**********")
		salesp_list = get_subordinates(grandparent)
		print("Child list  -------------------------------" , salesp_list)
		salesp_list = get_subordinates(get_subordinates(grandparent))
		print("Grand-child list --------------------------" , salesp_list)
		all_filteredchild_list = get_all_subordinates_ID(grandparent)
		all_filteredchild_list.append(Salesperson_codes[0])
		print("ALL list ----------------------------------" , all_filteredchild_list)
		print("Tuple is ----------------------------------", tuple(all_filteredchild_list) )
	
	invoice_status_map = get_invoice_status_map(filters)
	for invoice in invoice_status_map:
		row = {
			"so_created_date"	 : invoice[0] , 
			"so_number"			 : invoice[1] ,
			"customer_code"		 : invoice[2] , #Not needed for a salesperson
			"customer_name"		 : invoice[3] , 
			"DN_No"		 	  	 : invoice[4] ,
			"DN_createdon"		 : invoice[5] ,
			"DN_shipped_date"	 : invoice[6] , #Not needed for a salesperson
			"DN_transporter_name": invoice[7] , #Not needed for a salesperson
			"DN_tracking_id"	 : invoice[8] , 
			"INV_no"			 : invoice[9] , #Not needed for a salesperson
			"INV_total"			 : invoice[10],
			"so_salesperson"	 : invoice[11],

		        }
		if row["DN_transporter_name"]!= None and row["DN_tracking_id"]  !=None:
			row["DN_tracking_id"] 	  = hyperlink_format.format(link= Tracking_link(row["DN_transporter_name"] , row["DN_tracking_id"]) , text= row["DN_tracking_id"] )  
		else:
			row["DN_tracking_id"] 	  = red_color_format.format(value="Not Assigned")
			
			
			#"Not Assigned"

		if row["INV_total"]       == None:
			row["INV_total"]      =  red_color_format.format(value="Not Billed")
		else:
			pass

		if frappe.session.user in ["lian@khanalfoods.com","buddhiraj@khanalfoods.com","babu@khanalfoods.com","anand.tiwari@khanalfoods.com","rohan@khanalfoods.com"] :
			data.append(row) #"Administrator" , 
		else:
			if row["so_salesperson"] in all_filteredchild_list:
				#print("Salesperson list -------" ,len(invoice_status_map) )
				data.append(row)
			else:
				pass
		
	return data


def Tracking_link(logistics , tracking_id):

	if logistics!=None and tracking_id!=None and logistics.lower() in ['safexpress','bluedart','delhivery']:
		tracking_link = "https://www.aftership.com/track/" + str(logistics.lower()) + "/" + str(tracking_id)
	else: 
		tracking_link = "https://www.aftership.com/track"
	#print(tracking_link)
	return tracking_link

def get_invoice_status_map(filters=None):
	#frappe._dict   tuple(list)
	Salesperson_codes       = get_salesperson_from_session_user()	
	grandparent 			= int(Salesperson_codes[0])
	print("*********\n Query execution is successful \n**********")
	all_filteredchild_list  = get_all_subordinates_ID(grandparent)
	
	
	Filtered_Salespersons    = tuple(Salesperson_codes)
	if len(all_filteredchild_list) != 0:
		all_filteredchild_list.append(Salesperson_codes[0])
		Filtered_Salespersons = tuple(all_filteredchild_list) 
	
	print("Numbers of salesperson in final filter : " , len(Filtered_Salespersons))

	print("Filtered_Salespersons is ----------------------------------" , tuple(Filtered_Salespersons) )

	
	query_text_raw = """
			SELECT DISTINCT 
				SO.created_date, SO.docnum "SO Number",	 SO.customer_code "Customer Code",
				SO.customer_name "Customer Name", DN.docnum "DN #",
				DN.created_date "DN Created On", DN.shipped_date, 
				DN.transporter_name, DN.tracking_id,
				INV.docnum,INV.bill_total,SO.sales_person_code
				
			FROM `tabSAP Sales Order` SO 
			LEFT JOIN `tabSAP Delivery Notes` DN ON SO.docentry=DN.ref_sales_order AND DN.cancellation_status = 'csNo'
			LEFT JOIN `tabSAP AR Invoice` INV ON INV.ref_delivery_note=DN.docentry AND INV.cancellation_status = 'csNo'
			WHERE SO.created_date> '{FromDate}' AND SO.created_date< '{ToDate}'  AND SO.sales_person_code IN {filtered_salesperson}
			ORDER BY SO.docnum DESC
			
			"""
	#final_sql_result =	frappe.db.sql(query_text_raw)   #WHERE SO.created_date>'2022-04-30' 
	if filters.From_Date and filters.To_Date:
		modified_query_text = query_text_raw.format(FromDate = filters.From_Date ,ToDate   = filters.To_Date , filtered_salesperson= Filtered_Salespersons)
		final_sql_result =	frappe.db.sql(modified_query_text)
		print(filters.From_Date, filters.To_Date)
	# else:
	# 	final_sql_result =	frappe.db.sql(default_query_text)
	#print(final_sql_result)
	return final_sql_result
#
def get_columns(filters=None):
	return [
		
		
		{
			"label": _("SO Date"),
			"fieldname": "so_created_date",
			"fieldtype": "Date",
			"options": "SO Doc Entry",
			"width": 150,
		},

		{
			"label": _("Customer Name"),
			"fieldname": "customer_name",
			"fieldtype": "Data",
			"options": "SO Doc Entry",
			"width": 400,
		},

		{
			"label"    : _("Sales Order NO"),
			"fieldname": "so_number",
			"fieldtype": "Data",
			"options"  : "SAP Sales Order",
			"width": 150,
		},

		# {
		# 	"label": _("Customer Code"),
		# 	"fieldname": "customer_code",
		# 	"fieldtype": "Data",
		# 	"options": "SO Doc Entry",
		# 	"width": 200,
		# },
		
		# {
		# 	"label": _("DN #"),
		# 	"fieldname": "DN_No",
		# 	"fieldtype": "Data",
		# 	"options": "SO Doc Entry",
		# 	"width": 90,
		# },
		# {
		# 	"label": _("DN Date"),
		# 	"fieldname": "DN_createdon",
		# 	"fieldtype": "Date",
		# 	"options": "SO Doc Entry",
		# 	"width": 120,
		# },
		# {
		# 	"label": _("Invoice #"),
		# 	"fieldname": "INV_no",
		# 	"fieldtype": "Data",
		# 	"options": 'SAP AR Invoice', 
		# 	"width": 120,
		# },
		{
			"label": _("Invoice Amount"),
			"fieldname": "INV_total",
			"fieldtype": "Data",
			"options": "SO Doc Entry",
			"width": 150,
		},

		# {
		# 	"label": _("Shipped on"),
		# 	"fieldname": "DN_shipped_date",
		# 	"fieldtype": "Date",
		# 	"options": "SO Doc Entry",
		# 	"width": 110,
		# },
		# {
		# 	"label": _("Transporter"),
		# 	"fieldname": "DN_transporter_name",
		# 	"fieldtype": "Data",
		# 	"options": "SO Doc Entry",
		# 	"width": 120,
		# },
		{
			"label": _("Tracking Number"),
			"fieldname": "DN_tracking_id",
			"fieldtype": "HTML",
			"options": "SO Doc Entry",
			"width": 200,
		},
		# {
		# 	"label": _("Salesperson"),
		# 	"fieldname": "so_salesperson",
		# 	"fieldtype": "Data",
		# 	"options": "SO Doc Entry",
		# 	"width": 120,
		# },
	]
# # 






# SELECT DISTINCT 
# 				T0."DocEntry",	 'SO-' || T0."DocNum" "SO Number",	 T0."CardCode" "Customer Code",
# 				T0."CardName" "Customer Name",T0."DocTotal" "Order Value", T0."NumAtCard" "PO Number" , T2."DocNum" "Delivery Note No.",	 T0."DocDate" "Order Date",	 
# 				T2."Shipped Date", T0."DocDueDate" "Estimated Delivery Date", 
# 				T2."U_ShippingDate" "Delivered Date",
# 				(SELECT MAX("Name") FROM OCST WHERE "Code"=T3."State") "Region",
# 				(SELECT MAX("ZipCodeB") FROM RDR12 WHERE "DocEntry"=T3."DocEntry") "Pincode",
# 				CASE WHEN T1."LineStatus"='O' THEN 'Processing' WHEN T1."LineStatus"='C' THEN 
# 				'Shipped / Invoiced' WHEN T2."Delivered"='Y' THEN 'Delivered' ELSE '' END "Status",
# 				DAYS_BETWEEN(T0."DocDate",T2."Shipped Date") "Processing TAT",
# 				DAYS_BETWEEN(T2."U_ShippingDate",T2."Shipped Date") "Logistics TAT (Days)",
# 				T4."Location",T2."Transporter Name",T2."Tracking ID.",T2."Delivered",T0."U_Proof_of_Delivery"
	 
# 			FROM ORDR T0 
# 			INNER JOIN RDR1 T1 ON T0."DocEntry"=T1."DocEntry"
# 			LEFT JOIN 
# 			(select D2."U_Delivered" "Delivered",D2."TaxDate" "Shipped Date",
# 			D2."U_ShippingDate",D1."BaseEntry", D1."BaseLine" ,D2."U_TN" "Transporter Name", 
# 			D2."U_TrackingNo" "Tracking ID.", D2."DocNum"
# 			FROM DLN1 D1 INNER JOIN ODLN D2 ON  D1."DocEntry" = D2."DocEntry" AND D2."CANCELED"='N') T2 ON 
# 			T1."DocEntry"=T2."BaseEntry" and T1."LineNum"=T2."BaseLine"
# 			LEFT JOIN RDR12 T3 ON T3."DocEntry" = T0."DocEntry"
# 			LEFT JOIN OLCT T4 ON T1."LocCode" = T4."Code"

# 			WHERE T0."CANCELED" ='N' AND T0."DocManClsd" ='N' AND T1."LinManClsd" ='N'

# 			ORDER BY  T0."DocEntry" ASC		


# bench --site dev.localhost execute khanal_tech_integrations.khanal_tech_integrations.report.logistics_details_report.logistics_details_report.get_invoice_status_map 
# bench --site dev.localhost execute khanal_tech_integrations.utils.logistics.delete 
# bench --site medusa.localhost execute khanal_tech_integrations.khanal_tech_integrations.report.logistics_details_report.logistics_details_report.get_salesperson_code
# bench --site medusa.localhost execute khanal_tech_integrations.khanal_tech_integrations.report.logistics_details_report.logistics_details_report.get_suborinates_salespersonID