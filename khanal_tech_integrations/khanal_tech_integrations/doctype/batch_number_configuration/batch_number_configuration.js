frappe.ui.form.on('Batch Number Configuration', {
	refresh: function(frm) {
		// Add import button in list view
		if (frm.is_list) {
			return;
		}
		
		// Add custom import button in form
		if (frm.doc.__islocal) {
			frm.add_custom_button(__('Import from Excel'), function() {
				import_from_excel();
			});
		}
	}
});

// List view customization
frappe.listview_settings['Batch Number Configuration'] = {
	add_fields: ['category', 'item_code', 'variant'],
	
	onload: function(listview) {
		// Add bulk import button
		listview.page.add_menu_item(__('Import from Excel'), function() {
			import_from_excel();
		});
	}
};

function import_from_excel() {
	let d = new frappe.ui.Dialog({
		title: __('Import Batch Number Configuration from Excel'),
		fields: [
			{
				label: __('Upload Excel File'),
				fieldname: 'file',
				fieldtype: 'Attach',
				reqd: 1
			},
			{
				fieldtype: 'Section Break'
			},
			{
				fieldtype: 'HTML',
				options: `
					<div class="alert alert-info">
						<h5>Excel Format Requirements:</h5>
						<ul>
							<li><strong>Required columns:</strong> Category, Item Code, Variant, Warehouse, SKU Code</li>
							<li><strong>Optional column:</strong> Grams SKU</li>
							<li><strong>Warehouse:</strong> Can be single (e.g., "NH") or multiple (e.g., "NH, KG" or "NH\nKG")</li>
							<li>First row should contain column headers</li>
						</ul>
						<button class="btn btn-sm btn-secondary" onclick="frappe.batch_config_download_template()" style="margin-top: 10px;">
							Download Template
						</button>
					</div>
				`
			}
		],
		primary_action_label: __('Import'),
		primary_action: function(values) {
			if (!values.file) {
				frappe.msgprint(__('Please select an Excel file'));
				return;
			}
			
			// Get file URL - handle both full URL and file path
			let file_url = values.file;
			if (file_url && !file_url.startsWith('http') && !file_url.startsWith('/files/')) {
				file_url = '/files/' + file_url;
			}
			
			d.hide();
			
			// Show loading indicator
			frappe.show_alert({
				message: __('Importing data...'),
				indicator: 'blue'
			});
			
			frappe.call({
				method: 'khanal_tech_integrations.api.batch_number_config_import.import_from_excel',
				args: {
					file_url: file_url
				},
				callback: function(r) {
					if (r.message && r.message.success) {
						let msg = r.message.message;
						if (r.message.error_count > 0 && r.message.errors && r.message.errors.length > 0) {
							msg += '<br><br><strong>Errors:</strong><ul>';
							r.message.errors.forEach(function(err) {
								msg += '<li>Row ' + err.row + ': ' + err.error + '</li>';
							});
							msg += '</ul>';
						}
						
						frappe.msgprint({
							title: __('Import Completed'),
							message: msg,
							indicator: r.message.error_count > 0 ? 'orange' : 'green'
						});
						
						// Reload list view
						setTimeout(function() {
							if (cur_list) {
								cur_list.refresh();
							} else {
								location.reload();
							}
						}, 1000);
					} else {
						frappe.msgprint({
							title: __('Import Failed'),
							message: r.message ? r.message.message : __('Failed to import file'),
							indicator: 'red'
						});
					}
				},
				error: function(r) {
					frappe.msgprint({
						title: __('Import Error'),
						message: r.message || __('Failed to import file'),
						indicator: 'red'
					});
				}
			});
		}
	});
	
	d.show();
}

// Make function globally accessible
window.frappe = window.frappe || {};
frappe.batch_config_download_template = function download_template() {
	// Show loading message
	frappe.show_alert({
		message: __('Generating template...'),
		indicator: 'blue'
	});
	
	frappe.call({
		method: 'khanal_tech_integrations.api.batch_number_config_import.download_template',
		callback: function(r) {
			if (r.message && r.message.success) {
				try {
					// Convert base64 to blob
					const byteCharacters = atob(r.message.file_content);
					const byteNumbers = new Array(byteCharacters.length);
					for (let i = 0; i < byteCharacters.length; i++) {
						byteNumbers[i] = byteCharacters.charCodeAt(i);
					}
					const byteArray = new Uint8Array(byteNumbers);
					const blob = new Blob([byteArray], {
						type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
					});
					
					// Create download link
					const url = window.URL.createObjectURL(blob);
					const link = document.createElement('a');
					link.href = url;
					link.download = r.message.filename || 'Batch_Number_Configuration_Template.xlsx';
					document.body.appendChild(link);
					link.click();
					document.body.removeChild(link);
					
					// Clean up
					window.URL.revokeObjectURL(url);
					
					frappe.show_alert({
						message: __('Template downloaded successfully'),
						indicator: 'green'
					});
				} catch (e) {
					console.error('Download error:', e);
					frappe.msgprint({
						title: __('Download Failed'),
						message: __('Failed to create download file. Please try again.'),
						indicator: 'red'
					});
				}
			} else {
				frappe.msgprint({
					title: __('Download Failed'),
					message: r.message ? r.message.message : __('Failed to generate template'),
					indicator: 'red'
				});
			}
		},
		error: function(r) {
			console.error('Template download error:', r);
			frappe.msgprint({
				title: __('Download Error'),
				message: r.message || __('Failed to download template'),
				indicator: 'red'
			});
		}
	});
}

