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
            global EMAIL, PASSWORD, IMAP_SERVER, IMAP_PORT, LABEL_NAME
            EMAIL = email_record.get('email')
            PASSWORD = email_record.get('password')
            IMAP_SERVER = email_record.get('imap_server')
            IMAP_PORT = email_record.get('imap_port') or 993  # Default to 993 if not set
            LABEL_NAME = "More Retail"
        else:
            frappe.throw("Email record not found in the database.")
    else:
        frappe.throw("Email table does not exist.")

    # Fetch CardCode and SalesPersonCode from B2B-Customer-Details
    customer_details_record = frappe.db.get_value(
        "B2B_Customer_Details",
        None,
        ["cardcode3", "salespersoncode3"],
        as_dict=True
    )

    if customer_details_record:
        CardCode = customer_details_record.get('cardcode3')
        SalesPersonCode = customer_details_record.get('salespersoncode3')
        print("CardCode:", CardCode)
    else:
        frappe.throw("Customer details record not found in the database.")

    print("Starting email attachment processing...")
    try:
        mail = connect_to_email()
        read_attachments(mail, CardCode, SalesPersonCode)  # Pass SalesPersonCode here
        mail.logout()
        print("Finished email attachment processing.")
    except Exception as e:
        frappe.log_error(f"Error in process_email_attachments: {str(e)}")
        print(f"An error occurred: {str(e)}")


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


def extract_address_columns(pdf_data):
    # Wrap pdf_data in BytesIO to create a file-like object
    pdf_file = io.BytesIO(pdf_data)
    
    with pdfplumber.open(pdf_file) as pdf:
        page = pdf.pages[0]
        full_text = page.extract_text()

        # Extract the top line from the PDF (assumed to be company name)
        company_name_regex = full_text.split('\n')[0].strip() if full_text else None

        # Extract PO Number using regex
        po_number_match = re.search(r'PO\s*Number[:\s]*([A-Z0-9\-\/]+)(.*)?', full_text, re.IGNORECASE)
        # print("po_number_match", po_number_match)
        po_number = None
        if po_number_match:
            po_number = po_number_match.group(1).strip()
            extra_text = po_number_match.group(2).strip() if po_number_match.group(2) else ""
            if extra_text:
                # print(f"Extra text found after PO Number: {extra_text}, removing it.")
                pass  # Add this line to fix the indentation issue
            # print("Extracted PO Number:", po_number)

        # Define and extract shipping address only (based on coordinates)
        shipping_box = (0, 100, 290, 300)
        shipping_text = page.within_bbox(shipping_box).extract_text()

        # Clean and keep only relevant shipping lines
        clean_shipping = []
        if shipping_text:
            for line in shipping_text.split('\n'):
                line = line.strip()
                if re.search(r'^\d+', line):  # Line starts with a number
                    clean_shipping.append(line)
                elif clean_shipping and not re.search(r'(GSTIN|FSA|CIN)', line, re.IGNORECASE):
                    clean_shipping.append(line)
                elif re.search(r'(GSTIN|FSA|CIN)', line, re.IGNORECASE):
                    break  # Stop at unwanted tags

        shipping_result = "\n".join(clean_shipping).strip() if clean_shipping else None

    return company_name_regex, po_number, shipping_result


