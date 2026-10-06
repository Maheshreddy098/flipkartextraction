from email.header import decode_header
from datetime import datetime
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
from botocore.exceptions import NoCredentialsError
import frappe
import re
import email
import imaplib
import io
import boto3
from difflib import SequenceMatcher
import requests
import json
import pandas as pd  
import os

headersList = {
    "Accept": "*/*",
    "User-Agent": "Khanal Tech",
    "Content-Type": "application/json",
    "Prefer": "odata.maxpagesize=100"
}
payload = ''


@frappe.whitelist()
def process_email_attachments():
    # Email Configuration
    if frappe.get_single("B2B_EMAIL"):
        email_record = frappe.db.get_value(
            "B2B_EMAIL", 
            None, 
            ["EMAIL", "PASSWORD", "IMAP_SERVER", "IMAP_PORT", "LABEL_NAME"], 
            as_dict=True
        )
        
        if email_record:
            EMAIL = email_record.get('email')
            PASSWORD = email_record.get('password')
            IMAP_SERVER = email_record.get('imap_server')
            IMAP_PORT = email_record.get('imap_port') or 993  # Default to 993 if not set
            LABEL_NAME = "Bigbasket"
        else:
            frappe.throw("Email record not found in the database.")
    else:
        print("Table 'B2B_EMAIL' does not exist.")
        frappe.throw("Email table does not exist.")
    
     # Fetch CardCode and SalesPersonCode from B2B-Customer-Details
    customer_details_record = frappe.db.get_value(
        "B2B_Customer_Details", 
        None, 
        ["cardcode4", "salespersoncode4"], 
        as_dict=True
    )
    
    if customer_details_record:
        CardCode = customer_details_record.get('cardcode4')
        SalesPersonCode = customer_details_record.get('salespersoncode4')
        # print("CardCode:", CardCode)    
    else:
        frappe.throw("Customer details record not found in the database.")


    def connect_to_email():
        """Connect to the email server."""
        print("Connecting to email server...")
        try:
            mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
            mail.login(EMAIL, PASSWORD)
            print("Connected to email server.")
            return mail
        except imaplib.IMAP4.error as e:
            frappe.throw(f"IMAP login failed: {str(e)}")
        except ConnectionRefusedError as e:
            frappe.throw(f"Connection refused: {str(e)}. Please check the IMAP server and port.")
        except Exception as e:
            frappe.throw(f"An error occurred while connecting to the email server: {str(e)}")

    def fetch_email_subject(mail, email_uid):
        """Fetch the email subject directly from the email server."""
        try:
            status, msg_data = mail.uid('fetch', email_uid, '(RFC822)')
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        # Decode bytes to string
                        subject = subject.decode(encoding if encoding else "utf-8")
                    print(f"Fetched Email Subject: {subject}")  # Debugging
                    return subject
        except Exception as e:
            print(f"Error fetching email subject for UID {email_uid}: {str(e)}")
            return None


    def extract_po_details(xls_data):
        """Extract PO details from xls, xlsx, or HTML disguised as xls data."""
        try:
            # Detect file format and use the appropriate engine
            try:
                # Try reading as an XML-based .xlsx file
                xls_data = pd.read_excel(io.BytesIO(xls_data), sheet_name=None, engine='openpyxl')
            except Exception:
                # Fallback to reading as a binary .xls file
                xls_data = pd.read_excel(io.BytesIO(xls_data), sheet_name=None, engine='xlrd')
            
            extracted_data = {}  # Dictionary to store extracted details
            
            for sheet_name, df in xls_data.items():
                print(f"\n--- Processing Sheet: {sheet_name} ---")
                
               
                
                # Initialize variables for PO Number, PO Expiry Date, and Warehouse Address
                po_number = None
                po_expiry_date = None
                filtered_address = None
                
                # Extract "PO Number"
                po_number_row = df[df.apply(lambda row: row.astype(str).str.contains("PO Number", case=False).any(), axis=1)]
                if not po_number_row.empty:
                    po_number = po_number_row.iloc[0].dropna().to_string(index=False)
                    po_number = re.search(r"PO Number[:\s]*(\S+)", po_number)  # Extract only the PO Number
                    if po_number:
                        extracted_data["PO Number"] = po_number.group(1)  # Store the cleaned PO Number
                
                # Extract "PO Expiry date"
                po_expiry_date_row = df[df.apply(lambda row: row.astype(str).str.contains("PO Expiry date", case=False).any(), axis=1)]
                if not po_expiry_date_row.empty:
                    po_expiry_date = po_expiry_date_row.iloc[0].dropna().to_string(index=False)
                    po_expiry_date = po_expiry_date.split("PO Expiry date:")[1].strip() if "PO Expiry date:" in po_expiry_date else po_expiry_date
                    po_expiry_date = datetime.strptime(po_expiry_date, "%d/%b/%Y").strftime("%Y-%m-%d")  # Convert to YYYY-MM-DD format
                    extracted_data["PO Expiry Date"] = po_expiry_date
                
                # Extract "Warehouse Address" and filter the required portion
                warehouse_address_rows = df[df.apply(lambda row: row.astype(str).str.contains("Warehouse Address", case=False).any(), axis=1)]
                if not warehouse_address_rows.empty:
                    start_index = warehouse_address_rows.index[0]
                    address_block = df.iloc[start_index:start_index + 10].iloc[:, 0].dropna().astype(str).str.strip()  # Fetch up to 10 rows for safety
                    address_list = address_block.tolist()

                    # Extract rows until a pincode (6-digit number) is found
                    filtered_address = []
                    for line in address_list:
                        filtered_address.append(line)
                        if re.search(r'\b\d{6}\b', line):  # Stop if a pincode is found
                            break

                    extracted_data["Warehouse Address"] = "\n".join(filtered_address)
                
                # Extract table data
                table_start_row = df[df.apply(lambda row: row.astype(str).str.contains(r"\b(s(\.?|l)?\.?\s?no)\b", case=False).any(), axis=1)].index
                if not table_start_row.empty:
                    start_index = table_start_row[0]
                    table_data = df.iloc[start_index + 1:].dropna(how='all')  # Drop empty rows after the header
                    
                    # Set the first row as the header for the table
                    table_data.columns = df.iloc[start_index]
                    table_data = table_data.reset_index(drop=True)
                    
                    # Stop processing when the "Total" row is encountered
                    total_row_index = table_data[table_data.apply(lambda row: row.astype(str).str.contains("Total", case=False).any(), axis=1)].index
                    if not total_row_index.empty:
                        total_index = total_row_index[0]
                        table_data = table_data.iloc[:total_index]  # Keep rows only up to the "Total" row
                    
                    # Convert the table to JSON
                    table_json = table_data.to_json(orient="records")
                    extracted_data["Table Data"] = json.loads(table_json)  # Store table data as a list of dictionaries
                
                # Stop processing further sheets after fetching all required details
                if po_number or po_expiry_date or filtered_address:
                    break
            
            return extracted_data  # Return the extracted details
            
        except ImportError:
            print("Run: pip install openpyxl xlrd beautifulsoup4 pandas lxml")
        except Exception as e:
            print(f"An error occurred: {e}")
            return None


    def save_pdf_to_file(xls_data,extracted_data ):
        """Save the PDF to S3 inside a dynamically set folder."""
        # print("Saving PDF to S3...")
        # print(f"Extracted Data:.....")
        # print(f"xls_data: {xls_data}")
        po_number = extracted_data.get("PO Number")
        # print(f"PO Number: {po_number}")  
        if not po_number or po_number == "Not Found":
            po_number = "Unknown_PO"

        # Fetch AWS credentials, bucket name, and folder name
        if frappe.get_single("AWS"):
            aws_record = frappe.db.get_value(
                "AWS", None, 
                ["aws_access_key_id", "aws_secret_access_key", "bucket_name", "folder_insta"], 
                as_dict=True
            )

            if aws_record:
                aws_access_key_id = aws_record.aws_access_key_id.strip()
                aws_secret_access_key = aws_record.aws_secret_access_key.strip()
                bucket_name = aws_record.bucket_name.strip()
                folder_name = (aws_record.folder_insta or "Bigbasket").strip().strip('/')
            else:
                frappe.throw("AWS record not found in the database.")
        else:
            frappe.throw("AWS table does not exist.")

        # Initialize the S3 client
        s3 = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key
        )

        file_name = f"{folder_name}/Bigbasket_{po_number}.xls"  # Ensure proper path format

        try:
            # Upload the PDF to S3 inside the dynamic folder
            s3.put_object(Bucket=bucket_name, Key=file_name, Body=xls_data)

            # Construct the correct file URL
            file_url = f"https://{bucket_name}.s3.amazonaws.com/{file_name}"

            # print(f"PDF uploaded successfully: {file_url}")
            return file_url

        except NoCredentialsError:
            print("Credentials not available for accessing AWS S3")
            return None


    @frappe.whitelist()
    def fetch_item_sap_mapping():
        # print("Fetching Itemmap records...")
        item_sap_map = []
        
        # Fetch all Itemmap2 documents
        itemmap_records = frappe.get_all('Itemmap4')
        # print(f"Found {len(itemmap_records)} Itemmap4 records")
        
        for record in itemmap_records:
            itemmap_doc = frappe.get_doc("Itemmap4", record.name)
            if hasattr(itemmap_doc, "map_item") and itemmap_doc.map_item:
                for mapping in itemmap_doc.map_item:
                    item_sap_map.append({
                        'item_code': str(mapping.item_code).strip(),  # Ensure string and clean whitespace
                        'sap_code': str(mapping.sap_code).strip()
                    })
        
        # print("Mapped Items:", item_sap_map)
        return item_sap_map


    def move_email_to_processed(mail, email_uid):
        """Move an email to the Bigbasket-Processed folder using IMAP UIDs."""
        try:
            # Ensure the "Blinkit-Processed" folder exists
            mail.create('Bigbasket-Processed')
        except imaplib.IMAP4.error:
            pass  # Folder already exists, no need to create it

        try:
            # Copy the email using UID
            copy_result = mail.uid('copy', email_uid, 'Bigbasket-Processed')
            if copy_result[0] == 'OK':
                # Mark the original email for deletion using UID
                store_result = mail.uid('store', email_uid, '+FLAGS', '\\Deleted')
                if store_result[0] == 'OK':
                    mail.expunge()  # Permanently delete the email
                    # print(f"Moved email UID {email_uid} to Bigbasket folder.")
                    return True
                else:
                    print(f"Failed to mark email UID {email_uid} as deleted: {store_result}")
                    return False
            else:
                print(f"Failed to copy email UID {email_uid}: {copy_result}")
                return False
        except Exception as e:
            print(f"Error moving email UID {email_uid}: {str(e)}")
            return False




    @frappe.whitelist()
    def itemmaster(extracted_data, code_sheet_data):
        """Fetch from item master using a list of item codes, mapping to SAP codes."""
        # print("Received excel data:")
        doc_settings = frappe.get_doc('SAP Settings')
        session = AuthenticateSAPB1()
        payload = ''
        data = []  # Use `data` instead of `results`

        # Convert list to dict if needed
        if isinstance(code_sheet_data, list):
            code_sheet_data = {item['item_code']: item['sap_code'] for item in code_sheet_data}

        item_to_sap_map = code_sheet_data

        # Get the items from extracted_data
        items_list = extracted_data.get("Table Data", [])
        po_number = extracted_data.get("PO Number", "N/A")  # Extract PO Number for error reporting
        # print("Items List:", items_list)
        

        for item in items_list:
            # Use the correct key for item_code (SkuCode)
            item_code = str(item.get("SkuCode") or item.get("SKU Code")).strip()  # Handle both "SkuCode" and "SKU Code"
            # print(f"Processing item code: {item_code}")
            if not item_code:
                print("Skipping item with missing 'SkuCode'.")
                continue

            sap_code = item_to_sap_map.get(item_code)
            # print(f"Item code: {item_code}, SAP code: {sap_code}")
            if sap_code:
                url = doc_settings.sap_b1_url + f"Items('{sap_code}')"
                try:
                    response = session.request("GET", url, data=payload, headers=headersList, verify=False)

                    if response.status_code == 200:
                        item_data = response.json()
                        result_entry = {
                            "ItemCode": item_code,
                            "SAPCode": sap_code,
                            "ItemName": item_data.get('ItemName', 'N/A'),
                            "U_TaxRate": item_data.get('U_TaxRate', 'N/A'),
                            "U_GstTax": item_data.get('U_GstTax', 'N/A'),
                            "U_IgstTax": item_data.get('U_IgstTax', 'N/A')
                        }
                        # print(f"Result Entry: {result_entry}")  # Print each result entry
                        data.append(result_entry)  # Append to `data`
                    else:
                        print(f"Error fetching data for SAP code {sap_code} (Item code {item_code}): {response.text}")
                except Exception as e:
                    print(f"Exception occurred while fetching data for SAP code {sap_code} (Item code {item_code}): {e}")
            else:
                print(f"No mapping found for item code {item_code}, skipping...")

        if data:
            # print(f"Final Data: {data}")  # Print the final data list
            return data  # Return `data` directly
        else:
            error_message = "No matching records found for any item codes."
            print(error_message)
            frappe.log_error(error_message)
            send_error_email(po_number, error_message)  # Send error email with PO Number and error message
            return None


    @frappe.whitelist()
    def Get_CustomerDetails(CardCode, extracted_data):
        try:
            
            # print(f"CardCode:",CardCode)

            def similar(a, b):
                return SequenceMatcher(None, a.lower(), b.lower()).ratio()

            # Extract PO No and Main Address from item_list
            po_number = extracted_data.get("PO Number")
            delivered_to = extracted_data.get("Warehouse Address", "")
            print(f"PO Number: {po_number}")
            # print(f"Delivered To (raw): {delivered_to}")

            zip_match = re.search(r'\b\d{6}\b', delivered_to)
            delivered_zip = zip_match.group() if zip_match else None
            # print(f"Extracted ZIP code: {delivered_zip}")

            address_entries = []
            ada_docs = frappe.get_all("ADA_4", fields=["name"])
            for ada_doc in ada_docs:
                ada_record = frappe.get_doc("ADA_4", ada_doc.name)
                if hasattr(ada_record, "address_table4") and ada_record.address_table4:
                    for address in ada_record.address_table4:
                        address_entries.append({
                            'address_id': address.address_id, 
                            'address_entry': address.address_entry
                        })
            # print("Address Entries.............")
            # print(f"Address Entries: {address_entries}")

            best_match = None
            max_similarity = 0
            for entry in address_entries:
                similarity_score = similar(delivered_to, entry['address_entry'])
                if similarity_score > max_similarity:
                    max_similarity = similarity_score
                    best_match = entry

            if best_match and max_similarity > 0.6:
                matched_address_id = best_match['address_id']
                # print(f"Best Matching Address ID: {matched_address_id} with similarity {max_similarity}")
            else:
                return {'Status': 'Error', 'Message': "No sufficiently similar address entry found."}

            # Fetch SAP Customer Details
            try:
                # print("Fetching SAP Settings...")
                doc_settings = frappe.get_doc('SAP Settings')

                # print("Authenticating with SAP B1...")
                session = AuthenticateSAPB1()

                Url = doc_settings.sap_b1_url + f"BusinessPartners?$filter=CardCode eq '{CardCode}'"
               

                response = session.request("GET", Url, headers=headersList, verify=False)
                # print(f"Response Status: {response.status_code}, Response: {response.text}")

                customer_data = response.json()

                if not customer_data.get('value'):
                    print(f"No customer data found for CardCode: {CardCode}")
                    return {'Status': 'Error', 'Message': f"No customer data found for CardCode: {CardCode}."}

                customer_details = customer_data['value'][0]
                addresses = customer_details.get('BPAddresses', [])
                
                matched_state = None
                matched_address_name = None

                # Check if matched_address_id exists in SAP's AddressName
                for address in addresses:
                    if address.get('AddressName') == matched_address_id:
                        matched_address_name = address.get('AddressName')
                        matched_state = address.get('State')
                        print(f"Matched Address Found: {matched_address_name}, State: {matched_state}")
                        break

                return {
                    'Status': 'Success',
                    'Result': {
                        'CardCode': customer_details.get('CardCode', ''),
                        'CustomerName': customer_details.get('CardName', ''),
                        'Addresses': addresses,
                        'MatchedAddressName': matched_address_name,
                        'MatchedState': matched_state,
                        'SalesPersonCode': customer_details.get('SalesPersonCode', '')
                    }
                }

            except Exception as e:
                print(f"Error in SAP request: {str(e)}")
                return {'Status': 'Error', 'Message': f"Failed to fetch SAP data: {str(e)}"}

        except Exception as e:
            return {'Status': 'Error', 'Message': f"An error occurred: {str(e)}"}




    @frappe.whitelist()
    def process_b2b_data(json_data, email_uid_str):
        """
        Process the JSON data and store it in the Bigbasket doctype.
        """
        try:
            # Ensure json_data is not None
            if not json_data:
                print("Error: JSON data is None or empty.")
                return

            # Ensure json_data is a dictionary (if it's passed as a string, parse it)
            if isinstance(json_data, str):
                json_data = frappe.parse_json(json_data)

            po_number = json_data.get("po_number", "N/A")
            email_id = json_data.get("email_id", "N/A") 
            matched_address = json_data.get("MatchedAddress", {})
            matched_state = json_data.get("MatchedState", None)
            file_url = json_data.get("file_url", "")
            item_data_response = json_data.get("items", [])
            # print(f"Item Data Response: {item_data_response}")
            company_name = json_data.get("CompanyName", "Unknown Company")  # Extract company_name with a default value
            po_expiry_date = json_data.get("expiry_date", "N/A")  # Extract expiry_date with a default value
            customer_code = json_data.get("CardCode", "")  # Extract customer_code
            employee_id = json_data.get("SalesPersonCode", "")  # Extract employee_id
            # Extract "delivered_to" from json_data
            delivered_to = json_data.get("delivered_to", "Unknown Address")
            # print(f"Delivered To: {delivered_to}")
            # Check if Bigbasket doctype exists
            if not frappe.db.table_exists("Bigbasket"):
                print('Doctype "Bigbasket" does not exist.')
                return

            # Check if the record already exists
            existing_record_name = frappe.db.exists("Bigbasket", {"po_number": po_number})
            updated = False

            if existing_record_name:
                # Fetch and print the existing record's data
                existing_record = frappe.get_doc("Bigbasket", existing_record_name)
                print(f"Existing Record Data for P.O. Number {po_number}:")
                # print(frappe.as_json(existing_record))  # Print the existing record as JSON
                
                # Fetch the email subject directly from the email server
                email_subject = fetch_email_subject(mail, email_id)
                # print(f"Email Subject: {email_subject}")  # Debugging

                def is_partial_match(text, keywords):
                    """Check if any keyword partially matches the text."""
                    for keyword in keywords:
                        if SequenceMatcher(None, text.lower(), keyword.lower()).ratio() > 0.6:
                            return True
                    return False

                if email_subject and ("amend" in email_subject.lower() or "revised" in email_subject.lower()):
                    print("Email subject contains 'Amend' or 'Revised'. Proceeding to store in duplicate records.")
                    error_message = f"Email subject contains 'Amend' or 'Revised'. Proceeding to Update records."
                    send_error_email(po_number, error_message, file_url)

                    # Store the existing record in the duplicate records child table
                    duplicate_record = {
                        "record_data": frappe.as_json(existing_record),  # Store the existing record as JSON
                        "docentry": existing_record.get("docentry"),
                        "docnum": existing_record.get("docnum"),
                        "custom_creation": existing_record.get("creation"),  # Use a custom field
                        "custom_modified": existing_record.get("modified"),  # Use a custom field
                        "custom_modified_by": existing_record.get("modified_by"),  # Use a custom field
                        "po_number": existing_record.get("po_number"),
                        "update_status": existing_record.get("update_status"),
                        "sap_status": existing_record.get("sap_status"),
                    }
                    existing_record.append("duplicate_records", duplicate_record)  # Append to the child table

                    # Update the duplicate_records_status field
                    duplicate_count = len(existing_record.duplicate_records)
                    existing_record.duplicate_records_status = f"Amended/{duplicate_count}"

                    # Clear specific fields
                    fields_to_clear = [
                        "docstatus", "docnum", "docentry", "sap_status", "update_status", "document_status"
                    ]
                    for field in fields_to_clear:
                        existing_record.set(field, None)

                    # Clear child table data
                    existing_record.bigbasket_table = []

                    # Save the cleared record
                    existing_record.save()
                else:
                    print(f"Email subject does not contain 'Amended' or 'Revised'. Skipping email UID {email_id}.")
                    error_message = f"Email subject does not contain 'Amended' or 'Revised'. Skipping email UID {email_id}."

                    # Send error email
                    send_error_email(po_number, error_message, file_url)
                    print("djbvcdfhvfh")
                    return  # Skip processing this email

                updated = True
                # Proceed with updating the record
                doc = existing_record
            else:
                # Create new record
                doc = frappe.new_doc("Bigbasket")
                doc.duplicate_records_status = "False/0"  # Default value for new records

             # Update fields in the document
            doc.po_number = po_number
            doc.company_name = company_name  # Ensure company_name is updated
            doc.po_expiry_date = po_expiry_date  # Set expiry_date
            doc.email_id = email_id
            doc.po_url = file_url
            doc.delivered_to = delivered_to  # Set delivered_to using matched_address_id
            doc.matched_address_name = matched_address.get("AddressName", "")
            doc.matched_state = matched_state
            doc.customer_code = customer_code  # Set customer_code
            doc.employee_id = employee_id  # Set employee_id

            # Set default values for Billing_from and Billto
            doc.billing_from = "KT"
            doc.billto = "Local" if doc.matched_state == "KT" else "Central"

            # Initialize totals
            total_quantity = 0
            total_amount = 0
            unique_items = set()

            # Clear existing child table rows (if updating)
            if updated:
                doc.bigbasket_table = []

            # Add item details to the child table and accumulate totals
            for item in item_data_response:
                quantity = int(item.get("quantity") or 0)  # Ensure quantity is an integer
                total_item_amount = float(item.get("total_value") or 0.0)  # Ensure total_item_amount is a float
                # print("total_item_amount:", total_item_amount)

                item_code = item.get("item_code", "")


                # Determine the taxcode format based on matched_state
                tax_prefix = "KACS" if doc.matched_state == "KT" else "KAIG"
                tax_rate = int(item.get("U_TaxRate", 0))
                taxcode = f"{tax_prefix}{tax_rate}"

                # Append item to child table
                doc.append("bigbasket_table", {
                    "item_code": item_code,
                    "sap_code": item.get("sap_code", ""), 
                    "gst_amount": item.get("GST_Amount", 0),
                    "landing_cost": item.get("Landing_Cost", 0),
                    "product_description": item.get("item_name", ""),  # Include product_description
                    "quantity": quantity,
                    "basic_cost_price": item.get("basic_cost_price", 0),
                    "total_value": item.get("total_value", 0),
                    "mrp": item.get("mrp", 0),
                    "tax_rate": item.get("U_TaxRate", 0),
                    "gst_tax": item.get("U_GstTax", ""),
                    "igst_tax": item.get("U_IgstTax", ""),
                    "taxcode": taxcode,
                    "total_amount": total_item_amount
                })

                # Accumulate totals
                total_quantity += quantity
                total_amount += total_item_amount
                unique_items.add(item_code)

            # Update total fields in parent doctype
            doc.total_quantity = total_quantity
            doc.total_amount = total_amount
            doc.total_items = len(unique_items)

            # Save or insert the document
            if updated:
                doc.save()
                print(f"Record updated for P.O. Number: {po_number}.")
            else:
                doc.name = f"{po_number}-{frappe.generate_hash(length=8)}"
                doc.insert()
                print(f"New record created for P.O. Number: {po_number}.")

            # Execute only after the document is successfully saved or inserted
            try:
                if move_email_to_processed(mail, email_uid_str):
                    print(f"Moved email UID {email_uid_str}")
                else:
                    print(f"Failed to move email {email_uid_str}.")

                # with open(f"{po_number}.json", "w") as json_file:
                #     json.dump(json_data, json_file, indent=4)
            except Exception as e:
                error_message = f"Error during post-save operations: {str(e)}"
                print(error_message)
                frappe.log_error(f"Error in post-save operations: {str(e)}")
                send_error_email(po_number, error_message, file_url)
                return  # Stop further processing on error

        except Exception as e:
            error_message = f"Error processing bigbasket_table data: {str(e)}"
            print(error_message)
            frappe.log_error(f"Error in bigbasket_table: {str(e)}")
            send_error_email(po_number, error_message, file_url)
            return  # Stop further processing on error


    def read_attachments(mail, CardCode):
        """Read email attachments using UIDs"""
        try:
            mail.select(f'"{LABEL_NAME}"')  # Select the label
            status, messages = mail.uid('search', None, 'ALL')
            email_uids = messages[0].split()
            print(f"Found {len(email_uids)} emails in label {LABEL_NAME}.")

            for email_uid in email_uids:
                email_uid_str = email_uid.decode()
                print(f"Processing email UID: {email_uid_str}")

                try:
                    status, msg_data = mail.uid('fetch', email_uid_str, '(RFC822)')
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                filename = part.get_filename()

                                if filename and filename.lower().endswith((".xls", ".xlsx")):
                                    xls_data = part.get_payload(decode=True)
                                    if isinstance(xls_data, bytes):
                                        print(f"Found xls attachment: {filename}")
                                        extracted_data = extract_po_details(xls_data)

                                        # Initialize po_number and file_url early
                                        po_number = extracted_data.get("PO Number", "N/A") if extracted_data else "N/A"
                                        # print(f"Extracted PO Number: {po_number}")
                                        file_url = None

                                        if extracted_data is None:
                                            error_message = f"Extraction failed or 'IRCPL' not found for email UID {email_uid_str}."
                                            send_error_email(po_number=po_number, error_message=error_message, file_url=file_url)
                                            continue

                                        if not po_number or po_number == "N/A":
                                            error_message = f"'PO Number' is missing in extracted data for email UID {email_uid_str}."
                                            send_error_email(po_number=po_number, error_message=error_message, file_url=file_url)
                                            continue

                                        try:
                                            file_url = save_pdf_to_file(xls_data, extracted_data)
                                            customer_details = Get_CustomerDetails(CardCode, extracted_data)
                                            code_sheet_data = fetch_item_sap_mapping()
                                            itemmaster_result = itemmaster(extracted_data, code_sheet_data)

                                            if not isinstance(itemmaster_result, list):
                                                error_message = f"Error: itemmaster_result is not a list for email UID {email_uid_str}."
                                                send_error_email(po_number=po_number, error_message=error_message, file_url=file_url)
                                                continue

                                            matched_address = None
                                            if customer_details['Status'] == 'Success':
                                                matched_address = next(
                                                    (address for address in customer_details['Result']['Addresses']
                                                    if address['AddressName'] == customer_details['Result']['MatchedAddressName']), None)
                                                if matched_address:
                                                    matched_address = {
                                                        "AddressName": matched_address["AddressName"],
                                                        "State": matched_address["State"]
                                                    }

                                            merged_item_data = []
                                            item_response_dict = {item["ItemCode"]: item for item in itemmaster_result if item}

                                            for item in extracted_data.get("Table Data", []):  # Corrected from api_extracted
                                                item_code = str(item.get("SkuCode") or item.get("SKU Code")).strip()  # Handle both "SkuCode" and "SKU Code"
                                                if item_code in item_response_dict:
                                                    merged_item_data.append({
                                                        "item_code": item_code,
                                                        "sap_code": item_response_dict[item_code].get("SAPCode"),
                                                        "item_name": item_response_dict[item_code].get("ItemName"),
                                                        "quantity": item.get("Quantity"),
                                                        "total_value": item.get("TotalValue") or item.get("Total Value"),
                                                        "GST_Amount": item.get("GST Amount"),
                                                        "Landing_Cost": item.get("Landing Cost"),
                                                        "basic_cost_price": item.get("Basic Cost"),
                                                        "mrp": item.get("MRP"),
                                                        "U_TaxRate": item_response_dict[item_code].get("U_TaxRate", "N/A"),
                                                        "U_GstTax": item_response_dict[item_code].get("U_GstTax", "N/A"),
                                                        "U_IgstTax": item_response_dict[item_code].get("U_IgstTax", "N/A"),
                                                    })
                                                else:
                                                    print(f"Item code {item_code} not found in item master result.")
                                                    frappe.throw(f"Item code {item_code} not found in item master result. Stopping process.")

                                            json_data = {
                                                "po_number": po_number,
                                                "delivered_to": extracted_data.get("Warehouse Address"),
                                                "CompanyName": customer_details['Result']['CustomerName'],
                                                "expiry_date": extracted_data.get("PO Expiry Date"),
                                                "matched_address_id": customer_details['Result']['MatchedAddressName'],
                                                "MatchedAddress": matched_address,
                                                "MatchedState": customer_details['Result']['MatchedState'],
                                                "items": merged_item_data,
                                                "CardCode": CardCode,
                                                "SalesPersonCode": SalesPersonCode,
                                                "email_id": email_uid_str,
                                                "file_url": file_url
                                            }

                                            process_b2b_data(json_data, email_uid_str)

                                        except Exception as e:
                                            error_message = f"Error during processing for email UID {email_uid_str}: {str(e)}"
                                            send_error_email(po_number=po_number, error_message=error_message, file_url=file_url)
                                            continue

                                    else:
                                        error_message = f"Excel data is not bytes-like for {filename} in email UID {email_uid_str}."
                                        send_error_email(po_number=po_number, error_message=error_message, file_url=None)
                                        continue

                except Exception as e:
                    error_message = f"Error processing email UID {email_uid_str}: {str(e)}"
                    send_error_email(po_number=po_number, error_message=error_message, file_url=None)
                    continue  # Continue with the next email

        except Exception as e:
            error_message = f"Error occurred while reading attachments: {str(e)}"
            send_error_email(po_number="N/A", error_message=error_message, file_url=None)
            return {"Status": "Failed", "Message": str(e)}


    # print("Starting email attachment processing...")
    try:
        mail = connect_to_email()
        # CardCode = "C03566"
        result = read_attachments(mail, CardCode)
        # print(result)
        mail.logout()
        print("Finished email attachment processing.")
    except Exception as e:
        frappe.log_error(f"Error in process_email_attachments: {str(e)}")
        print(f"An error occurred: {str(e)}")

