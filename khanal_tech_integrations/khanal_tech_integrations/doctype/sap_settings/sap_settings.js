// Copyright (c) 2022, Khanal Tech and contributors
// For license information, please see license.txt

frappe.ui.form.on('SAP Settings', {
	refresh: function(frm) {
		// // Your refresh logic here
		// frm.add_custom_button('Initiate Session', () => {
		// 	console.log('Initiating session...');
		// });
	},
	// initiate_session: function(frm) {
	// 	// Your action logic for the "initiate_session" button here
	// 	console.log('Initiating session...');
	// }
});

frappe.ui.form.on("SAP Settings", "initiate_session", function(frm) { 
	console.log('Initiating session...');
	frappe.call({
		method: "khanal_tech_integrations.utils.sap.renew_sap_session", //dotted path to server method
		callback: function(r) {
			// code snippet
		}
	});
});
		



