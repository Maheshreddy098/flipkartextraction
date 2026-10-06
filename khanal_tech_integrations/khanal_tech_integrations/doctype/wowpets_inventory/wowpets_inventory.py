import frappe
from frappe.model.document import Document


class WowPetsInventory(Document):
	def validate(self):
		self.total_qty = (self.available_qty or 0) + (self.allocated_qty or 0)
