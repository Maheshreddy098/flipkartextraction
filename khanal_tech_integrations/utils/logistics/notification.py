import frappe
from frappe.utils import add_to_date
from datetime import datetime,date
from jinja2 import Template
import os

@frappe.whitelist()
def daily_progress():
    ToDate = frappe.utils.nowdate()
    FromDate = add_to_date(ToDate,days=-15)
    salespersonList = frappe.db.get_list('SAP Salesperson', pluck="salesperson_code")
    for salesperson_code in salespersonList:
        # print(salesperson_code,'salesperson_code')
        get_invoice_Query(fromDate=FromDate,toDate=ToDate,salespersons=salesperson_code)
    pass





def get_invoice_Query(fromDate=None,toDate=None,salespersons=None):
	# print(fromDate,toDate,salespersons)

	query_text_single_salesperson = """
			SELECT DISTINCT 
				SO.created_date,                                            #0
				SO.docnum "SO Number",	                                    #1
				DN.transporter_name,                                        #2
				DN.tracking_id,                                             #3
				INV.docnum,                                                 #4
				INV.bill_total,                                             #5
				SO.sales_person_code,                                       #6
                DN.delivery_status,                                         #7
                DN.docentry,                                                #8
                INV.doc_currency,                                           #9
                INV.series_name,                                            #10
                SO.series_name,                                             #11
                SO.customer_name                                            #12
				
				
			FROM `tabSAP Sales Order` SO 
			LEFT JOIN `tabSAP Delivery Notes` DN ON SO.docentry=DN.ref_sales_order AND DN.cancellation_status = 'csNo'
			LEFT JOIN `tabSAP AR Invoice Detail` INV ON INV.ref_delivery_note=DN.docentry AND INV.cancellation_status = 'csNo' 
			WHERE SO.created_date>= '{FromDate}' AND SO.created_date<= '{ToDate}'  AND SO.sales_person_code = {single_salesperson} AND SO.currency = 'INR'
			ORDER BY SO.docnum DESC
			
			"""

	modified_query_text = query_text_single_salesperson.format(FromDate = fromDate,ToDate = toDate,single_salesperson=salespersons)
	final_sql_result =	frappe.db.sql(modified_query_text)
    #print(final_sql_result)
	return result(final_sql_result,salespersons)




@frappe.whitelist()
def result(final_sql_result,salespersons):
    if not final_sql_result:
        pass
        # print("The tuple is empty")
    else:
        # with open('/Users/shahilkhan/Desktop/khanalFoods/frappe-bench/apps/khanal_tech_integrations/khanal_tech_integrations/www/intranet/email.html', 'r') as f:

        file_path = os.path.join(os.path.dirname(__file__), 'email.html')
        # print(file_path,'filepath')
        with open(file_path, 'r') as f:
            # contents = f.read()
            # print(contents)
            template_str = f.read()
        # print(template_str)

        template = Template(template_str)
        # print(template)
        # rendered_html = template.render(name='John')
        ToDate = frappe.utils.nowdate()
        FromDate = add_to_date(ToDate,days=-15)
        to_date_obj = datetime.strptime(ToDate, "%Y-%m-%d")
        to_date_str = to_date_obj.strftime("%d %B %Y")

        from_date_obj = datetime.strptime(FromDate, "%Y-%m-%d")
        from_date_str = from_date_obj.strftime("%d %B %Y")
        rendered_message = template.render(
                subject='working',
                list=final_sql_result,
                ToDate=to_date_str,
                FromDate=from_date_str,
            )
        document = frappe.db.get_list('SAP Salesperson', filters={'salesperson_code':salespersons },pluck='salesperson_name')
        for salesperson_name in document:
            doc=frappe.get_doc("SAP Salesperson",salesperson_name)
            print(doc.email)
            print(doc.salesperson_code)
        # print(ToDate)
        

        
        email_args={
                "recipients":doc.email,
                "message":rendered_message,
                "subject":'Your Order Details for the period of. ' +from_date_str+ " to " + to_date_str,    
                        }
        frappe.enqueue(method=frappe.sendmail,queue='short',timeout=300, **email_args)
        # print('sent')
       

# bench --site dev.localhost execute khanal_tech_integrations.utils.logistics.notification.daily_progress
# bench --site beta.khanaltech.com execute khanal_tech_integrations.utils.logistics.notification.daily_progress
# bench --site khanaltech.com execute khanal_tech_integrations.utils.logistics.notification.daily_progress