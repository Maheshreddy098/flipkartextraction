import frappe
from frappe.model.document import Document
from frappe.utils import flt, cint


class RealAquaticsOrder(Document):
	def validate(self):
		if not self.items or len(self.items) == 0:
			frappe.throw(frappe._("At least one item is required"))
		for i, row in enumerate(self.items, 1):
			qty = flt(row.get("quantity") or 0)
			units_per_box = cint(row.get("number_of_units_per_box") or 0)
			num_boxes = cint(row.get("number_of_boxes") or 0)
			if qty > 0 and units_per_box > 0 and num_boxes > 0:
				if abs((units_per_box * num_boxes) - qty) > 0.001:
					frappe.throw(
						frappe._("Row {0}: Units per box × Number of boxes must equal Quantity").format(i)
					)
