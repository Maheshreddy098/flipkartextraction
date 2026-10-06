// Copyright (c) 2025, Khanal Tech Integrations and contributors
// For license information, please see license.txt

frappe.ui.form.on("SAP Test Layer", {
	refresh(frm) {},
});

frappe.ui.form.on("SAP Test Layer", "login", function (frm) {
	frappe.call({
		method: "khanal_tech_integrations.khanal_tech_integrations.doctype.sap_test_layer.sap_test_layer.login",
		freeze: true,
		freeze_message: __("Logging into test SAP..."),
		callback: function (r) {
			if (r.message && r.message.success) {
				frappe.show_alert({ message: r.message.message, indicator: "green" });
				frm.reload_doc();
			}
		},
	});
});

frappe.ui.form.on("SAP Test Layer", "check_connection", function (frm) {
	frappe.call({
		method: "khanal_tech_integrations.khanal_tech_integrations.doctype.sap_test_layer.sap_test_layer.check_connection",
		freeze: true,
		freeze_message: __("Checking test SAP connection..."),
		callback: function (r) {
			if (!r.message) return;
			const { hana, service_layer } = r.message;
			frappe.msgprint({
				title: __("Test SAP Connection Check"),
				message: `
					<b>HANA:</b> ${hana.ok ? "✅ OK" : "❌ Failed"}<br>${frappe.utils.escape_html(hana.message)}<br><br>
					<b>Service Layer:</b> ${service_layer.ok ? "✅ OK" : "❌ Failed"}<br>${frappe.utils.escape_html(service_layer.message)}
				`,
				indicator: hana.ok && service_layer.ok ? "green" : "red",
			});
			frm.reload_doc();
		},
	});
});
