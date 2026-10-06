import frappe


def create_test_batch_number_configuration():
	"""Create a test record and commit. Returns inserted doc name."""
	doc = frappe.get_doc({
		"doctype": "Batch Number Configuration",
		"category": "Hardened Cheese Bread",
		"item_code": "ITEM-TEST-001",
		"variant": "V1",
		"warehouse": "NH",
		"grams_sku": "100",
		"sku_code": "12",
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def get_test_batch_number_configuration():
	"""Fetch the test record."""
	return frappe.get_all(
		"Batch Number Configuration",
		filters={"item_code": "ITEM-TEST-001"},
		fields=["name", "item_code", "sku_code"],
	)

