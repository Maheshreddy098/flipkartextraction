import frappe
from frappe.utils import add_to_date
import json

def get_context(context):
    Today = frappe.utils.nowdate()
    FilterDate = add_to_date(Today,days=-30)
    inventorylist = frappe.db.get_list('SAP Inventory Report',pluck='name')
    # inventorylist = frappe.db.get_list('SAP Inventory Report', filters={
    #     'created_date': ['>=', FilterDate],
    #     'created_date': ['<=', Today]
    # }, pluck='name')
    # inventorylist = frappe.db.get_list('SAP Inventory Report',pluck='name')
    print(inventorylist,'inventorylist')
    result = []
    for i in inventorylist:
        print(i)
        doc = frappe.get_doc('SAP Inventory Report', i)
        print(len(doc.lineitems),'doc.lineitems')
        line_items = []
    
        for table_row in doc.lineitems:
            # print(table_row)
            line_item = {
                'ItemCode': table_row.itemcode,
                'Quantity': table_row.quantity,
                'DistNumber': table_row.distnumber,
                'ItemName':table_row.itemname,
                'WhsCode':table_row.whscode,
                'ExpDate':table_row.expdate,
                'MnfDate':table_row.mnfdate,
                # Add more fields as needed
            }
            line_items.append(line_item)

   
            data = {
                'lineitems': line_items,
                'createddate': doc.created_date
            }
          
        result.append(data)

    table = []
    unique_data_list = []
    serial_number = 1

    for entry in result:
        for line_item in entry["lineitems"]:
            item_identifier = line_item["ItemCode"] + line_item["DistNumber"] + line_item["WhsCode"]

            row_data = [
                serial_number,
                line_item["ItemCode"],
                line_item["ItemName"]
            ]

            for entry2 in result:
                filtered_line_items = [item for item in entry2["lineitems"] if
                                    item["ItemCode"] == line_item["ItemCode"] and
                                    item["DistNumber"] == line_item["DistNumber"] and
                                    item["WhsCode"] == line_item["WhsCode"]]

                quantity = filtered_line_items[0]["Quantity"] if filtered_line_items else ""
                row_data.append(quantity)

            row_data.append(line_item["DistNumber"])
            row_data.append(line_item["WhsCode"])

            row_data_string = json.dumps(row_data[1:])

            if row_data_string not in unique_data_list:
                unique_data_list.append(row_data_string)
                table.append(row_data)
                serial_number += 1

    print(len(table))
    context={
        "result":result,
        "table":table
    }
    return context


@frappe.whitelist()
def datatable_data():
    Today = frappe.utils.nowdate()
    FilterDate = add_to_date(Today,days=-30)
    inventorylist = frappe.db.get_list('SAP Inventory Report',pluck='name')
    # inventorylist = frappe.db.get_list('SAP Inventory Report', filters={
    #     'created_date': ['>=', FilterDate],
    #     'created_date': ['<=', Today]
    # }, pluck='name')
    print(len(inventorylist),' lenght inventorylist')
    print(inventorylist,'inventorylist')
    result = []
    for i in inventorylist:
        print(i)
        doc = frappe.get_doc('SAP Inventory Report', i)
        line_items = []
    
        for table_row in doc.lineitems:
            # print(table_row)
            line_item = {
                'ItemCode': table_row.itemcode,
                'Quantity': table_row.quantity,
                'DistNumber': table_row.distnumber,
                'ItemName':table_row.itemname,
                'WhsCode':table_row.whscode,
                'ExpDate':table_row.expdate,
                'MnfDate':table_row.mnfdate,
                # Add more fields as needed
            }
            line_items.append(line_item)

   
            data = {
                'lineitems': line_items,
                'createddate': doc.created_date
            }
          
        result.append(data)

    return frappe.as_json(result)