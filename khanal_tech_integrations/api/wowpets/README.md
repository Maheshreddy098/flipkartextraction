# WowPets API

WowPets integration with SAP B1 and the WowPets frontend. All constants and SAP-related settings are centralized here.

## Module overview

| Module | Purpose |
|--------|---------|
| **`__init__.py`** | Constants: warehouses, SAP codes (`SAP_PO_COMPONENT_WAREHOUSE`, `SAP_PO_FINISHED_WAREHOUSE`), Shiphero, etc. |
| **`auth.py`** | Team/role checks (`get_user_team`, `is_manager`, `get_user_wowpets_roles`) for KhanalFoods vs Warehouse. |
| **`work_order.py`** | Work Order CRUD, BOM load, Production Order create/release, **Issue for Production**, Receipt from Production. |
| **`sap_issue_for_production.py`** | Shared Issue-for-Production: SAP login (cached), fetch PO lines, build payload, POST `/InventoryGenExits`. Used by `work_order.consume_and_issue` and `work_order.create_production_order_and_issue`. |
| **`sap_master.py`** | SAP B1 session, BOM fetch, batch lookup, GRN, stock transfer, inventory list. |
| **`orders.py`** | Orders CRUD and SAP stock transfer when warehouse marks complete. |
| **`purchase_order.py`** | Purchase Order and GRN posting to SAP. |
| **`returns.py`** | Returns flow. |
| **`inventory.py`** | Allocate/consume and SAP inventory list. |
| **`inventory_transfer.py`** | Shiphero inventory transfer. |
| **`work_order_sap_test.py`** | Bench-executable tests: list WOs, run full SAP flow, create PO only, get PO lines, Issue+Receipt, `post_wo_fgdc1018_full_flow`. |

## SAP Production flow (Work Order)

1. **Create Production Order** – from WO items; then **Release** (required before Issue).
2. **Issue for Production** – via `sap_issue_for_production.issue_for_production(po_id, items, doc_date)` (cached session, 401 retry).
3. **Receipt from Production** – POST to `/InventoryGenEntries`; then optionally close PO.

See **`WOWPETS_SAP_INTEGRATION_ISSUES.md`** in this folder for payload rules and known SAP behaviours.

## Running tests

From app root:

```bash
bench --site YOUR_SITE execute khanal_tech_integrations.api.wowpets.work_order_sap_test.post_wo_fgdc1018_full_flow
bench --site YOUR_SITE execute --args '["WP-WO-2026-00001"]' khanal_tech_integrations.api.wowpets.work_order_sap_test.run_wo_sap_test
```

Use a user with WowPets KhanalFoods role for team checks.
