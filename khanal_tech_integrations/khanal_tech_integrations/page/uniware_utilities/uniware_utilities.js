frappe.pages['uniware-utilities'].on_page_load = function(wrapper) {
	
	// new UnicommercePage(wrapper);
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Uniware Utilities',
		single_column: true
	});

	// add a normal inner button
	// page.add_inner_button('Update Posts', () => update_posts())
	frappe.breadcrumbs.add("Setup");

	$(frappe.render_template("uniware_utilities")).appendTo(this.page.main);//page.body.addClass("no-border"));
}