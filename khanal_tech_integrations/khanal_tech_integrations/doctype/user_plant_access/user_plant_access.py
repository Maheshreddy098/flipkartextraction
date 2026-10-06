# Copyright (c) 2025, Khanal Tech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class UserPlantAccess(Document):
	def validate(self):
		"""Validate that the user-plant combination is unique"""
		# Check if another User Plant Access exists with the same user and plant
		existing = frappe.db.exists(
			"User Plant Access",
			{
				"user": self.user,
				"plant": self.plant,
				"name": ["!=", self.name]
			}
		)
		
		if existing:
			frappe.throw(
				f"User Plant Access already exists for user {self.user} and plant {self.plant}",
				title="Duplicate Entry"
			)
