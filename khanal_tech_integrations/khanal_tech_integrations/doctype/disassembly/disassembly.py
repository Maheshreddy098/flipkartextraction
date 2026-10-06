# Copyright (c) 2025, Khanal Tech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
import json

class Disassembly(Document):
	def validate(self):
		"""Validate the document"""
		# Ensure production_order_docnum is unique (handled by unique constraint in JSON)
		if self.production_order_docnum:
			# Check if another record with same production_order_docnum exists (excluding current record)
			existing = frappe.db.exists("Disassembly", {
				"production_order_docnum": self.production_order_docnum,
				"name": ["!=", self.name]
			})
			if existing:
				frappe.throw(_("Production Order DocNum {0} already exists. Please use a different value.").format(self.production_order_docnum))


