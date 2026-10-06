// Copyright (c) 2026, Khanal Tech and contributors
// For license information, please see license.txt

frappe.ui.form.on("Delivery API Settings", {
	refresh(frm) {
		frm.dashboard.add_comment(
			__(
				"Values here are used by the Logistics Delivery portal (Delhivery LTL + PostgreSQL delhivery_lr). Site config keys override these when set. Submit (default) upserts tracking to Postgres and patches RDS during the request, then SAP in background — run bench worker. Set logistics_delivery_async_snapshot_rds_after_delhivery=1 to defer snapshot+RDS+SAP all to the worker. Set logistics_delivery_full_sync_submit=1 for fully synchronous submit."
			),
			"blue",
			true
		);
	},
});
