# Copyright (c) 2023, Khanal Tech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
import json
from frappe import _
import os
import requests
from datetime import datetime
from frappe.utils import add_to_date
from khanal_tech_integrations.utils.safexpress.automated_invoice_attach import Saved_InvDoc

headersList = {
        "Accept": "*/*",
        "User-Agent": "Khanal Tech",
        "Content-Type": "application/json" ,
         "Prefer": "odata.maxpagesize=900",
    }

payload={}

TransportationCodeDict={
	"SafeExpress": 1,
	"DP World": 2,
	"Delhivery": 3,
	"Local delivery partner": 4,
	"Platform Fulfilled": 5
	}
class SAPARInvoiceDetail(Document):
    def before_save(self):
        if not self.is_new():
            if frappe.db.exists("SAP AR Invoice Detail", self.name):
                # if not self.way_bill_number:
                #     frappe.throw("The 'way_bill_number' field is mandatory when updating the document.")

                if self.shipping_status == 'Pending' and self.shipping_charges :
                    # Trigger the Patch_ShippingCost function
                    response = Patch_ShippingCost(self)
                    if response.status_code == 204:
                        self.shipping_status = 'Completed'
                    else:
                        # Throw an error if the response status code is not 204
                        frappe.throw(f"Failed to update shipping cost. Error: {response.text} (Status Code: {response.status_code})")
                    print(f"Patch Response: {response}")

                # Get the original value of pod_url
                # original_pod_url = frappe.db.get_value("SAP AR Invoice Detail", self.name, "pod_url")

                if self.pod_status == 'Pending' and self.pod_url:
                    print(self.pod_status, self.pod_url, 'self.pod_status, self.pod_url', '\n')
                    # Trigger the Update_pod_url function and get the POD link
                    PodLink = Update_pod_url(self)
                    # Trigger the Patch_POD_Link function
                    patch_response = Patch_POD_Link(self, PodLink)
                    if patch_response.status_code == 204:
                        self.pod_status = 'Completed'
                        # pass
                    else:
                        # Throw an error if the response status code is not 204
                        frappe.throw(f"Failed to update POD link. Error: {patch_response.text} (Status Code: {patch_response.status_code})")
                    print(f"POD URL: {PodLink}")

            else:
                # Handle the case where the document is not found
                frappe.throw(f"Document not found: {self.name}")


# bench --site dev.localhost execute  --args "{ '01-01-2024' }"  khanal_tech_integrations.khanal_tech_integrations.doctype.sap_ar_invoice_detail.sap_ar_invoice_detail.Add_Status_Cancelled



def Add_Status_Cancelled(Date):  # Example: '28-09-2023'
    # Ensure that Date is a datetime.date object
    if isinstance(Date, str):
        Date = datetime.strptime(Date, '%d-%m-%Y').date()

    # Fetch documents with 'shipping_status' as 'Pending' and 'doc_date' <= Date
    doclist = frappe.db.get_list(
        'SAP AR Invoice Detail',
        filters={
            'shipping_status': 'Pending',
            'doc_date': ['<=', Date]
        },
        pluck='name'
    )

    print(len(doclist), 'Documents to be updated')

    # Update 'shipping_status' to 'Cancelled' for each document
    for doc_name in doclist:
        frappe.db.set_value('SAP AR Invoice Detail', doc_name, 'shipping_status', 'Cancelled')

    # Optionally commit the changes if necessary
    frappe.db.commit()

    print(len(doclist), 'Length')
    # print(doclist, 'Documents')

def Patch_ShippingCost(self):
	print('**'*10)
	session = AuthenticateSAPB1()
	doc_settings = frappe.get_doc('SAP Settings')
	Url                     = doc_settings.sap_b1_url+"Invoices({Docentry})"
	reqUrl_modified         = Url.format(Docentry=self.name)        
	transport_code = TransportationCodeDict.get(self.transporter_type)
	if transport_code is None:
		frappe.throw(f"Unknown transporter type '{self.transporter_type}' — cannot determine SAP TransportationCode.")
	payload = json.dumps(
		{
			"U_ShippingCost": self.shipping_charges,
			"TransportationCode": transport_code,
			"U_TN": self.transporter_type,
			"U_TrackingNo": self.way_bill_number,
		}
	)
	response = session.request("PATCH", reqUrl_modified, headers=headersList, data=payload,verify=False)
	# print(response.text,'response')
	# print(response.status_code,'response')
	return response


