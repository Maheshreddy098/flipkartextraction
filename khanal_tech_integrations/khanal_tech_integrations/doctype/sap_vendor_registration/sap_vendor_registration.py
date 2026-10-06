# Copyright (c) 2023, Khanal Tech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
# from frappe import Document, call

class SAPVendorRegistration(Document):
	pass

    # def validate(self):
    #     # This method will be called when the document is saved/updated
        
    #     # Assuming 'gst_number' is a field in your document
    #     if self.gst_number:
    #         self.check_gst_validity()

    # def check_gst_validity(self):
    #     # Perform GST validity check using the 'frappe.call' method
    #     response = frappe.call("khanal_tech_integrations.utils.vrf.gst_verification.check_gst_validity", self.name)
        
    #     # Process the response as needed
    #     # For example, you might want to raise an exception if GST is invalid, or update some fields based on the response
        
    #     # Example:
    #     if response == "valid":
    #         self.valid_gst = True
    #     else:
    #         self.valid_gst = False

# class SAPVendorRegistration(Document):
#     def validate(self):
#         # Get the document before saving
#     #     previous_doc = self.get_doc_before_save()
        

#     #     # Check if gst_number has changed or is newly added
#     #     if self.is_new() or self.gst_number != (previous_doc.get("gst_number") if previous_doc else None):
#     #         self.trigger_gst_verification()

#     # def trigger_gst_verification(self):
# 	    # frappe.msgprint('changed',self.name)
#         doc_name = self.name
#         response = frappe.call("khanal_tech_integrations.utils.vrf.gst_verification.check_gst_validity", doc_name)
#         # You can process the response as needed
#         # For example: print("Response from frappe.call:", response)


# # class SAPVendorRegistration(Document):
# #     def onload(self):
# #         doc_name = self.name
# #         response=frappe.call("khanal_tech_integrations.utils.vrf.gst_verification.check_gst_validity", doc_name)
# # 		# response = frappe.call("khanal_tech_integrations.utils.vrf.gst_verification.check_gst_validity", {"data": self.gst_number})
        
# #         # print("Response from frappe.call:", response)
# # 		# return

