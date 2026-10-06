

frappe.listview_settings['Supplier'] = {
    // add_fields: ["status", "customer", "delivery_date"],
    // get_indicator: function(doc) {
    //     switch (doc.status) {
    //         case "Draft":
    //             return [__("Draft"), "red", "status,=,Draft"];
    //         case "To Deliver and Bill":
    //         case "To Deliver":
    //             return [__("To Deliver"), "orange", "status,=,To Deliver"];
    //         case "Completed":
    //             return [__("Completed"), "green", "status,=,Completed"];
    //         case "Cancelled":
    //             return [__("Cancelled"), "darkgrey", "status,=,Cancelled"];
    //     }
    // },
    onload: function(listview) {
        listview.page.add_menu_item('Fetch All Suppliers', function() {
            // Add your custom button action here
            // frappe.msgprint('Custom Button Clicked');
            frappe.call('khanal_tech_integrations.utils.procure_to_pay.syncBP_master.get_sap_bp_master', {
                arg1: 'value1',
                arg2: 'value2'
            }).then(result => {
                console.log(result);
                frappe.msgprint(result.message);
            });
        });
    }
};