// Copyright (c) 2022, Khanal Tech and contributors
// For license information, please see license.txt

frappe.ui.form.on("Unicommerce Orders", {
	refresh(frm) {
		_render_linkage_intro(frm);
		_add_order_actions(frm);
	},
});

function _render_linkage_intro(frm) {
	const status = (frm.doc.pipeline_status || '').toLowerCase();
	const invoice = frm.doc.sap_ar_invoice_docentry || '';
	const cn = frm.doc.sap_ar_creditnote_docentry || '';
	const invoice_badge = invoice
		? `<span style="background:#dcfce7;color:#166534;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;">AR Linked: ${frappe.utils.escape_html(invoice)}</span>`
		: `<span style="background:#f3f4f6;color:#374151;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;">AR Not Linked</span>`;
	const cn_badge = cn
		? `<span style="background:#ede9fe;color:#5b21b6;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;">CN Linked: ${frappe.utils.escape_html(cn)}</span>`
		: `<span style="background:#f3f4f6;color:#374151;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;">CN Not Linked</span>`;
	const pipe_badge = `<span style="background:#e0f2fe;color:#075985;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;">Pipeline: ${frappe.utils.escape_html(status || 'unknown')}</span>`;
	frm.set_intro(`<div style="display:flex;gap:8px;flex-wrap:wrap;">${pipe_badge}${invoice_badge}${cn_badge}</div>`, status === 'posted' ? 'green' : 'blue');
}

function _add_order_actions(frm) {
	frm.add_custom_button("Validate Order", () => _validate_order(frm), "Actions");
	frm.add_custom_button("Open Ops Center", () => frappe.set_route("unicommerce-ops-center"), "Navigate");
	frm.add_custom_button("Unicommerce Settings", () => frappe.set_route("Form", "Unicommerce Settings"), "Navigate");

	const retryable = ["failed", "dead", "batch_hold", "ready", "verify"].includes((frm.doc.pipeline_status || "").toLowerCase());
	if (retryable) {
		frm.add_custom_button("Queue Retry", () => _retry_order(frm, "queue"), "Actions");
		frm.add_custom_button("Retry Now (Sync)", () => _retry_order(frm, "now"), "Actions");
	}
}

function _validate_order(frm) {
	frappe.call({
		method: "khanal_tech_integrations.unicommerce.api.ops.ops_validate_order",
		args: { record_name: frm.doc.name },
		freeze: false,
		callback(r) {
			const d = r.message || {};
			const batch = d.batch_check || {};
			const shortages = batch.missing || [];
			frappe.msgprint({
				title: `Validate Order: ${frm.doc.name}`,
				indicator: d.ready_for_invoice && d.payload_ok && batch.ok !== false ? "green" : "orange",
				message: `
					<div style="font-size:12px;line-height:1.7;">
						<div><strong>Status:</strong> ${frappe.utils.escape_html(d.status || "—")}</div>
						<div><strong>Channel:</strong> ${frappe.utils.escape_html(d.channel || "—")}</div>
						<div><strong>Ready:</strong> ${d.ready_for_invoice ? "Yes" : "No"}</div>
						<div><strong>Payload:</strong> ${d.payload_ok ? `OK (${d.line_count || 0} lines)` : "Failed"}</div>
						<div><strong>Batch Check:</strong> ${batch.ok !== false ? "OK" : `${shortages.length} shortage(s)`}</div>
					</div>
				`,
			});
		},
	});
}

function _retry_order(frm, mode) {
	frappe.call({
		method: "khanal_tech_integrations.unicommerce.api.ops.ops_retry",
		args: {
			doctype: "Unicommerce Orders",
			name: frm.doc.name,
			mode,
		},
		freeze: mode === "now",
		freeze_message: mode === "now" ? "Retrying now…" : "Queueing retry…",
		callback(r) {
			const d = r.message || {};
			if (d.queued) {
				frappe.show_alert({ message: "Order queued for retry", indicator: "blue" }, 4);
			} else if (d.outcome === "posted") {
				frappe.show_alert({ message: "Order posted to SAP", indicator: "green" }, 5);
			} else {
				frappe.show_alert({ message: `Retry result: ${d.outcome || "done"}`, indicator: d.outcome === "failed" ? "red" : "blue" }, 5);
			}
			frm.reload_doc();
		},
	});
}