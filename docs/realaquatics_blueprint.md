# Real Aquatics 3PL Portal — Complete Build Blueprint

**Branch:** `RealAquatics_Yogesha_09062026`  
**Partner:** Real Aquatics (UK)  
**Date:** 2026-06-09  
**Author:** Yogesha / Khanal Tech  

---

## Overview

Build an identical 3PL management portal for Real Aquatics (UK) mirroring the WowPets (US) system.  
Same Frappe app, same SAP B1 server URL — **different CompanyDB and different HANA schema**.  
WowPets code is never touched. Everything is isolated under the `real_aquatics` namespace.

---

## Key Differences vs WowPets

| Item | WowPets (US) | Real Aquatics (UK) |
|---|---|---|
| SAP Settings DocType | `INC SAP Settings` | `Real Aquatics SAP Settings` |
| SAP CompanyDB | INC company DB | UK company DB *(TBD — fill when SAP UK is ready)* |
| HANA schema | INC schema | UK schema *(TBD)* |
| SAP B1 URL | US server URL | **Same URL** |
| HANA host/port/user/pass | INC credentials | **Same credentials** |
| Redis session cache key | `wowpets_sap_b1_session` | `real_aquatics_sap_b1_session` |
| Role prefix | `WowPets*` | `RealAquatics*` |
| DocType prefix | `WowPets*` | `Real Aquatics*` |
| Python module path | `api/wowpets/` | `api/real_aquatics/` |
| Frontend URL | `/wowpets` | `/realaquatics` |
| Frontend folder | `wowpets-frontend/` | `realaquatics-frontend/` |
| Frontend build output | `public/wowpets/` | `public/realaquatics/` |
| ShipHero support | Yes | **No** — removed |
| Warehouse codes | `WO - STR` / `WO -FG` | Placeholder `RA - STR` / `RA - FG` *(update before go-live)* |
| AWS IAM credentials | `wowpets_access_key_id` / `wowpets_secret_access_key` | **Same credentials** — reused from AWS doctype |
| KF Attachments S3 bucket | `wowpets_khanalfoods_bucket` (AWS doctype field) | `real_aquatics_khanalfoods_bucket` *(new field in AWS doctype)* |
| Ticket Attachments S3 bucket | `wowpets-tickets` (hardcoded constant) | `realaquatics-tickets` *(constant in tickets.py)* |
| S3 AWS region | `wowpets_region` | **Same region** — reused from AWS doctype |

---

## Naming Rules for New DocTypes

| WowPets name | Real Aquatics name | Machine name (fieldname/table ref) |
|---|---|---|
| WowPets Order | Real Aquatics Order | `real_aquatics_order` |
| WowPets Order Item | Real Aquatics Order Item | `real_aquatics_order_item` |
| WowPets Purchase Order | Real Aquatics Purchase Order | `real_aquatics_purchase_order` |
| WowPets Purchase Order Item | Real Aquatics Purchase Order Item | `real_aquatics_purchase_order_item` |
| WowPets Work Order | Real Aquatics Work Order | `real_aquatics_work_order` |
| WowPets Work Order Item | Real Aquatics Work Order Item | `real_aquatics_work_order_item` |
| WowPets Dispatch Order | Real Aquatics Dispatch Order | `real_aquatics_dispatch_order` |
| WowPets Dispatch Order Item | Real Aquatics Dispatch Order Item | `real_aquatics_dispatch_order_item` |
| WowPets Inventory Transfer | Real Aquatics Inventory Transfer | `real_aquatics_inventory_transfer` |
| WowPets Inventory Transfer Item | Real Aquatics Inventory Transfer Item | `real_aquatics_inventory_transfer_item` |
| WowPets Inventory | Real Aquatics Inventory | `real_aquatics_inventory` |
| WowPets Return | Real Aquatics Return | `real_aquatics_return` |
| WowPets Return Item | Real Aquatics Return Item | `real_aquatics_return_item` |
| WowPets Ticket | Real Aquatics Ticket | `real_aquatics_ticket` |
| WowPets Ticket Comment | Real Aquatics Ticket Comment | `real_aquatics_ticket_comment` |
| WowPets Ticket Attachment | Real Aquatics Ticket Attachment | `real_aquatics_ticket_attachment` |
| WowPets KF Attachment | Real Aquatics KF Attachment | `real_aquatics_kf_attachment` |
| WowPets SAP Log | Real Aquatics SAP Log | `real_aquatics_sap_log` |
| INC SAP Settings | Real Aquatics SAP Settings | `real_aquatics_sap_settings` |

---

## Autoname / Naming Series

| DocType | Autoname |
|---|---|
| Real Aquatics Order | `RA-ORD-.YYYY.-.#####` |
| Real Aquatics Purchase Order | `RA-PO-.YYYY.-.#####` |
| Real Aquatics Work Order | `RA-WO-.YYYY.-.#####` |
| Real Aquatics Dispatch Order | `RA-DO-.YYYY.-.#####` |
| Real Aquatics Inventory Transfer | `RA-IT-.YYYY.-.#####` |
| Real Aquatics Return | `RA-RET-.YYYY.-.#####` |
| Real Aquatics Ticket | `RA-TKT-.YYYY.-.#####` |

---

## Complete File Inventory

### Phase 1 — SAP Settings DocType

```
khanal_tech_integrations/khanal_tech_integrations/doctype/real_aquatics_sap_settings/
    real_aquatics_sap_settings.json
    real_aquatics_sap_settings.py
    __init__.py
```

### Phase 2 — Python API Module

```
khanal_tech_integrations/api/real_aquatics/
    __init__.py             ← warehouse constants
    auth.py                 ← RealAquatics* roles, access checks
    sap_master.py           ← SAP B1 session, HANA, item/vendor/BOM/inventory APIs
    sap_issue_for_production.py  ← production issue/receipt
    orders.py               ← FBA/customer order CRUD + workflow
    purchase_order.py       ← vendor PO CRUD + SAP PO+GRN
    work_order.py           ← production order CRUD + SAP WO
    dispatch_orders.py      ← sales order CRUD + SAP SO
    inventory.py            ← inventory read-only from SAP
    inventory_transfer.py   ← internal stock transfer CRUD + SAP
    returns.py              ← returns CRUD + workflow
    tickets.py              ← support ticket CRUD
    kf_attachments.py       ← S3/attachment handling
    sap_log.py              ← SAP audit log writer
```

### Phase 3 — DocType Directories (19 total)

All go in: `khanal_tech_integrations/khanal_tech_integrations/doctype/`

Each directory contains: `<name>.json`, `<name>.py`, `__init__.py`  
Main doctypes also get: `<name>.js` (minimal stub)  
Main doctypes also get: `test_<name>.py` (empty test stub)

```
real_aquatics_sap_settings/      ← Single DocType
real_aquatics_order/
real_aquatics_order_item/
real_aquatics_purchase_order/
real_aquatics_purchase_order_item/
real_aquatics_work_order/
real_aquatics_work_order_item/
real_aquatics_dispatch_order/
real_aquatics_dispatch_order_item/
real_aquatics_inventory_transfer/
real_aquatics_inventory_transfer_item/
real_aquatics_inventory/
real_aquatics_return/
real_aquatics_return_item/
real_aquatics_ticket/
real_aquatics_ticket_comment/
real_aquatics_ticket_attachment/
real_aquatics_kf_attachment/
real_aquatics_sap_log/
```

