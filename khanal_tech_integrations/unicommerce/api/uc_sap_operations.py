import json

import frappe
from datetime import datetime
from frappe.utils import add_days, get_datetime, now_datetime, today

from ..validators import get_gaps, refresh_recon
from ..workers.fetch import fetch_orders, fetch_returns
from ..workers.invoice import post_invoices
from ..workers.credit_note import post_credit_notes
from ..validators.pre_check import comprehensive_pre_posting_validation

# Defaults for your “March 1-10, 2026 / Flipkart” run
LEGACY_CHANNEL_DEFAULT = "FLIPKART"
LEGACY_START_DDMMYYYY_DEFAULT = "01-03-2026"
LEGACY_END_DDMMYYYY_DEFAULT = "10-03-2026"


def _ddmmyyyy_to_iso(date_str: str, *, is_end: bool) -> str:
	dt = datetime.strptime(date_str, "%d-%m-%Y")
	if is_end:
		dt = dt.replace(hour=23, minute=59, second=59)
	else:
		dt = dt.replace(hour=0, minute=0, second=0)
	return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@frappe.whitelist()
def get_dashboard_data():
	# Legacy dashboard counters (Unicommerce Orders doctype).
	orders_complete = frappe.db.count(
		"Unicommerce Orders",
		filters={"status": "COMPLETE"},
	)

	orders_posted = frappe.db.count(
		"Unicommerce Orders",
		filters={"status": "COMPLETE", "sap_ar_invoice_docentry": ["!=", ""],},
	)

	# For kiosk donut/status UI we keep the same keys, but legacy doctype doesn't have the staging sub-statuses.
	order_counts = {
		"fetched": orders_complete,
		"ready": max(orders_complete - orders_posted, 0),
		"posting": 0,
		"verify": 0,
		"posted": orders_posted,
		"failed": 0,
		"dead": 0,
		"batch_hold": 0,
	}

	credit_pending_row = frappe.db.sql(
		"""
		SELECT COUNT(*) AS cnt
		FROM `tabUnicommerce Orders`
		WHERE status = 'COMPLETE'
		  AND return_code IS NOT NULL
		  AND return_code != ''
		  AND (sap_ar_creditnote_docentry IS NULL OR sap_ar_creditnote_docentry = '')
		""",
		as_dict=True,
	)
	credit_pending = int((credit_pending_row[0] or {}).get("cnt") or 0)

	credit_posted_row = frappe.db.sql(
		"""
		SELECT COUNT(*) AS cnt
		FROM `tabUnicommerce Orders`
		WHERE status = 'COMPLETE'
		  AND return_code IS NOT NULL
		  AND return_code != ''
		  AND (sap_ar_creditnote_docentry IS NOT NULL AND sap_ar_creditnote_docentry != '')
		""",
		as_dict=True,
	)
	credit_posted = int((credit_posted_row[0] or {}).get("cnt") or 0)
	credit_counts = {
		"pending": credit_pending,
		"posting": 0,
		"posted": credit_posted,
		"failed": 0,
		"dead": 0,
	}

	posted_today = frappe.db.count(
		"Unicommerce Orders",
		filters={"status": "COMPLETE", "sap_ar_invoice_docentry": ["!=", ""], "modified": [">=", add_days(today(), 0)]},
	)
	failed_today = 0

	settings = frappe.get_single("Unicommerce Settings")
	last_sync = "never"
	try:
		cursors = json.loads(settings.last_fetched_at_json or "{}")
		last_sync = cursors.get("orders") or cursors.get("returns") or "never"
	except Exception:
		pass

	volume_7d = []
	for i in range(6, -1, -1):
		day = add_days(today(), -i)
		next_day = add_days(day, 1)
		fetched = frappe.db.count(
			"Unicommerce Orders",
			filters={"status": "COMPLETE", "displayorderdatetime": ["between", [day, next_day]]},
		)
		posted = frappe.db.count(
			"Unicommerce Orders",
			filters={"status": "COMPLETE", "sap_ar_invoice_docentry": ["!=", ""], "displayorderdatetime": ["between", [day, next_day]]},
		)
		failed = 0
		volume_7d.append(
			{"day": get_datetime(day).strftime("%a"), "fetched": fetched, "posted": posted, "failed": failed}
		)

	recent = frappe.db.sql(
		"""
		SELECT
			o.uniware_id AS uc_order_id,
			o.status AS status,
			o.modified AS modified,
			o.sap_ar_invoice_docnum AS sap_doc_num,
			COALESCE(o.ar_invoice_reconciliation_status, '') AS last_error
		FROM `tabUnicommerce Orders` o
		ORDER BY o.modified desc
		LIMIT %(limit)s
		""",
		{"limit": 8},
		as_dict=True,
	)
	gaps = get_gaps(min_tax_diff=1.0, min_unit_price_diff=1.0, limit=8)
	return {
		"kpis": {
			"orders_synced": order_counts["posted"],
			"orders_ready": order_counts["ready"],
			"credit_notes_posted": credit_counts["posted"],
			"returns_pending": credit_counts["pending"],
			"posted_today": posted_today,
			"failed_today": failed_today,
			"reconciliation_gaps": len(gaps),
		},
		"orders": order_counts,
		"credit_notes": credit_counts,
		"last_sync": last_sync,
		"volume_7d": volume_7d,
		"recent_log": recent,
		"reconciliation_gaps": gaps,
		"system_health": {
			"unicommerce": "Live",
			"sap": "Live",
			"frappe_queue_pending": _pending_jobs_count(),
		},
	}


