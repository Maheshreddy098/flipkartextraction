frappe.ready(function() {

	// Fetch bank list from SAP (ODSC master) and populate the Bank Name dropdown.
	// When a bank is selected, auto-fill the Bank Code field.
	frappe.call({
		method: 'khanal_tech_integrations.utils.purchase.vendor_Posting.get_sap_bank_list',
		callback: function(r) {
			if (!r.message || !r.message.length) return;

			var banks = r.message; // [{code, name}, ...]

			// Build the options string for the Select field
			var options = [''].concat(banks.map(b => b.name));
			var field = frappe.web_form.get_field('bank_name');
			if (field) {
				field.df.options = options.join('\n');
				field.refresh();
			}

			// Auto-fill bank_code when a bank is selected
			frappe.web_form.on('bank_name', function(field, value) {
				var match = banks.find(b => b.name === value);
				frappe.web_form.set_value('bank_code', match ? match.code : '');
			});
		}
	});

});
