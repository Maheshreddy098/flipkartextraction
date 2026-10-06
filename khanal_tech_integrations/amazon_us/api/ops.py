"""Frappe whitelist endpoints for the Amazon US Ops Center page and /amazonus SPA."""
import json
import uuid

import frappe

from khanal_tech_integrations.amazon_us import ORDER_DOCTYPE, enforce_posting_cutoff

# Roles allowed to trigger anything that writes to Amazon staging or SAP.
# Everyone else with site access gets a read-only console.
_POSTER_ROLES = {"Amazon US Manager", "System Manager"}


def _can_post():
    return bool(_POSTER_ROLES & set(frappe.get_roles()))


def _require_poster():
    if not _can_post():
        frappe.throw(
            "View-only access: posting actions need the Amazon US Manager role.",
            frappe.PermissionError,
        )


def _resolve_upload_path(csv_path):
    """
    Resolve a user-supplied CSV path and confirm it's a real file inside the
    site's private/files directory -- rejects any path (including one built
    from '..' traversal) that resolves outside it. Without this, any
    Amazon US Manager could point enqueue_csv_comparison/enqueue_reconciliation
    at an arbitrary bench-readable file (site_config.json, /etc/passwd, ...)
    and get its contents back via the job's log/result cache. Manually
    downloaded MTR CSVs belong under private/files like any other
    operational upload on this site.
    """
    import os

    allowed_dir = os.path.realpath(frappe.get_site_path("private", "files"))
    resolved = os.path.realpath(csv_path)
    if os.path.commonpath([allowed_dir, resolved]) != allowed_dir:
        frappe.throw(
            f"CSV must be placed under the site's private files directory ({allowed_dir}), "
            f"not {csv_path}."
        )
    if not os.path.isfile(resolved):
        frappe.throw(f"File not found: {csv_path}")
    return resolved


@frappe.whitelist()
def get_session_info():
    """Boot info for the SPA: who am I and can I trigger posting actions."""
    return {
        "user": frappe.session.user,
        "full_name": frappe.utils.get_fullname(frappe.session.user),
        "can_post": _can_post(),
    }


@frappe.whitelist()
def get_recon_summary(from_date, to_date):
    """
    Month-reconciliation blockers for the given COALESCE(ship, purchase) window:
    which SKUs keep orders stuck un-mapped, and which SAP items keep failed
    orders failing (stock / inactive), with order counts for each.
    """
    window = "COALESCE(o.actual_ship_date, o.purchase_date) BETWEEN %(frm)s AND %(to)s"
    params = {"frm": f"{from_date} 00:00:00", "to": f"{to_date} 23:59:59"}

    unmapped = frappe.db.sql(
        f"""
        SELECT i.seller_sku, COUNT(DISTINCT o.name) AS orders
        FROM `tabAmazon US Order` o
        JOIN `tabAmazon US Order Item` i ON i.parent = o.name
        WHERE o.stage = 'fetched' AND i.is_mapped = 0 AND {window}
        GROUP BY i.seller_sku ORDER BY orders DESC LIMIT 30
        """,
        params, as_dict=True,
    )

    failed_errors = frappe.db.sql(
        f"""
        SELECT SUBSTRING(COALESCE(o.last_error, ''), 1, 120) AS error,
               COUNT(*) AS orders
        FROM `tabAmazon US Order` o
        WHERE o.stage = 'failed' AND {window}
        GROUP BY 1 ORDER BY orders DESC LIMIT 15
        """,
        params, as_dict=True,
    )

    failed_items = frappe.db.sql(
        f"""
        SELECT i.seller_sku, i.sap_item_code, COUNT(DISTINCT o.name) AS orders
        FROM `tabAmazon US Order` o
        JOIN `tabAmazon US Order Item` i ON i.parent = o.name
        WHERE o.stage = 'failed' AND {window}
        GROUP BY i.seller_sku, i.sap_item_code ORDER BY orders DESC LIMIT 15
        """,
        params, as_dict=True,
    )

    return {
        "unmapped_skus": unmapped,
        "failed_errors": failed_errors,
        "failed_items": failed_items,
    }


