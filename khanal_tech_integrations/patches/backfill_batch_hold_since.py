"""
Backfill ``batch_hold_since`` for existing ``Unicommerce Orders`` that are
currently in ``batch_hold`` status.

Why this patch exists
---------------------
``batch_hold_since`` is a new column added in Apr 2026 to power the
"escalate stuck holds to ``dead`` after N attempts / H hours" rule in
``workers/invoice._recover_batch_hold_orders``.

On first deploy the column is NULL for every existing row. The recovery code
has a safe fallback — ``row.batch_hold_since or row.modified`` — but that
fallback means every batch_hold order whose ``modified`` is older than the
``BATCH_HOLD_MAX_HOURS`` cap (48 h) would escalate to ``dead`` on the very
first ``post_invoices`` run after deploy. That is almost certainly not what
the operator wants: a production tenant can easily have hundreds of holds
whose ``modified`` is days or weeks old.

This patch resets the wall-clock by setting ``batch_hold_since = NOW()`` for
every row currently in ``batch_hold``. The attempt-count cap
(``BATCH_HOLD_MAX_ATTEMPTS``) is unaffected, so genuinely stuck orders still
escalate on the next few cycles — but only based on the new, explicit
lifecycle signal rather than a tangentially-related ``modified`` timestamp.
"""

import frappe
from frappe.utils import now_datetime


def execute():
    rows = frappe.get_all(
        "Unicommerce Orders",
        filters={"pipeline_status": "batch_hold", "batch_hold_since": ["is", "not set"]},
        fields=["name"],
        limit=0,
    )
    if not rows:
        print("No batch_hold orders with NULL batch_hold_since — nothing to backfill.")
        return

    now_ts = now_datetime()
    print(f"Backfilling batch_hold_since for {len(rows)} existing batch_hold orders...")
    updated = 0
    for row in rows:
        frappe.db.set_value(
            "Unicommerce Orders",
            row.name,
            {"batch_hold_since": now_ts},
            update_modified=False,
        )
        updated += 1
        if updated % 200 == 0:
            frappe.db.commit()
            print(f"  progress: {updated}/{len(rows)}")
    frappe.db.commit()
    print(
        f"Backfill complete: set batch_hold_since={now_ts.isoformat()} on {updated} order(s). "
        "The 48-hour wall-clock cap now counts from deploy time for these orders; "
        "the attempt-count cap is unaffected."
    )
