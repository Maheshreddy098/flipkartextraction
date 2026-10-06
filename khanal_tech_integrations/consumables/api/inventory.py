import frappe
from frappe.utils.data import cint
from khanal_tech_integrations.consumables.services.role_guard import (
    require_consumables_role,
    assert_plant_access,
)
from khanal_tech_integrations.consumables.hana.client import ConsumablesHANAClient
from khanal_tech_integrations.consumables.hana.inventory_queries import (
    get_warehouse_stock_summary,
    get_warehouse_inventory,
    get_item_batch_detail,
    search_consumable_items,
)


def _build_item_groups(rows):
    """Group batch rows by (warehouse_code, item_code, item_name); preserve first-seen order."""
    order_keys = []
    groups = {}
    for r in rows:
        wh = str(r.get("warehouse_code") or "").strip()
        ic = str(r.get("item_code") or "").strip()
        nm = str(r.get("item_name") or "").strip()
        key = (wh, ic, nm)
        if key not in groups:
            groups[key] = []
            order_keys.append(key)
        groups[key].append(r)
    return order_keys, groups


@frappe.whitelist()
def get_warehouses(plant_code):
    """Return active warehouses for a plant with per-warehouse stock summary from HANA."""
    require_consumables_role()
    assert_plant_access(plant_code)

    plant_doc = frappe.get_doc("Consumables Plant", plant_code)
    active_warehouses = [w for w in plant_doc.warehouses if w.is_active]

    with ConsumablesHANAClient() as client:
        result = []
        for w in active_warehouses:
            summary = get_warehouse_stock_summary(client, w.warehouse_code)
            result.append({
                "warehouse_code": w.warehouse_code,
                "warehouse_name": w.warehouse_name,
                "warehouse_type": w.warehouse_type,
                "sap_address_code": getattr(w, "sap_address_code", "") or "",
                "item_count": summary.get("item_count", 0),
                "batch_count": summary.get("batch_count", 0),
                "total_qty": summary.get("total_qty", 0.0),
                "expiring_soon": summary.get("expiring_soon", 0),
            })

    return {"warehouses": result}


@frappe.whitelist()
def get_inventory(
    plant_code,
    warehouse_code,
    item_group=None,
    search=None,
    page=1,
    page_size=50,
    paginate_by_item=1,
):
    """Return inventory for a warehouse.

    When paginate_by_item is true (default), page/page_size refer to distinct items
    (item_code + item_name + warehouse); each item includes all its batch rows.

    When paginate_by_item is false, returns all batch rows (no slicing); use for export
    or merging multi-warehouse views.
    """
    require_consumables_role()
    assert_plant_access(plant_code)

    page = int(page)
    page_size = int(page_size)
    paginate_by_item = cint(paginate_by_item)

    with ConsumablesHANAClient() as client:
        rows = get_warehouse_inventory(
            client,
            warehouse_code,
            item_group=item_group or None,
            search=search or None,
        )

    order_keys, groups = _build_item_groups(rows)
    total_distinct_items = len(order_keys)
    total_batch_rows = len(rows)

    if not paginate_by_item:
        return {
            "items": rows,
            "total": total_distinct_items,
            "total_distinct_items": total_distinct_items,
            "total_batch_rows": total_batch_rows,
            "page": 1,
            "page_size": total_batch_rows,
        }

    start = (page - 1) * page_size
    page_keys = order_keys[start : start + page_size]
    paginated = []
    for k in page_keys:
        paginated.extend(groups[k])

    return {
        "items": paginated,
        "total": total_distinct_items,
        "total_distinct_items": total_distinct_items,
        "total_batch_rows": total_batch_rows,
        "page": page,
        "page_size": page_size,
    }


@frappe.whitelist()
def get_batch_detail(plant_code, warehouse_code, item_code):
    """Return all batches for one item in a warehouse, sorted FIFO."""
    require_consumables_role()
    assert_plant_access(plant_code)

    with ConsumablesHANAClient() as client:
        batches = get_item_batch_detail(client, warehouse_code, item_code)

    return {"batches": batches}


@frappe.whitelist()
def search_items_for_request(search=None):
    """Search all active consumable items from SAP HANA OITM for CMR item picker.
    Returns items regardless of current stock level."""
    require_consumables_role()

    q = (search or "").strip()
    if len(q) < 2:
        return {"items": []}

    settings = frappe.get_single("Consumables Settings")
    configured_codes = []
    for row in (settings.consumable_item_groups or []):
        if getattr(row, "is_active", 1) and getattr(row, "item_group_code", None):
            configured_codes.append(str(row.item_group_code).strip())

    with ConsumablesHANAClient() as client:
        items = search_consumable_items(client, q, configured_codes)

    return {"items": items}


@frappe.whitelist()
def get_item_suggestions(search=None, limit=25):
    """Return item master suggestions for transfer item picker fallback."""
    require_consumables_role()

    try:
        limit = max(1, min(int(limit or 25), 100))
    except Exception:
        limit = 25

    q = (search or "").strip()
    filters = [
        ["Item", "disabled", "=", 0],
    ]
    kwargs = {
        "filters": filters,
        "fields": ["item_code", "item_name"],
        "order_by": "item_code asc",
        "limit_page_length": limit,
        "ignore_permissions": True,
    }

    if q:
        kwargs["or_filters"] = [
            ["Item", "item_code", "like", f"%{q}%"],
            ["Item", "item_name", "like", f"%{q}%"],
        ]

    items = frappe.get_all("Item", **kwargs)
    return {"items": items}