@frappe.whitelist()
def enqueue_fetch(from_date, to_date):
    """Enqueue SP-API order fetch + staging job. Returns {job_id}."""
    _require_poster()
    job_id = str(uuid.uuid4())
    frappe.cache().set_value(
        f"amz_us_fetch_{job_id}",
        json.dumps({"status": "queued"}),
        expires_in_sec=3600,
    )
    frappe.enqueue(
        "khanal_tech_integrations.amazon_us.workers.fetch.fetch_and_stage",
        queue="long",
        timeout=7200,
        from_date=from_date,
        to_date=to_date,
        progress_id=job_id,
    )
    return {"job_id": job_id}


@frappe.whitelist()
def get_fetch_result(job_id):
    """Poll fetch job progress/result from cache."""
    raw = frappe.cache().get_value(f"amz_us_fetch_{job_id}")
    if not raw:
        return {"status": "not_found"}
    return json.loads(raw)


@frappe.whitelist()
def enqueue_fetch_via_report(from_date, to_date, lookback_days=30):
    """
    Enqueue bulk order fetch via SP-API Reports API (one flat-file report per
    <=30-day chunk, item-level rows inline) instead of the slow Orders API +
    per-order OrderItems loop. Same staging/ready rules as enqueue_fetch.
    lookback_days extends the window backwards to catch orders purchased
    before from_date but posted (charged/shipped) inside the range -- the MTR
    report is posted-date indexed, so without this a month's fetch misses its
    trailing-purchase orders. Returns {job_id}.
    """
    _require_poster()
    job_id = str(uuid.uuid4())
    frappe.cache().set_value(
        f"amz_us_report_fetch_{job_id}",
        json.dumps({"status": "queued"}),
        expires_in_sec=3600,
    )
    frappe.enqueue(
        "khanal_tech_integrations.amazon_us.workers.order_report.fetch_and_stage_via_report",
        queue="long",
        timeout=7200,
        from_date=from_date,
        to_date=to_date,
        lookback_days=int(lookback_days),
        progress_id=job_id,
    )
    return {"job_id": job_id}


@frappe.whitelist()
def get_report_fetch_result(job_id):
    """Poll bulk report-fetch job progress/result from cache."""
    raw = frappe.cache().get_value(f"amz_us_report_fetch_{job_id}")
    if not raw:
        return {"status": "not_found"}
    return json.loads(raw)


@frappe.whitelist()
def enqueue_post(from_date, to_date):
    """Enqueue SAP posting job for all ready orders in date range. Returns {job_id}."""
    _require_poster()
    enforce_posting_cutoff(from_date)
    job_id = str(uuid.uuid4())
    frappe.cache().set_value(
        f"amz_us_post_{job_id}",
        json.dumps({"status": "queued"}),
        expires_in_sec=3600,
    )
    frappe.enqueue(
        "khanal_tech_integrations.amazon_us.workers.invoice.post_ready_orders",
        queue="long",
        timeout=7200,
        from_date=from_date,
        to_date=to_date,
        progress_id=job_id,
    )
    return {"job_id": job_id}


@frappe.whitelist()
def get_post_result(job_id):
    """Poll post job progress/result from cache."""
    raw = frappe.cache().get_value(f"amz_us_post_{job_id}")
    if not raw:
        return {"status": "not_found"}
    return json.loads(raw)


@frappe.whitelist()
def get_stats(from_date, to_date):
    """
    Return order counts by stage for the given date range.

    Windows on COALESCE(actual_ship_date, purchase_date): ship date is what
    decides the MTR month (and what posting selects by), while orders not yet
    shipped/settled stay visible under their purchase month instead of
    disappearing until the FBA shipments sync fills their ship date.
    """
    rows = frappe.db.sql(
        """
        SELECT stage, COUNT(*) AS cnt
        FROM `tabAmazon US Order`
        WHERE COALESCE(actual_ship_date, purchase_date) BETWEEN %s AND %s
        GROUP BY stage
        """,
        (f"{from_date} 00:00:00", f"{to_date} 23:59:59"),
        as_dict=True,
    )
    counts = {s: 0 for s in ("fetched", "ready", "posting", "posted", "failed", "dead")}
    for r in rows:
        counts[r.stage] = r.cnt

    shipped = frappe.db.sql(
        """
        SELECT COUNT(*)
        FROM `tabAmazon US Order`
        WHERE order_status = 'Shipped'
        AND COALESCE(actual_ship_date, purchase_date) BETWEEN %s AND %s
        """,
        (f"{from_date} 00:00:00", f"{to_date} 23:59:59"),
    )[0][0]

    return {"total": sum(counts.values()), "shipped": shipped, **counts}


