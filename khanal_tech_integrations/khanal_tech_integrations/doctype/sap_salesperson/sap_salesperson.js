// Copyright (c) 2022, Khanal Tech and contributors
// For license information, please see license.txt


// frappe.ui.form.on('SAP Salesperson', "refresh", 
// 		function(frm) {
//     		frm.add_custom_button(__("Do Something"), 	
// 		function() {
//             console.log("Did something");
//         });
//     });

// frappe.ui.form.on('SAP Salesperson', "refresh", 
// function(frm){
// 		frm.add_custom_button("Button Description", 
// 		function(){	var myWin = window.open("https://example.com/ 1");
// 		});
		
// });


// frappe.listview_settings['SAP Salesperson'] = {

//     onload(listview) {
//         // triggers once before the list is loaded
//         console.log("loaded", listview);
//         listview.page.add_action_item('Action1', () => my_action_handler());
//         listview.page.set_secondary_action('Action2', () => refresh(), 'octicon octicon-sync');
//   }
// }

frappe.ui.form.on('SAP Salesperson', {
	refresh: function(frm) {
		frm.add_custom_button('Get All Salesperson',()=>{
			//frappe.throw('Testing it now')
			frappe.call({
        		method: "khanal_tech_integrations.utils.logistics.salesperson.get_Salespersons", //dotted path to server method
        		callback: function(r) {
            	// code snippet
        		}
    		});
		})

		frm.add_custom_button('Delete All',()=>{
			//frappe.throw('Testing it now')
			frappe.call({
        		method: "khanal_tech_integrations.utils.logistics.salesperson.delete", //dotted path to server method
        		callback: function(r) {
            	// code snippet
        		}
    		});
		})

		
	}
});

// bench --site medusa.localhost execute khanal_tech_integrations.utils.logistics.salesperson.get_Salespersons