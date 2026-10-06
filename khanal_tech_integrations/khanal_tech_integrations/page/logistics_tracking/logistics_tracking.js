frappe.pages['logistics-tracking'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Logistics Tracking',
		single_column: true
	});
	var so_count = 0;
	frappe.logistics_tracking.run();

	$(frappe.render_template("logistics_tracking",{data:so_count})).appendTo(this.page.main);
	// console.log(this.page.main);
	
}

frappe.logistics_tracking = {

	run: function(){
		var me = frappe.logistics_tracking;

		frappe.call({
			method: 'khanal_tech_integrations.khanal_tech_integrations.page.logistics_tracking.logistics_tracking.get_so_count',
			args:{},
			callback: function(r){
				console.log(r.message);
				
				if (r.message) {
					console.log(r.message);
					data = r.message;

					so_count  = data.so_count;
					inv_count = data.inv_count;
					so_count_last30days = data.so_count_last30days;
					$('#so_count').text(so_count.toLocaleString('en-IN'));
					$('#inv_count').text(inv_count.toLocaleString('en-IN'));
					$('#so_count_last30days').text(so_count_last30days.toLocaleString('en-IN'));

					} else {
						frappe.show_alert({message: __('No Sales Order'), indicator: 'gray'});
					// me.more.parent().addClass('hidden');
				}
			}
		});
		
		//$(frappe.render_template("logistics_tracking")).appendTo(me.body);
	},
}