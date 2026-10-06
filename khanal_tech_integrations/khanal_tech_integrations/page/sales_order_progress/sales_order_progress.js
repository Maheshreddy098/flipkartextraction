// frappe.pages['sales-order-progress'].on_page_load = function(wrapper) {
// 	var page = frappe.ui.make_app_page({
// 		parent: wrapper,
// 		title: 'Sales Order Progress Dashboard',
// 		single_column: true
// 	});

// 	page.add_inner_button('Update Posts', () => update_posts())
// }

frappe.pages['sales-order-progress'].on_page_load = function(wrapper) {
	new MyPage(wrapper);
}



// PAGE CONTENT
MyPage = Class.extend({
	init: function(wrapper){
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: 'Sales Order Progress Dashboard',
			single_column: true
		});
		// make page
		this.make();
	},

		// make page
		make: function(){
			// grab the class
			let me = $(this);
			// push dom elemt to page
			$(frappe.render_template(frappe.estate_app_page.body, this)).appendTo(this.page.main);
			let scrtag = document.createElement('script');
			scrtag.src = "https://unpkg.com/frappe-datatable@latest"
			scrtag.type = "text/javascript";
			// append script tage to page
		  document.head.appendChild(scrtag);
			// execute methods
			// form query
			function makeTable(data){
				let datatable = new DataTable("#queryResult", {
					columns: data.tablehead,
					data: data.content,
					inlineFilters: true,
					dropdownButton: '▼'
				});
			}
	        
			// work with form data
			function makeQuery(formQuery){
				// document.querySelector("#queryResult").innerText = formQuery;
				frappe.call({
				method: "khanal_tech_integrations.khanal_tech_integrations.page.sales_order_progress.database_console.query_database", //dotted path to server method
							args: {query:formQuery},
							callback: function(r) {
					// code snippet
					// /workspace/development/frappe-bench/apps/khanal_tech_integrations/khanal_tech_integrations/khanal_tech_integrations/page/sales_order_progress/database_console.py
									let el = $("#queryResult");
									let result = r.message;
									console.log(result);
									if(result.reply==0){
										frappe.throw(result.content)
									} else if(result.reply==2){
										el.addClass("text-danger");
										el[0].innerText = result.content;
									} else {
										if(result.content.length>1){
											makeTable(result);
										} else {
											frappe.msgprint("Empty Set")
										}
									}
				}
			})
			}
			// get form data
			$("#queryForm").submit(e=>{
				e.preventDefault();
				let formquery = $("#query")[0].value;
				console.log(formquery);
				if(formquery.length>1){
					makeQuery(formquery);
				}
			})
			// end function
	
		}
	
		// end of class
	})
	
	// HTML CONTENT
	let body = `
				<div id="">
					<form id="queryForm">
					  <div class="form-group">
						<label for="query">Enter SQL QUERY</label>
						<textarea class="form-control" id="query" aria-describedby="query" placeholder="Enter Query"></textarea>
						<small id="emailHelp" class="form-text text-muted text-danger">Think before you type.</small>
					  </div>
					  <button type="submit" class="btn btn-primary">Submit</button>
					</form>
					<br>
				</div>
				<div id="queryResult">
				</div>
	`;
	// frappe.estate_app_page = {}
	frappe.estate_app_page = {
		body: body
	}