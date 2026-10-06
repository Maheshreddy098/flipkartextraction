# Single warehouse for all WowPets inventory (PO inwards, WO components, finished goods)
WOWPETS_WAREHOUSE = "WowPets Warehouse"

# --- SAP B1 warehouse codes (exact strings as configured in SAP) ---
# Components/raw materials warehouse
SAP_COMPONENT_WAREHOUSE = "WO - STR"
# Finished goods warehouse
SAP_FINISHED_WAREHOUSE = "WO -FG"

# SAP B1 PO line warehouse
PO_WAREHOUSE = SAP_COMPONENT_WAREHOUSE

# Shiphero: create Inventory Transfer instead of PO+GRN (replace with actual SAP vendor code)
SHIPHERO_VENDOR_CODE = "SHIPHERO"

# Shiphero PO flow warehouse codes (used when vendor_code == SHIPHERO_VENDOR_CODE)
# IMPORTANT: verify these codes against SAP before go-live
SHIPHERO_FROM_WAREHOUSE = "SC-STR"
SHIPHERO_TO_WAREHOUSE = SAP_COMPONENT_WAREHOUSE

# Shiphero Inventory Transfer flow warehouses (from ShipHero warehouse to WowPets warehouse)
SHIPHERO_IT_FROM_WAREHOUSE = "SC-STR"
SHIPHERO_IT_TO_WAREHOUSE = SAP_COMPONENT_WAREHOUSE

# SAP warehouse codes used for raw material availability checks on Work Order
WOWPETS_SAP_AVAILABILITY_WAREHOUSES = (SAP_COMPONENT_WAREHOUSE, SAP_FINISHED_WAREHOUSE)

# Orders: default warehouse to consume (transfer from) when warehouse marks order complete
ORDERS_FROM_WAREHOUSE = SAP_FINISHED_WAREHOUSE

# Warehouse team Inventory page: show stock from these SAP warehouses only
WOWPETS_WAREHOUSE_INVENTORY_WAREHOUSES = (SAP_COMPONENT_WAREHOUSE, SAP_FINISHED_WAREHOUSE)

# --- SAP Production (Work Order) ---
SAP_PO_COMPONENT_WAREHOUSE = SAP_COMPONENT_WAREHOUSE
SAP_PO_FINISHED_WAREHOUSE = SAP_FINISHED_WAREHOUSE
# AccountCode on Issue lines (must match ApprovalPage for SAP compatibility)
SAP_ISSUE_ACCOUNT_CODE = "13400000-01-001-01"
