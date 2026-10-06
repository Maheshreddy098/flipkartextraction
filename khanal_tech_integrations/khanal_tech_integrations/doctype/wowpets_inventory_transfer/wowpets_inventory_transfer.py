import frappe
from frappe.model.document import Document


class WowPetsInventoryTransfer(Document):
	def validate(self):
		if not self.items or len(self.items) == 0:
			frappe.throw(frappe._("At least one item is required"))
