// Copyright (c) 2023, Khanal Tech and contributors
// For license information, please see license.txt

frappe.ui.form.on("Dispatch Record", {
	refresh: function(frm) {
		frm.add_custom_button('DN Create',()=>{
			//frappe.throw('Testing it now')
			frappe.call({
        		method: "khanal_tech_integrations.utils.DN_Creation_Unicommerce.DN_Creation_from_Upload", //dotted path to server method
        		callback: function(r) {
            	// code snippet
        		}
    		});
		})

		
	}
});