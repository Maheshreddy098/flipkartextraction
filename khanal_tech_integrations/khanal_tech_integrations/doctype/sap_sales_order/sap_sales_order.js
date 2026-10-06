// Copyright (c) 2022, Khanal Tech and contributors
// For license information, please see license.txt

frappe.ui.form.on('SAP Sales Order', {

	refresh: function(frm) {
		frm.add_custom_button('Get All SalesOrders',()=>{
			//frappe.throw('Testing it now')
			frappe.call({
        		method: "khanal_tech_integrations.utils.logistics.sales_order.update", //dotted path to server method
        		callback: function(r) {
            	// code snippet
        		}
    		});
		})

		// frm.add_custom_button('Delete All',()=>{
		// 	//frappe.throw('Testing it now')
		// 	frappe.call({
        // 		method: "khanal_tech_integrations.utils.logistics.sales_order.delete", //dotted path to server method
        // 		callback: function(r) {
        //     	// code snippet
        // 		}
    	// 	});
		// })
		frm.add_custom_button('Get Pallets',()=>{
			//frappe.throw('Testing it now')
			frappe.call({
				method: "khanal_tech_integrations.utils.Sales.Get_pallets.pallet_Single",
				args: {
					DocEntry: frm.docname  // Pass the doctype name as an argument
				},
				callback: function (r) {
					// code snippet
					if (r.message) {
						// Show a success message
						frappe.msgprint({
							message: r.message,
							alert: true
						});
					} else {
						// Show an error message
						frappe.msgprint({
							message: "An error occurred while getting pallets.",
							title: "Error",
							indicator: "red"
						});
					}
					

				}
			});
		})

		
	}
});