### Phase 4 — Frontend

```
realaquatics-frontend/
    index.html
    package.json
    vite.config.ts          ← copy wowpets, no changes needed (uses build.config.js)
    tailwind.config.js      ← copy wowpets
    build.config.js         ← copy wowpets
    src/
        config/
            settings.js     ← FOLDER_NAME='realaquatics', BASE_PATH='/realaquatics', PORT=8082
        App.vue             ← copy wowpets
        main.js             ← copy wowpets
        router.js           ← replace /wowpets → /realaquatics
        layouts/
            AppLayout.vue   ← copy, update title to "Real Aquatics"
        pages/
            Login.vue       ← copy, update title
            khanalfoods/
                Dashboard.vue
                Orders.vue
                OrderForm.vue
                PurchaseOrders.vue
                PurchaseOrderForm.vue
                WorkOrders.vue
                WorkOrderForm.vue
                DispatchOrders.vue
                DispatchOrderForm.vue
                Returns.vue
                Tickets.vue
                [NO ShipheroTransfers.vue]
                [NO ShipheroTransferForm.vue]
            warehouse/
                Dashboard.vue
                Inventory.vue
                OrderProcess.vue
                PendingPurchaseOrders.vue
                PendingWorkOrders.vue
                PurchaseOrderDetail.vue
                WorkOrderProcess.vue
                DispatchOrderProcess.vue
                Returns.vue
        core/
            api/
                apiClient.js        ← copy wowpets
                orders.js           ← update API paths to real_aquatics.*
                purchaseOrders.js
                workOrders.js
                dispatchOrders.js
                returns.js
                inventory.js        ← no shiphero endpoint
                tickets.js
                kfAttachments.js
                sapMaster.js
                inventoryTransfers.js  ← renamed from shipheroTransfers.js
            auth/
                authService.js      ← copy, update VERIFY_ACCESS endpoint
            stores/
                session.js          ← copy wowpets
                notifications.js    ← copy wowpets
            utils/
                exportCsv.js        ← copy wowpets
        components/
            common/                 ← copy all from wowpets (no changes)
                DataTable.vue
                ItemSearch.vue
                VendorSearch.vue
                StatusBadge.vue
                ConfirmDialog.vue
                TicketDialog.vue
                KFAttachments.vue
                RecentListCard.vue
                Notifications.vue
```

### Phase 5 — Route + Hooks Changes (existing files)

```
khanal_tech_integrations/route.py       ← add /realaquatics routes
khanal_tech_integrations/hooks.py       ← add after_migrate + 4 new roles in fixtures
khanal_tech_integrations/public/realaquatics/index.html   ← SPA entry point (build output)
```

### Phase 6 — AWS DocType Change (existing file)

```
khanal_tech_integrations/khanal_tech_integrations/doctype/aws/aws.json
    ← Add 2 new fields: real_aquatics_khanalfoods_bucket, real_aquatics_tickets_bucket
    ← Add both fieldnames to field_order array
```

---

## DocType Field Specifications

### `real_aquatics_sap_settings` (Single DocType)

Exact copy of `inc_sap_settings.json` with:
- `"name": "Real Aquatics SAP Settings"`
- `"module": "Khanal Tech Integrations"`
- `"issingle": 1`
- All fields identical: `companydb`, `username`, `password`, `routeid`, `sap_b1_url`, `expires_on`, `b1session`, `initiate_session`, `hana_host`, `hana_user`, `hana_password`, `hana_port`, `hana_schema`

### `real_aquatics_order` fields

Same as `wowpets_order` with these changes:
- `"autoname": "RA-ORD-.YYYY.-.#####"`
- `"name": "Real Aquatics Order"`
- `items` table `options` → `"Real Aquatics Order Item"`
- Roles in permissions → `Real Aquatics KhanalFoods User/Manager`, `Real Aquatics Warehouse User/Manager`
- Section label `"Address (USA – not sent to SAP)"` → `"Address (UK – not sent to SAP)"`
- Field label `"State (e.g. CA)"` → `"County/Region"`

### `real_aquatics_order_item` fields

Exact copy of `wowpets_order_item` with:
- `"name": "Real Aquatics Order Item"`, `"istable": 1`

### `real_aquatics_purchase_order` fields

Same as `wowpets_purchase_order` with:
- `"autoname": "RA-PO-.YYYY.-.#####"`
- `"name": "Real Aquatics Purchase Order"`
- `items` table `options` → `"Real Aquatics Purchase Order Item"`
- Roles → `Real Aquatics *`

### `real_aquatics_purchase_order_item` fields

Exact copy of `wowpets_purchase_order_item` with name changed.

### `real_aquatics_work_order` fields

Same as `wowpets_work_order` with:
- `"autoname": "RA-WO-.YYYY.-.#####"`
- `"name": "Real Aquatics Work Order"`
- `items` table → `"Real Aquatics Work Order Item"`
- Roles → `Real Aquatics *`

### `real_aquatics_work_order_item` fields

Exact copy of `wowpets_work_order_item` with name changed.

### `real_aquatics_dispatch_order` fields

Same as `wowpets_dispatch_order` with:
- `"autoname": "RA-DO-.YYYY.-.#####"` (also update `naming_series` field options)
- `"name": "Real Aquatics Dispatch Order"`
- `items` table → `"Real Aquatics Dispatch Order Item"`
- Roles → `Real Aquatics *`

### `real_aquatics_dispatch_order_item` fields

Exact copy of `wowpets_dispatch_order_item` with name changed.

### `real_aquatics_inventory_transfer` fields

Same as `wowpets_inventory_transfer` with:
- `"autoname": "RA-IT-.YYYY.-.#####"`
- `"name": "Real Aquatics Inventory Transfer"`
- `items` table → `"Real Aquatics Inventory Transfer Item"`
- Roles → `Real Aquatics *`

### `real_aquatics_inventory_transfer_item` fields

Exact copy with name changed.

### `real_aquatics_inventory` fields

Exact copy of `wowpets_inventory` with name changed. No permissions change needed beyond System Manager + RA roles.

### `real_aquatics_return` fields

Same as `wowpets_return` with:
- `"autoname": "RA-RET-.YYYY.-.#####"`
- `"name": "Real Aquatics Return"`
- `reference_doctype` Select options: `\nReal Aquatics Purchase Order\nReal Aquatics Work Order`
- `items` table → `"Real Aquatics Return Item"`
- Roles → `Real Aquatics *`

### `real_aquatics_return_item` fields

Exact copy with name changed.

### `real_aquatics_ticket` fields

Same as `wowpets_ticket` with:
- `"autoname": "RA-TKT-.YYYY.-.#####"`
- `"name": "Real Aquatics Ticket"`
- `section` Select options: `Purchase Order\nInventory Transfer\nWork Order\nDispatch Order\nOther` (removed ShipHero/FBA, added Inventory Transfer)
- `comments` table → `"Real Aquatics Ticket Comment"`
- `attachments` table → `"Real Aquatics Ticket Attachment"`
- Roles → `Real Aquatics *`

