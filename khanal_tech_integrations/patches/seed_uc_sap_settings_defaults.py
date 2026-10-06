import frappe


def execute():
    """Seed safe default values for Unicommerce Settings (SAP integration maps).

    Uses raw SQL against tabSingles so the patch works even when run before
    the DocType schema is fully synced (e.g., on first migrate).
    """
    doctype = "Unicommerce Settings"

    if not frappe.db.exists("DocType", doctype):
        return

    defaults = {
        "channel_customer_map": "{}",
        "bill_to_code_map": "{}",
        "ship_to_code_map": "{}",
        "tax_code_map": "{}",
        "tax_inclusive_map": "{}",
        "warehouse_map": "{}",
        "channel_warehouse_map": "{}",
        "last_fetched_at_json": "{}",
        "ar_invoice_series_map": "{}",
        "channel_origin_state_map": "{}",
        "max_retry_attempts": "3",
        "posting_timeout_mins": "5",
    }

    for fieldname, default_value in defaults.items():
        # ON DUPLICATE KEY: only set if the existing value is NULL or empty string.
        frappe.db.sql(
            """
            INSERT INTO `tabSingles` (doctype, field, value)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                value = IF(value IS NULL OR value = '', %s, value)
            """,
            (doctype, fieldname, default_value, default_value),
        )

    frappe.db.commit()
