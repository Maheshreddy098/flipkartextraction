// Copyright (c) 2025, Khanal Tech and contributors
// For license information, please see license.txt

frappe.ui.form.on("INC SAP Settings", "initiate_session", function (frm) {
	frappe.call({
		method: "khanal_tech_integrations.api.wowpets.sap_master.initiate_inc_sap_session",
		callback: function (r) {
			if (r.exc) {
				frappe.msgprint({ title: __("Error"), indicator: "red", message: r.exc });
			} else if (r.message) {
				frm.reload_doc();
				frappe.show_alert({ message: __("Session initiated"), indicator: "green" });
			}
		},
	});
});