### `real_aquatics_ticket_comment` fields

Exact copy with name changed.

### `real_aquatics_ticket_attachment` fields

Exact copy with name changed.

### `real_aquatics_kf_attachment` fields

Exact copy with name changed.

### `real_aquatics_sap_log` fields

Same as `wowpets_sap_log` with:
- `"name": "Real Aquatics SAP Log"`
- `operation` Select options: remove `Stock Transfer - Shiphero` (not applicable), keep all others

---

## Python Controller Specifications

### `real_aquatics_sap_settings.py`
```python
from frappe.model.document import Document

class RealAquaticsSAPSettings(Document):
    pass
```

### `real_aquatics_order.py`
```python
import frappe
from frappe.model.document import Document
from frappe.utils import flt, cint

class RealAquaticsOrder(Document):
    def validate(self):
        if not self.items:
            frappe.throw(frappe._("At least one item is required"))
        for i, row in enumerate(self.items, 1):
            qty = flt(row.get("quantity") or 0)
            units_per_box = cint(row.get("number_of_units_per_box") or 0)
            num_boxes = cint(row.get("number_of_boxes") or 0)
            if qty > 0 and units_per_box > 0 and num_boxes > 0:
                if abs((units_per_box * num_boxes) - qty) > 0.001:
                    frappe.throw(
                        frappe._("Row {0}: Units per box × Number of boxes must equal Quantity").format(i)
                    )
```

### `real_aquatics_purchase_order.py`
```python
import frappe
from frappe.model.document import Document

class RealAquaticsPurchaseOrder(Document):
    def validate(self):
        self.calculate_totals()

    def before_save(self):
        for row in self.items:
            row.amount = (row.qty or 0) * (row.rate or 0)
        self.calculate_totals()

    def calculate_totals(self):
        self.total_qty = sum(row.qty or 0 for row in self.items)
        self.total_amount = sum(row.amount or 0 for row in self.items)
```

### `real_aquatics_inventory.py`
```python
import frappe
from frappe.model.document import Document

class RealAquaticsInventory(Document):
    def validate(self):
        self.total_qty = (self.available_qty or 0) + (self.allocated_qty or 0)
```

### `real_aquatics_inventory_transfer.py`
```python
import frappe
from frappe.model.document import Document

class RealAquaticsInventoryTransfer(Document):
    def validate(self):
        if not self.items:
            frappe.throw(frappe._("At least one item is required"))
```

### All other controllers (work_order, dispatch_order, return, ticket, sap_log, kf_attachment, all child tables)
```python
from frappe.model.document import Document

class RealAquatics<Name>(Document):
    pass
```

---

## `api/real_aquatics/__init__.py` — Warehouse Constants

```python
# Real Aquatics (UK) SAP B1 warehouse codes
# PLACEHOLDER — replace with actual UK SAP warehouse codes before go-live
RA_COMPONENT_WAREHOUSE = "RA - STR"
RA_FINISHED_WAREHOUSE = "RA - FG"

PO_WAREHOUSE = RA_COMPONENT_WAREHOUSE
ORDERS_FROM_WAREHOUSE = RA_FINISHED_WAREHOUSE
RA_SAP_AVAILABILITY_WAREHOUSES = (RA_COMPONENT_WAREHOUSE, RA_FINISHED_WAREHOUSE)
RA_WAREHOUSE_INVENTORY_WAREHOUSES = (RA_COMPONENT_WAREHOUSE, RA_FINISHED_WAREHOUSE)

# Issue Account Code for Production Orders
# PLACEHOLDER — confirm with Real Aquatics finance/SAP team before go-live
RA_ISSUE_ACCOUNT_CODE = "TBD"
```

---

## `api/real_aquatics/auth.py` — Access Control

```python
import frappe
from frappe import _

REAL_AQUATICS_ROLES = {
    "khanalfoods": ["RealAquatics KhanalFoods User", "RealAquatics KhanalFoods Manager"],
    "warehouse":   ["RealAquatics Warehouse User",   "RealAquatics Warehouse Manager"],
}

MANAGER_ROLES = ["RealAquatics KhanalFoods Manager", "RealAquatics Warehouse Manager"]


def get_user_real_aquatics_roles(user=None):
    user = user or frappe.session.user
    return [r for r in frappe.get_roles(user) if r.startswith("RealAquatics")]


def get_user_team(user=None):
    roles = get_user_real_aquatics_roles(user)
    if not roles:
        return None
    has_kf = any("KhanalFoods" in r for r in roles)
    has_wh = any("Warehouse" in r for r in roles)
    if has_kf and has_wh:
        frappe.log_error(
            f"User {user or frappe.session.user} has dual RealAquatics roles. Defaulting to khanalfoods.",
            "RealAquatics Dual-Role User",
        )
        return "khanalfoods"
    return "khanalfoods" if has_kf else ("warehouse" if has_wh else None)


def is_manager(user=None):
    return any(r in MANAGER_ROLES for r in get_user_real_aquatics_roles(user))


def check_real_aquatics_access():
    if not get_user_real_aquatics_roles():
        frappe.throw(_("No Real Aquatics access"), frappe.PermissionError)


@frappe.whitelist(allow_guest=True)
def verify_real_aquatics_access(user=None):
    user = user or frappe.session.user
    if user == "Guest":
        return {"has_access": False}
    roles = get_user_real_aquatics_roles(user)
    if not roles:
        return {"has_access": False}
    team = get_user_team(user)
    return {
        "has_access": True,
        "user": user,
        "team": team,
        "roles": roles,
        "is_manager": is_manager(user),
        "full_name": frappe.db.get_value("User", user, "full_name"),
    }


@frappe.whitelist(allow_guest=True)
def get_real_aquatics_user_info():
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Not logged in"), frappe.AuthenticationError)
    roles = get_user_real_aquatics_roles(user)
    if not roles:
        frappe.throw(_("No Real Aquatics access"), frappe.PermissionError)
    return {
        "user": user,
        "full_name": frappe.db.get_value("User", user, "full_name"),
        "team": get_user_team(user),
        "roles": roles,
        "is_manager": is_manager(user),
    }
```

---

## `api/real_aquatics/sap_master.py` — SAP B1 Session

Key differences from `api/wowpets/sap_master.py`:

```python
# Settings DocType
_SETTINGS_DOCTYPE = "Real Aquatics SAP Settings"

# Redis cache key — separate from WowPets, no collision
_SAP_SESSION_CACHE_KEY = "real_aquatics_sap_b1_session"
_SAP_SESSION_CACHE_TTL = 28 * 60

# Log prefix
_LOG_TITLE = "RealAquatics SAP Error"

# Warehouse imports come from api/real_aquatics/__init__.py
from khanal_tech_integrations.api.real_aquatics import (
    RA_COMPONENT_WAREHOUSE,
    RA_FINISHED_WAREHOUSE,
    PO_WAREHOUSE,
    ORDERS_FROM_WAREHOUSE,
    RA_SAP_AVAILABILITY_WAREHOUSES,
)

# after_migrate hook
def _ensure_ra_sap_settings_hana_fields():
    """Auto-add HANA fields to Real Aquatics SAP Settings. Safe to run multiple times."""
    # identical logic to _ensure_inc_sap_settings_hana_fields()
    # but targets "Real Aquatics SAP Settings"

# initiate session whitelisted endpoint
@frappe.whitelist()
def initiate_ra_sap_session():
    _check_real_aquatics_access()
    session, b1_url = _get_sap_session(force_login=True)
    ...
```

