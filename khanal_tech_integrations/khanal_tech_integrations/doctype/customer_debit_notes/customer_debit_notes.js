// Copyright (c) 2024, Khanal Tech and contributors
// For license information, please see license.txt

frappe.ui.form.on("Customer Debit Notes", {
	refresh(frm) {
        
        frm.add_custom_button(__('Post CN to SAP'), ()=> {
            // frm.change_custom_button_type('Post CN to SAP', null, 'danger');
            frappe.call({
                method: "khanal_tech_integrations.khanal_tech_integrations.doctype.customer_debit_notes.customer_debit_notes.post_cn_to_sap",
                args: {
                    "name": frm.doc.name
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint(r.message);
                    }
                }
            });
        }).addClass('btn-primary');
        if (frm.doc.status === 'Completed' || frm.doc.status === 'Cancelled') {
            // frm.get_field('post_cn_to_sap').toggle_enable(false);
            // Make the button read only
            frm.remove_custom_button('Post CN to SAP');
            // Make the whole form read only
            // Make all fields read-only
            $.each(frm.fields_dict, function(fieldname, field) {
                frm.set_df_property(fieldname, 'read_only', 1);
            });
            // Make all buttons read-only
            // $.each(frm.custom_buttons, function(i, btn) {
            //     frm.get_btn(btn).addClass('disabled');
            // });
            frm.disable_save();
        }
        // Custom buttons in groups
        // frm.add_custom_button('Closed', () => {
        //     frm.doc.status = 'Closed'
        // }, 'Set Status');
	},
});