def API_DATA(po_number):
    url = "https://q9tnbydjxd.execute-api.ap-south-1.amazonaws.com/dev/po"
    payload = {
        "username": "2115794",
        "password": "2115794"
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

        # Log the raw response and parsed data
        # print(f"Raw API Response for PO number {po_number}: {response.text}")
        # print(f"Parsed API Data: {data}")

        if not data:
            print(f"API returned no data for PO number: {po_number}")
            return None

        if isinstance(data, list):
            for order in data:
                if str(order.get("ORDER_NO")) == str(po_number):
                    po_number = order.get("ORDER_NO")
                    extracted_data = order.get("EXPIRY_DATE")
                    
                    extracted_items = []
                    for item in order.get("Details", []):
                        if not item:
                            print("Skipping empty item in API response.")
                            continue
                        item_code = item.get("ITEM")
                        product_description = item.get("ITEM_DESC")
                        quantity = item.get("QTY_ORDERED")
                        basic_cost_price = item.get("UNIT_COST")
                        mrp = item.get("MRP")
                        tax_amount = item.get("TAX_AMOUNT")
                        tax_percentage = item.get("TAX_PERC")
                        extracted_items.append({
                            "item_code": item_code,
                            "product_description": product_description,
                            "quantity": quantity,
                            "basic_cost_price": basic_cost_price,
                            "mrp": mrp,
                            "tax_amount": tax_amount,
                        })

                    return {
                        "po_number": po_number,
                        "expiry_date": extracted_data,
                        "items": extracted_items
                    }
            print(f"No matching order found for PO number: {po_number}")
        else:
            print(f"Unexpected API response format: {data}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"API Request failed: {e}")
        return None


@frappe.whitelist()
def save_pdf_to_file(pdf_data, po_number, shipping_address):
    """Save the PDF to S3 inside a dynamically set folder."""
    if not po_number or po_number == "Not Found":
        po_number = "Unknown_PO"

    # Fetch AWS credentials, bucket name, and folder name
    if frappe.get_single("AWS"):
        aws_record = frappe.db.get_value(
            "AWS", None, 
            ["aws_access_key_id", "aws_secret_access_key", "bucket_name", "folder_moreretails"], 
            as_dict=True
        )

        if aws_record:
            aws_access_key_id = aws_record.aws_access_key_id.strip()
            aws_secret_access_key = aws_record.aws_secret_access_key.strip()
            bucket_name = aws_record.bucket_name.strip()
            folder_name = (aws_record.folder_moreretails or "MoreRetails").strip().strip('/')
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

    file_name = f"{folder_name}/MoreRetails_{po_number}.pdf"  # Ensure proper path format

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
def Get_CustomerDetails(CardCode, po_number, shipping_result):
    """Fetch best matching address ID using CardCode, PO number, and shipping address."""
    import re
    from difflib import SequenceMatcher

    try:
        # print(f"Received CardCode: {CardCode}")
        # print(f"PO Number: {po_number}")
        # print(f"Shipping Address: {shipping_address}")

        delivered_to = shipping_result
        # print(f"Delivered To (raw): {delivered_to}")

        # Extract ZIP code from the shipping address
        zip_match = re.search(r'\b\d{6}\b', delivered_to)
        delivered_zip = zip_match.group() if zip_match else None
        # print(f"Extracted ZIP code: {delivered_zip}")

        # Fetch address entries from ADA_3
        address_entries = []
        ada_docs = frappe.get_all("ADA_3", fields=["name"])
        for ada_doc in ada_docs:
            ada_record = frappe.get_doc("ADA_3", ada_doc.name)
            if hasattr(ada_record, "address_table3") and ada_record.address_table3:
                for address in ada_record.address_table3:
                    address_entries.append({
                        'address_id': address.address_id,
                        'address_entry': address.address_entry
                    })
        # print("Address Entries:", address_entries)

        # Find the best matching address
        def similar(a, b):
            if not a or not b:
                return 0
            return SequenceMatcher(None, a.lower(), b.lower()).ratio()

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
            error_message = "No sufficiently similar address entry found."
            print(error_message)
            send_error_email(
                po_number=str(po_number),
                error_message=error_message,
                file_url=None,
                channel_name="More Retails"
            )
            return None  # Stop further processing

        # Fetch SAP Customer Details
        try:
            # print("Fetching SAP Settings...")
            doc_settings = frappe.get_doc('SAP Settings')

            print("Authenticating with SAP B1...")
            session = AuthenticateSAPB1()

            Url = doc_settings.sap_b1_url + f"BusinessPartners?$filter=CardCode eq '{CardCode}'"
            response = session.request("GET", Url, headers=headersList, verify=False)

            customer_data = response.json()

            if not customer_data.get('value'):
                error_message = f"No customer data found for CardCode: {CardCode}"
                print(error_message)
                send_error_email(
                    po_number=str(po_number),
                    error_message=error_message,
                    file_url=None,
                    channel_name="More Retails"
                )
                return None  # Stop further processing

            customer_details = customer_data['value'][0]
            addresses = customer_details.get('BPAddresses', [])

            matched_state = None
            matched_address_name = None

            # Check if matched_address_id exists in SAP's AddressName
            for address in addresses:
                if address.get('AddressName') == matched_address_id:
                    matched_address_name = address.get('AddressName')
                    matched_state = address.get('State')
                    # print(f"Matched Address Found: {matched_address_name}, State: {matched_state}")
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
            error_message = f"Error in SAP request: {str(e)}"
            print(error_message)
            send_error_email(
                po_number=str(po_number),
                error_message=error_message,
                file_url=None,
                channel_name="More Retails"
            )
            return None  # Stop further processing

    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        print(error_message)
        send_error_email(
            po_number=str(po_number),
            error_message=error_message,
            file_url=None,
            channel_name="More Retails"
        )
        return None  # Stop further processing




@frappe.whitelist()
def fetch_item_sap_mapping():
    print("Fetching Itemmap records...")
    item_sap_map = []
    
    # Fetch all Itemmap3 documents
    itemmap_records = frappe.get_all('Itemmap3')
    # print(f"Found {len(itemmap_records)} Itemmap3 records")
    
    for record in itemmap_records:
        itemmap_doc = frappe.get_doc("Itemmap3", record.name)
        if hasattr(itemmap_doc, "map_item") and itemmap_doc.map_item:
            for mapping in itemmap_doc.map_item:
                item_sap_map.append({
                    'item_code': str(mapping.item_code).strip(),  # Ensure string and clean whitespace
                    'sap_code': str(mapping.sap_code).strip()
                })
    
    # print("Mapped Items:", item_sap_map)
    return item_sap_map




def move_email_to_processed(mail, email_uid):
    """Move an email to the Blinkit-Processed folder using IMAP UIDs."""
    try:
        # Ensure the "Blinkit-Processed" folder exists
        mail.create('MoreRetails-Processed')
    except imaplib.IMAP4.error:
        pass  # Folder already exists, no need to create it

    try:
        # Copy the email using UID
        copy_result = mail.uid('copy', email_uid, 'MoreRetails-Processed')
        if copy_result[0] == 'OK':
            # Mark the original email for deletion using UID
            store_result = mail.uid('store', email_uid, '+FLAGS', '\\Deleted')
            if store_result[0] == 'OK':
                mail.expunge()  # Permanently delete the email
                print(f"Moved email UID {email_uid} to MoreRetails-Processed folder.")  # Keep only one print statement
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
def itemmaster(code_sheet_data, api_extracted, email_uid_str):
    """Fetch from item master using a list of item codes, mapping to SAP codes."""
    # print("Received API extracted data:", api_extracted)
    # print("Received code_sheet_data...")

    doc_settings = frappe.get_doc('SAP Settings')
    session = AuthenticateSAPB1()
    payload = ''
    results = []

    # Convert list to dict if needed
    if isinstance(code_sheet_data, list):
        code_sheet_data = {item['item_code']: item['sap_code'] for item in code_sheet_data}

    item_to_sap_map = code_sheet_data

    # Get the items from api_extracted
    items_list = api_extracted.get("items", [])

    for item in items_list:
        item_code = str(item.get("item_code"))
        sap_code = item_to_sap_map.get(item_code)

        if not sap_code:
            error_message = f"No mapping found for item code {item_code}, stopping process."
            print(error_message)
            frappe.log_error(error_message)
            send_error_email(
                po_number=str(api_extracted.get("po_number", "Unknown")),  # Ensure string conversion
                error_message=str(error_message),  # Ensure string conversion
                file_url=None,
                channel_name="More Retails"
            )
            return False  # Stop further processing

        url = doc_settings.sap_b1_url + f"Items('{sap_code}')"
        try:
            response = session.request("GET", url, data=payload, headers=headersList, verify=False)

            if response.status_code == 200:
                item_data = response.json()
                results.append({
                    "ItemCode": item_code,
                    "SAPCode": sap_code,
                    "ItemName": item_data.get('ItemName', 'N/A'),
                    "U_TaxRate": item_data.get('U_TaxRate', 'N/A'),
                    "U_GstTax": item_data.get('U_GstTax', 'N/A'),
                    "U_IgstTax": item_data.get('U_IgstTax', 'N/A')
                })
            else:
                print(f"Error fetching data for SAP code {sap_code} (Item code {item_code}): {response.text}")
        except Exception as e:
            print(f"Exception occurred while fetching data for SAP code {sap_code} (Item code {item_code}): {e}")

    if results:
        return {"data": results}
    else:
        frappe.throw("No matching records found for any item codes.")


@frappe.whitelist()
def process_b2b_data(json_data, mail, email_uid_str):
    """
    Process the JSON data and store it in the MoreRetails doctype.
    """
    try:
        # Ensure json_data is not None
        if not json_data:
            print("Error: JSON data is None or empty.")
            return

        # Ensure json_data is a dictionary (if it's passed as a string, parse it)
        if isinstance(json_data, str):
            json_data = frappe.parse_json(json_data)

        # Print the entire JSON data
        # print("Received JSON Data:", json.dumps(json_data, indent=2))

        # Safely extract data from JSON with default values
        po_number = json_data.get("po_number", "N/A")
        company_name = json_data.get("CompanyName", "N/A")
        po_expiry_date = json_data.get("expiry_date", "N/A")  # Extract expiry_date
        email_id = json_data.get("email_id", "N/A")
        file_url = json_data.get("file_url", "")
        delivered_to = json_data.get("matched_address_id", "Unknown Address")  # Use matched_address_id for delivered_to
        matched_address = json_data.get("MatchedAddress", {})
        matched_state = json_data.get("MatchedState", None)
        item_data_response = json_data.get("items", [])
        customer_code = json_data.get("CardCode", "")  # Extract customer_code
        employee_id = json_data.get("SalesPersonCode", "")  # Extract employee_id

        # Check if MoreRetails doctype exists
        if not frappe.db.table_exists("MoreRetails"):
            print('Doctype "MoreRetails" does not exist.')
            return

        # Check if the record already exists
        existing_record_name = frappe.db.exists("MoreRetails", {"po_number": po_number})
        updated = False

        if existing_record_name:
            # Update existing record
            doc = frappe.get_doc("MoreRetails", existing_record_name)
            updated = True
        else:
            # Create new record
            doc = frappe.new_doc("MoreRetails")

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
        doc.billto = "Local" if matched_state == "KT" else "Central"

        # Initialize totals
        total_quantity = 0
        total_amount = 0
        unique_items = set()

        # Clear existing child table rows (if updating)
        if updated:
            doc.moreretail_table = []

        # Add item details to the child table and accumulate totals
        for item in item_data_response:
            quantity = item.get("quantity", 0)
            total_item_amount = item.get("basic_cost_price", 0) * quantity
            item_code = item.get("item_code", "")

            # Determine the taxcode format based on matched_state
            tax_prefix = "KACS" if matched_state == "KT" else "KAIG"
            tax_rate = int(item.get("U_TaxRate", 0))
            taxcode = f"{tax_prefix}{tax_rate}"

            # Append item to child table
            doc.append("moreretail_table", {
                "item_code": item_code,
                "sap_code": item.get("sap_code", ""),
                "item_name": item.get("item_name", ""),
                "product_description": item.get("product_description", ""),  # Include product_description
                "quantity": quantity,
                "basic_cost_price": item.get("basic_cost_price", 0),
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

        # Commit the transaction
        try:
            if move_email_to_processed(mail, email_uid_str):  # Pass mail explicitly
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
            send_error_email(
                po_number=str(po_number),  # Ensure string conversion
                error_message=str(error_message),  # Ensure string conversion
                file_url=str(file_url) if file_url else None,  # Ensure string conversion
                channel_name="More Retails"
            )
            return False  # Stop further processing on error

    except Exception as e:
        error_message = f"Error processing zepto_table data: {str(e)}"
        print(error_message)
        frappe.log_error(f"Error in zepto_table: {str(e)}")
        send_error_email(
            po_number=str(po_number),  # Ensure string conversion
            error_message=str(error_message),  # Ensure string conversion
            file_url=str(file_url) if file_url else None,  # Ensure string conversion
            channel_name="More Retails"
        )

        # Stop further processing and do not move the email
        print(f"Halting process for email UID {email_uid_str} due to error.")
        return False  # Indicate failure to the caller

    return True  # Indicate success to the caller


def read_attachments(mail, CardCode, SalesPersonCode):  # Add SalesPersonCode as a parameter
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

                            if filename and filename.lower().endswith(".pdf"):
                                pdf_data = part.get_payload(decode=True)
                                if isinstance(pdf_data, bytes):
                                    print(f"Found PDF attachment: {filename}")

                                    # Extract data from the PDF
                                    company_name_regex, po_number, shipping_result = extract_address_columns(pdf_data)

                                    # Check for valid company name
                                    if "More Retail Private Limited" in company_name_regex:
                                        # print("Found valid PDF:", filename)
                                        api_extracted = API_DATA(po_number)
                                        if not api_extracted:
                                            send_error_email(
                                                po_number=str(po_number),
                                                error_message="Missing API data.",
                                                file_url=None,
                                                channel_name="More"
                                            )
                                            continue

                                        file_url = save_pdf_to_file(pdf_data, po_number, shipping_result)
                                        print(f"File saved at: {file_url}")

                                        customer_details = Get_CustomerDetails(CardCode, po_number, shipping_result)
                                        if not customer_details or customer_details.get('Status') != 'Success':
                                            send_error_email(
                                                po_number=str(po_number),
                                                error_message="Missing or invalid customer details.",
                                                file_url=file_url,
                                                channel_name="More Retails"
                                            )
                                            continue

                                        code_sheet_data = fetch_item_sap_mapping()
                                        itemmaster_result = itemmaster(code_sheet_data, api_extracted, email_uid_str)
                                        if not itemmaster_result:
                                            send_error_email(
                                                po_number=str(api_extracted.get("po_number", "Unknown")),
                                                error_message="Missing item mapping.",
                                                file_url=file_url,
                                                channel_name="More Retails"
                                            )
                                            continue

                                        # Prepare JSON data
                                        matched_address = next(
                                            (address for address in customer_details['Result']['Addresses']
                                             if address['AddressName'] == customer_details['Result']['MatchedAddressName']), None)
                                        if matched_address:
                                            matched_address = {
                                                "AddressName": matched_address["AddressName"],
                                                "State": matched_address["State"]
                                            }

                                        merged_item_data = []
                                        item_response_dict = {item["ItemCode"]: item for item in itemmaster_result.get("data", []) if item}
                                        for item in api_extracted.get("items", []):
                                            item_code = str(item.get("item_code"))
                                            if item_code in item_response_dict:
                                                merged_item_data.append({
                                                    "item_code": item_code,
                                                    "sap_code": item_response_dict[item_code].get("SAPCode"),
                                                    "item_name": item_response_dict[item_code].get("ItemName"),
                                                    "quantity": item.get("quantity"),
                                                    "basic_cost_price": item.get("basic_cost_price"),
                                                    "mrp": item.get("mrp"),
                                                    "U_TaxRate": item_response_dict[item_code].get("U_TaxRate", "N/A"),
                                                    "U_GstTax": item_response_dict[item_code].get("U_GstTax", "N/A"),
                                                    "U_IgstTax": item_response_dict[item_code].get("U_IgstTax", "N/A"),
                                                })

                                        json_data = {
                                            "po_number": po_number,
                                            "CompanyName": customer_details['Result']['CustomerName'],
                                            "expiry_date": api_extracted.get("expiry_date"),
                                            "matched_address_id": shipping_result,
                                            "MatchedAddress": matched_address,
                                            "MatchedState": customer_details['Result']['MatchedState'],
                                            "items": merged_item_data,
                                            "CardCode": CardCode,
                                            "SalesPersonCode": SalesPersonCode,
                                            "email_id": email_uid_str,
                                            "file_url": file_url
                                        }

                                        success = process_b2b_data(json_data, mail, email_uid_str)
                                        if not success:
                                            send_error_email(
                                                po_number=str(json_data.get("po_number", "Unknown")),
                                                error_message="Processing failure in process_b2b_data.",
                                                file_url=json_data.get("file_url"),
                                                channel_name="More Retails"
                                            )
                                            continue

            except Exception as e:
                send_error_email(
                    po_number="Unknown",
                    error_message=f"Error processing email UID {email_uid_str}: {str(e)}",
                    file_url=None,
                    channel_name="More Retails"
                )
                continue  # Log the error and continue processing other emails
    except Exception as e:
        send_error_email(
            po_number="Unknown",
            error_message=f"Error reading attachments: {str(e)}",
            file_url=None,
            channel_name="More Retails"
        )


def send_error_email(po_number, error_message, file_url=None, channel_name="More Retails"):
    """Send an error email using the HTML template."""
    try:
        # Debugging: Ensure the function is called
        print(f"send_error_email called with po_number: {po_number}, error_message: {error_message}, file_url: {file_url}, channel_name: {channel_name}")

        # Fetch all users with the role 'B2B_MoreRetails'
        recipients = frappe.get_all(
            "Has Role",
            filters={"role": "B2B_MoreRetails"},
            fields=["parent"],
        )
        if not recipients:
            frappe.log_error("No recipients found with the role 'B2B_MoreRetails'.")
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

        # Replace placeholders with actual values, ensuring all replacements are strings
        html_content = (
            html_template
            .replace("{{ po_number or \"N/A\" }}", str(po_number or "N/A"))  # Convert to string
            .replace("{{ error_message or \"No details provided.\" }}", str(error_message or "No details provided."))  # Convert to string
            .replace("{{ file_url or \"\" }}", str(file_url or ""))  # Convert to string
            .replace("{{ channel_name }}", str(channel_name))  # Convert to string
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
        print(f"Failed to send error email: {str(e)}")       


# Only for standalone testing (not used when Frappe calls the method)
if __name__ == "__main__":
    process_email_attachments()