All other functions (`get_items`, `search_items`, `search_vendors`, `search_customers`, `get_bom`, `get_batches_for_item`, `get_inventory_list_from_sap`, `get_item_stock_from_sap`, etc.) are identical — just using `_SETTINGS_DOCTYPE` and `_SAP_SESSION_CACHE_KEY` everywhere instead of hardcoded strings.

---

## `api/real_aquatics/sap_log.py`

```python
import frappe

def log_real_aquatics_sap(reference_doctype, reference_name, operation, status,
                           request_payload=None, response_payload=None, error_message=None):
    doc = frappe.get_doc({
        "doctype": "Real Aquatics SAP Log",
        "reference_doctype": reference_doctype,
        "reference_name": reference_name,
        "operation": operation,
        "status": status,
        "request_payload": str(request_payload or ""),
        "response_payload": str(response_payload or ""),
        "error_message": str(error_message or ""),
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
```

---

## Each API Module — Function Signatures

All modules follow this exact pattern. Function names and signatures are **identical to WowPets**. Only the DocType references and SAP module imports change.

### `orders.py`
- `get_list(status=None, page=1, page_size=20)`
- `get_detail(name)`
- `create(data)`
- `update(name, data)`
- `submit_for_approval(name)`
- `approve(name)`
- `reject(name, reason=None)`
- `accept(name)`
- `start_packaging(name)`
- `complete(name)`
- `send_to_sap(name)`
- `retry_sap(name)`
- `retry_sap_request(name)`
- `revert_to_draft(name)`
- `delete_draft(name)`
- `warehouse_request_kf_assistance(name, message=None)`
- `kf_update_for_warehouse_resume(name)`
- `kf_release_warehouse_hold(name)`
- `preview_sap(name)`

### `purchase_order.py`
- `get_list(status=None, page=1, page_size=20)`
- `get_detail(name)`
- `create(data)`
- `update(name, data)`
- `submit_for_approval(name)`
- `approve(name)`
- `reject(name, reason=None)`
- `accept(name)`
- `update_accepted_quantities(name, items)`
- `receive(name)`
- `create_grn(name)`
- `retry_sap_sync(name)`
- `retry_grn(name)`
- `revert_to_draft(name)`
- `delete_draft(name)`
- `warehouse_request_kf_assistance(name, message=None)`
- `kf_update_for_warehouse_resume(name)`
- `kf_release_warehouse_hold(name)`

### `work_order.py`
- `get_list(status=None, page=1, page_size=20)`
- `get_detail(name)`
- `create(data)`
- `update(name, data)`
- `submit_for_approval(name)`
- `approve(name)`
- `reject(name, reason=None)`
- `start_processing(name)`
- `warehouse_mark_consumed(name)`
- `warehouse_complete(name)`
- `consume_and_issue(name)`
- `retry_issue_for_production(name)`
- `complete(name)`
- `create_production_order_and_issue(name)`
- `retry_create_production_order(name)`
- `receipt_from_production(name)`
- `revert_to_draft(name)`
- `delete_draft(name)`
- `warehouse_request_kf_assistance(name, message=None)`
- `kf_update_for_warehouse_resume(name)`
- `kf_release_warehouse_hold(name)`

### `dispatch_orders.py`
- `get_list(status=None, page=1, page_size=20)`
- `get_detail(name)`
- `create(data)`
- `update(name, data)`
- `submit_for_approval(name)`
- `approve(name)`
- `reject(name, reason=None)`
- `accept(name)`
- `start_preparation(name)`
- `dispatch(name)`
- `retry_sap(name)`
- `reconcile_status(name)`
- `revert_to_draft(name)`
- `delete_draft(name)`
- `warehouse_request_kf_assistance(name, message=None)`
- `kf_update_for_warehouse_resume(name)`
- `kf_release_warehouse_hold(name)`

### `inventory.py`
- `get_inventory(warehouse=None, search=None, page=1, page_size=50)`
- `get_item_stock(item_code, warehouse=None)`
- *(NO `get_shiphero_inventory` — removed)*

### `inventory_transfer.py`
- `get_list(status=None, page=1, page_size=20)`
- `get_detail(name)`
- `create(data)`
- `update(name, data)`
- `submit_for_approval(name)`
- `approve(name)`
- `reject(name, reason=None)`
- `accept(name)`
- `update_accepted_quantities(name, items)`
- `send_to_sap(name)`
- `retry_sap_request(name)`
- `mark_received(name)`
- `revert_to_draft(name)`
- `delete_draft(name)`
- `warehouse_request_kf_assistance(name, message=None)`
- `kf_update_for_warehouse_resume(name)`
- `kf_release_warehouse_hold(name)`

### `returns.py`
- `get_list(status=None, page=1, page_size=20)`
- `get_detail(name)`
- `create(data)`
- `submit_return(name)`
- `approve_return(name)`
- `process_return(name)`

### `tickets.py`
- `get_list(status=None, page=1, page_size=20)`
- `get_detail(name)`
- `create(data)`
- `update(name, data)`
- `add_comment(name, content)`
- `list_comments(name)`
- `add_attachment(name, file_name, file_url)`
- `list_attachments(name)`

### `kf_attachments.py`
- `upload_attachment(reference_doctype, reference_name, file_content, file_name, module_folder=None)`
- `list_attachments(reference_doctype, reference_name)`
- `delete_attachment(name)`

---

## Hooks Changes

### `hooks.py` — `after_migrate` section

```python
after_migrate = [
    "khanal_tech_integrations.api.wowpets.sap_master._ensure_inc_sap_settings_hana_fields",
    "khanal_tech_integrations.api.real_aquatics.sap_master._ensure_ra_sap_settings_hana_fields",  # NEW
]
```

### `hooks.py` — `fixtures` section (Role additions)

```python
{"doctype": "Role", "filters": [["name", "in", [
    "WowPets KhanalFoods User",
    "WowPets KhanalFoods Manager",
    "WowPets Warehouse User",
    "WowPets Warehouse Manager",
    # NEW — Real Aquatics roles
    "RealAquatics KhanalFoods User",
    "RealAquatics KhanalFoods Manager",
    "RealAquatics Warehouse User",
    "RealAquatics Warehouse Manager",
]]]},
```

---

## `route.py` Changes

```python
# Real Aquatics 3PL SPA routes  ← ADD THIS BLOCK
{'from_route': '/realaquatics',                          'to_route': 'realaquatics'},
{'from_route': '/realaquatics/login',                    'to_route': 'realaquatics'},
{'from_route': '/realaquatics/khanalfoods',              'to_route': 'realaquatics'},
{'from_route': '/realaquatics/khanalfoods/<path:path>',  'to_route': 'realaquatics'},
{'from_route': '/realaquatics/warehouse',                'to_route': 'realaquatics'},
{'from_route': '/realaquatics/warehouse/<path:path>',    'to_route': 'realaquatics'},
```

