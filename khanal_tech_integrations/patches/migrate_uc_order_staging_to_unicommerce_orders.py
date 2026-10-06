import frappe


def execute():
    """Migrate UC Order Staging records into Unicommerce Orders."""
    if not frappe.db.table_exists("UC Order Staging"):
        return

    rows = frappe.db.sql(
        """
        SELECT uc_order_id, channel, order_date, status, attempt_count,
               last_error, sap_doc_entry, sap_doc_num, payload_json, uc_raw_json,
               tax_expected, tax_actual, tax_diff,
               unit_price_expected, unit_price_actual, unit_price_diff,
               posting_started_at
        FROM `tabUC Order Staging`
        ORDER BY creation asc
        """,
        as_dict=True,
    )

    migrated = 0
    updated = 0

    for row in rows:
        order_id = (row.uc_order_id or "").strip()
        if not order_id:
            continue

        existing = frappe.db.exists("Unicommerce Orders", order_id)

        if not existing:
            # New record — insert via ORM so Frappe handles naming/timestamps
            doc = frappe.get_doc({
                "doctype": "Unicommerce Orders",
                "uniware_id": order_id,
                "channel_name": row.channel or "",
                "order_date": row.order_date,
                "pipeline_status": row.status or "fetched",
                "attempt_count": int(row.attempt_count or 0),
                "last_error": row.last_error or "",
                "sap_ar_invoice_docentry": row.sap_doc_entry or "",
                "sap_ar_invoice_docnum": row.sap_doc_num or "",
                "payload_json": row.payload_json or "",
                "order_json": row.uc_raw_json or "",
                "ar_invoice_tax_expected": float(row.tax_expected or 0),
                "ar_invoice_tax_actual": float(row.tax_actual or 0),
                "ar_invoice_tax_diff": float(row.tax_diff or 0),
                "ar_invoice_unit_price_expected": float(row.unit_price_expected or 0),
                "ar_invoice_unit_price_actual": float(row.unit_price_actual or 0),
                "ar_invoice_unit_price_diff": float(row.unit_price_diff or 0),
                "posting_started_at": row.posting_started_at,
            })
            doc.insert(ignore_permissions=True, ignore_if_duplicate=True)
            migrated += 1
        else:
            # Record exists (legacy data) — just set the new pipeline fields
            frappe.db.set_value("Unicommerce Orders", order_id, {
                "pipeline_status": row.status or "fetched",
                "attempt_count": int(row.attempt_count or 0),
                "last_error": row.last_error or "",
                "sap_ar_invoice_docentry": row.sap_doc_entry or "",
                "sap_ar_invoice_docnum": row.sap_doc_num or "",
                "payload_json": row.payload_json or "",
                "order_json": row.uc_raw_json or "",
                "ar_invoice_tax_expected": float(row.tax_expected or 0),
                "ar_invoice_tax_actual": float(row.tax_actual or 0),
                "ar_invoice_tax_diff": float(row.tax_diff or 0),
                "ar_invoice_unit_price_expected": float(row.unit_price_expected or 0),
                "ar_invoice_unit_price_actual": float(row.unit_price_actual or 0),
                "ar_invoice_unit_price_diff": float(row.unit_price_diff or 0),
            }, update_modified=False)
            updated += 1

        if (migrated + updated) % 200 == 0:
            frappe.db.commit()
            print(f"  Progress: {migrated} inserted, {updated} updated...")

    # Fix credit note staging links: if stored value is a UC Order Staging doc name,
    # update to the actual order code (Unicommerce Orders name = order code).
    frappe.db.sql("""
        UPDATE `tabUC Credit Note Staging` cn
        INNER JOIN `tabUC Order Staging` os ON os.name = cn.uc_order_id
        SET cn.uc_order_id = os.uc_order_id
    """)

    frappe.db.commit()
    print(f"Migration complete: {migrated} inserted, {updated} updated into Unicommerce Orders.")
