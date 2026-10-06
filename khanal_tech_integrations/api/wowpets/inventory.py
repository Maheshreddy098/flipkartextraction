"""WowPets inventory: all stock data from SAP (no local WowPets Inventory). Write APIs are no-ops."""
import frappe
from frappe import _
from khanal_tech_integrations.api.wowpets.auth import check_wowpets_access, get_user_wowpets_roles
from khanal_tech_integrations.api.wowpets import (
	WOWPETS_WAREHOUSE,
	WOWPETS_WAREHOUSE_INVENTORY_WAREHOUSES,
	SHIPHERO_IT_FROM_WAREHOUSE,
)


_check_wowpets_access = check_wowpets_access


@frappe.whitelist()
def get_inventory(warehouse=None, search=None, page=1, page_size=50):
	"""List inventory from SAP (WowPets FG/STR warehouses). warehouse filter: None/'all' = both, 'WO - STR' or 'WO -FG' = single."""
	_check_wowpets_access()
	from khanal_tech_integrations.api.wowpets.sap_master import get_inventory_list_from_sap
	wh_codes = WOWPETS_WAREHOUSE_INVENTORY_WAREHOUSES
	if warehouse and str(warehouse).strip():
		wh = str(warehouse).strip()
		if wh in WOWPETS_WAREHOUSE_INVENTORY_WAREHOUSES:
			wh_codes = (wh,)
	result = get_inventory_list_from_sap(
		warehouse_codes=wh_codes,
		search=search,
		page=int(page) or 1,
		page_size=int(page_size) or 50,
	)
	return {"data": result.get("data") or [], "total": result.get("total") or 0}


@frappe.whitelist()
def get_shiphero_inventory(search=None, page=1, page_size=50):
	"""List ShipHero inventory from SAP (SC-STR / SC-FG warehouses only)."""
	_check_wowpets_access()
	from khanal_tech_integrations.api.wowpets.sap_master import get_inventory_list_from_sap

	# ShipHero inventory lives in SC-STR and SC-FG in SAP.
	result = get_inventory_list_from_sap(
		warehouse_codes=("SC-STR", "SC-FG"),
		search=search,
		page=int(page) or 1,
		page_size=int(page_size) or 50,
	)
	return {"data": result.get("data") or [], "total": result.get("total") or 0}




@frappe.whitelist()
def get_item_stock(item_code, warehouse=None):
	"""Get item stock from SAP only (WowPets FG/STR warehouses). No local data."""
	_check_wowpets_access()
	from khanal_tech_integrations.api.wowpets.sap_master import get_item_stock_from_sap
	sap = get_item_stock_from_sap(item_code)
	qty = sap.get("available_qty", 0)
	return {
		"available_qty": qty,
		"allocated_qty": 0,
		"total_qty": qty,
	}


# --- No-ops: no local inventory; SAP is source of truth ---

def increase_inventory(item_code, item_name, qty, warehouse=None):
	"""No-op. Stock is managed in SAP."""
	pass


def decrease_inventory(item_code, qty, warehouse=None):
	"""No-op. Stock is managed in SAP."""
	pass


def allocate_inventory(item_code, qty, warehouse=None):
	"""No-op. Returns default warehouse for callers that expect one."""
	return warehouse or WOWPETS_WAREHOUSE


def deallocate_inventory(item_code, qty, warehouse=None):
	"""No-op. Stock is managed in SAP."""
	pass


def consume_allocated(item_code, qty, warehouse=None):
	"""No-op. Consumption is posted to SAP (Issue for Production)."""
	pass