def Update_pod_url(self):

	base_url = frappe.utils.get_url()

	if not self.pod_url or "amazonaws.com" in self.pod_url:
		# Already an S3 URL — nothing to migrate
		return self.pod_url

	file_url=base_url + self.pod_url
	file_name = os.path.basename(self.pod_url)
	filename, extension = os.path.splitext(file_name)
	unique_filename = f"{self.name}_PodFile{extension}"

	file_extension = file_url.split('.')[-1]
	lowercase_extension = file_extension.lower()

	response = requests.get(file_url)
	response.raise_for_status()  # Raise exception for non-200 response

	content = response.content
	aws_upload_url = "https://tg31l9q380.execute-api.us-west-1.amazonaws.com/dev/khanalfoods-fileupload-bucket/"+file_name #!Live
	content_type_dict = {
	'pdf': 'application/pdf',
	'jpg': 'image/jpeg',
	'jpeg': 'image/jpeg',
	'png': 'image/png',
	'ppt': 'application/vnd.ms-powerpoint',
	'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
	'doc': 'application/msword',
	'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
	}
	content_type = content_type_dict.get(lowercase_extension, 'application/octet-stream')
	headers = {'Content-Type': content_type}
	aws_response = requests.put(aws_upload_url, headers=headers, data=content)
	aws_response.raise_for_status()  # Raise exception for upload failure
	
	# File_url='https://testingbucketsample.s3.eu-north-1.amazonaws.com/'+file_name #!Test
	File_url='https://khanalfoods-fileupload-bucket.s3.us-west-1.amazonaws.com/'+file_name #!Live


	self.pod_url=File_url

	return File_url
	   

	
		
def Patch_POD_Link(self,PodLink):
	session = AuthenticateSAPB1()
	doc_settings = frappe.get_doc('SAP Settings')
	Url                     = doc_settings.sap_b1_url+"Invoices({Docentry})"
	reqUrl_modified         = Url.format(Docentry=self.name)        
	transport_code = TransportationCodeDict.get(self.transporter_type)
	if transport_code is None:
		frappe.throw(f"Unknown transporter type '{self.transporter_type}' — cannot determine SAP TransportationCode.")
	payload = json.dumps(
		{
			"U_Pod_Link": PodLink,
			"TransportationCode": transport_code,
			"U_TN": self.transporter_type,
			"U_TrackingNo": self.way_bill_number,

		}
	)
	response = session.request("PATCH", reqUrl_modified, headers=headersList, data=payload,verify=False)
	print(response.text,'response')
	print(response.status_code,'response')
	return response


# def Set_to_Public(doc, method):

#     if doc.is_private == 1:        
#         # Set the file to public
#         doc.is_private = 0
#         doc.insert(
# 			ignore_permissions=True, 
# 			ignore_links=True,
# 			ignore_if_duplicate=True,
# 			ignore_mandatory=True
# 		)
        
def Set_to_Public(doc, method):
    print(doc.attached_to_doctype,'doc.attached_to_doctype')
    # Check if the document's attached_to_doctype is one of the specified values
    if doc.attached_to_doctype in ['SAP AR Invoice Detail', 'SAP Vendor Registration']:
        if doc.is_private == 1:
            # Set the file to public
            doc.is_private = 0
            
            # Use save() method to update the existing document
            doc.insert( 
				ignore_permissions=True, 
				ignore_links=True,
				ignore_if_duplicate=True,
				ignore_mandatory=True
				)
            
            # Commit changes to the database
            # frappe.db.commit()




# bench --site khanaltech.com execute  --args "{ '30' }"  khanal_tech_integrations.khanal_tech_integrations.doctype.sap_ar_invoice_detail.sap_ar_invoice_detail.Fetch_Ar_InvoiceDetails


@frappe.whitelist()
def Fetch_Ar_InvoiceDetails(Day):
    session = AuthenticateSAPB1()
    Today = frappe.utils.nowdate()
    FilterDate = add_to_date(Today,days=-int(Day))
    print(FilterDate,'FilterDate')

    doc_settings = frappe.get_doc('SAP Settings')
    # reqUrl = doc_settings.sap_b1_url+"BusinessPartners?$filter(UpdateDate ge '{FilterDate}')" 
    req_url = f"{doc_settings.sap_b1_url}Invoices?$filter=UpdateDate ge '{FilterDate}' and GSTTransactionType eq 'gsttrantyp_GSTTaxInvoice'"

    # Modified_count_url = reqUrl.format(FilterDate=FilterDate)
    response = session.request("GET", req_url, data=payload,  headers=headersList,verify=False)
    inv_master = dict(response.json())
    # print (inv_master)
    
    # for i in range(1,2):
    while inv_master.get('odata.nextLink', None):
        update_inv_master(inv_master)
        print (inv_master['odata.nextLink'])
        next_url = doc_settings.sap_b1_url+inv_master['odata.nextLink']
        response = session.request("GET", next_url, data=payload, headers=headersList, verify=False)
        inv_master = dict(response.json())
        
    update_inv_master(inv_master)

def update_inv_master(inv_master):

    for i in range(len(inv_master['value'])):
        inv_DocEntry = inv_master['value'][i]['DocEntry']
        # print(inv_master['value'][i],'inv_DocEntry')
        if frappe.db.exists("SAP AR Invoice Detail", inv_DocEntry):
            print('present DocEntry',inv_DocEntry)
        else:
            print('not present DocEntry',inv_DocEntry)
            Saved_InvDoc(inv_master['value'][i])

    pass