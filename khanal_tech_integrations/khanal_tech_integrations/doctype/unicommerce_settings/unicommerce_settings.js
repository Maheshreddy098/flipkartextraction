// Copyright (c) 2022, Khanal Tech and contributors
// For license information, please see license.txt

frappe.ui.form.on('Unicommerce Settings', {
	refresh: function (frm) {
		frm.add_custom_button('Test Connections', function () {
			frappe.show_alert({ message: 'Testing connections…', indicator: 'blue' });
			frappe.call({
				method: 'khanal_tech_integrations.unicommerce.health.check_connections',
				freeze: true,
				freeze_message: 'Connecting…',
				callback: function (r) {
					if (!r.message) return;
					const s = r.message;
					const sap_ok = s.sap_login && s.sap_login.ok;
					const uc_ok  = s.uc_login  && s.uc_login.ok;

					function conn_row(label, ok, msg) {
						const bg     = ok ? '#d4edda' : '#f8d7da';
						const border = ok ? '#c3e6cb' : '#f5c6cb';
						const col    = ok ? '#155724' : '#721c24';
						return `<div style="background:${bg};border:1px solid ${border};border-radius:6px;padding:12px 16px;margin-bottom:8px;">
							<span style="font-size:1.1rem;font-weight:700;color:${col};margin-right:10px;">${ok ? '✓' : '✗'}</span>
							<strong style="font-size:13px;">${label}:</strong>
							<span style="color:${col};font-weight:600;"> ${ok ? 'Connected' : 'Failed'}</span>
							${msg ? `<div style="font-size:11px;color:#6c757d;margin-top:4px;">${frappe.utils.escape_html(msg)}</div>` : ''}
						</div>`;
					}

					frappe.msgprint({
						title: 'Connection Test Results',
						indicator: sap_ok && uc_ok ? 'green' : 'red',
						message: conn_row('SAP B1 Service Layer', sap_ok, s.sap_login && s.sap_login.message)
							+ conn_row('Unicommerce API', uc_ok, s.uc_login && s.uc_login.message),
					});

					// Reload form so token fields (access_token, expires_on) show updated values.
					if (uc_ok) {
						frm.reload_doc();
					}
				},
				error: function () {
					frappe.msgprint({
						title: 'Connection Test Failed',
						indicator: 'red',
						message: 'Could not reach the server. Check Frappe logs for details.',
					});
				},
			});
		}, 'Actions');
	},
});