---

## Frontend `settings.js` — Real Aquatics

```javascript
const FRAPPE_APP_NAME = 'khanal_tech_integrations'
const FOLDER_NAME = 'realaquatics'
const BASE_PATH = '/realaquatics'

const DEV_SERVER = {
    PORT: 8082,    // Different port from WowPets (8081) for simultaneous dev
    HOST: '0.0.0.0',
}

export default { FRAPPE_APP_NAME, FOLDER_NAME, BASE_PATH, DEV_SERVER }

export const APP_CONFIG = {
    BASE_PATH,
    FRAPPE_API_URL: '',
    API_TIMEOUT: 30000,
    API_ENDPOINTS: {
        LOGIN: '/api/method/login',
        LOGOUT: '/api/method/logout',
        VERIFY_ACCESS: '/api/method/khanal_tech_integrations.api.real_aquatics.auth.verify_real_aquatics_access',
        USER_INFO:     '/api/method/khanal_tech_integrations.api.real_aquatics.auth.get_real_aquatics_user_info',

        // Purchase Orders
        PO_LIST:                    '/api/method/khanal_tech_integrations.api.real_aquatics.purchase_order.get_list',
        PO_DETAIL:                  '/api/method/khanal_tech_integrations.api.real_aquatics.purchase_order.get_detail',
        PO_CREATE:                  '/api/method/khanal_tech_integrations.api.real_aquatics.purchase_order.create',
        PO_UPDATE:                  '/api/method/khanal_tech_integrations.api.real_aquatics.purchase_order.update',
        PO_SUBMIT:                  '/api/method/khanal_tech_integrations.api.real_aquatics.purchase_order.submit_for_approval',
        PO_APPROVE:                 '/api/method/khanal_tech_integrations.api.real_aquatics.purchase_order.approve',
        PO_REJECT:                  '/api/method/khanal_tech_integrations.api.real_aquatics.purchase_order.reject',
        PO_ACCEPT:                  '/api/method/khanal_tech_integrations.api.real_aquatics.purchase_order.accept',
        PO_UPDATE_ACCEPTED_QTYS:    '/api/method/khanal_tech_integrations.api.real_aquatics.purchase_order.update_accepted_quantities',
        PO_RECEIVE:                 '/api/method/khanal_tech_integrations.api.real_aquatics.purchase_order.receive',
        PO_REVERT:                  '/api/method/khanal_tech_integrations.api.real_aquatics.purchase_order.revert_to_draft',
        PO_RETRY_SAP:               '/api/method/khanal_tech_integrations.api.real_aquatics.purchase_order.retry_sap_sync',
        PO_CREATE_GRN:              '/api/method/khanal_tech_integrations.api.real_aquatics.purchase_order.create_grn',
        PO_RETRY_GRN:               '/api/method/khanal_tech_integrations.api.real_aquatics.purchase_order.retry_grn',
        PO_WAREHOUSE_REQUEST_KF:    '/api/method/khanal_tech_integrations.api.real_aquatics.purchase_order.warehouse_request_kf_assistance',
        PO_KF_UPDATE_RESUME:        '/api/method/khanal_tech_integrations.api.real_aquatics.purchase_order.kf_update_for_warehouse_resume',
        PO_KF_RELEASE_HOLD:         '/api/method/khanal_tech_integrations.api.real_aquatics.purchase_order.kf_release_warehouse_hold',
        PO_DELETE:                  '/api/method/khanal_tech_integrations.api.real_aquatics.purchase_order.delete_draft',

        // Work Orders
        WO_LIST:                    '/api/method/khanal_tech_integrations.api.real_aquatics.work_order.get_list',
        WO_DETAIL:                  '/api/method/khanal_tech_integrations.api.real_aquatics.work_order.get_detail',
        WO_CREATE:                  '/api/method/khanal_tech_integrations.api.real_aquatics.work_order.create',
        WO_UPDATE:                  '/api/method/khanal_tech_integrations.api.real_aquatics.work_order.update',
        WO_SUBMIT:                  '/api/method/khanal_tech_integrations.api.real_aquatics.work_order.submit_for_approval',
        WO_APPROVE:                 '/api/method/khanal_tech_integrations.api.real_aquatics.work_order.approve',
        WO_REJECT:                  '/api/method/khanal_tech_integrations.api.real_aquatics.work_order.reject',
        WO_START:                   '/api/method/khanal_tech_integrations.api.real_aquatics.work_order.start_processing',
        WO_RETRY_PO:                '/api/method/khanal_tech_integrations.api.real_aquatics.work_order.retry_create_production_order',
        WO_WAREHOUSE_MARK_CONSUMED: '/api/method/khanal_tech_integrations.api.real_aquatics.work_order.warehouse_mark_consumed',
        WO_WAREHOUSE_COMPLETE:      '/api/method/khanal_tech_integrations.api.real_aquatics.work_order.warehouse_complete',
        WO_CONSUME_AND_ISSUE:       '/api/method/khanal_tech_integrations.api.real_aquatics.work_order.consume_and_issue',
        WO_RETRY_ISSUE:             '/api/method/khanal_tech_integrations.api.real_aquatics.work_order.retry_issue_for_production',
        WO_COMPLETE:                '/api/method/khanal_tech_integrations.api.real_aquatics.work_order.complete',
        WO_REVERT:                  '/api/method/khanal_tech_integrations.api.real_aquatics.work_order.revert_to_draft',
        WO_DELETE:                  '/api/method/khanal_tech_integrations.api.real_aquatics.work_order.delete_draft',
        WO_CREATE_PRODUCTION_AND_ISSUE: '/api/method/khanal_tech_integrations.api.real_aquatics.work_order.create_production_order_and_issue',
        WO_RECEIPT_FROM_PRODUCTION:     '/api/method/khanal_tech_integrations.api.real_aquatics.work_order.receipt_from_production',
        WO_WAREHOUSE_REQUEST_KF:    '/api/method/khanal_tech_integrations.api.real_aquatics.work_order.warehouse_request_kf_assistance',
        WO_KF_UPDATE_RESUME:        '/api/method/khanal_tech_integrations.api.real_aquatics.work_order.kf_update_for_warehouse_resume',
        WO_KF_RELEASE_HOLD:         '/api/method/khanal_tech_integrations.api.real_aquatics.work_order.kf_release_warehouse_hold',

        // Inventory
        INVENTORY_LIST:             '/api/method/khanal_tech_integrations.api.real_aquatics.inventory.get_inventory',
        ITEM_STOCK:                 '/api/method/khanal_tech_integrations.api.real_aquatics.inventory.get_item_stock',

        // Returns
        RETURN_LIST:                '/api/method/khanal_tech_integrations.api.real_aquatics.returns.get_list',
        RETURN_DETAIL:              '/api/method/khanal_tech_integrations.api.real_aquatics.returns.get_detail',
        RETURN_CREATE:              '/api/method/khanal_tech_integrations.api.real_aquatics.returns.create',
        RETURN_SUBMIT:              '/api/method/khanal_tech_integrations.api.real_aquatics.returns.submit_return',
        RETURN_APPROVE:             '/api/method/khanal_tech_integrations.api.real_aquatics.returns.approve_return',
        RETURN_PROCESS:             '/api/method/khanal_tech_integrations.api.real_aquatics.returns.process_return',

        // SAP Master
        SAP_ITEMS:                  '/api/method/khanal_tech_integrations.api.real_aquatics.sap_master.get_items',
        SAP_SEARCH:                 '/api/method/khanal_tech_integrations.api.real_aquatics.sap_master.search_items',
        SAP_VENDORS:                '/api/method/khanal_tech_integrations.api.real_aquatics.sap_master.search_vendors',
        SAP_CUSTOMERS:              '/api/method/khanal_tech_integrations.api.real_aquatics.sap_master.search_customers',
        SAP_GET_CUSTOMER_ADDRESSES: '/api/method/khanal_tech_integrations.api.real_aquatics.sap_master.get_customer_addresses',
        SAP_ADD_CUSTOMER_ADDRESS:   '/api/method/khanal_tech_integrations.api.real_aquatics.sap_master.add_customer_address',
        SAP_BOM:                    '/api/method/khanal_tech_integrations.api.real_aquatics.sap_master.get_bom',
        SAP_BATCHES_FOR_ITEM:       '/api/method/khanal_tech_integrations.api.real_aquatics.sap_master.get_batches_for_item',
        SAP_BATCHES_FOR_DISPATCH:   '/api/method/khanal_tech_integrations.api.real_aquatics.sap_master.get_batches_for_dispatch_item',
        SAP_WAREHOUSES:             '/api/method/khanal_tech_integrations.api.real_aquatics.sap_master.get_warehouses',
        SAP_HEALTH:                 '/api/method/khanal_tech_integrations.api.real_aquatics.sap_master.get_sap_health',
        SAP_INIT_SESSION:           '/api/method/khanal_tech_integrations.api.real_aquatics.sap_master.initiate_ra_sap_session',
        SAP_PO_SERIES:              '/api/method/khanal_tech_integrations.api.real_aquatics.sap_master.get_production_order_series_from_hana',

        // Inventory Transfers (was ShipHero in WowPets)
        IT_LIST:                    '/api/method/khanal_tech_integrations.api.real_aquatics.inventory_transfer.get_list',
        IT_DETAIL:                  '/api/method/khanal_tech_integrations.api.real_aquatics.inventory_transfer.get_detail',
        IT_CREATE:                  '/api/method/khanal_tech_integrations.api.real_aquatics.inventory_transfer.create',
        IT_UPDATE:                  '/api/method/khanal_tech_integrations.api.real_aquatics.inventory_transfer.update',
        IT_SUBMIT:                  '/api/method/khanal_tech_integrations.api.real_aquatics.inventory_transfer.submit_for_approval',
        IT_APPROVE:                 '/api/method/khanal_tech_integrations.api.real_aquatics.inventory_transfer.approve',
        IT_REJECT:                  '/api/method/khanal_tech_integrations.api.real_aquatics.inventory_transfer.reject',
        IT_ACCEPT:                  '/api/method/khanal_tech_integrations.api.real_aquatics.inventory_transfer.accept',
        IT_UPDATE_ACCEPTED_QTYS:    '/api/method/khanal_tech_integrations.api.real_aquatics.inventory_transfer.update_accepted_quantities',
        IT_SEND_TO_SAP:             '/api/method/khanal_tech_integrations.api.real_aquatics.inventory_transfer.send_to_sap',
        IT_RETRY_SAP:               '/api/method/khanal_tech_integrations.api.real_aquatics.inventory_transfer.retry_sap_request',
        IT_MARK_RECEIVED:           '/api/method/khanal_tech_integrations.api.real_aquatics.inventory_transfer.mark_received',
        IT_WAREHOUSE_REQUEST_KF:    '/api/method/khanal_tech_integrations.api.real_aquatics.inventory_transfer.warehouse_request_kf_assistance',
        IT_KF_UPDATE_RESUME:        '/api/method/khanal_tech_integrations.api.real_aquatics.inventory_transfer.kf_update_for_warehouse_resume',
        IT_KF_RELEASE_HOLD:         '/api/method/khanal_tech_integrations.api.real_aquatics.inventory_transfer.kf_release_warehouse_hold',
        IT_REVERT:                  '/api/method/khanal_tech_integrations.api.real_aquatics.inventory_transfer.revert_to_draft',
        IT_DELETE:                  '/api/method/khanal_tech_integrations.api.real_aquatics.inventory_transfer.delete_draft',

        // Orders
        ORDER_LIST:                 '/api/method/khanal_tech_integrations.api.real_aquatics.orders.get_list',
        ORDER_DETAIL:               '/api/method/khanal_tech_integrations.api.real_aquatics.orders.get_detail',
        ORDER_CREATE:               '/api/method/khanal_tech_integrations.api.real_aquatics.orders.create',
        ORDER_UPDATE:               '/api/method/khanal_tech_integrations.api.real_aquatics.orders.update',
        ORDER_SUBMIT:               '/api/method/khanal_tech_integrations.api.real_aquatics.orders.submit_for_approval',
        ORDER_APPROVE:              '/api/method/khanal_tech_integrations.api.real_aquatics.orders.approve',
        ORDER_REJECT:               '/api/method/khanal_tech_integrations.api.real_aquatics.orders.reject',
        ORDER_ACCEPT:               '/api/method/khanal_tech_integrations.api.real_aquatics.orders.accept',
        ORDER_START_PACKAGING:      '/api/method/khanal_tech_integrations.api.real_aquatics.orders.start_packaging',
        ORDER_COMPLETE:             '/api/method/khanal_tech_integrations.api.real_aquatics.orders.complete',
        ORDER_PREVIEW_SAP:          '/api/method/khanal_tech_integrations.api.real_aquatics.orders.preview_sap',
        ORDER_SEND_TO_SAP:          '/api/method/khanal_tech_integrations.api.real_aquatics.orders.send_to_sap',
        ORDER_RETRY_SAP:            '/api/method/khanal_tech_integrations.api.real_aquatics.orders.retry_sap',
        ORDER_RETRY_SAP_REQUEST:    '/api/method/khanal_tech_integrations.api.real_aquatics.orders.retry_sap_request',
        ORDER_WAREHOUSE_REQUEST_KF: '/api/method/khanal_tech_integrations.api.real_aquatics.orders.warehouse_request_kf_assistance',
        ORDER_KF_UPDATE_RESUME:     '/api/method/khanal_tech_integrations.api.real_aquatics.orders.kf_update_for_warehouse_resume',
        ORDER_KF_RELEASE_HOLD:      '/api/method/khanal_tech_integrations.api.real_aquatics.orders.kf_release_warehouse_hold',
        ORDER_REVERT:               '/api/method/khanal_tech_integrations.api.real_aquatics.orders.revert_to_draft',
        ORDER_DELETE:               '/api/method/khanal_tech_integrations.api.real_aquatics.orders.delete_draft',

        // Dispatch Orders
        DISPATCH_LIST:              '/api/method/khanal_tech_integrations.api.real_aquatics.dispatch_orders.get_list',
        DISPATCH_DETAIL:            '/api/method/khanal_tech_integrations.api.real_aquatics.dispatch_orders.get_detail',
        DISPATCH_CREATE:            '/api/method/khanal_tech_integrations.api.real_aquatics.dispatch_orders.create',
        DISPATCH_UPDATE:            '/api/method/khanal_tech_integrations.api.real_aquatics.dispatch_orders.update',
        DISPATCH_SUBMIT:            '/api/method/khanal_tech_integrations.api.real_aquatics.dispatch_orders.submit_for_approval',
        DISPATCH_APPROVE:           '/api/method/khanal_tech_integrations.api.real_aquatics.dispatch_orders.approve',
        DISPATCH_REJECT:            '/api/method/khanal_tech_integrations.api.real_aquatics.dispatch_orders.reject',
        DISPATCH_ACCEPT:            '/api/method/khanal_tech_integrations.api.real_aquatics.dispatch_orders.accept',
        DISPATCH_START_PREPARATION: '/api/method/khanal_tech_integrations.api.real_aquatics.dispatch_orders.start_preparation',
        DISPATCH_DISPATCH:          '/api/method/khanal_tech_integrations.api.real_aquatics.dispatch_orders.dispatch',
        DISPATCH_RETRY_SAP:         '/api/method/khanal_tech_integrations.api.real_aquatics.dispatch_orders.retry_sap',
        DISPATCH_WAREHOUSE_REQUEST_KF: '/api/method/khanal_tech_integrations.api.real_aquatics.dispatch_orders.warehouse_request_kf_assistance',
        DISPATCH_KF_UPDATE_RESUME:  '/api/method/khanal_tech_integrations.api.real_aquatics.dispatch_orders.kf_update_for_warehouse_resume',
        DISPATCH_KF_RELEASE_HOLD:   '/api/method/khanal_tech_integrations.api.real_aquatics.dispatch_orders.kf_release_warehouse_hold',
        DISPATCH_RECONCILE:         '/api/method/khanal_tech_integrations.api.real_aquatics.dispatch_orders.reconcile_status',
        DISPATCH_REVERT:            '/api/method/khanal_tech_integrations.api.real_aquatics.dispatch_orders.revert_to_draft',
        DISPATCH_DELETE:            '/api/method/khanal_tech_integrations.api.real_aquatics.dispatch_orders.delete_draft',

        // KhanalFoods Attachments
        KF_ATTACH_UPLOAD:           '/api/method/khanal_tech_integrations.api.real_aquatics.kf_attachments.upload_attachment',
        KF_ATTACH_LIST:             '/api/method/khanal_tech_integrations.api.real_aquatics.kf_attachments.list_attachments',
        KF_ATTACH_DELETE:           '/api/method/khanal_tech_integrations.api.real_aquatics.kf_attachments.delete_attachment',

        // Tickets
        TICKETS_LIST:               '/api/method/khanal_tech_integrations.api.real_aquatics.tickets.get_list',
        TICKETS_DETAIL:             '/api/method/khanal_tech_integrations.api.real_aquatics.tickets.get_detail',
        TICKETS_CREATE:             '/api/method/khanal_tech_integrations.api.real_aquatics.tickets.create',
        TICKETS_UPDATE:             '/api/method/khanal_tech_integrations.api.real_aquatics.tickets.update',
        TICKETS_ADD_ATTACHMENT:     '/api/method/khanal_tech_integrations.api.real_aquatics.tickets.add_attachment',
        TICKETS_LIST_ATTACHMENTS:   '/api/method/khanal_tech_integrations.api.real_aquatics.tickets.list_attachments',
        TICKETS_ADD_COMMENT:        '/api/method/khanal_tech_integrations.api.real_aquatics.tickets.add_comment',
        TICKETS_LIST_COMMENTS:      '/api/method/khanal_tech_integrations.api.real_aquatics.tickets.list_comments',
    },
}
```

