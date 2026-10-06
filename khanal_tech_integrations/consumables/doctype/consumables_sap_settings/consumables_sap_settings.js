// Copyright (c) 2026, Khanal Tech and contributors
// For license information, please see license.txt

frappe.ui.form.on("Consumables SAP Settings", "initiate_session", function (frm) {
	frappe.call({
		method: "khanal_tech_integrations.consumables.api.admin.initiate_consumables_sap_session",
		callback: function (r) {
			if (r.exc) {
				frappe.msgprint({ title: __("Error"), indicator: "red", message: r.exc });
			} else if (r.message) {
				frm.reload_doc();
				if (r.message.status === "success") {
					frappe.show_alert({ message: __(r.message.message), indicator: "green" });
				} else {
					frappe.msgprint({ title: __("Error"), indicator: "red", message: r.message.message });
				}
			}
		},
	});
});