def _pending_jobs_count() -> int:
	try:
		if not frappe.db.table_exists("RQ Job"):
			return 0
		rows = frappe.db.sql(
			"""SELECT COUNT(*) AS cnt FROM `tabRQ Job` WHERE status IN ('queued', 'started')""",
			as_dict=True,
		)
		return int((rows[0] or {}).get("cnt") or 0)
	except Exception:
		return 0


@frappe.whitelist()
def pull_orders(max_orders=100):
	return pull_orders_legacy(
		max_orders=max_orders,
		channel_name=LEGACY_CHANNEL_DEFAULT,
		start_date=LEGACY_START_DDMMYYYY_DEFAULT,
		end_date=LEGACY_END_DDMMYYYY_DEFAULT,
	)


@frappe.whitelist()
def pull_orders_legacy(
	max_orders=100,
	channel_name=LEGACY_CHANNEL_DEFAULT,
	start_date=LEGACY_START_DDMMYYYY_DEFAULT,
	end_date=LEGACY_END_DDMMYYYY_DEFAULT,
):
	"""
	Compatibility wrapper that now uses the new fetch worker.
	"""
	from_dt = datetime.strptime(start_date, "%d-%m-%Y").strftime("%Y-%m-%d")
	to_dt = datetime.strptime(end_date, "%d-%m-%Y").strftime("%Y-%m-%d")
	return fetch_orders(max_orders=int(max_orders), from_date=from_dt, to_date=to_dt)


@frappe.whitelist()
def promote_to_ready(limit=50):
	# Legacy pipeline doesn't have fetched/ready queues.
	return {"moved_to_ready": 0, "limit": int(limit), "note": "No-op for legacy pipeline"}


@frappe.whitelist()
def process_orders(limit=50):
	return process_orders_legacy(
		limit=limit,
		channel_name=LEGACY_CHANNEL_DEFAULT,
		start_date=LEGACY_START_DDMMYYYY_DEFAULT,
		end_date=LEGACY_END_DDMMYYYY_DEFAULT,
	)


@frappe.whitelist()
def process_orders_legacy(
	limit=50,
	channel_name=LEGACY_CHANNEL_DEFAULT,
	start_date=LEGACY_START_DDMMYYYY_DEFAULT,
	end_date=LEGACY_END_DDMMYYYY_DEFAULT,
):
	# `create_channel_invoices` posts all unposted orders in the date range.
	# We cap the number of orders fetched during `pull_orders` via max_orders.
	# The `limit` arg is kept for UI compatibility.
	if int(limit) <= 0:
		return {"status": "skipped", "message": "limit <= 0"}
	validation = comprehensive_pre_posting_validation(
		channel_name=channel_name,
		start_date=start_date,
		end_date=end_date,
		order_list=None,
	)
	if not validation.get("is_valid", False):
		return {
			"status": "validation_failed",
			"error": "Pre-posting validation failed; cannot create AR invoices.",
			"validation_result": validation,
		}
	return post_invoices(limit=int(limit))


@frappe.whitelist()
def retry_batch_holds(limit=500):
	# Legacy shim: the active pipeline DOES maintain a `batch_hold` queue
	# (see `Unicommerce Orders.pipeline_status`). The emergency manual-release
	# entry-point is `khanal_tech_integrations.unicommerce.workers.fetch.retry_batch_holds`.
	# This legacy endpoint stays as a no-op so any older clients calling it
	# keep working without releasing holds unexpectedly.
	return {
		"moved_to_ready": 0,
		"limit": int(limit),
		"note": (
			"No-op. Use unicommerce.workers.fetch.retry_batch_holds "
			"(Ops Center → Batch Validation → Release batch holds) to manually "
			"release holds, or rely on auto-recovery inside post_invoices."
		),
	}


