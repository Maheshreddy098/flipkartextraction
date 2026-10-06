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
import csv
from difflib import get_close_matches
import pdfplumber
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
            LABEL_NAME = "Zepto"
        else:
            frappe.throw("Email record not found in the database.")
    else:
        print("Table 'B2B_EMAIL' does not exist.")
        frappe.throw("Email table does not exist.")
    
     # Fetch CardCode and SalesPersonCode from B2B-Customer-Details
    customer_details_record = frappe.db.get_value(
        "B2B_Customer_Details", 
        None, 
        ["cardcode5", "salespersoncode5"], 
        as_dict=True
    )
    
    if customer_details_record:
        CardCode = customer_details_record.get('cardcode5')
        SalesPersonCode = customer_details_record.get('salespersoncode5')
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
                    # print(f"Fetched Email Subject: {subject}")  # Debugging
                    return subject
        except Exception as e:
            print(f"Error fetching email subject for UID {email_uid}: {str(e)}")
            return None


    
    def extract_shipping_address_and_po(pdf_data):
        """Extract shipping address and PO number from the given PDF data using pdfplumber."""
        keywords = "Shipping Address"
        address_lines = []
        po_number = None

        # Wrap pdf_data in BytesIO to create a file-like object
        pdf_file = io.BytesIO(pdf_data)

        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue

                # Extract PO No
                if not po_number:
                    po_match = re.search(r'\bPO No:\s*(\w+)', text)
                    if po_match:
                        po_number = po_match.group(1)

                # Extract Shipping Address
                lines = text.split('\n')
                try:
                    # Find the index of the "Shipping Address" keyword
                    index = next(i for i, line in enumerate(lines) if keywords.lower() in line.lower())
                    # Extract lines until a 6-digit pincode is encountered
                    for i in range(index + 1, len(lines)):
                        line = lines[i].strip()
                        if not line:
                            continue
                        # Check if the line contains a 6-digit pincode
                        match = re.search(r'\b\d{6}\b', line)
                        if match:
                            address_lines.append(line[:match.end()])  # Truncate at the pincode
                            break
                        if line not in address_lines:  # Avoid duplicate lines
                            address_lines.append(line)
                    break  # Stop after first match
                except StopIteration:
                    print(f"Keyword '{keywords}' not found on this page.")
                except Exception as e:
                    print(f"Error extracting shipping address: {e}")

        # Filter out empty lines
        address_lines = [line for line in address_lines if line]

        # Remove any occurrence of "Shipping Address:" or "Address:" from the extracted lines
        address_lines = [line.replace("Shipping Address:", "").replace("Address:", "").strip() for line in address_lines]

        # Construct the final address
        final_address = "\n".join(address_lines) if address_lines else "Address not found"

        # Construct the JSON-like dictionary
        extracted_data = {
            "po_number": po_number,
            "Shipping Address": final_address
        }

        # print("Extracted Data:", extracted_data)
        return extracted_data


    def extract_excel(xlsx_data):
        """Extract data from the given CSV content."""
        # Define the required columns
        required_columns = [
            "PoNumber", "Sku", "SkuDesc", "IGSTPercentage", "MRP", "Quantity",
            "UnitBaseCost", "LandingCost", "TotalAmount", "PoExpiryDate", "TotalAmount"
        ]
        
        extracted_data = []
        csv_content = xlsx_data.decode('utf-8')  # Decode the byte data to a string
        reader = csv.DictReader(io.StringIO(csv_content))  # Use StringIO to read CSV content from memory

        # Normalize the CSV headers
        headers = reader.fieldnames
        column_mapping = {}
        
        for required_col in required_columns:
            # Find the closest match for each required column
            match = get_close_matches(required_col.lower(), [header.lower() for header in headers], n=1, cutoff=0.6)
            if match:
                # Map the required column to the closest matching header
                column_mapping[required_col] = next(header for header in headers if header.lower() == match[0])
        
        for row in reader:
            # Extract data for the required columns
            extracted_row = {key: row[column_mapping[key]] for key in column_mapping if key in column_mapping}
            extracted_data.append(extracted_row)
        
        return extracted_data



    @frappe.whitelist()
    def Get_CustomerDetails(CardCode,extracted_pdf_data):
        try:
           
            def similar(a, b):
                return SequenceMatcher(None, a.lower(), b.lower()).ratio()

            po_number = extracted_pdf_data.get("po_number")
            delivered_to = extracted_pdf_data.get("Shipping Address", "")
            # print("Delivered To (raw):", delivered_to)

            zip_match = re.search(r'\b\d{6}\b', delivered_to)
            delivered_zip = zip_match.group() if zip_match else None
            # print(f"Extracted ZIP code: {delivered_zip}")

            address_entries = []
            ada_docs = frappe.get_all("ADA_5", fields=["name"])
            for ada_doc in ada_docs:
                ada_record = frappe.get_doc("ADA_5", ada_doc.name)
                if hasattr(ada_record, "address_table5") and ada_record.address_table5:
                    for address in ada_record.address_table5:
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


             # Add a check to ensure matched_address_id is not empty
            if not matched_address_id:
                error_message = "Best Matching Address ID is empty. Stopping further processing."
                print(error_message)
                frappe.log_error(error_message)
                return {'Status': 'Error', 'Message': error_message}    

            # Fetch SAP Customer Details
            try:
                # print("Fetching SAP Settings...")
                doc_settings = frappe.get_doc('SAP Settings')

                print("Authenticating with SAP B1...")
                session = AuthenticateSAPB1()

                Url = doc_settings.sap_b1_url + f"BusinessPartners?$filter=CardCode eq '{CardCode}'"
                # print(f"Requesting SAP API: {Url}")

                response = session.request("GET", Url, headers=headersList, verify=False)
                # print(f"Response Status: {response.status_code}, Response: {response.text}")

                customer_data = response.json()
                # print(f"Customer Data: {customer_data}")

                if not customer_data.get('value'):
                    print(f"No customer data found for CardCode: {CardCode}")
                    return {'Status': 'Error', 'Message': f"No customer data found for CardCode: {CardCode}."}

                customer_details = customer_data['value'][0]
                # print(f"Customer Details: {customer_details}")
                addresses = customer_details.get('BPAddresses', [])
                # print(f"Addresses: {addresses}")
                
                matched_state = None
                matched_address_name = None

                # Check if matched_address_id exists in SAP's AddressName
                for address in addresses:
                    # Ensure `address` is a dictionary
                    if isinstance(address, dict):
                        # print(f"AddressName in current address: {address.get('AddressName')}")
                        if address.get('AddressName') == matched_address_id:
                            # print(f"Matched AddressName: {address.get('AddressName')}")
                            matched_address_name = address.get('AddressName')
                            matched_state = address.get('State')
                            print(f"Matched Address Found: {matched_address_name}, State: {matched_state}")
                            break
                    else:
                        # Log unexpected address format for debugging
                        print(f"Unexpected address format: {type(address)} - {address}. Skipping this entry.")

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
    def fetch_item_sap_mapping():
        # print("Fetching Itemmap records...")
        item_sap_map = []
        
        # Fetch all Itemmap5 documents
        itemmap_records = frappe.get_all('Itemmap5')
        # print(f"Found {len(itemmap_records)} Itemmap4 records")
        
        for record in itemmap_records:
            itemmap_doc = frappe.get_doc("Itemmap5", record.name)
            if hasattr(itemmap_doc, "map_item") and itemmap_doc.map_item:
                for mapping in itemmap_doc.map_item:
                    item_sap_map.append({
                        'item_code': str(mapping.item_code).strip(),  # Ensure string and clean whitespace
                        'sap_code': str(mapping.sap_code).strip()
                    })
        
        # print("Mapped Items:", item_sap_map)
        return item_sap_map

    def save_pdf_to_file(pdf_data, extracted_pdf_data):
        """Save the PDF to S3 inside a dynamically set folder."""
        print("Saving PDF to S3...")
        po_number = extracted_pdf_data.get("po_number")
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
                folder_name = (aws_record.folder_insta or "Zepto").strip().strip('/')
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

        # Correct the file extension to .pdf
        file_name = f"{folder_name}/Zepto_{po_number}.pdf"

        try:
            # Upload the PDF to S3 inside the dynamic folder
            s3.put_object(Bucket=bucket_name, Key=file_name, Body=pdf_data)

            # Construct the correct file URL
            file_url = f"https://{bucket_name}.s3.amazonaws.com/{file_name}"

            # print(f"PDF uploaded successfully: {file_url}")
            return file_url

        except NoCredentialsError:
            print("Credentials not available for accessing AWS S3")
            return None

    
    @frappe.whitelist()
    def itemmaster(extracted_excel_data, code_sheet_data, po_number=None, file_url=None):
        """Fetch from item master using a list of item codes, mapping to SAP codes."""
        
        doc_settings = frappe.get_doc('SAP Settings')
        session = AuthenticateSAPB1()  # Authenticate with SAP B1
        payload = ''
        results = []

        # Ensure code_sheet_data is a dictionary
        if isinstance(code_sheet_data, list):
            # Convert list of dictionaries to a single dictionary
            code_sheet_data = {item['item_code']: item['sap_code'] for item in code_sheet_data}

        # Create a mapping from item_code to sap_code
        item_to_sap_map = code_sheet_data

        for item in extracted_excel_data:
            item_code = str(item['Sku'])  # Ensure it's a string for dictionary lookup
            # print(f"Checking item_code: {item_code} in mapping...")

            # Check if the item_code exists in the mapping
            sap_code = item_to_sap_map.get(item_code)

            if sap_code:
                # print(f"Mapped SAP item code for {item_code}: {sap_code}")

                url = doc_settings.sap_b1_url + f"Items('{sap_code}')"
                try:
                    response = session.request("GET", url, data=payload, headers=headersList, verify=False)

                    if response.status_code == 200:
                        item_data = response.json()
                        item_name = item_data.get('ItemName', 'N/A')
                        tax_rate = item_data.get('U_TaxRate', 'N/A')
                        gst_tax = item_data.get('U_GstTax', 'N/A')
                        igst_tax = item_data.get('U_IgstTax', 'N/A')
                        brand = item_data.get('U_BN', 'N/A')

                        results.append({
                            "ItemCode": item_code,
                            "SAPCode": sap_code,
                            "ItemName": item_name,
                            "U_TaxRate": tax_rate,
                            "U_GstTax": gst_tax,
                            "U_IgstTax": igst_tax,
                            "U_BN": brand
                        })
                    else:
                        print(f"Error fetching data for SAP code {sap_code} (Item code {item_code}): {response.text}")

                except Exception as e:
                    print(f"Exception occurred while fetching data for SAP code {sap_code} (Item code {item_code}): {e}")
            else:
                error_message = f"No mapping found for item code {item_code}. Stopping the process."
                print(error_message)
                frappe.log_error(error_message)
                raise ValueError(error_message)  # Stop the process by raising an exception

        if results:
            return {"data": results}
        else:
            error_message = "No matching records found for any item codes."
            print(error_message)
            frappe.log_error(error_message)
            send_error_email(po_number or "N/A", error_message, file_url or "None")  # Pass po_number and file_url explicitly
            return None


    @frappe.whitelist()
    def process_b2b_data(json_data, email_uid_str):
        try:
            # Ensure json_data is not None
            if not json_data:
                print("Error: JSON data is None or empty.")
                return

            # Ensure json_data is a dictionary (if it's passed as a string, parse it)
            if isinstance(json_data, str):
                json_data = frappe.parse_json(json_data)

            # Safely extract data from JSON with default values
            po_number = json_data.get("po_number", "N/A")  # Default to "N/A" if po_number is missing
            email_id = json_data.get("email_id", "N/A")  # Extract email_id from json_data
            Shipping_address = json_data.get("Shipping_address", {})
            customer_details = json_data.get("customer_details", {})
            file_url = json_data.get("file_url", "")
            item_data_response = json_data.get("item_data_response", {}).get("data", [])

            if not frappe.db.table_exists("Zepto"):
                print('Doctype "Zepto" does not exist.')
                return

            # Check if the record already exists
            existing_record_name = frappe.db.exists("Zepto", {"po_number": po_number})
            updated = False
            
            if existing_record_name:
                # Fetch and print the existing record's data
                existing_record = frappe.get_doc("Zepto", existing_record_name)
                print(f"Existing Record Data for P.O. Number {po_number}:")
                # print(frappe.as_json(existing_record))  # Print the existing record as JSON
                
                # Fetch the email subject directly from the email server
                email_subject = fetch_email_subject(mail, email_id)
                # print(f"Email Subject: {email_subject}")  # Debugging

                if email_subject and is_partial_match(email_subject, ["amend", "amendment", "revised", "revise"]):
                    # print("Email subject contains 'Amend' or 'Revised'. Proceeding to store in duplicate records.")
                    error_message = f"Email subject contains 'Amend' or 'Revised'. Proceeding to Update records."
                    

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
                    existing_record.append("duplicate_records_zepto", duplicate_record)  # Append to the child table

                    # Update the duplicate_records_status field
                    duplicate_count = len(existing_record.duplicate_records_zepto)
                    existing_record.duplicate_records_status = f"Amended/{duplicate_count}"

                    # Clear specific fields
                    fields_to_clear = [
                        "docstatus", "docnum", "docentry", "sap_status", "update_status", "document_status"
                    ]
                    for field in fields_to_clear:
                        existing_record.set(field, None)

                    # Clear child table data
                    existing_record.zepto_table = []

                    # Save the cleared record
                    existing_record.save()
                else:
                    print(f"Email subject does not contain 'Amended' or 'Revised'. Skipping email UID {email_id}.")
                    error_message = f"Email subject does not contain 'Amended' or 'Revised'. Skipping email UID {email_id}."

                    # Send error email
                    send_error_email(po_number, error_message, file_url)
                    
                    return  # Skip processing this email

                updated = True
                # Proceed with updating the record
                doc = existing_record
            else:
                # Create new record
                doc = frappe.new_doc("Zepto")
                doc.duplicate_records_status = "False/0"  # Default value for new records




             # Update fields in the document
            doc.po_number = po_number
            doc.company_name = customer_details.get("CustomerName", "")  # Ensure company_name is updated
            
            # Fetch and reformat Po_ExpiryDate from the first item in item_data_response, if available
            if item_data_response:
                # print(f"item_data_response: {item_data_response}")  # Debugging: Print the entire response
                # Access the first item in the "data" list
                raw_date = item_data_response[0].get("Po_ExpiryDate", "")  # Corrected access
                # print(f"Raw Po_ExpiryDate: {raw_date}")  # Debugging: Print the raw date value

                # ...existing code...
                if raw_date:
                    try:
                        # Attempt to parse the date in multiple formats
                        for date_format in ["%Y-%m-%d %H:%M:%S", "%d/%m/%y %H:%M", "%Y-%m-%d"]:
                            try:
                                parsed_date = datetime.strptime(raw_date, date_format)
                                doc.po_expiry_date = parsed_date.strftime("%Y-%m-%d")  # Format to YYYY-MM-DD
                                break
                            except ValueError:
                                continue
                        else:
                            raise ValueError(f"Date format not recognized: {raw_date}")
                    except ValueError as e:
                        print(f"Error parsing Po_ExpiryDate: {e}")  # Debugging: Log the error
                        doc.po_expiry_date = ""  # Fallback to empty string if parsing fails
                else:
                    print("Po_ExpiryDate is missing or empty in item_data_response.")  # Debugging: Log missing date
                    doc.po_expiry_date = ""
                # ...existing code...
            else:
                print("item_data_response is empty or invalid.")  # Debugging: Log empty response
                doc.po_expiry_date = ""

            doc.email_id = email_id
            doc.po_url = file_url
            doc.delivered_to = Shipping_address  # Set delivered_to using matched_address_id
            doc.matched_address_name = customer_details.get("MatchedAddress", {}).get("AddressName", "")  # Corrected key
            doc.matched_state = customer_details.get("MatchedState", "")  # Corrected key
            doc.customer_code = customer_details.get("CardCode", "")  # Set customer_code
            # doc.employee_id = customer_details.get("SalesPersonCode", "")  # Set employee_id

            # Set default values for Billing_from and Billto
            doc.billing_from = "KT"
            doc.billto = "Local" if doc.matched_state == "KT" else "Central"

            # Initialize totals
            total_quantity = 0
            total_amount = 0
            total_taxable_value = 0  # Initialize total taxable value
            main_total_tax = 0  # Initialize main total tax
            unique_items = set()

            # Clear existing child table rows (if updating)
            if updated:
                doc.zepto_table = []

            # Add item details to the child table and accumulate totals
            if item_data_response:
                for item in item_data_response:
                    # Ensure item is not None
                    if not item:
                        print("Warning: Found a None item in item_data_response. Skipping...")
                        continue

                    quantity = int(item.get("Quantity") or 0)  # Ensure quantity is an integer
                    basic_cost_price = float(item.get("BasicCostPrice") or 0.0)  # Ensure basic_cost_price is a float
                    taxable_value = basic_cost_price * quantity  # Calculate taxable value
                    total_taxable_value += taxable_value  # Accumulate total taxable value
                    main_total_tax += taxable_value  # Accumulate main total tax
                    # print("total_taxable_value", total_taxable_value)
                    total_item_amount = float(item.get("TotalAmount") or 0.0)  # Ensure total_item_amount is a float

                    item_code = item.get("ItemCode", "")

                    # Determine the taxcode format based on matched_state
                    tax_prefix = "KACS" if doc.matched_state == "KT" else "KAIG"
                    tax_rate = int(item.get("U_TaxRate", 0))
                    taxcode = f"{tax_prefix}{tax_rate}"

                    # Append item to child table
                    doc.append("zepto_table", {
                        "item_code": item_code,
                        "sap_code": item.get("SAPCode", ""),
                        "landing_rate": item.get("LandingRate", 0),
                        "product_description": item.get("ItemName", ""),
                        "quantity": quantity,
                        "basic_cost_price": basic_cost_price,
                        "total_amount": total_item_amount,
                        "mrp": item.get("MRP", 0),
                        "tax_rate": item.get("U_TaxRate", 0),
                        "gst_tax": item.get("U_GstTax", ""),
                        "igst_tax": item.get("U_IgstTax", ""),
                        "brand": item.get("U_BN", ""),
                        "taxcode": taxcode,
                        "taxable_value": taxable_value  # Add taxable value to child table
                    })

                    # Accumulate totals
                    total_quantity += quantity
                    total_amount += total_item_amount
                    unique_items.add(item_code)


                    # Assign the brand value from the first item in the response
            if item_data_response:
                doc.product = item_data_response[0].get("U_BN", "")
            else:
                doc.product = None  # Default to None if no items are present
           

            # Update total fields in parent doctype
            doc.total_quantity = total_quantity
            doc.total_amount = total_amount
            doc.total_items = len(unique_items)
            doc.taxable_value = total_taxable_value  # Update taxable value in parent doctype
            doc.main_total_tax = main_total_tax  # Update main total tax field

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
                # # Safeguard: Ensure po_number is valid before writing the JSON file
                # if po_number and po_number != "N/A":
                #     with open(f"{po_number}.json", "w") as json_file:
                #         json.dump(json_data, json_file, indent=4)
                # else:
                #     print(f"Skipping JSON file creation due to invalid PO Number: {po_number}")

                
            except Exception as e:
                error_message = f"Error during post-save operations: {str(e)}"
                print(error_message)
                frappe.log_error(f"Error in post-save operations: {str(e)}")
                send_error_email(po_number, error_message, file_url)
                return  # Stop further processing on error

        except Exception as e:
            error_message = f"Error processing zepto_table data: {str(e)}"
            print(error_message)
            frappe.log_error(f"Error in zepto_table: {str(e)}")
            send_error_email(po_number, error_message, file_url)
            return  # Stop further processing on error   



    def move_email_to_processed(mail, email_uid):
        """Move an email to the Zepto-Processed folder using IMAP UIDs."""
        try:
            # Ensure the "Blinkit-Processed" folder exists
            mail.create('Zepto-Processed')
        except imaplib.IMAP4.error:
            pass  # Folder already exists, no need to create it

        try:
            # Copy the email using UID
            copy_result = mail.uid('copy', email_uid, 'Zepto-Processed')
            if copy_result[0] == 'OK':
                # Mark the original email for deletion using UID
                store_result = mail.uid('store', email_uid, '+FLAGS', '\\Deleted')
                if store_result[0] == 'OK':
                    mail.expunge()  # Permanently delete the email
                    # print(f"Moved email UID {email_uid} to Zepto folder.")
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

                # Initialize po_number and file_url with default values
                po_number = "N/A"
                file_url = None

                try:
                    status, msg_data = mail.uid('fetch', email_uid_str, '(RFC822)')
                    for response_part in msg_data:
                        if isinstance(response_part, tuple) and isinstance(response_part[1], bytes):
                            msg = email.message_from_bytes(response_part[1])
                        elif isinstance(response_part, bytes):
                            try:
                                msg = email.message_from_bytes(response_part)
                            except Exception as e:
                                print(f"Error processing response_part: {e}")
                                continue
                        else:
                            print(f"Skipping unexpected response_part: {type(response_part)}")
                            continue

                        if msg.is_multipart():
                            pdf_data = xlsx_data = None
                            extracted_data = ""
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                filename = part.get_filename()
                                if filename:
                                    if filename.lower().endswith(".pdf") and pdf_data is None:  # Process the first PDF
                                        pdf_data = part.get_payload(decode=True)
                                        if isinstance(pdf_data, bytes):
                                            print(f"Found PDF attachment: {filename}")
                                            # Extract metadata from the PDF
                                            extracted_pdf_data = extract_shipping_address_and_po(pdf_data)
                                            # print(f"Extracted Data: {extracted_pdf_data}")

                                            
                                    elif filename.lower().endswith(".csv") and xlsx_data is None:  # Process the first Excel file
                                        xlsx_data = part.get_payload(decode=True)
                                        print(f"Found XLSX attachment: {filename}")
                                        extracted_excel_data = extract_excel(xlsx_data)
                                        

                            # Validate PO number match
                            if pdf_data and xlsx_data:
                                pdf_po_number = extracted_pdf_data.get("po_number")
                                po_number = pdf_po_number  # Update po_number as soon as it's available
                                excel_po_numbers = {row.get("PoNumber") for row in extracted_excel_data}

                                if pdf_po_number in excel_po_numbers:
                                    print(f"PO Number {pdf_po_number} matches in both PDF and Excel data. Proceeding to the next step.")

                                    po_number = pdf_po_number  # Ensure po_number is defined here
                                    email_id = email_uid_str  # Ensure email_id is defined here
                                    existing_record_name = frappe.db.exists("Zepto", {"po_number": po_number})
                                    updated = False

                                    if existing_record_name:
                                        # Fetch and print the existing record's data
                                        existing_record = frappe.get_doc("Zepto", existing_record_name)
                                        # print(f"Existing Record Data for P.O. Number {po_number}:")

                                        email_subject = fetch_email_subject(mail, email_id)
                                        print(f"Email Subject: {email_subject}")  # Debugging

                                        if email_subject and is_partial_match(email_subject, ["amend", "amendment", "revised", "revise"]):
                                            print("Email subject contains 'Amend' or 'Revised'")
                                             
                                    # Save PDF to S3 only if file_url is not already set
                                    if not file_url:
                                        file_url = save_pdf_to_file(pdf_data, extracted_pdf_data)    

                                    customer_details = Get_CustomerDetails(CardCode, extracted_pdf_data)

                                    # Safeguard: Ensure customer_details contains 'Result'
                                    if customer_details.get('Status') != 'Success' or 'Result' not in customer_details:
                                        error_message = f"Error: Customer details not found or incomplete for PO Number {pdf_po_number}."
                                        print(f"Calling send_error_email for UID {email_uid_str}")
                                        send_error_email(pdf_po_number or "N/A", error_message, file_url or "None")
                                        continue

                                    code_sheet_data = fetch_item_sap_mapping()
                                    item_data_response = itemmaster(extracted_excel_data, code_sheet_data, pdf_po_number, file_url)

                                    merged_item_data = []
                                    item_response_dict = {item["ItemCode"]: item for item in item_data_response.get("data", [])}

                                    for item in extracted_excel_data:
                                        item_code = item["Sku"]
                                        if str(item_code) in item_response_dict:
                                            merged_item = {
                                                **item_response_dict[str(item_code)],
                                                "Quantity": item["Quantity"],
                                                "Po_ExpiryDate": item["PoExpiryDate"],
                                                "ProductDescription": item["SkuDesc"],
                                                "BasicCostPrice": item["UnitBaseCost"],
                                                "LandingRate": item["LandingCost"],
                                                "MRP": item["MRP"],
                                                "TotalAmount": item["TotalAmount"]
                                            }
                                            merged_item_data.append(merged_item)
                                        else:
                                            merged_item_data.append({
                                                "ItemCode": item["Sku"],
                                                "Quantity": item["Quantity"],
                                                "ProductDescription": item["SkuDesc"],
                                                "BasicCostPrice": item["UnitBaseCost"],
                                                "LandingRate": item["LandingCost"],
                                                "MRP": item["MRP"],
                                                "TotalAmount": item["TotalAmount"]
                                            })
                                    
                                    item_data_response["data"] = merged_item_data

                                    matched_address = None
                                    if customer_details['Status'] == 'Success':
                                        matched_address = next((address for address in customer_details['Result']['Addresses'] if address['AddressName'] == customer_details['Result']['MatchedAddressName']), None)
                                        if matched_address:
                                            matched_address = {
                                                "AddressName": matched_address["AddressName"],
                                                "State": matched_address["State"]
                                            }

                                    json_data = {
                                        "po_number": pdf_po_number,
                                        "email_id": email_uid_str,
                                        "Shipping_address": extracted_pdf_data["Shipping Address"],
                                        "customer_details": {
                                            "CardCode": customer_details['Result'].get('CardCode', ''),
                                            "SalesPersonCode": SalesPersonCode,
                                            "CustomerName": customer_details['Result'].get('CustomerName', ''),
                                            "MatchedAddress": matched_address,
                                            "MatchedState": customer_details['Result'].get('MatchedState', '')
                                        },
                                        "file_url": file_url,
                                        "item_data_response": item_data_response
                                    }
                                    # print(f"JSON Data: {json_data}")
                                    print(f"JSON Data......")
                                    # Process the data
                                    process_b2b_data(json_data, email_uid_str)

                                    # # Safeguard: Ensure po_number is valid before writing the JSON file
                                    # if pdf_po_number and pdf_po_number != "N/A":
                                    #     # with open(f"{pdf_po_number}.json", "w") as json_file:
                                    #     #     json.dump(json_data, json_file, indent=4)
                                    # else:
                                    #     print(f"Skipping JSON file creation due to invalid PO Number: {pdf_po_number}")
                                else:
                                    error_message = f"PO Number mismatch or missing in extracted data for email UID {email_uid_str}."
                                    print(f"Calling send_error_email for UID {email_uid_str}")
                                    send_error_email(pdf_po_number or "N/A", error_message, file_url or "None")
                                    continue
                            # Save PDF to S3 only if file_url is not already set
                            if not file_url:
                                file_url = save_pdf_to_file(pdf_data, extracted_pdf_data)  # Save PDF and get file URL

                            # Process item data
                            item_data_response = itemmaster(extracted_excel_data, code_sheet_data, pdf_po_number, file_url)
                            # ...existing code...

                except Exception as e:
                    error_message = f"Error processing email UID {email_uid_str}: {str(e)}"
                    print(error_message)
                    send_error_email(po_number, error_message, file_url)  # Pass updated po_number and file_url
                    continue  # Continue with the next email

        except Exception as e:
            error_message = f"Error occurred while reading attachments: {str(e)}"
            print(error_message)
            send_error_email("N/A", error_message)
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




def send_error_email(po_number, error_message, file_url=None, channel_name="Zepto"):
    """Send an error email using the HTML template."""
    try:
        # Debugging: Ensure the function is called
        print(f"send_error_email called with po_number: {po_number}, error_message: {error_message}, file_url: {file_url}, channel_name: {channel_name}")

        # Fetch all users with the role 'B2B_Instamart'
        recipients = frappe.get_all(
            "Has Role",
            filters={"role": "B2B_Zepto"},
            fields=["parent"],
        )
        if not recipients:
            frappe.log_error("No recipients found with the role 'B2B_Zepto'.")
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
        print(f"Recipients fetched: {recipient_emails}")

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
        print(f"Sending email to: {recipient_emails}")

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


def is_partial_match(text, keywords):
    """Check if any keyword is similar to the text."""
    text = text.lower()  # Convert text to lowercase for case-insensitive comparison
    for keyword in keywords:
        keyword = keyword.lower()  # Convert keyword to lowercase
        if keyword in text or SequenceMatcher(None, text, keyword).ratio() > 0.6:
            return True
    return False

# Call the main function 
if __name__ == "__main__":
    process_email_attachments()





