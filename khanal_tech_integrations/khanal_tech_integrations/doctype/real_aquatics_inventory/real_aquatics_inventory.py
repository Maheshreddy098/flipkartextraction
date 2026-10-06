import frappe
from frappe.model.document import Document


class RealAquaticsInventory(Document):
	def validate(self):
		self.total_qty = (self.available_qty or 0) + (self.allocated_qty or 0)