@frappe.whitelist()
def pull_returns(max_returns=100):
	return pull_returns_legacy(
		max_returns=max_returns,
		channel_name=LEGACY_CHANNEL_DEFAULT,
		start_date=LEGACY_START_DDMMYYYY_DEFAULT,
		end_date=LEGACY_END_DDMMYYYY_DEFAULT,
	)


@frappe.whitelist()
def pull_returns_legacy(
	max_returns=100,
	channel_name=LEGACY_CHANNEL_DEFAULT,
	start_date=LEGACY_START_DDMMYYYY_DEFAULT,
	end_date=LEGACY_END_DDMMYYYY_DEFAULT,
):
	"""
	Compatibility wrapper that now uses the new returns worker.
	"""
	from_dt = datetime.strptime(start_date, "%d-%m-%Y").strftime("%Y-%m-%d")
	to_dt = datetime.strptime(end_date, "%d-%m-%Y").strftime("%Y-%m-%d")
	return fetch_returns(max_returns=int(max_returns), from_date=from_dt, to_date=to_dt)


@frappe.whitelist()
def process_credit_notes(limit=50):
	return process_credit_notes_legacy(
		limit=limit,
		channel_name=LEGACY_CHANNEL_DEFAULT,
		start_date=LEGACY_START_DDMMYYYY_DEFAULT,
		end_date=LEGACY_END_DDMMYYYY_DEFAULT,
	)


@frappe.whitelist()
def process_credit_notes_legacy(
	limit=50,
	channel_name=LEGACY_CHANNEL_DEFAULT,
	start_date=LEGACY_START_DDMMYYYY_DEFAULT,
	end_date=LEGACY_END_DDMMYYYY_DEFAULT,
):
	if int(limit) <= 0:
		return {"status": "skipped", "message": "limit <= 0"}
	return post_credit_notes(limit=int(limit))


@frappe.whitelist()
def refresh_reconciliation(limit=200):
	# Legacy reconciliation on Unicommerce Orders (includes credit notes too).
	return refresh_recon(limit=int(limit))


@frappe.whitelist()
def verify_one_invoice_per_order_api(limit=10000):
	"""
	Kiosk-friendly wrapper using current legacy defaults.
	"""
	return verify_one_invoice_per_order(
		channel_name=LEGACY_CHANNEL_DEFAULT,
		start_date=LEGACY_START_DDMMYYYY_DEFAULT,
		end_date=LEGACY_END_DDMMYYYY_DEFAULT,
		only_posted=True,
		limit=int(limit),
	)


@frappe.whitelist()
def delete_legacy_unicommerce_orders(
	channel_name=LEGACY_CHANNEL_DEFAULT,
	start_date=LEGACY_START_DDMMYYYY_DEFAULT,
	end_date=LEGACY_END_DDMMYYYY_DEFAULT,
	dry_run=True,
):
	"""
	Delete only `Unicommerce Orders` records for the given channel + date window.
	This intentionally does NOT touch UC staging doctypes.

	Important: destructive. Defaults to `dry_run=True`.
	"""
	frappe.only_for("System Manager")
	from_dt = datetime.strptime(start_date, "%d-%m-%Y")
	to_dt = datetime.strptime(end_date, "%d-%m-%Y").replace(hour=23, minute=59, second=59)
	from_dt = from_dt.replace(hour=0, minute=0, second=0)

	channel_upper = (channel_name or "").strip().upper()
	if not channel_upper:
		return {"status": "error", "error": "channel_name is required"}

	rows = frappe.db.sql(
		"""
		SELECT o.name
		FROM `tabUnicommerce Orders` o
		WHERE UPPER(o.channel_name) = %(channel)s
		  AND o.displayorderdatetime BETWEEN %(from_dt)s AND %(to_dt)s
		""",
		{"channel": channel_upper, "from_dt": from_dt, "to_dt": to_dt},
		as_dict=True,
	)
	names = [r.get("name") for r in (rows or []) if r.get("name")]

	if dry_run:
		return {
			"status": "dry_run",
			"channel_name": channel_upper,
			"start_date": start_date,
			"end_date": end_date,
			"count": len(names),
		}

	deleted = 0
	for nm in names:
		frappe.delete_doc("Unicommerce Orders", nm, ignore_permissions=True, force=True)
		deleted += 1
		frappe.db.commit()

	return {
		"status": "success",
		"channel_name": channel_upper,
		"start_date": start_date,
		"end_date": end_date,
		"deleted": deleted,
	}


