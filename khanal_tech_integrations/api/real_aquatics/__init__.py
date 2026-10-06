# Single warehouse for all Real Aquatics inventory (PO inwards, WO components, finished goods)
REALAQUATICS_WAREHOUSE = "Real Aquatics Warehouse"

# --- SAP B1 warehouse codes (exact strings as configured in the UK CompanyDB) ---
# Components/raw materials warehouse (SAP: "Real Pets-Stores")
SAP_COMPONENT_WAREHOUSE = "RP-STR"
# Finished goods warehouse (SAP: "Real Pets-FG")
SAP_FINISHED_WAREHOUSE = "RP-FG"

# SAP B1 PO line warehouse
PO_WAREHOUSE = SAP_COMPONENT_WAREHOUSE

# (Real Aquatics has no ShipHero flow — those constants were removed.)


def normalize_warehouse_code(code):
	"""Normalize warehouse code for string comparison: strip, uppercase, remove spaces and dashes.
	'RP-STR', 'RP - STR', and 'RPSTR' all compare equal after normalization."""
	if not code:
		return ""
	return "".join(c for c in str(code).strip().upper() if c.isalnum() or c in "- ").replace(" ", "").replace("-", "")

# SAP warehouse codes used for raw material availability checks on Work Order
REALAQUATICS_SAP_AVAILABILITY_WAREHOUSES = (SAP_COMPONENT_WAREHOUSE, SAP_FINISHED_WAREHOUSE)

# Orders: default warehouse to consume (transfer from) when warehouse marks order complete
ORDERS_FROM_WAREHOUSE = SAP_FINISHED_WAREHOUSE

# Warehouse team Inventory page: show stock from these SAP warehouses only
REALAQUATICS_WAREHOUSE_INVENTORY_WAREHOUSES = (SAP_COMPONENT_WAREHOUSE, SAP_FINISHED_WAREHOUSE)

# --- SAP Production (Work Order) ---
SAP_PO_COMPONENT_WAREHOUSE = SAP_COMPONENT_WAREHOUSE
SAP_PO_FINISHED_WAREHOUSE = SAP_FINISHED_WAREHOUSE
# AccountCode on Issue lines — PLACEHOLDER, confirm UK GL account with finance before go-live
SAP_ISSUE_ACCOUNT_CODE = "TBD"

# --- VAT (per finance): UK counterparty = standard 20%, non-UK = Outside Scope of VAT (0%) ---
# Purchase side (PO/GRN — GRN inherits from PO via BaseEntry/BaseLine, no separate code needed)
REALAQUATICS_PO_TAX_CODE_UK = "I1"      # UK std rate 20.0% (Input)
REALAQUATICS_PO_TAX_CODE_NON_UK = "IOut"  # UK Outside Scope of VAT (Input)
# Sales side (Dispatch Order -> Sales Order -> Delivery -> AR Invoice; Delivery/Invoice inherit from Sales Order)
REALAQUATICS_SALES_TAX_CODE_UK = "O1"      # UK Std rate 20.0% (Output)
REALAQUATICS_SALES_TAX_CODE_NON_UK = "OOut"  # UK Outside Scope of VAT (Output)
UK_COUNTRY_CODE = "GB"


def tax_code_for_country(country_code, *, sales=False):
	"""Map a SAP BusinessPartner/Address Country code to the correct Real Aquatics VAT code.
	GB = standard 20% rate; anything else = Outside Scope of VAT (0%)."""
	is_uk = (country_code or "").strip().upper() == UK_COUNTRY_CODE
	if sales:
		return REALAQUATICS_SALES_TAX_CODE_UK if is_uk else REALAQUATICS_SALES_TAX_CODE_NON_UK
	return REALAQUATICS_PO_TAX_CODE_UK if is_uk else REALAQUATICS_PO_TAX_CODE_NON_UK
