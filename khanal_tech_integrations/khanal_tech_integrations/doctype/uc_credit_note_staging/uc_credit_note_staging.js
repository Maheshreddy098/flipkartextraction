// Copyright (c) 2026, Khanal Tech and contributors
// For license information, please see license.txt

const _CN_STATUS_CONFIG = {
    pending:  { color: "#6b7280", bg: "#f3f4f6", label: "Pending" },
    posting:  { color: "#92400e", bg: "#fef3c7", label: "Posting" },
    posted:   { color: "#15803d", bg: "#dcfce7", label: "Posted ✓" },
    failed:   { color: "#dc2626", bg: "#fee2e2", label: "Failed ✗" },
    dead:     { color: "#7f1d1d", bg: "#fca5a5", label: "Dead ✗" },
};

frappe.ui.form.on("UC Credit Note Staging", {
    refresh(frm) {
        _render_cn_banner(frm);
        _add_cn_buttons(frm);
        _render_cn_sap_link(frm);
    },
});

function _render_cn_banner(frm) {
    if (frm.$cn_banner) frm.$cn_banner.remove();

    const status = frm.doc.status || "pending";
    const cfg = _CN_STATUS_CONFIG[status] || { color: "#6b7280", bg: "#f3f4f6", label: status };

    const $banner = $(`
        <div style="
            background: ${cfg.bg};
            border: 1.5px solid ${cfg.color}33;
            border-left: 4px solid ${cfg.color};
            border-radius: 8px;
            padding: 12px 18px;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 8px;
        ">
            <div style="display:flex;align-items:center;gap:12px">
                <span style="
                    background:${cfg.color};
                    color:#fff;
                    padding:3px 12px;
                    border-radius:12px;
                    font-size:0.78rem;
                    font-weight:700;
                    letter-spacing:0.3px;
                    text-transform:uppercase;
                ">${cfg.label}</span>
                <span style="font-weight:600;font-size:0.9rem;color:${cfg.color}">
                    ${frm.doc.uc_return_id || ""}
                </span>
                ${frm.doc.return_type ? `<span style="font-size:0.78rem;color:#6b7280;background:#f3f4f6;padding:2px 8px;border-radius:10px">${frm.doc.return_type}</span>` : ""}
            </div>
            <div style="font-size:0.78rem;color:#6b7280;display:flex;gap:16px;flex-wrap:wrap">
                ${frm.doc.return_date ? `<span>Return: <strong>${frappe.datetime.str_to_user(frm.doc.return_date)}</strong></span>` : ""}
                ${frm.doc.attempt_count !== undefined ? `<span>Attempts: <strong>${frm.doc.attempt_count}</strong></span>` : ""}
                ${frm.doc.parent_sap_doc_entry ? `<span>Parent SAP: <strong>${frm.doc.parent_sap_doc_entry}</strong></span>` : ""}
                ${frm.doc.sap_credit_doc_entry ? `<span>Credit SAP: <strong>${frm.doc.sap_credit_doc_entry}</strong></span>` : ""}
            </div>
        </div>`);

    frm.$cn_banner = $banner;
    $(frm.layout.wrapper).prepend($banner);

    if (frm.doc.last_error && ["failed", "dead"].includes(status)) {
        if (frm.$cn_err_banner) frm.$cn_err_banner.remove();
        const $err = $(`
            <div style="
                background:#fef2f2;
                border:1px solid #fecaca;
                border-radius:8px;
                padding:12px 18px;
                margin-bottom:14px;
                font-size:0.82rem;
            ">
                <div style="font-weight:600;color:#dc2626;margin-bottom:4px">⚠ Last Error</div>
                <pre style="margin:0;white-space:pre-wrap;word-break:break-word;color:#7f1d1d;font-size:0.78rem;background:transparent;border:none;padding:0">${frappe.utils.escape_html(frm.doc.last_error)}</pre>
            </div>`);
        $(frm.layout.wrapper).prepend($err);
        frm.$cn_err_banner = $err;
    }
}

function _add_cn_buttons(frm) {
    const status = frm.doc.status;
    const retryable = ["failed", "dead"].includes(status);

    frm.add_custom_button("Validate Credit Note", () => _cn_validate(frm), "Actions");

    if (retryable) {
        frm.add_custom_button("Queue for Retry", () => _cn_retry(frm, "queue"), "Actions");
        frm.add_custom_button("Retry Now (Sync)", () => _cn_retry(frm, "now"), "Actions");
    }

    frm.add_custom_button("Open Ops Center", () => frappe.set_route("unicommerce-ops-center"), "Navigate");
    frm.add_custom_button("Parent Order", () => {
        if (frm.doc.uc_order_id) {
            frappe.set_route("Form", "Unicommerce Orders", frm.doc.uc_order_id);
        } else {
            frappe.show_alert({ message: "No parent order linked", indicator: "orange" });
        }
    }, "Navigate");
}

function _render_cn_sap_link(frm) {
    if (!frm.doc.sap_credit_doc_entry) return;
    frm.set_intro(
        `SAP Credit Note posted: <strong>Entry ${frm.doc.sap_credit_doc_entry}</strong>`,
        "green"
    );
}

function _cn_retry(frm, mode) {
    const label = mode === "now" ? "Retrying synchronously…" : "Queuing for retry…";
    frappe.show_alert({ message: label, indicator: "blue" });
    frappe.call({
        method: "khanal_tech_integrations.unicommerce.api.ops.ops_retry",
        args: { doctype: "UC Credit Note Staging", name: frm.doc.name, mode },
        freeze: mode === "now",
        freeze_message: "Executing retry…",
        callback(r) {
            if (!r.message) return;
            const res = r.message;
            if (res.queued) {
                frappe.show_alert({ message: "Queued — will post on next scheduler run", indicator: "blue" });
            } else if (res.outcome === "posted") {
                frappe.show_alert({ message: "Credit note posted to SAP!", indicator: "green" });
            } else {
                frappe.show_alert({ message: `Result: ${res.outcome || "done"}${res.error ? " — " + res.error.substring(0, 80) : ""}`, indicator: res.outcome === "failed" ? "red" : "blue" });
            }
            frm.reload_doc();
        },
    });
}

function _cn_validate(frm) {
    if (!frm.doc.uc_return_id) {
        frappe.show_alert({ message: "Missing uc_return_id", indicator: "orange" });
        return;
    }
    frappe.call({
        method: "khanal_tech_integrations.unicommerce.api.ops.ops_validate_credit_note",
        args: { uc_return_id: frm.doc.uc_return_id },
        freeze: false,
        callback(r) {
            const d = r.message || {};
            frappe.msgprint({
                title: `Validate CN: ${frm.doc.uc_return_id}`,
                indicator: Number(d.unresolved_items || 0) > 0 ? "orange" : "green",
                message: `
                    <div style="font-size:12px;line-height:1.7;">
                        <div><strong>CN Record:</strong> ${frappe.utils.escape_html(d.record_name || "—")}</div>
                        <div><strong>Parent Order:</strong> ${frappe.utils.escape_html(d.parent_record || "—")}</div>
                        <div><strong>Parent Status:</strong> ${frappe.utils.escape_html(d.parent_status || "—")}</div>
                        <div><strong>Parent SAP DocEntry:</strong> ${frappe.utils.escape_html(d.parent_sap_doc_entry || "—")}</div>
                        <div><strong>Items:</strong> ${d.item_count || 0} | <strong>Unresolved:</strong> ${d.unresolved_items || 0}</div>
                    </div>
                `,
            });
        },
    });
}
