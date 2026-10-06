# Copyright (c) 2024, Khanal Tech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
import json


class CustomerDebitNotes(Document):
	def before_save(self):
		if self.sap_customer_code:
			customer = frappe.db.get_value('Customer', {'custom_sap_customer_code': self.sap_customer_code}, 'name')
			if customer:
				self.customer_name = customer
			else:
				frappe.throw(f"No customer found with SAP customer code: {self.sap_customer_code}")
		if self.credit_note_line_item_details:
			channel = self.customer_name
			#  Update the Line Item SAP codes based on customer sku code
			for line in self.credit_note_line_item_details:
				# print (channel)
				if "flipkart" in channel.lower():
					item = frappe.db.get_value('SAP ItemCode Marketplace Mapping', {'flipkart_fsn': line.customers_sku}, 'sap_item_code')
					line.sap_item_code = item
					# print (item)
			# 	item = frappe.db.get_value('Item', {'item_code': line.item_code}, 'name')
			# 	if item:
			# 		line.item_name = item
			# 	else:
			# 		frappe.throw(f"No item found with item code: {line.item_code}")
			# self.total_amount = sum([row.amount for row in self.credit_note_line_item_details])


@frappe.whitelist()
def post_cn_to_sap(name):
	doc = frappe.get_doc('Customer Debit Notes', name)
	# frappe.msgprint(f"Posting Customer Debit Note {doc.name} to SAP.")
	 
	if doc.sap_customer_code:
		session = AuthenticateSAPB1()
		headersList = {
			"Accept": "*/*",
			"User-Agent": "Khanal Tech",
			"Content-Type": "application/json",
			"Prefer": "odata.maxpagesize=100",
		}
		payload = ''
		# print (doc.original_invoice_number.split('/')[1])
		reqUrl = frappe.get_doc('SAP Settings').sap_b1_url + "Invoices" + "?$filter=DocNum eq " + \
					doc.original_invoice_number.split('/')[1] + 'and CardCode eq' + "'" +doc.sap_customer_code + "'"
		response = session.request("GET", reqUrl, data=payload, headers=headersList, verify=False)
		ar_invoice = dict(response.json())
		
		if ar_invoice.get('value', None) and len(ar_invoice['value']) == 1:
			ar_inv = ar_invoice['value'][0]
			
			# doc_entry = ar_invoice['value'][0]['DocEntry']
			# payload = {
			# 	"CardCode": doc.sap_customer_code,
			# 	"DocDate": doc.cn_posting_date.strftime('%Y-%m-%d'),
			# 	"DocDueDate": doc.due_date.strftime('%Y-%m-%d'),
			# 	"TaxDate": doc.document_date.strftime('%Y-%m-%d'),
			# 	"DocCurrency": "INR",
			# 	# "Comments": doc.reason_for_credit,
			# 	# "JournalMemo": doc.reason_for_credit,
			# 	# "PaymentGroupCode": -1,
			# 	"Series": 199, #KACN23 || 350 KACN24
			# 	"DocType": "S",
			# 	# "PaymentTerms": ar_inv['PaymentTerms'],
			# 	"DocObjectCode": "13",

			# 	# "DocTotal": doc.total_amount,
			# 	# "DocTotalFC": doc.total_amount,
			# 	# "DocRate": 1,
			# 	# "DocEntry": doc_entry,
			# 	"DocumentLines": []
			# }
			
			# if doc.dn_type == 'Quantity Return Debit Note':
			# 	IssuingReason = 3
			# 	ReturnReason = "Short Supply",
			# if doc.dn_type == 'Price Difference Debit Note':
			# 	IssuingReason = 4
			# 	ReturnReason = "Price Variance",
				# 1 - Sales Return
				# 2 - Post sale discount
				# 3 - Deficiency in service
				# 4 - Correction in invoice
				# 5 - Change in POS
				# 6 - Finalization of Provisional Assessment
				# 7 - Others
			payload = {
						"DocType": "dDocument_Items",
						# "HandWritten": "tNO",
						"DocDate": doc.cn_posting_date.strftime('%Y-%m-%d'),
						"DocDueDate": doc.due_date.strftime('%Y-%m-%d'),
						"TaxDate": doc.document_date.strftime('%Y-%m-%d'), # Document Date
						"CardCode": doc.sap_customer_code,
						"NumAtCard": doc.customers_dn_number, # Reference
						"DocCurrency": "INR",
						"DocObjectCode":14, # 14 for AR Credit Memo
						# "Confirmed": "tYES",
						"Series": 350, # 350 for AR Credit Memo KACN24
						# // "TaxExemptionLetterNum": null,
						"DocumentSubType": "bod_GSTTaxInvoice",
						# "PeriodIndicator": "FY2425",
						# // "AuthorizationStatus": "dasWithout",
						# // "RelevantToGTS": "tNO",
						# // "BPLName": null,
						# // "VATRegNum": null,
						# // "PriceMode": null,
						# // "Revision": "tNO",
						# //"IssuingReason": IssuingReason,
						"OriginalRefNo": ar_inv['DocNum'],
						"OriginalRefDate": ar_inv['DocDate'],
						"GSTTransactionType": "gsttrantyp_GSTTaxInvoice",
						"UseBillToAddrToDetermineTax": "tYES",
						"DocumentLines": []
						# "DocumentLines": [
						# 	{
						# 		"ItemCode": "FGHN0022",
						# 		# "ItemDescription": "HN Basmati Rice - 5KG",
						# 		"Quantity": 1.0,
						# 		# // "ShipDate": "2023-03-29",
						# 		# // "Currency": "INR",
						# 		"BaseType": 13,
						# 		"BaseEntry": 18562,
						# 		"BaseLine": 2,
								
						# 		# // "TaxCode": "KAIG5",
						# 		# // "TaxType": "tt_Yes",
						# 		# // "TaxLiable": "tYES",
						# 		# // "PickStatus": "tNO",
						# 		# // "PickQuantity": 0.0,
						# 		# // "PickListIdNumber": null,
						# 		# // "OriginalItem": null,
						# 		# // "BackOrder": "tYES",
						# 		# "FreeText": "",
								
						# 		# // "EqualizationTaxPercent": 0.0,
						# 		# // "TotalEqualizationTax": 0.0,
						# 		# // "TotalEqualizationTaxFC": 0.0,
						# 		# // "TotalEqualizationTaxSC": 0.0,
						# 		# // "NetTaxAmount": 29.28550,
						# 		# // "NetTaxAmountFC": 0.0,
						# 		# // "NetTaxAmountSC": 29.28550,
						# 		# // "MeasureUnit": "Pcs",
						# 		# // "UnitsOfMeasurment": 1.0,
						# 		# // "LineTotal": 585.710,
						# 		# // "TaxPercentagePerRow": 5.0,
						# 		# // "TaxTotal": 29.28550,
								
						# 		# // "PickStatusEx": "dlps_NotPicked",
						# 		# // "TaxBeforeDPM": 0.0,
						# 		# // "TaxBeforeDPMFC": 0.0,
						# 		# // "TaxBeforeDPMSC": 0.0,
						# 		# // "CFOPCode": null,
						# 		# // "CSTCode": null,
						# 		# // "Usage": null,
						# 		# // "TaxOnly": "tNO",
								
						# 		//"LineType": "dlt_Regular",
						
						# 		# // "LocationCode": 5,
								
						# 		"WithoutInventoryMovement": "tYES",
						# 		# // "AgreementNo": null,
						# 		# // "AgreementRowNumber": null,
						# 		# // "ActualBaseEntry": null,
						# 		# // "ActualBaseLine": null,
						# 		# // "DocEntry": 4710,
								
						# 		"ConsiderQuantity": "tNO"
								
						# 	},
						# ]
					}

			
			for line in doc.credit_note_line_item_details:
				# get the base line from the original invoice based on the item code
				BaseLine = get_line_num(item_code=line.sap_item_code,lines_data=ar_inv['DocumentLines']) 

				line_dict = {
					"ItemCode": line.sap_item_code,
					"Quantity": line.quantity,
					"Currency": "INR",
					"BaseType": 13,
					"BaseEntry": ar_inv['DocEntry'],
					"BaseLine": BaseLine,
					"LineType": "dlt_Regular",
					"WithoutInventoryMovement": "tYES",
					"ConsiderQuantity": "tNO"
					# //"ReturnReason": ReturnReason
				}

				if line.rate_variance:
					line_dict["Price"] = line.rate_variance

				payload['DocumentLines'].append(line_dict)
			
		print (payload)
		
		# reqUrl = frappe.get_doc('SAP Settings').sap_b1_url + "CreditNotes"
		reqUrl = frappe.get_doc('SAP Settings').sap_b1_url + "Drafts"
		response = session.request("POST", reqUrl, data=json.dumps(payload), headers=headersList, verify=False)
		print (response.text)
		
		doc.original_invoice_docentry = ar_inv['DocEntry']
		doc.response_json = response.text
		doc.posted_json = json.dumps(payload,indent=4)
		doc.save()
		if response.status_code == 201:
			frappe.msgprint(f"Customer Debit Note {doc.name} posted to SAP.")
		else:
			frappe.throw(f"Error posting Customer Debit Note {doc.name} to SAP. {response.text}")
		# sap_customer = frappe.get_doc('SAP Customer', doc.sap_customer_code)


# Get the line number from the original invoice
# item_code = "FGHN0015", lines_data = data["DocumentLines"]
def get_line_num(item_code,lines_data):
    for line in lines_data:
        if line["ItemCode"] == item_code:
            return line["LineNum"]
    return None