---

## `public/realaquatics/index.html` — SPA Entry Point

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Real Aquatics 3PL</title>
    <script type="module" crossorigin src="/assets/khanal_tech_integrations/realaquatics/assets/index.js"></script>
    <link rel="stylesheet" href="/assets/khanal_tech_integrations/realaquatics/assets/index.css">
  </head>
  <body>
    <div id="app"></div>
    {% for key in boot %}
    <script>window["{{ key }}"] = {{ boot[key] | tojson }};</script>
    {% endfor %}
  </body>
</html>
```

*Note: asset filenames will be fingerprinted after Vite build. Rebuild and update this file after first build.*

---

## S3 / Attachments Configuration

### Decision Summary

| Decision | Answer |
|---|---|
| S3 buckets | **Separate** — Real Aquatics gets its own buckets |
| AWS IAM credentials | **Same** as WowPets (`wowpets_access_key_id` / `wowpets_secret_access_key`) |
| S3 region | Same as WowPets (`wowpets_region`) |
| KF attachments bucket | `realaquatics-khanalfoods` *(create in AWS before go-live)* |
| Ticket attachments bucket | `realaquatics-tickets` *(create in AWS before go-live)* |

### AWS DocType — 2 New Fields to Add

The `aws.json` doctype (in `khanal_tech_integrations/khanal_tech_integrations/doctype/aws/`) needs two new fields added inside the `fields` array, after the existing WowPets fields:

```json
{
  "fieldname": "section_break_realaquatics",
  "fieldtype": "Section Break",
  "label": "Real Aquatics S3"
},
{
  "fieldname": "real_aquatics_khanalfoods_bucket",
  "fieldtype": "Data",
  "label": "Real Aquatics KhanalFoods Attachments Bucket",
  "description": "S3 bucket for Real Aquatics KF document attachments (e.g. realaquatics-khanalfoods)"
},
{
  "fieldname": "real_aquatics_tickets_bucket",
  "fieldtype": "Data",
  "label": "Real Aquatics Tickets Bucket",
  "description": "S3 bucket for Real Aquatics ticket attachments (e.g. realaquatics-tickets)"
}
```

Also add these two fieldnames to the `field_order` array in `aws.json`.

**No new credentials fields** — `wowpets_access_key_id`, `wowpets_secret_access_key`, and `wowpets_region` are reused as-is for Real Aquatics.

### `api/real_aquatics/kf_attachments.py` — S3 Config

```python
MODULE_FOLDER_MAP = {
    "Real Aquatics Order":              "orders",
    "Real Aquatics Work Order":         "work-orders",
    "Real Aquatics Purchase Order":     "purchase-orders",
    "Real Aquatics Dispatch Order":     "dispatch-orders",
    "Real Aquatics Inventory Transfer": "inventory-transfers",
}

