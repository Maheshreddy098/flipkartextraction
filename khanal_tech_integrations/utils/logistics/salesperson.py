from xml.dom.expatbuilder import parseString
import requests
import json
import frappe
from frappe.utils import add_to_date, now, get_datetime, now_datetime
import re

from khanal_tech_integrations.utils.sap import AuthenticateSAPB1

headersList = {
                "Accept": "*/*",
                "User-Agent": "Khanal Tech",
                "Content-Type": "application/json" 
            }

@frappe.whitelist()
def get_Salespersons():
    session = AuthenticateSAPB1()
    for i in range(5):
        doc_settings = frappe.get_doc('SAP Settings')
        reqUrl = doc_settings.sap_b1_url+"SalesPersons?$skip="  + str(20*i) 
        payload = ""

        headersList = {
                "Accept": "*/*",
                "User-Agent": "Thunder Client (https://www.thunderclient.com)",
                "Content-Type": "application/json" 
            }
        response = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
        all_people = dict(response.json())
        
        try:
            if all_people['value'] is not None:
                for Single_salesperson in all_people['value']:
                    doc = frappe.new_doc('SAP Salesperson')
                    doc.salesperson_code        = Single_salesperson["SalesEmployeeCode"]
                    doc.salesperson_name        = Single_salesperson["SalesEmployeeName"]
                    doc.employee_id             = Single_salesperson["EmployeeID"]
                    doc.reporting_manger_code   = Single_salesperson["Fax"] #Reportingmanger-code
                    doc.mobile                  = Single_salesperson["Mobile"]
                    doc.email                   = Single_salesperson["Email"]
                    print(Single_salesperson["SalesEmployeeName"])
                    doc.save()
                    frappe.db.commit()
                    try:
                            #try saving, skip if already exist
                        doc.save()
                        frappe.db.commit() #
                    except frappe.DuplicateEntryError:
                        pass
            elif all_people['value'] is None:
                break
        except Exception as e:
                print(e)

    frappe.msgprint(msg ='Data Inserted successfully',title ='Success')


@frappe.whitelist()
def delete():
    x = 'SAP Salesperson'
    print(len(frappe.get_list(x)))
    for documentt in frappe.get_list(x):
        documentt = frappe.get_doc( x , documentt.name)
        documentt.delete()

# dummy = {
#             "SalesEmployeeCode": -1,
#             "SalesEmployeeName": "-No Sales Employee-",
#             "Remarks": null,
#             "CommissionForSalesEmployee": 0.0,
#             "CommissionGroup": 0,
#             "Locked": "tYES",
#             "EmployeeID": null,
#             "Active": "tYES",
#             "Telephone": null,
#             "Mobile": null,
#             "Fax": null,
#             "Email": null
#         },