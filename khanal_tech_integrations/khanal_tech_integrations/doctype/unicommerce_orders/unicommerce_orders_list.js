frappe.listview_settings['Unicommerce Orders'] = {
    // add fields to fetch
    // add_fields: ['status'],
    // // set default filters
    // filters: [
    //     ['status', '=', 'COMPLETE']
    // ],
    // hide_name_column: true, // hide the last column which shows the `name`
    onload(listview) {
        // triggers once before the list is loaded
    },
    before_render() {
        // triggers before every render of list records
    },

    // set this to true to apply indicator function on draft documents too
    // has_indicator_for_draft: false,

    get_indicator(doc) {
        // customize indicator color
        if (doc.status=='COMPLETE') {
            return [__("COMPLETE"), "green"];
        } else if (doc.status=='PROCESSING') {
            return [__("PROCESSING"), "yellow", "public,=,No"];
        }
        else if (doc.status=='CANCELLED') {
            return [__("CANCELLED"), "red"];
        }
    },
    // primary_action() {
    //     // triggers when the primary action is clicked
    // },
    // get_form_link(doc) {
    //     // override the form route for this doc
    // },
    // add a custom button for each row
    // button: {
    //     show(doc) {
    //         return doc.reference_name;
    //     },
    //     get_label() {
    //         return 'View';
    //     },
    //     get_description(doc) {
    //         return __('View {0}', [`${doc.reference_type} ${doc.reference_name}`])
    //     },
    //     action(doc) {
    //         frappe.set_route('Form', doc.reference_type, doc.reference_name);
    //     }
    // },


    // format how a field value is shown
    // formatters: {
    //     title(val) {
    //         return val.bold();
    //     },
    //     public(val) {
    //         return val ? 'Yes' : 'No';
    //     }
    // }
}
