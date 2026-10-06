# Copyright (c) 2025, Khanal Tech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class SAPBatchHold(Document):
    def before_save(self):
        if not self.created_by:
            self.created_by = frappe.session.user
        
        # Auto-calculate analytics if not set
        if not self.total_orders and self.order_list:
            try:
                order_data = frappe.parse_json(self.order_list) if isinstance(self.order_list, str) else self.order_list
                self.total_orders = len(order_data) if order_data else 0
            except:
                self.total_orders = 0
        
        # Note: total_failed_items is now set directly by the code, no auto-calculation needed
    
    def on_update(self):
        # Log status changes
        if self.has_value_changed('status'):
            frappe.log_error(
                f"SAP Batch Hold {self.name} status changed to {self.status}",
                "SAP Batch Hold Status Change"
            )
