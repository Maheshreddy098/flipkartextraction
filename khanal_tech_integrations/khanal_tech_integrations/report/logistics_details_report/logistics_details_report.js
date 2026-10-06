// Copyright (c) 2022, Khanal Tech and contributors
// For license information, please see license.txt
/* eslint-disable */


// var someDate = new Date();
// var numberOfDaysToAdd = 30;
// var result = someDate.setDate(someDate.getDate() - numberOfDaysToAdd);


// var date = new Date(result);
// var year = date.getFullYear();
// var month = date.getMonth() + 1;
// var day = date.getDate();

// var from_Date_default = [ day,month,year, ].join('-');
// console.log(from_Date_default);

//console.log("hello");

frappe.query_reports["Logistics Details Report"] = { 

	
	"filters": [
		// {
        //     fieldname: 'company',
        //     label: __('Company'),
        //     fieldtype: 'Link',
        //     options: 'Company',
        //     default: frappe.defaults.get_user_default('company')
        // },
		

		// {
		// 	fieldname	:"Salesperson",
		// 	label		: __("Salesperson"),
		// 	fieldtype	: "Link",
		// 	options		: "SAP Salesperson",
		// 	default     : "Rohan Pradhan"  
		// },

		{
			fieldname   : "From_Date",
			label  	    : __("From Date"),
			fieldtype	: "Date",
			default		: frappe.datetime.month_start(), //Beginning of the curret month
		},

		{
			fieldname 	: "To_Date",
			label 		: __("To Date"),
			fieldtype   : "Date",
			default		: frappe.datetime.get_today(),
		}, 

		

	],

// 	"formatter": function (row, cell, value, columnDef, dataContext, default_formatter) {
// 		value = default_formatter(row, cell, value, columnDef, dataContext);

// 	// if (columnDef.id != "Debit") {
// 	// 	value = "<span style='color:#006400!important;font-weight:bold';>" + value + "</span>";
// 	// }


// 	return value;
// }

	
	// formatter (value, row, column, data, default_formatter) {
	// 	value = default_formatter(value, row, column, data);
	// 	if (column.id ==  "Customer Name" ) {
	// 		 		HTML_Value = value 
	// 		    }
	// 	return "<span style='color:red!important;font-weight:bold'>" + value + "</span>";
	// 	},

	
};




// "formatter":function (row, cell, value, columnDef, dataContext, default_formatter) {
// 	value = default_formatter(row, cell, value, columnDef, dataContext);
//    if (columnDef.id != "Invoice Amount" && dataContext["Invoice Amount"] > 1000 ) {
// 		value = "<span style='color:red!important;font-weight:bold'>" + value + "</span>";
//    }
// //    if (columnDef.id != "Customer" && columnDef.id != "Payment Date" && dataContext["Rental Payment"] > 100) {
// //         value = "<span style='color:green!important;font-weight:bold'>" + value + "</span>";
// //    }
//    return value;  //"Tracking Number"
// }

//filling with color ---- value = <p style='margin:0px;padding-left:5px;background-color:red!important;'>${value}</p>