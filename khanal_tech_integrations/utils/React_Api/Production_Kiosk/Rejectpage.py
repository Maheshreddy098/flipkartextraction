import frappe
import json
from frappe.utils import add_to_date
from datetime import datetime



# @frappe.whitelist()
# def Production_Reject(ProdID):
#     doc = frappe.get_doc("Production Kiosk", ProdID)
#     doc.status ='Production Rejected'

#     for Expected_Production in doc.expected_output_table:
#         line_items_details_json = json.loads(Expected_Production.line_items_deatils)
#         for SingleList in line_items_details_json:
#             cratenumber = SingleList.get('cratenumber')
#             if cratenumber:
#                 name = f"{Expected_Production.batch_number}-{Expected_Production.item_code}"
#                 except_Crate = frappe.get_doc("Crate Assignment", name)
#                 for single_except_Crate in except_Crate.crate_assignment_table:
#                     if single_except_Crate.crate_no == cratenumber and single_except_Crate.consumed == 1:
#                         return "Message: Consumed crate found with cratenumber: {}".format(cratenumber)
#                     else:
#                         single_except_Crate.unconsumable=1
#                     except_Crate.save()


  


#     for PreProduction in doc.pre_pro_associate_table_tab:
#         # print(PreProduction)
#         crateDoc = frappe.get_doc("Crate Assignment", PreProduction.crate_assignment)
#         for single_item in crateDoc.crate_assignment_table:
#             if single_item.crate_no==PreProduction.crate_number:
#                 single_item.consumed=0

#             crateDoc.save()

#     return "No consumed crate found."



    # for PreProduction in doc.pre_pro_associate_table_tab:
    #     # print(PreProduction)
    #     crateDoc = frappe.get_doc("Crate Assignment", PreProduction.crate_assignment)
    #     for single_item in crateDoc.crate_assignment_table:
    #         if single_item.crate_no==PreProduction.crate_number:
    #             single_item.consumed=0

    #         crateDoc.save()


@frappe.whitelist()
def Production_Reject(ProdID):
    doc = frappe.get_doc("Production Kiosk", ProdID)
    doc.status ='Production Rejected'



    for Expected_Production in doc.expected_output_table:
        name = f"{Expected_Production.batch_number}-{Expected_Production.item_code}"
        if frappe.db.exists("Crate Assignment", name):
            except_Crate = frappe.get_doc("Crate Assignment", name)
            line_items_details_json = json.loads(Expected_Production.line_items_deatils)
            for SingleList in line_items_details_json:
                cratenumber = SingleList.get('cratenumber')
                if cratenumber:
                    for single_except_Crate in except_Crate.crate_assignment_table:
                        if single_except_Crate.crate_no == cratenumber:
                            if (single_except_Crate.consumed == 1):
                                # crate_marked = True
                                print('The output crate has already been assigned to another production order as input and hence this production order cannot be rejected')
                                return {"status": "Error", "message": 'The output crate has already been assigned to another production order as input and hence this production order cannot be rejected.'}
                                # break
                            else:
                                single_except_Crate.unconsumable = 1
                                except_Crate.save()
                                return {"status": "Success", "message": 'One of the Crate is assigned  to another production order as input and hence this production order.'}

            # if not crate_marked:
            #     except_Crate.save()
            #     print(crate_marked,'crate_marked')
                


    for PreProduction in doc.pre_pro_associate_table_tab:
        crateDoc = frappe.get_doc("Crate Assignment", PreProduction.crate_assignment)
        for single_item in crateDoc.crate_assignment_table:
            if single_item.crate_no == PreProduction.crate_number:
                single_item.consumed = 0
        crateDoc.save()


    doc.save()

    return {"status": "Success", "message": 'Production order rejected successfully.'}
    # return "No consumed crate found."





# bench --site dev.localhost execute --args "{'PID-0689'}"  khanal_tech_integrations.utils.React_Api.Production_Kiosk.Rejectpage.Production_Reject