# Note: WowPets uses "fba-transfers" for Orders. Real Aquatics has no FBA so it's renamed "orders".

def _get_aws_config():
    """Read AWS doctype and return (s3_client, bucket_name) for Real Aquatics."""
    aws = frappe.get_single("AWS")
    if not aws.wowpets_access_key_id:          # Same IAM credentials as WowPets
        frappe.throw(
            _("WowPets/Real Aquatics S3 credentials are not configured in the AWS doctype"),
            frappe.ValidationError,
        )
    secret = aws.get_password("wowpets_secret_access_key")
    if not secret:
        frappe.throw(
            _("WowPets/Real Aquatics S3 secret access key is not configured in the AWS doctype"),
            frappe.ValidationError,
        )
    region = aws.wowpets_region or "us-west-1"    # Same region as WowPets
    bucket = aws.real_aquatics_khanalfoods_bucket or "realaquatics-khanalfoods"   # ← different bucket
    client = boto3.client(
        "s3",
        aws_access_key_id=aws.wowpets_access_key_id,
        aws_secret_access_key=secret,
        region_name=region,
    )
    return client, bucket
```

S3 key structure (same pattern as WowPets):
```
{module_folder}/{docname}/{name_timestamp.ext}
e.g.  purchase-orders/RA-PO-2026-00001/invoice_1749456000.pdf
```

### `api/real_aquatics/tickets.py` — S3 Config

```python
RA_TICKET_BUCKET = "realaquatics-tickets"      # separate bucket from WowPets
RA_TICKET_REGION = "us-west-1"                  # same region

