// Copyright (c) 2022, Khanal Tech and contributors
// For license information, please see license.txt

frappe.ui.form.on('SAP Inventory Transfers', {
	refresh: function(frm) {
		frm.add_custom_button('Inv Get', () => {
			frappe.call({
				method: "khanal_tech_integrations.utils.sap.bulk_process_inventory_transfers",
				callback: function(r) {
					if (r.message) frappe.msgprint(JSON.stringify(r.message));
				}
			});
		});

		frm.add_custom_button('PO Check', () => {
			frappe.call({
				method: "khanal_tech_integrations.unicommerce.workers.grn.refresh_po_status",
				args: { days: 30 },
				callback: function(r) {
					frm.reload_doc();
					frappe.msgprint('PO status refreshed.');
				}
			});
		}, 'Unicommerce');

		frm.add_custom_button('PO Create', () => {
			frappe.confirm(
				`Create Unicommerce PO for <b>${frm.doc.name}</b>?`,
				() => {
					frappe.call({
						method: "khanal_tech_integrations.unicommerce.workers.grn.push_po",
						args: { inv_transfer_docname: frm.doc.name },
						freeze: true,
						freeze_message: 'Creating PO in Unicommerce…',
						callback: function(r) {
							frm.reload_doc();
							if (r.message && r.message.success) {
								frappe.msgprint(`PO created: ${r.message.purchaseOrderCode}`);
							} else {
								frappe.msgprint({
									title: 'PO Creation Failed',
									message: (r.message && r.message.message) || 'Unknown error',
									indicator: 'red'
								});
							}
						}
					});
				}
			);
		}, 'Unicommerce');

		frm.add_custom_button('Fill GRN', () => {
			if (!frm.doc.uniware_po_id) {
				frappe.msgprint('Create the PO first before filling GRN.');
				return;
			}
			if (frm.doc.uniware_grn_no) {
				frappe.msgprint(`GRNs already created: ${frm.doc.uniware_grn_no}`);
				return;
			}
			frappe.confirm(
				`Fill GRN items in Unicommerce for <b>${frm.doc.name}</b>?`,
				() => {
					frappe.call({
						method: "khanal_tech_integrations.unicommerce.workers.grn.fill_grn_items",
						args: { inv_transfer_docname: frm.doc.name },
						freeze: true,
						freeze_message: 'Filling GRN items…',
						callback: function(r) {
							frm.reload_doc();
							const msg = r.message || {};
							if (msg.success) {
								frappe.msgprint(`GRN filled. Synced: ${msg.synced}, Failed: ${msg.failed}. GRNs: ${(msg.grn_codes || []).join(', ')}`);
							} else {
								frappe.msgprint({
									title: 'GRN Fill Failed',
									message: (msg.errors || []).join('\n') || 'Unknown error',
									indicator: 'red'
								});
							}
						}
					});
				}
			);
		}, 'Unicommerce');

		frm.add_custom_button('Sync Inventory', () => {
			frappe.confirm(
				`Remove transferred quantities from Unicommerce inventory for <b>${frm.doc.name}</b>?`,
				() => {
					frappe.call({
						method: "khanal_tech_integrations.unicommerce.workers.inventory.push_transfer",
						args: { inv_transfer_docname: frm.doc.name },
						freeze: true,
						freeze_message: 'Syncing inventory…',
						callback: function(r) {
							frm.reload_doc();
							const msg = r.message || {};
							if (msg.success) {
								frappe.msgprint(`Inventory synced. Status: ${msg.status}, Synced: ${msg.synced}`);
							} else {
								frappe.msgprint({
									title: 'Inventory Sync Failed',
									message: (msg.errors || []).join('\n') || msg.message || 'Unknown error',
									indicator: 'red'
								});
							}
						}
					});
				}
			);
		}, 'Unicommerce');
	}
});
