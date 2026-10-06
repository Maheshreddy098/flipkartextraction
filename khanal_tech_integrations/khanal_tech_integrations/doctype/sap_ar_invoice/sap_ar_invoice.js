// Copyright (c) 2022, Khanal Tech and contributors
// For license information, please see license.txt




frappe.ui.form.on('SAP AR Invoice', {
	refresh: function(frm) {
		frm.add_custom_button('Get All Invoices',()=>{
			//frappe.throw('Testing it now')
			frappe.call({
        		method: "khanal_tech_integrations.utils.logistics.ar_invoice.update", //dotted path to server method
        		callback: function(r) {
            	// code snippet
        		}
    		});
		})

		frm.add_custom_button('Delete All',()=>{
			//frappe.throw('Testing it now')
			frappe.call({
        		method: "khanal_tech_integrations.utils.logistics.ar_invoice.delete", //dotted path to server method
        		callback: function(r) {
            	// code snippet
        		}
    		});
		})

		
	}
});