SECTION_PREFIX_MAP = {
    "Purchase Order":       "PurchaseOrder",
    "Work Order":           "WorkOrder",
    "Inventory Transfer":   "InventoryTransfer",   # ← replaces FBA/Shiphero from WowPets
    "Dispatch Order":       "DispatchOrders",
    "Other":                "Other",
}

def _get_ra_s3_client():
    aws = frappe.get_single("AWS")
    if not aws.wowpets_access_key_id:              # Same IAM credentials
        frappe.throw(
            _("S3 credentials are not configured in the AWS doctype"),
            frappe.ValidationError,
        )
    secret = aws.get_password("wowpets_secret_access_key")
    region = aws.wowpets_region or RA_TICKET_REGION
    return boto3.client(
        "s3",
        aws_access_key_id=aws.wowpets_access_key_id,
        aws_secret_access_key=secret,
        region_name=region,
    )
```

Ticket attachment S3 key structure:
```
{section_prefix}/{ticket_name}/{name_timestamp.ext}
e.g.  PurchaseOrder/RA-TKT-2026-00001/photo_1749456000.jpg
```

Download URL pattern (presigned, 1-hour expiry — same as WowPets).

### AWS Pre-Go-Live Checklist

- [ ] Create S3 bucket `realaquatics-khanalfoods` in AWS console (same region as `wowpets-khanalfoods`)
- [ ] Create S3 bucket `realaquatics-tickets` in AWS console
- [ ] Ensure the existing WowPets IAM user has `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` on both new buckets
- [ ] Set bucket policy (private — no public access, presigned URLs only)
- [ ] Fill `real_aquatics_khanalfoods_bucket` field in Frappe AWS doctype: `realaquatics-khanalfoods`
- [ ] Fill `real_aquatics_tickets_bucket` field in Frappe AWS doctype: `realaquatics-tickets`

---

## Implementation Checklist (ordered)

### Phase 1 — Foundation (do first)
- [ ] Create `real_aquatics_sap_settings` DocType (JSON + py + __init__.py)
- [ ] Create `api/real_aquatics/__init__.py` (warehouse constants)
- [ ] Create `api/real_aquatics/auth.py`
- [ ] Create `api/real_aquatics/sap_log.py`
- [ ] Create `api/real_aquatics/sap_master.py`
- [ ] Create `api/real_aquatics/sap_issue_for_production.py`
- [ ] Update `hooks.py` — add after_migrate entry + 4 roles to fixtures
- [ ] Run `bench migrate` — verify `Real Aquatics SAP Settings` is created in Frappe desk

### Phase 2 — DocTypes
- [ ] real_aquatics_order + item
- [ ] real_aquatics_purchase_order + item
- [ ] real_aquatics_work_order + item
- [ ] real_aquatics_dispatch_order + item
- [ ] real_aquatics_inventory_transfer + item
- [ ] real_aquatics_inventory
- [ ] real_aquatics_return + item
- [ ] real_aquatics_ticket + comment + attachment
- [ ] real_aquatics_kf_attachment
- [ ] real_aquatics_sap_log
- [ ] Run `bench migrate` — verify all 18 DocTypes appear in desk

### Phase 3 — API Modules
- [ ] `orders.py`
- [ ] `purchase_order.py`
- [ ] `work_order.py`
- [ ] `dispatch_orders.py`
- [ ] `inventory.py`
- [ ] `inventory_transfer.py`
- [ ] `returns.py`
- [ ] `tickets.py`
- [ ] `kf_attachments.py`
- [ ] Test each with `bench console` or Postman before moving to frontend

### Phase 4 — Frontend
- [ ] Create `realaquatics-frontend/` directory structure
- [ ] `src/config/settings.js` with RA endpoints (full list above)
- [ ] Copy and update all pages (remove ShipHero pages, rename IT references)
- [ ] Copy and update `router.js`
- [ ] Copy shared components unchanged
- [ ] `npm install` in `realaquatics-frontend/`
- [ ] `npm run build` — verify output lands in `public/realaquatics/`

### Phase 5 — Routes & Entry Point
- [ ] Update `route.py` — add 6 RA routes
- [ ] Create `public/realaquatics/index.html` (stub, will be overwritten by build)
- [ ] Run `bench restart`
- [ ] Test `/realaquatics` in browser — login page loads

### Phase 6 — S3 / AWS Configuration
- [ ] Add 2 new fields to `aws.json` (`real_aquatics_khanalfoods_bucket`, `real_aquatics_tickets_bucket`)
- [ ] Run `bench migrate`
- [ ] Create `realaquatics-khanalfoods` bucket in AWS console
- [ ] Create `realaquatics-tickets` bucket in AWS console
- [ ] Add `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` permissions for both new buckets to the existing IAM user
- [ ] Set both buckets as private (no public access — presigned URLs only)
- [ ] Fill `real_aquatics_khanalfoods_bucket` in Frappe AWS doctype
- [ ] Fill `real_aquatics_tickets_bucket` in Frappe AWS doctype
- [ ] Test file upload on a Real Aquatics PO and a ticket

### Phase 7 — SAP Configuration & Go-Live
- [ ] Fill in `companydb` in `Real Aquatics SAP Settings`
- [ ] Fill in `hana_schema` in `Real Aquatics SAP Settings`
- [ ] Replace warehouse placeholder codes in `api/real_aquatics/__init__.py`
- [ ] Replace `RA_ISSUE_ACCOUNT_CODE` with real UK account code
- [ ] Test SAP connection with "Initiate Session" button
- [ ] Assign `RealAquatics *` roles to users in Frappe desk
- [ ] End-to-end test: create PO → approve → sync to SAP → receive

---

## What is Never Touched

- `api/wowpets/` — zero changes
- `INC SAP Settings` doctype — zero changes
- All `wowpets_*` DocTypes — zero changes
- `wowpets-frontend/` — zero changes
- WowPets roles in fixtures — zero changes (only additions)
- All other existing modules in the app — zero changes
