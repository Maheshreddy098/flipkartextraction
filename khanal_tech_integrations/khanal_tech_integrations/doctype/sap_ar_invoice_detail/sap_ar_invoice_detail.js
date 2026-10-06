// Copyright (c) 2023, Khanal Tech and contributors
// For license information, please see license.txt

// frappe.ui.form.on("SAP AR Invoice Detail", {
// 	// refresh(frm) {
// 	// },
//     validate(frm) {
//         // Log the values for debugging
//         console.log(frm.doc.shipping_charges, 'frm.doc.shipping_charges');
//         console.log(frm.doc.__original_shipping_charges, 'frm.doc.__original_shipping_charges');

//         // Check if shipping_charges has changed
//         // if (frm.doc.shipping_charges !== frm.doc.__original_shipping_charges) {
//         //     frm.set_value('shipping_status', 'Pending');
//         // }
//     },
// });
frappe.ui.form.on("SAP AR Invoice Detail", {
    onload(frm) {
        // Initialize the original value of shipping_charges on form load
        if (!frm.is_new()) {
            frm._original = frm._original || {};
            frm._original.shipping_charges = frm.doc.shipping_charges;

        }
    },

    validate(frm) {
        // Retrieve the original value of shipping_charges
        var original_shipping_charges = frm._original && frm._original.shipping_charges;

       
        // Check if shipping_charges has changed
        if (original_shipping_charges != null && frm.doc.shipping_charges !== original_shipping_charges) {
            frm.set_value('shipping_status', 'Pending');
        }

        if (frm.doc.pod_url == '') {
            frm.set_value('pod_status', 'Pending');
        }
    }
});