import frappe
from frappe.model.document import Document


class WowPetsPurchaseOrder(Document):
	def validate(self):
		self.calculate_totals()

	def calculate_totals(self):
		self.total_qty = sum(row.qty or 0 for row in self.items)
		self.total_amount = sum(row.amount or 0 for row in self.items)

	def before_save(self):
		for row in self.items:
			row.amount = (row.qty or 0) * (row.rate or 0)
		self.calculate_totals()
