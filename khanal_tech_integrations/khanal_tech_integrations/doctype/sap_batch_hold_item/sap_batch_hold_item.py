# Copyright (c) 2025, Khanal Tech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class SAPBatchHoldItem(Document):
    def before_save(self):
        # Auto-calculate shortage if not set
        if not hasattr(self, 'shortage_qty') or self.shortage_qty is None:
            self.shortage_qty = self.required_qty - self.available_qty if self.required_qty and self.available_qty else 0
