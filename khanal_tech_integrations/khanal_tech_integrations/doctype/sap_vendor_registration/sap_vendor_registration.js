// Copyright (c) 2023, Khanal Tech and contributors
// For license information, please see license.txt

// frappe.ui.form.on("SAP Vendor Registration", {
// 	refresh(frm) {

// 	},
// });


frappe.ui.form.on('SAP Vendor Registration', {
	refresh: function (frm) {
		frm.add_custom_button('Update To SAP', () => {
			// frappe.throw('Testing it now')
			if (!frm.doc.vendor_type) {
				frappe.msgprint('Vendor Type is empty. Please fill it before proceeding.');
				return;
			}
			if (!frm.doc.internal_point_of_contact) {
				frappe.msgprint('Internal Point of Contact is empty. Please fill it before proceeding.');
				return;
			}
			
			const validFormat = /\S+@\S+\.\S+/;
			if (!validFormat.test(frm.doc.internal_point_of_contact)) {
				// Invalid format, show an error message or take appropriate action
				frappe.msgprint("Internal Point of Contact Invalid email address. Please enter a valid email.");
				frm.doc.internal_point_of_contact = ""; // Clear the field value
				frm.refresh_field("internal_point_of_contact"); // Refresh the field to reflect changes
				return;
			}
			frappe.call({
				method: "khanal_tech_integrations.utils.purchase.vendor_Posting.PostingVendor_to_SAP",
				args: {
					docname: frm.docname  // Pass the doctype name as an argument
				},
				callback: function (r) {
					// code snippet
					

				}
			});
		})
		
		frm.add_custom_button('Download', () => {
			// frappe.throw('Testing it now')
			frappe.call({
				method: "khanal_tech_integrations.utils.purchase.vendor_Posting.download_file",
				args: {
					docname: frm.docname  // Pass the doctype name as an argument
				},
				callback: function (r) {
					// code snippet
					if (r.message) {
						// Convert the base64 encoded zip file data to a Blob
						const byteCharacters = atob(r.message);
						const byteNumbers = new Array(byteCharacters.length);
						for (let i = 0; i < byteCharacters.length; i++) {
							byteNumbers[i] = byteCharacters.charCodeAt(i);
						}
						const byteArray = new Uint8Array(byteNumbers);
						const blob = new Blob([byteArray], { type: "application/zip" }); // Set the correct MIME type for zip
		
						// Create a temporary download link and trigger the download
						const link = document.createElement("a");
						link.href = URL.createObjectURL(blob);
						link.download = "Vendor_Attachments.zip"; // Set the filename for the zip file
						link.click();
		
						// Clean up after download
						URL.revokeObjectURL(link.href);
					}
				}
			});
		})
		// frm.add_custom_button('Check GST',()=>{
		// 	frappe.call({
		// 		method: "khanal_tech_integrations.utils.cashfree.vrf.gst_verification.check_gst_validity",
		//         args: {
		// 			docname: frm.docname  
		// 		},
		// 		callback: function(r) {
		// 			// frm.save();
        //     		frm.reload_doc();
		// 		}
		// 	});
		// })
		
		// frappe.web_form.on('gst_number', (field, value) => {
		// 	alert(gst_number,'gst_number')
		// });


	}
});

// frappe.ui.form.on('SAP Vendor Registration', {
//     onload: function(frm) {
// 		{
// 		alert(frm)
//         // This function will be triggered when the gst_number field changes
        
//         // Get the new value of the gst_number field
//         var newGstNumber = frm.doc.gst_number;
        
//         // Perform actions based on the new value
//         // For example, you can display an alert or update other fields
//         if (newGstNumber) {
//             frappe.msgprint('GST Number changed to: ' + newGstNumber);
//             // You can also perform additional actions here
//         }
//     }
// });
// frappe.ui.form.on('SAP Vendor Registration', {
//     onload: function(frm) {
// 		console.log(frm)
//         // This function will be triggered when the form is validated
        
//         // Check if the gst_number field has been newly added or updated
//         frappe.call({
// 			method: "khanal_tech_integrations.utils.cashfree.vrf.gst_verification.check_gst_validity",
// 			args: {
// 				docname: frm.docname  // Pass the doctype name as an argument
// 			},
// 			callback: function (r) {
// 				// code snippet
// 			}
// 		});
//     }
// });




// if (r.message) {
// 	// Convert the base64 encoded file data to a Blob
// 	const byteCharacters = atob(r.message);
// 	const byteNumbers = new Array(byteCharacters.length);
// 	for (let i = 0; i < byteCharacters.length; i++) {
// 		byteNumbers[i] = byteCharacters.charCodeAt(i);
// 	}
// 	const byteArray = new Uint8Array(byteNumbers);
// 	const blob = new Blob([byteArray], { type: "application/octet-stream" });

// 	// Create a temporary download link and trigger the download
// 	const link = document.createElement("a");
// 	link.href = URL.createObjectURL(blob);
// 	link.download = "downloaded_file.png"; // Set the filename here
// 	link.click();

// 	// Clean up after download
// 	URL.revokeObjectURL(link.href);
// }