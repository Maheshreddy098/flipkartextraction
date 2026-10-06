# Copyright (c) 2024, Khanal Tech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class InternalEmployeeList(Document):
	
	# def before_save(self):
	# 	print(self,'\n\n')
		# if self.sap_customer_code:
			# customer = frappe.db.get_value('Customer', {'custom_sap_customer_code': self.sap_customer_code}, 'name')
		# 	if customer:
		# 		self.customer_name = customer
		# 	else:
		# 		frappe.throw(f"No customer found with SAP customer code: {self.sap_customer_code}")
		# if self.credit_note_line_item_details:
	pass
