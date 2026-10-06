"""
Backfill scalar fields and line_items in existing Unicommerce Orders records
from their stored order_json, using the same extraction logic as fetch.py.

v2: also fixes zero-valued numeric fields that were stored as "" due to the
    `value or ""` bug in the original _safe_str helper.
"""
import json

import frappe

from khanal_tech_integrations.unicommerce.workers.fetch import (
    _build_line_items,
    _extract_channel,
    _extract_order_date,
    _extract_order_scalar_fields,
)


def execute():
    total = frappe.db.count("Unicommerce Orders")
    print(f"Backfilling {total} Unicommerce Orders records...")

    names = frappe.get_all("Unicommerce Orders", fields=["name"], order_by="creation asc", limit=0)
    updated = 0
    skipped = 0

    for row in names:
        name = row.name
        raw_json = frappe.db.get_value("Unicommerce Orders", name, "order_json")
        if not raw_json:
            skipped += 1
            continue

        try:
            order = json.loads(raw_json)
        except Exception:
            skipped += 1
            continue

        # Build all scalar field updates
        scalar_updates = {
            "channel_name": _extract_channel(order),
            "order_date": _extract_order_date(order),
        }
        for k, v in _extract_order_scalar_fields(order).items():
            if v is None:
                continue
            # JSON/Text fields must be strings; never store raw dicts (causes SQL syntax error)
            if isinstance(v, (dict, list)):
                v = json.dumps(v)
            scalar_updates[k] = v

        # Update scalar fields (fast path — no ORM overhead)
        frappe.db.set_value("Unicommerce Orders", name, scalar_updates, update_modified=False)

        # Rebuild line items via ORM (child table requires doc.save())
        line_items_data = _build_line_items(order)
        if line_items_data:
            try:
                doc = frappe.get_doc("Unicommerce Orders", name)
                doc.set("line_items", [])
                for item_data in line_items_data:
                    doc.append("line_items", item_data)
                doc.save(ignore_permissions=True)
            except Exception as e:
                frappe.logger().warning(
                    "backfill_unicommerce_order_fields: line_items failed for %s: %s", name, e
                )

        updated += 1

        if updated % 100 == 0:
            frappe.db.commit()
            print(f"  Progress: {updated}/{total} updated, {skipped} skipped...")

    frappe.db.commit()
    print(f"Backfill complete: {updated} updated, {skipped} skipped (no order_json).")
