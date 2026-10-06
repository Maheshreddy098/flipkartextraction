

frappe.ready(function() {
    frappe.web_form.validate = () => {
		let data = frappe.web_form.get_values();
		let json_data = JSON.stringify(data);
		console.log(json_data,'json_data');
		console.log(data)
		frappe.call({
			method: 'khanal_tech_integrations.khanal_tech_integrations.web_form.procurement_order_form.procurement_order_form.ProcurementAdding_To_SAP',
			args: {
				data: json_data
			},
			callback: function(response) {
				console.log(response);
			}
		});
	}
	// let web_form_doc = frappe.web_form_doc;
	// let reference_doc = frappe.reference_doc;
	// console.log(reference_doc,'reference_doc')
	// var inputValue = frm.doc.po_no	;
	// console.log(inputValue,'po_no');
	// if (reference_doc) {
	// 	frappe.call({
	// 		method: 'frappe.client.get',
	// 		args: {
	// 			doctype: 'SAP Purchase Order',
	// 			filters: { 'key': reference_doc.purchase_no
	// 		}
	// 		},
	// 		callback: function(response) {
	// 			var sapProcurementData = response.message;
	// 			// Use the fetched data as needed
	// 			console.log(sapProcurementData);
	// 		}
	// 	});
	// }
	
	
})

