frappe.pages['prozo-utility'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Prozo Utilities',
		single_column: false,
		card_layout: true,
	});

	// this.parent = parent;
	// this.page = this.parent.page;
	// this.page.sidebar.html(
	// 	`<ul class="standard-sidebar leaderboard-sidebar overlay-sidebar"></ul>`
	// );
	// this.$sidebar_list = this.page.sidebar.find("ul");


	let $btn = page.set_primary_action('Update Inventory Transfers', () => update_inventory_transfer(), 'octicon octicon-plus')
	page.add_inner_button('Post PO', () => post_po())
	page.add_inner_button('Update GRN', () => update_grn())
}

console.log(frappe.get_route());



// FUNCTIONS
function post_po(){
	// call with all options
	frappe.call({
		method: 'khanal_tech_integrations.utils.prozo.purchase_orders.process_po',
		// args: {
		// 	role_profile: 'Test'
		// },
		// disable the button until the request is completed
		btn: $('.primary-action'),
		// freeze the screen until the request is completed
		freeze: true,
		callback: (r) => {
			// on success
			console.log('PO Posted successfully!');
			frappe.show_alert({
				message:'PO Posted successfully!',
				indicator:'green'
			}, 8);
		},
		error: (r) => {
			// on error
			frappe.show_alert({
				message:'PO Posting failed!',
				indicator:'red'
			}, 8);
		}
	})

}

function update_grn(){
	frappe.call({
		method: 'khanal_tech_integrations.utils.prozo.purchase_orders.complete_grn',
		freeze: true,
		callback: (r) =>{
			frappe.show_alert({
				message:'GRNs posted successfully',
				indicator:'green'
			}, 5);
		}

	})
}

function update_inventory_transfer(){
	frappe.call({
		method: 'khanal_tech_integrations.utils.sap.bulk_process_inventory_transfers',
		freeze: true,
		callback: (r) =>{
			frappe.show_alert({
				message:'Inventory Transfers Posted',
				indicator:'green'
			}, 5);
		}

	})
}