@frappe.whitelist()
def get_orders(from_date, to_date, stage=None, page=1, page_size=50, search=None):
    """
    Return paginated order list from the staging doctype.
    Same COALESCE(actual_ship_date, purchase_date) window as get_stats, so the
    list, the tiles, and what a posting run would select all agree.
    """
    page = int(page)
    page_size = int(page_size)

    conditions = "COALESCE(o.actual_ship_date, o.purchase_date) BETWEEN %(frm)s AND %(to)s"
    params = {"frm": f"{from_date} 00:00:00", "to": f"{to_date} 23:59:59"}
    if stage and stage != "all":
        conditions += " AND o.stage = %(stage)s"
        params["stage"] = stage

    # search matches order id, buyer name, or any line item's SKU -- needs a
    # join + DISTINCT since one order can have several matching item rows.
    join = ""
    if search and search.strip():
        params["search"] = f"%{search.strip()}%"
        join = "LEFT JOIN `tabAmazon US Order Item` si ON si.parent = o.name"
        conditions += (
            " AND (o.amazon_order_id LIKE %(search)s"
            " OR o.buyer_name LIKE %(search)s"
            " OR si.seller_sku LIKE %(search)s)"
        )

    orders = frappe.db.sql(
        f"""
        SELECT DISTINCT o.name, o.amazon_order_id, o.order_status, o.stage,
               o.purchase_date, o.actual_ship_date, o.sap_doc_entry, o.sap_doc_num,
               o.posted_at, o.last_error, o.cn_doc_num, o.refunded_at
        FROM `tabAmazon US Order` o
        {join}
        WHERE {conditions}
        ORDER BY COALESCE(o.actual_ship_date, o.purchase_date) DESC
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        {**params, "limit": page_size, "offset": (page - 1) * page_size},
        as_dict=True,
    )

    for o in orders:
        o["item_count"] = frappe.db.count("Amazon US Order Item", {"parent": o["name"]})

    total = frappe.db.sql(
        f"SELECT COUNT(DISTINCT o.name) FROM `tabAmazon US Order` o {join} WHERE {conditions}", params
    )[0][0]

    return {
        "orders": orders,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@frappe.whitelist()
def get_order_detail(order_name):
    """
    Full detail for one order: every order field, all line items, and which
    settlement period(s) paid it out (reverse lookup on Settlement Line).
    Local DB only -- no SAP call, safe to load on every drawer open.
    """
    if not frappe.db.exists(ORDER_DOCTYPE, order_name):
        return {"status": "error", "message": f"Order not found: {order_name}"}

    order = frappe.db.get_value(ORDER_DOCTYPE, order_name, "*", as_dict=True)
    items = frappe.get_all(
        "Amazon US Order Item",
        filters={"parent": order_name},
        fields=[
            "seller_sku", "sap_item_code", "is_mapped", "asin", "title",
            "quantity", "quantity_ordered", "quantity_shipped",
            "item_price_amount", "item_tax_amount", "shipping_price_amount",
            "shipping_tax_amount", "shipping_discount_amount",
            "promotion_discount_amount", "cod_fee", "unit_price",
        ],
    )
    settlement_lines = frappe.db.sql(
        """
        SELECT sl.parent AS settlement_name, s.settlement_id, s.deposit_date,
               SUM(sl.amount) AS principal_amount
        FROM `tabAmazon US Settlement Line` sl
        JOIN `tabAmazon US Settlement` s ON s.name = sl.parent
        WHERE sl.order_id = %s AND sl.transaction_type = 'Order' AND sl.amount_description = 'Principal'
        GROUP BY sl.parent, s.settlement_id, s.deposit_date
        ORDER BY s.deposit_date DESC
        """,
        order_name, as_dict=True,
    )

    return {
        "status": "ok",
        "order": order,
        "items": items,
        "settlement_lines": settlement_lines,
    }


@frappe.whitelist()
def get_credit_note_detail(order_name):
    """
    Live SAP query for a credit note's reversal line detail -- never
    persisted locally (only the invoice's payload_json is stored), so this
    is the only source. Called on-demand, not bulk-loaded with the order.
    """
    cn_doc_entry = frappe.db.get_value(ORDER_DOCTYPE, order_name, "cn_doc_entry")
    if not cn_doc_entry:
        return {"status": "error", "message": "No credit note on this order"}

    from khanal_tech_integrations.amazon_us.client.sap import get_credit_note_lines
    try:
        lines = get_credit_note_lines(cn_doc_entry)
    except Exception as e:
        return {"status": "error", "message": f"SAP lookup failed: {e}"}

    return {"status": "ok", "lines": lines}


@frappe.whitelist()
def export_orders_csv(from_date, to_date, stage=None, search=None):
    """Stream a CSV of get_orders' full matching set (not just one page)."""
    import csv
    import io

    conditions = "COALESCE(o.actual_ship_date, o.purchase_date) BETWEEN %(frm)s AND %(to)s"
    params = {"frm": f"{from_date} 00:00:00", "to": f"{to_date} 23:59:59"}
    if stage and stage != "all":
        conditions += " AND o.stage = %(stage)s"
        params["stage"] = stage

    join = ""
    if search and search.strip():
        params["search"] = f"%{search.strip()}%"
        join = "LEFT JOIN `tabAmazon US Order Item` si ON si.parent = o.name"
        conditions += (
            " AND (o.amazon_order_id LIKE %(search)s"
            " OR o.buyer_name LIKE %(search)s"
            " OR si.seller_sku LIKE %(search)s)"
        )

    columns = [
        "amazon_order_id", "order_status", "stage", "purchase_date", "actual_ship_date",
        "buyer_name", "order_total_amount", "order_total_currency",
        "sap_doc_num", "posted_at", "cn_doc_num", "refunded_at", "last_error",
    ]
    rows = frappe.db.sql(
        f"""
        SELECT DISTINCT o.{', o.'.join(columns)}
        FROM `tabAmazon US Order` o
        {join}
        WHERE {conditions}
        ORDER BY COALESCE(o.actual_ship_date, o.purchase_date) DESC
        """,
        params, as_dict=True,
    )

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)

    frappe.response.filecontent = buf.getvalue()
    frappe.response.type = "download"
    frappe.response.filename = f"amazon_us_orders_{from_date}_to_{to_date}.csv"


@frappe.whitelist()
def enqueue_fba_shipments_sync(from_date, to_date):
    """Enqueue FBA shipments report sync for the given date range. Returns {job_id}."""
    _require_poster()
    job_id = str(uuid.uuid4())
    frappe.cache().set_value(
        f"amz_us_fba_shipments_{job_id}",
        json.dumps({"status": "queued"}),
        expires_in_sec=3600,
    )
    frappe.enqueue(
        "khanal_tech_integrations.amazon_us.workers.fba_shipments.sync_fba_shipments_range",
        queue="long",
        timeout=1200,
        from_date=from_date,
        to_date=to_date,
        progress_id=job_id,
    )
    return {"job_id": job_id}


@frappe.whitelist()
def get_fba_shipments_result(job_id):
    """Poll FBA shipments sync progress/result from cache."""
    raw = frappe.cache().get_value(f"amz_us_fba_shipments_{job_id}")
    if not raw:
        return {"status": "not_found"}
    return json.loads(raw)


@frappe.whitelist()
def post_single(amazon_order_id):
    """Synchronously post one order to SAP. Returns result dict."""
    _require_poster()
    from khanal_tech_integrations.amazon_us.workers.invoice import post_single_order
    return post_single_order(amazon_order_id)


@frappe.whitelist()
def enqueue_settlement_sync():
    """Enqueue settlement report sync. Returns {job_id}."""
    _require_poster()
    job_id = str(uuid.uuid4())
    frappe.cache().set_value(
        f"amz_us_settlement_{job_id}",
        json.dumps({"status": "queued"}),
        expires_in_sec=3600,
    )
    frappe.enqueue(
        "khanal_tech_integrations.amazon_us.workers.settlement.sync_settlement_reports",
        queue="long",
        timeout=1800,
        progress_id=job_id,
    )
    return {"job_id": job_id}


@frappe.whitelist()
def get_settlement_result(job_id):
    """Poll settlement sync progress/result from cache."""
    raw = frappe.cache().get_value(f"amz_us_settlement_{job_id}")
    if not raw:
        return {"status": "not_found"}
    return json.loads(raw)


@frappe.whitelist()
def get_settlement_reconciliation(settlement_id):
    """Return order-level reconciliation for a settlement period."""
    from khanal_tech_integrations.amazon_us.workers.settlement import get_settlement_reconciliation as _recon
    return _recon(settlement_id)


@frappe.whitelist()
def get_settlements(page=1, page_size=20):
    """Return paginated list of stored settlement periods."""
    page = int(page)
    page_size = int(page_size)
    settlements = frappe.get_all(
        "Amazon US Settlement",
        fields=[
            "name", "settlement_id", "status", "currency",
            "settlement_start_date", "settlement_end_date", "deposit_date",
            "total_amount", "gross_revenue", "total_fees",
            "total_refunds", "total_reimbursements",
        ],
        order_by="deposit_date desc",
        limit=page_size,
        start=(page - 1) * page_size,
    )
    return {
        "settlements": settlements,
        "total": frappe.db.count("Amazon US Settlement"),
        "page": page,
        "page_size": page_size,
    }


@frappe.whitelist()
def enqueue_reprocess_all_settlements():
    """Enqueue reprocess of all stored settlements (use after parser fix). Returns {job_id}."""
    _require_poster()
    job_id = str(uuid.uuid4())
    frappe.cache().set_value(
        f"amz_us_settlement_{job_id}",
        json.dumps({"status": "queued"}),
        expires_in_sec=3600,
    )
    frappe.enqueue(
        "khanal_tech_integrations.amazon_us.workers.settlement.reprocess_all_settlements",
        queue="long",
        timeout=3600,
        progress_id=job_id,
    )
    return {"job_id": job_id}


@frappe.whitelist()
def enqueue_bulk_retry(from_date, to_date):
    """Reset all failed orders in date range to ready and re-post them. Returns {job_id}."""
    _require_poster()
    enforce_posting_cutoff(from_date)
    job_id = str(uuid.uuid4())
    frappe.cache().set_value(
        f"amz_us_post_{job_id}",
        json.dumps({"status": "queued"}),
        expires_in_sec=3600,
    )
    frappe.enqueue(
        "khanal_tech_integrations.amazon_us.workers.invoice.bulk_retry_failed_orders",
        queue="long",
        timeout=7200,
        from_date=from_date,
        to_date=to_date,
        progress_id=job_id,
    )
    return {"job_id": job_id}


@frappe.whitelist()
def retry_order(amazon_order_id):
    """Reset a failed order to ready and re-attempt SAP post."""
    _require_poster()
    if not frappe.db.exists(ORDER_DOCTYPE, amazon_order_id):
        return {"status": "error", "message": "Order not found"}
    current_stage = frappe.db.get_value(ORDER_DOCTYPE, amazon_order_id, "stage")
    if current_stage != "failed":
        return {"status": "error", "message": f"Order stage is '{current_stage}', not failed"}
    frappe.db.set_value(ORDER_DOCTYPE, amazon_order_id, "stage", "ready", update_modified=False)
    frappe.db.commit()
    from khanal_tech_integrations.amazon_us.workers.invoice import post_single_order
    return post_single_order(amazon_order_id)


@frappe.whitelist()
def enqueue_csv_comparison(csv_path):
    """
    Enqueue a read-only comparison of a manually downloaded Custom Unified
    Transaction CSV against SAP. NEVER posts -- no dry_run parameter exists
    on purpose. The CSV report and the live Finances API do not reconcile
    1:1 (documented Amazon platform limitation, see credit_note.py), so the
    CSV is a human cross-check tool only; post_refunds_from_finances_api is
    the single source that actually posts. Returns {job_id}.
    """
    _require_poster()
    csv_path = _resolve_upload_path(csv_path)

    job_id = str(uuid.uuid4())
    frappe.cache().set_value(
        f"amz_us_creditnote_{job_id}",
        json.dumps({"status": "queued"}),
        expires_in_sec=3600,
    )
    frappe.enqueue(
        "khanal_tech_integrations.amazon_us.workers.credit_note.compare_csv_against_sap",
        queue="long",
        timeout=3600,
        csv_path=csv_path,
        progress_id=job_id,
    )
    return {"job_id": job_id}


@frappe.whitelist()
def enqueue_credit_notes_live(from_date, to_date, dry_run=1):
    """
    Enqueue AR Credit Note posting sourced live from SP-API Finances API for
    [from_date, to_date] (YYYY-MM-DD Pacific). dry_run defaults to 1. Returns {job_id}.
    """
    _require_poster()
    enforce_posting_cutoff(from_date)
    dry_run = bool(int(dry_run))
    job_id = str(uuid.uuid4())
    frappe.cache().set_value(
        f"amz_us_creditnote_{job_id}",
        json.dumps({"status": "queued"}),
        expires_in_sec=3600,
    )
    frappe.enqueue(
        "khanal_tech_integrations.amazon_us.workers.credit_note.post_refunds_from_finances_api",
        queue="long",
        timeout=3600,
        from_date=from_date,
        to_date=to_date,
        dry_run=dry_run,
        progress_id=job_id,
    )
    return {"job_id": job_id}


@frappe.whitelist()
def get_credit_note_result(job_id):
    """Poll credit note job progress/result from cache."""
    raw = frappe.cache().get_value(f"amz_us_creditnote_{job_id}")
    if not raw:
        return {"status": "not_found"}
    return json.loads(raw)


@frappe.whitelist()
def test_sap_connection():
    """Test SAP B1 login and HANA connectivity. Returns status dict."""
    results = {}

    # SAP B1 login
    try:
        from khanal_tech_integrations.amazon_us.client.sap import _login
        from khanal_tech_integrations.amazon_us import _SAP_SESSION_CACHE_KEY
        frappe.cache().delete_value(_SAP_SESSION_CACHE_KEY)
        session, b1_url = _login()
        doc = frappe.get_doc("INC SAP Settings")
        results["sap_b1"] = {"ok": True, "url": b1_url, "db": doc.companydb}
    except Exception as e:
        results["sap_b1"] = {"ok": False, "error": str(e)}

    # HANA connectivity
    try:
        from khanal_tech_integrations.amazon_us.client.hana import _connect, _close, _get_schema
        schema = _get_schema()
        conn, cursor = _connect()
        if conn:
            cursor.execute(f'SELECT COUNT(*) FROM "{schema}"."OBTQ"')
            count = cursor.fetchone()[0]
            _close(conn, cursor)
            results["hana"] = {"ok": True, "schema": schema, "obtq_rows": count}
        else:
            results["hana"] = {"ok": False, "error": "Connection failed — check error log"}
    except Exception as e:
        results["hana"] = {"ok": False, "error": str(e)}

    return results


@frappe.whitelist()
def enqueue_shipping_supplements(from_date, to_date, dry_run=1):
    """
    Enqueue the one-off shipping-supplement repair (CNs posted before the
    shipping fix get a service-only supplement CN). dry_run defaults to 1.
    Returns {job_id}.
    """
    _require_poster()
    enforce_posting_cutoff(from_date)
    dry_run = bool(int(dry_run))
    job_id = str(uuid.uuid4())
    frappe.cache().set_value(
        f"amz_us_creditnote_{job_id}",
        json.dumps({"status": "queued"}),
        expires_in_sec=3600,
    )
    frappe.enqueue(
        "khanal_tech_integrations.amazon_us.workers.credit_note.post_shipping_supplements",
        queue="long",
        timeout=3600,
        from_date=from_date,
        to_date=to_date,
        dry_run=dry_run,
        progress_id=job_id,
    )
    return {"job_id": job_id}


@frappe.whitelist()
def get_kpis(from_date, to_date):
    """
    Management/finance KPIs for the window (ship-date = MTR month):
    posted revenue, AOV, refund rate, daily revenue series, and the
    gross→fees→refunds→net payout bridge from settlements overlapping the
    window. Revenue uses the staged order totals of POSTED orders — the same
    amounts the SAP invoices carry.
    """
    window = "COALESCE(o.actual_ship_date, o.purchase_date) BETWEEN %(frm)s AND %(to)s"
    params = {"frm": f"{from_date} 00:00:00", "to": f"{to_date} 23:59:59"}

    head = frappe.db.sql(
        f"""
        SELECT COUNT(*) AS orders,
               COALESCE(SUM(o.order_total_amount), 0) AS revenue,
               SUM(o.cn_doc_num IS NOT NULL AND o.cn_doc_num != '') AS refunded_orders
        FROM `tabAmazon US Order` o
        WHERE o.stage = 'posted' AND {window}
        """,
        params, as_dict=True,
    )[0]

    daily = frappe.db.sql(
        f"""
        SELECT DATE(COALESCE(o.actual_ship_date, o.purchase_date)) AS day,
               COUNT(*) AS orders,
               COALESCE(SUM(o.order_total_amount), 0) AS revenue
        FROM `tabAmazon US Order` o
        WHERE o.stage = 'posted' AND {window}
        GROUP BY 1 ORDER BY 1
        """,
        params, as_dict=True,
    )

    settlements = frappe.db.sql(
        """
        SELECT COALESCE(SUM(gross_revenue), 0) AS gross,
               COALESCE(SUM(total_fees), 0) AS fees,
               COALESCE(SUM(total_refunds), 0) AS refunds,
               COALESCE(SUM(total_reimbursements), 0) AS reimbursements,
               COALESCE(SUM(total_amount), 0) AS net_payout,
               COUNT(*) AS periods
        FROM `tabAmazon US Settlement`
        WHERE settlement_end_date >= %(frm)s AND settlement_start_date <= %(to)s
        """,
        params, as_dict=True,
    )[0]

    orders = int(head.orders or 0)
    revenue = float(head.revenue or 0)
    refunded = int(head.refunded_orders or 0)
    return {
        "orders_posted": orders,
        "revenue_posted": round(revenue, 2),
        "aov": round(revenue / orders, 2) if orders else 0,
        "refunded_orders": refunded,
        "refund_rate": round(100.0 * refunded / orders, 2) if orders else 0,
        "daily": [{"day": str(d.day), "orders": int(d.orders), "revenue": round(float(d.revenue), 2)} for d in daily],
        "settlements": {k: (float(v) if k != "periods" else int(v)) for k, v in settlements.items()},
    }


@frappe.whitelist()
def get_health():
    """
    Tech health strip: how fresh each pipeline stage is and what's stuck.
    All timestamps are the site timezone strings the workers wrote.
    """
    row = frappe.db.sql(
        """
        SELECT MAX(creation) AS last_staged,
               MAX(posted_at) AS last_posted,
               MAX(refunded_at) AS last_refunded,
               SUM(stage = 'posting' AND posting_started_at < (NOW() - INTERVAL 15 MINUTE)) AS stuck_posting,
               MIN(CASE WHEN stage = 'failed' THEN modified END) AS oldest_failed
        FROM `tabAmazon US Order`
        """,
        as_dict=True,
    )[0]

    ship_cov = frappe.db.sql(
        """
        SELECT SUM(actual_ship_date IS NULL) AS missing, COUNT(*) AS total
        FROM `tabAmazon US Order` WHERE stage = 'posted'
        """,
        as_dict=True,
    )[0]

    from khanal_tech_integrations.amazon_us import _SAP_SESSION_CACHE_KEY
    sap_session = bool(frappe.cache().get_value(_SAP_SESSION_CACHE_KEY))

    total_posted = int(ship_cov.total or 0)
    missing = int(ship_cov.missing or 0)
    return {
        "last_staged": str(row.last_staged) if row.last_staged else None,
        "last_posted": str(row.last_posted) if row.last_posted else None,
        "last_refunded": str(row.last_refunded) if row.last_refunded else None,
        "stuck_posting": int(row.stuck_posting or 0),
        "oldest_failed": str(row.oldest_failed) if row.oldest_failed else None,
        "ship_date_coverage": round(100.0 * (total_posted - missing) / total_posted, 1) if total_posted else 100.0,
        "sap_session_cached": sap_session,
    }


@frappe.whitelist()
def enqueue_reset_for_repost(from_date, to_date, dry_run=1):
    """
    Reset posted orders in [from_date, to_date] (ship date) back to ready so
    they can be re-posted -- e.g. after repointing INC SAP Settings at a
    different company DB. dry_run defaults to 1. Returns {job_id}.
    """
    _require_poster()
    enforce_posting_cutoff(from_date)
    dry_run = bool(int(dry_run))
    job_id = str(uuid.uuid4())
    frappe.cache().set_value(
        f"amz_us_post_{job_id}",
        json.dumps({"status": "queued"}),
        expires_in_sec=3600,
    )
    frappe.enqueue(
        "khanal_tech_integrations.amazon_us.workers.invoice.reset_for_repost",
        queue="long",
        timeout=1800,
        from_date=from_date,
        to_date=to_date,
        dry_run=dry_run,
        progress_id=job_id,
    )
    return {"job_id": job_id}


@frappe.whitelist()
def enqueue_reconciliation(csv_path, from_date, to_date):
    """
    Enqueue the MTR-vs-SAP reconciliation workbook build for [from_date, to_date].
    Returns {job_id}; poll get_reconciliation_result for the download URL.
    """
    _require_poster()
    csv_path = _resolve_upload_path(csv_path)

    job_id = str(uuid.uuid4())
    frappe.cache().set_value(
        f"amz_us_recon_{job_id}",
        json.dumps({"status": "queued"}),
        expires_in_sec=3600,
    )
    frappe.enqueue(
        "khanal_tech_integrations.amazon_us.workers.reconciliation.build_reconciliation_file",
        queue="long",
        timeout=3600,
        csv_path=csv_path,
        from_date=from_date,
        to_date=to_date,
        progress_id=job_id,
    )
    return {"job_id": job_id}


@frappe.whitelist()
def get_reconciliation_result(job_id):
    """Poll reconciliation job progress/result from cache."""
    raw = frappe.cache().get_value(f"amz_us_recon_{job_id}")
    if not raw:
        return {"status": "not_found"}
    return json.loads(raw)


@frappe.whitelist()
def enqueue_inventory_reconciliation():
    """
    Enqueue an Amazon FBA vs SAP inventory comparison for every mapped SKU.
    Read-only (never posts), but gated like every other enqueue_* endpoint
    since it spends live Amazon API quota. Returns {job_id}.
    """
    _require_poster()
    job_id = str(uuid.uuid4())
    frappe.cache().set_value(
        f"amz_us_inventory_recon_{job_id}",
        json.dumps({"status": "queued"}),
        expires_in_sec=3600,
    )
    frappe.enqueue(
        "khanal_tech_integrations.amazon_us.workers.inventory_reconciliation.build_inventory_reconciliation",
        queue="long",
        timeout=1200,
        progress_id=job_id,
    )
    return {"job_id": job_id}


@frappe.whitelist()
def get_inventory_reconciliation_result(job_id):
    """Poll inventory reconciliation job progress/result from cache."""
    raw = frappe.cache().get_value(f"amz_us_inventory_recon_{job_id}")
    if not raw:
        return {"status": "not_found"}
    return json.loads(raw)
