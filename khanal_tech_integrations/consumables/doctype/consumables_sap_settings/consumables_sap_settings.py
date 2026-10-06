# Copyright (c) 2026, Khanal Tech and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class ConsumablesSAPSettings(Document):
	"""Single doctype for consumables' own SAP B1 Service Layer, HANA, and
	Crystal Reports connection settings — isolated from the shared SAP
	Settings doctype so consumables can point at a test company DB without
	affecting the other live verticals (unicommerce, amazon_us, B2B, etc.)
	that share SAP Settings."""
	pass
