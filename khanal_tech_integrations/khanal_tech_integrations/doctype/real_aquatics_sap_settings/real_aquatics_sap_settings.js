// Copyright (c) 2025, Khanal Tech and contributors
// For license information, please see license.txt

frappe.ui.form.on("Real Aquatics SAP Settings", "initiate_session", function (frm) {
	frappe.call({
		method: "khanal_tech_integrations.api.real_aquatics.sap_master.initiate_real_aquatics_sap_session",
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