def send_error_email(po_number, error_message, file_url=None, channel_name="Bigbasket"):
    """Send an error email using the HTML template."""
    try:
        # Debugging: Ensure the function is called
        print(f"send_error_email called with po_number: {po_number}, error_message: {error_message}, file_url: {file_url}, channel_name: {channel_name}")

        # Fetch all users with the role 'B2B_Bigbasket'
        recipients = frappe.get_all(
            "Has Role",
            filters={"role": "B2B_Bigbasket"},
            fields=["parent"],
        )
        if not recipients:
            frappe.log_error("No recipients found with the role 'B2B_Bigbasket'.")
            return

        # Extract email addresses of the users
        recipient_emails = []
        for user in recipients:
            email = frappe.db.get_value("User", user["parent"], "email")
            enabled = frappe.db.get_value("User", user["parent"], "enabled")
            if email and enabled:
                recipient_emails.append(email)

        if not recipient_emails:
            frappe.log_error("No enabled users with valid email addresses found.")
            return

        # Debugging: Ensure recipients are fetched
        # print(f"Recipients fetched: {recipient_emails}")

        # Load the HTML template
        template_path = os.path.join(
            os.path.dirname(__file__), "email_template.html"
        )
        if not os.path.exists(template_path):
            frappe.log_error(f"Email template not found at {template_path}.")
            return

        with open(template_path, "r") as file:
            html_template = file.read()

        # Replace placeholders with actual values
        html_content = (
            html_template
            .replace("{{ po_number or \"N/A\" }}", po_number or "N/A")
            .replace("{{ error_message or \"No details provided.\" }}", error_message or "No details provided.")
            .replace("{{ file_url or \"\" }}", file_url or "")
            .replace("{{ channel_name }}", channel_name)  # Pass channel_name to the template
        )

        # Debugging: Ensure email is being sent
        # print(f"Sending email to: {recipient_emails}")

        # Send the email
        try:
            frappe.sendmail(
                recipients=recipient_emails,
                subject=f"Notification from B2B {channel_name} Channel - PO Number: {po_number}",
                message=html_content,
            )
            print("Email sent successfully.")
        except Exception as e:
            print(f"Error while sending email: {str(e)}")
            frappe.log_error(f"Error while sending email: {str(e)}")

    except AttributeError as e:
        frappe.log_error(f"AttributeError: {str(e)} - Check if objects are None.")
        print(f"AttributeError in send_error_email: {str(e)}")  # Debugging
    except Exception as e:
        frappe.log_error(f"Failed to send error email: {str(e)}")
        print(f"Failed to send error email: {str(e)}")  # Debugging

# Call the main function 
if __name__ == "__main__":
    process_email_attachments()