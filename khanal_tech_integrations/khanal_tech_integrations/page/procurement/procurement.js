frappe.pages['procurement'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'procurement Page',
		single_column: true
	});
}