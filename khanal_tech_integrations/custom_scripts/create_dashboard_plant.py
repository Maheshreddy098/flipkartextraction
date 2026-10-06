"""
Script to create Dashboard plant for Admin access
Run this script using: bench --site [site-name] execute khanal_tech_integrations.custom_scripts.create_dashboard_plant.create_dashboard_plant
"""

import frappe


def create_dashboard_plant():
	"""
	Create Dashboard plant if it doesn't exist
	"""
	try:
		# Check if Dashboard plant already exists
		existing_plants = frappe.get_all(
			"Plant",
			filters={"plant_id": "dashboard"},
			fields=["name"]
		)
		
		if existing_plants:
			frappe.msgprint(f"Dashboard plant already exists: {existing_plants[0].name}")
			return existing_plants[0].name
		
		# Create new Dashboard plant
		plant_doc = frappe.get_doc({
			"doctype": "Plant",
			"plant_id": "dashboard",
			"plant_name": "Dashboard",
			"location": "System",
			"status": "Active",
			"plant_type": "Admin Dashboard",
			"description": "Admin Dashboard for system-wide monitoring and management"
		})
		
		plant_doc.insert(ignore_permissions=True)
		frappe.db.commit()
		
		frappe.msgprint(f"✅ Dashboard plant created successfully: {plant_doc.name}")
		return plant_doc.name
		
	except frappe.DuplicateEntryError:
		frappe.msgprint("Dashboard plant already exists")
		return None
	except Exception as e:
		frappe.log_error(f"Error creating Dashboard plant: {str(e)}")
		frappe.msgprint(f"❌ Error creating Dashboard plant: {str(e)}")
		raise


if __name__ == "__main__":
	create_dashboard_plant()