@frappe.whitelist()
def verify_one_invoice_per_order(
	channel_name=LEGACY_CHANNEL_DEFAULT,
	start_date=LEGACY_START_DDMMYYYY_DEFAULT,
	end_date=LEGACY_END_DDMMYYYY_DEFAULT,
	only_posted=True,
	limit=10000,
):
	"""
	Audit checker for the "1 UC order => 1 SAP invoice" rule.

	Returns:
	- multi_order_invoice_docs: SAP DocEntry used by >1 UC order in selected window
	- duplicate_order_rows: same UC order has >1 distinct SAP DocEntry (should not happen)
	- orphan_rows: posted rows with missing sap_ar_invoice_docentry
	"""
	from_dt = datetime.strptime(start_date, "%d-%m-%Y").replace(hour=0, minute=0, second=0)
	to_dt = datetime.strptime(end_date, "%d-%m-%Y").replace(hour=23, minute=59, second=59)
	channel_upper = (channel_name or "").strip().upper()

	where_extra = "AND o.status = 'COMPLETE'" if only_posted else ""

	# Base rows from the window.
	rows = frappe.db.sql(
		f"""
		SELECT
			o.name,
			o.uniware_id,
			o.channel_name,
			o.displayorderdatetime,
			o.status,
			COALESCE(o.sap_ar_invoice_docentry, '') AS sap_ar_invoice_docentry,
			COALESCE(o.sap_ar_invoice_docnum, '') AS sap_ar_invoice_docnum
		FROM `tabUnicommerce Orders` o
		WHERE UPPER(o.channel_name) = %(channel)s
		  AND o.displayorderdatetime BETWEEN %(from_dt)s AND %(to_dt)s
		  {where_extra}
		ORDER BY o.displayorderdatetime ASC
		LIMIT %(limit)s
		""",
		{
			"channel": channel_upper,
			"from_dt": from_dt,
			"to_dt": to_dt,
			"limit": int(limit),
		},
		as_dict=True,
	)

	# 1) Same SAP DocEntry mapped to >1 UC order.
	doc_to_orders = {}
	for r in rows:
		doc_entry = str(r.get("sap_ar_invoice_docentry") or "").strip()
		uc_order = str(r.get("uniware_id") or "").strip()
		if not doc_entry or not uc_order:
			continue
		doc_to_orders.setdefault(doc_entry, set()).add(uc_order)

	multi_order_invoice_docs = []
	for doc_entry, orders in doc_to_orders.items():
		if len(orders) > 1:
			multi_order_invoice_docs.append(
				{
					"sap_ar_invoice_docentry": doc_entry,
					"uc_order_count": len(orders),
					"uc_orders": sorted(list(orders))[:50],
				}
			)

	# 2) Same UC order with >1 distinct SAP docentry.
	order_to_docs = {}
	for r in rows:
		doc_entry = str(r.get("sap_ar_invoice_docentry") or "").strip()
		uc_order = str(r.get("uniware_id") or "").strip()
		if not uc_order:
			continue
		if doc_entry:
			order_to_docs.setdefault(uc_order, set()).add(doc_entry)

	duplicate_order_rows = []
	for uc_order, docentries in order_to_docs.items():
		if len(docentries) > 1:
			duplicate_order_rows.append(
				{
					"uniware_id": uc_order,
					"docentry_count": len(docentries),
					"sap_docentries": sorted(list(docentries))[:50],
				}
			)

	# 3) COMPLETE rows with missing docentry.
	orphan_rows = [
		{
			"name": r.get("name"),
			"uniware_id": r.get("uniware_id"),
			"displayorderdatetime": r.get("displayorderdatetime"),
			"status": r.get("status"),
		}
		for r in rows
		if str(r.get("sap_ar_invoice_docentry") or "").strip() == ""
	]

	ok = (len(multi_order_invoice_docs) == 0) and (len(duplicate_order_rows) == 0)
	return {
		"ok": ok,
		"channel_name": channel_upper,
		"start_date": start_date,
		"end_date": end_date,
		"only_posted": bool(only_posted),
		"row_count": len(rows),
		"multi_order_invoice_doc_count": len(multi_order_invoice_docs),
		"duplicate_order_count": len(duplicate_order_rows),
		"orphan_count": len(orphan_rows),
		"multi_order_invoice_docs": multi_order_invoice_docs[:100],
		"duplicate_order_rows": duplicate_order_rows[:100],
		"orphan_rows_sample": orphan_rows[:200],
	}

