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
            LABEL_NAME = "Flipkart"
        else:
            frappe.throw("Email record not found in the database.")
    else:
        print("Table 'B2B_EMAIL' does not exist.")
        frappe.throw("Email table does not exist.")
    
     # Fetch CardCode and SalesPersonCode from B2B-Customer-Details
    customer_details_record = frappe.db.get_value(
        "B2B_Customer_Details", 
        None, 
        ["cardcode6", "salespersoncode6"], 
        as_dict=True
    )
    
    if customer_details_record:
        CardCode = customer_details_record.get('cardcode6')
        SalesPersonCode = customer_details_record.get('salespersoncode6')
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

    def extract_po_data(xls_data):
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
                po_number = None
                po_expiry = None
                shipped_to = ""
                table_data = None
                totals = {}
                items = []

                for idx, row in df.iterrows():
                    row_str = " ".join(row.dropna().astype(str))

                    # PO Number
                    if "PO#" in row_str:
                        match = re.search(r'PO#\s*([A-Z0-9]+)', row_str)
                        if match:
                            po_number = match.group(1)

                    # PO Expiry
                    if "PO Expiry" in row_str:
                        match = re.search(r'PO Expiry\s*[:\-]?\s*([\d\-]+)', row_str)
                        if match:
                            po_expiry = match.group(1)

                    # Shipped To Address
                    if "SHIPPED TO ADDRESS" in row_str.upper() and not shipped_to:
                        # Extract the address from the same row, starting from the next column
                        full_address = " ".join(row[1:].dropna().astype(str)).strip()
                        # Dynamically truncate the address at the first unrelated section or keyword
                        stop_keywords = ["GSTIN", "STATE CODE", "ORDER DETAILS", "BILLED TO ADDRESS"]
                        for keyword in stop_keywords:
                            if (keyword in full_address.upper()):
                                full_address = full_address.split(keyword, 1)[0].strip()
                                break
                        shipped_to = full_address

                    # Extract item table starting at "HSN/SA Code"
                    if "HSN/SA Code" in row_str:
                        header_row = df.iloc[idx].dropna().astype(str).tolist()
                        data_start = idx + 1
                        for j in range(data_start, len(df)):
                            item_row = df.iloc[j].dropna().astype(str).tolist()
                            # Stop at total or summary lines
                            if any(kw in " ".join(item_row) for kw in ["Total Quantity=", "Important Notification"]):
                                break
                            if len(item_row) == len(header_row):
                                items.append(dict(zip(header_row, item_row)))

                    # Totals parsing (from rest of the rows)
                    if "Total Quantity=" in row_str:
                        match = re.search(r'Total Quantity=\s*(\d+)', row_str)
                        if match:
                            totals["Total Quantity"] = match.group(1)
                    if "Total=" in row_str:
                        total_vals = re.findall(r'([\d,]+\.\d+)\s*INR', row_str)
                        if total_vals:
                            totals["Subtotal"] = total_vals[0]
                            if len(total_vals) > 1:
                                totals["Tax Amount"] = total_vals[1]
                            if len(total_vals) > 2:
                                totals["Total Amount"] = total_vals[2]

                extracted_data[sheet_name] = {
                    "po_number": po_number,
                    "po_expiry": po_expiry,
                    "shipped_to": shipped_to,
                    "items": items,
                    "totals": totals
                }
            
            return extracted_data

        except Exception as e:
            print(f"Error extracting PO data: {e}")
            return None

    
    def save_pdf_to_file(extracted_data, xls_data):
        """Save the PDF to S3 inside a dynamically set folder."""
       
        po_number = next(iter(extracted_data.values())).get("po_number")  # Extract the 'po_number' value
        print(f"PO Number: {po_number}")  
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
                folder_name = (aws_record.folder_insta or "Flipkart").strip().strip('/')
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

        file_name = f"{folder_name}/Flipkart_{po_number}.xls"  # Ensure proper path format

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
        itemmap_records = frappe.get_all('Itemmap6')
        print(f"Found {len(itemmap_records)} Itemmap4 records")
        
        for record in itemmap_records:
            itemmap_doc = frappe.get_doc("Itemmap6", record.name)
            if hasattr(itemmap_doc, "map_item") and itemmap_doc.map_item:
                for mapping in itemmap_doc.map_item:
                    item_sap_map.append({
                        'item_code': str(mapping.item_code).strip(),  # Ensure string and clean whitespace
                        'sap_code': str(mapping.sap_code).strip()
                    })
        
        # print("Mapped Items:", item_sap_map)
        return item_sap_map


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
        items_list = next(iter(extracted_data.values())).get("items", [])  # Fetch 'items' from extracted_data
        # print("Items List:", items_list)
        

        for item in items_list:
            # Use 'FSN/ISBN13' as item_code
            item_code = str(item.get("FSN/ISBN13")).strip()  # Fetch 'FSN/ISBN13' as item_code
            # print(f"Processing item code: {item_code}")
            if not item_code:
                print("Skipping item with missing 'FSN/ISBN13'.")
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
            frappe.throw("No matching records found for any item codes.")



    @frappe.whitelist()
    def Get_CustomerDetails(CardCode, extracted_data):
        try:
            # print(f"CardCode:",CardCode)
            def similar(a, b):
                return SequenceMatcher(None, a.lower(), b.lower()).ratio()

            # Extract PO No and Main Address from item_list
            po_number = next(iter(extracted_data.values())).get("po_number")
            # print(f"PO Number (raw): {po_number}")
            delivered_to = next(iter(extracted_data.values())).get("shipped_to")
            # print(f"Delivered To (raw): {delivered_to}")

            zip_match = re.search(r'\b\d{6}\b', delivered_to)
            delivered_zip = zip_match.group() if zip_match else None
            # print(f"Extracted ZIP code: {delivered_zip}")

            address_entries = []
            ada_docs = frappe.get_all("ADA_6", fields=["name"])
            for ada_doc in ada_docs:
                ada_record = frappe.get_doc("ADA_6", ada_doc.name)
                if hasattr(ada_record, "address_table6") and ada_record.address_table6:
                    for address in ada_record.address_table6:
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



    def move_email_to_processed(mail, email_uid):
        """Move an email to the Flipkart-Processed folder using IMAP UIDs."""
        try:
            # Ensure the "Blinkit-Processed" folder exists
            mail.create('Flipkart-Processed')
        except imaplib.IMAP4.error:
            pass  # Folder already exists, no need to create it

        try:
            # Copy the email using UID
            copy_result = mail.uid('copy', email_uid, 'Flipkart-Processed')
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


    def send_error_notification(email_uid, error_message, po_number=None):
        """Send an email notification for processing errors."""
        try:
            # Fetch all users with the role 'flipkart_Zepto'
            recipients = frappe.get_all(
                "Has Role",
                filters={"role": "B2B_Flipkart"},
                fields=["parent"],
            )
            # Extract email addresses of the users
            recipient_emails = [
                frappe.db.get_value("User", user["parent"], "email")
                for user in recipients
                if frappe.db.get_value("User", user["parent"], "enabled")  # Ensure the user is enabled
            ]
            # Remove any None values (in case some users don't have an email)
            recipient_emails = [email for email in recipient_emails if email]

            if not recipient_emails:
                print("No users found with the role 'B2B_Flipkart'. Email not sent.")
                return

            # Ensure po_number is meaningful
            po_number = po_number or "Unknown_PO"

            # Print the PO number
            print(f"PO Number in error notification: {po_number}")

            # Include PO number in the email body if available
            po_number_info = f"<p><b>PO Number:</b> {po_number}</p>" if po_number else ""

            # Send the email
            frappe.sendmail(
                recipients=recipient_emails,
                subject=f"Error in B2B_Flipkart Email UID: {email_uid}",
                message=f"""
                    <p>Dear User,</p>
                    <p>An error occurred while processing the email with UID: <b>{email_uid}</b>.</p>
                    {po_number_info}
                    <p><b>Error Details:</b> {error_message}</p>
                    <p>Please check the logs for more information.</p>
                    <p>Regards,<br>Khanal Tech Integrations</p>
                """
            )
            print(f"Error notification sent for email UID {email_uid} to users with the role 'B2B_Flipkart'.")
        except Exception as e:
            print(f"Failed to send error notification: {str(e)}")



    # **************************************************************************** 

    @frappe.whitelist()
    def process_b2b_data(json_data):
        """
        Process the JSON data and store it in the B2B doctype.
        """
        try:
            # Ensure json_data is not None
            print(f"Received JSON Data: {json_data}")
            if not json_data:
                print("Error: JSON data is None or empty.")
                return

            # Ensure json_data is a dictionary (if it's passed as a string, parse it)
            if isinstance(json_data, str):
                json_data = frappe.parse_json(json_data)

            # Helper function to clean numeric fields
            def clean_numeric(value):
                """Remove non-numeric characters and convert to float or int."""
                if isinstance(value, str):
                    value = re.sub(r'[^\d.-]', '', value)  # Remove non-numeric characters
                try:
                    return int(value) if value.isdigit() else float(value)
                except ValueError:
                    return value  # Return as-is if conversion fails

            # Clean numeric fields in items
            for item in json_data.get("items", []):
                for key, value in item.items():
                    if isinstance(value, str) and "INR" in value:  # Check for "INR" in the value
                        item[key] = clean_numeric(value)

            # Clean numeric fields in totals
            for key, value in json_data.get("totals", {}).items():
                if isinstance(value, str) and "INR" in value:  # Check for "INR" in the value
                    json_data["totals"][key] = clean_numeric(value)

            # Initialize totals
            total_quantity = 0
            total_amount = 0
            unique_items = set()

            # Calculate totals from items
            for item in json_data.get("items", []):
                quantity = clean_numeric(item.get("Quantity", 0))
                total = clean_numeric(item.get("Total Amount", 0))
                item_code = item.get("FSN/ISBN13", "").strip()

                total_quantity += quantity
                total_amount += total
                if item_code:
                    unique_items.add(item_code)

            total_items = len(unique_items)  # Count unique items

            # Safely extract data from JSON with default values
            po_number = json_data.get("po_number", "N/A")  # Default to "N/A" if po_number is missing
            email_id = json_data.get("email_id", "N/A")  # Extract email_id from json_data
            delivered_to = json_data.get("delivered_to", {})
            customer_details = json_data.get("customer_details", {})
            file_url = json_data.get("file_url", "")

            item_data_response = json_data.get("item_data_response", [])  # Ensure this is treated as a list
            po_expiry = json_data.get("po_expiry", None)  # Extract po_expiry from json_data
            if po_expiry:
                try:
                    # Parse the date in the format 'YY-MM-DD' and convert to 'YYYY-MM-DD'
                    parsed_date = datetime.strptime(po_expiry, "%y-%m-%d")
                    po_expiry = parsed_date.strftime("%Y-%m-%d")  # Convert to 'YYYY-MM-DD'
                except ValueError:
                    print(f"Invalid date format for PO Expiry: {po_expiry}")
                    po_expiry = None  # Fallback to None if parsing fails

            if not frappe.db.table_exists("Flipkart"):
                print('Doctype "Flipkart" does not exist.')
                return

            # Check if the record already exists
            existing_record_name = frappe.db.exists("Flipkart", {"po_number": po_number})
            updated = False

            if existing_record_name:
                # Update existing record
                doc = frappe.get_doc("Flipkart", existing_record_name)
                updated = True
            else:
                # Create new record
                doc = frappe.new_doc("Flipkart")

            # Update fields in the document
            doc.po_number = po_number
            doc.company_name = customer_details.get("CustomerName", "")  # Ensure company_name is updated
            doc.email_id = email_id
            doc.po_url = file_url
            doc.delivered_to = delivered_to  # Set delivered_to directly
            doc.matched_address_name = customer_details.get("MatchedAddress", {}).get("AddressName", "")
            doc.matched_state = customer_details.get("MatchedState", "")
            doc.customer_code = customer_details.get("CardCode", "")
            doc.employee_id = customer_details.get("SalesPersonCode", "")
            doc.po_expiry_date = po_expiry

            # Set calculated totals
            doc.total_quantity = total_quantity
            doc.total_amount = total_amount
            doc.total_items = total_items

            # Set default values for Billing_from and Billto
            matched_state = doc.matched_state
            doc.billing_from = "KT"
            doc.billto = "Local" if matched_state == "KT" else "Central"

            # Clear existing child table rows (if updating)
            if updated:
                doc.flipkart_table = []

            # Add items to the child table
            items = json_data.get("items", [])  # Ensure items are fetched from json_data
            if item_data_response and items:
                for item, item_data in zip(items, item_data_response):
                    tax_prefix = "KACS" if doc.matched_state == "KT" else "KAIG"
                    tax_rate = int(item_data.get("U_TaxRate", 0))
                    taxcode = f"{tax_prefix}{tax_rate}"

                    child_row = {
                        "quantity": item.get("Quantity", 0),
                        "item_code": item_data.get("ItemCode", ""),
                        "sap_code": item_data.get("SAPCode", ""),
                        "product_description": item_data.get("ItemName", ""),
                        "tax_rate": item_data.get("U_TaxRate", 0),
                        "gst_tax": item_data.get("U_GstTax", ""),
                        "igst_tax": item_data.get("U_IgstTax", ""),
                        "mrp": item.get("Supplier MRP", ""),
                        "basic_cost_price": item.get("Supplier Price", ""),
                        "taxable_value": item.get("Taxable Value", ""),
                        "igst_rate": item.get("IGST Rate", ""),
                        "igst_amount_per_unit": item.get("IGST Amount(per unit)", ""),
                        "sgst_utgst_rate": item.get("SGST/UTGST Rate", ""),
                        "sgst_utgst_amount_per_unit": item.get("SGST/UTGST Amount(per unit)", ""),
                        "cgst_rate": item.get("CGST Rate", ""),
                        "cgst_amount_per_unit": item.get("CGST Amount(per unit)", ""),
                        "cess_rate": item.get("CESS Rate", ""),
                        "cess_amount_per_unit": item.get("CESS Amount(per unit)", ""),
                        "tax_amount": item.get("Tax Amount", ""),
                        "total_amount": item.get("Total Amount", ""),
                        "taxcode": taxcode  # Added taxcode
                    }
                    doc.append("flipkart_table", child_row)

            # Save or insert the document
            if updated:
                doc.save()
                print(f"Record updated for P.O. Number: {po_number}.")
            else:
                doc.name = f"{po_number}-{frappe.generate_hash(length=8)}"
                doc.insert()
                print(f"New record created for P.O. Number: {po_number}.")

        except Exception as e:
            print(f"Error processing B2B data: {str(e)}")
            frappe.log_error(f"Error in process_b2b_data: {str(e)}")

    

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
                                    # Decode the filename if necessary
                                    xls_data = part.get_payload(decode=True)
                                    if isinstance(xls_data, bytes):
                                        print(f"Found xls attachment: {filename}")  # Print only the filename
                                        extracted_data = extract_po_data(xls_data)
                                        po_number = next(iter(extracted_data.values())).get("po_number", "Unknown_PO")
                                        print(f"Extracted PO Number: {po_number}")  # Debug print for PO number

                                        file_url = save_pdf_to_file(extracted_data, xls_data)  # Pass xls_data here
                                        customer_details = Get_CustomerDetails(CardCode, extracted_data)

                                        code_sheet_data = fetch_item_sap_mapping()
                                        itemmaster_result = itemmaster(extracted_data, code_sheet_data)

                                        matched_address = None
                                        if customer_details['Status'] == 'Success':
                                            matched_address = next((address for address in customer_details['Result']['Addresses'] if address['AddressName'] == customer_details['Result']['MatchedAddressName']), None)
                                            if matched_address:
                                                matched_address = {
                                                    "AddressName": matched_address["AddressName"],
                                                    "State": matched_address["State"]
                                                }

                                        json_data = {
                                            "po_number": po_number,
                                            "email_id": email_uid_str,
                                            "delivered_to": next(iter(extracted_data.values())).get("shipped_to"),
                                            "customer_details": {
                                                "CardCode": customer_details['Result']['CardCode'],
                                                "SalesPersonCode": SalesPersonCode,
                                                "CustomerName": customer_details['Result']['CustomerName'],
                                                "MatchedAddress": matched_address,
                                                "MatchedState": customer_details['Result']['MatchedState']
                                            },
                                            "file_url": file_url,
                                            "item_data_response": itemmaster_result,
                                            "items": next(iter(extracted_data.values())).get("items"),
                                            "totals": next(iter(extracted_data.values())).get("totals"),
                                            "po_expiry": next(iter(extracted_data.values())).get("po_expiry")
                                        }
                                        print(f"JSON Data: {json_data}")

                                        process_b2b_data(json_data)

                                        # Move the email to the processed folder
                                        if move_email_to_processed(mail, email_uid_str):
                                            print(f"Moved email UID {email_uid_str}")
                                        else:
                                            print(f"Failed to move email {email_uid_str}.")

                                        with open(f"{po_number}.json", "w") as json_file:
                                            json.dump(json_data, json_file, indent=4)

                                    else:
                                        send_error_notification(email_uid_str, str(e), po_number)

                except Exception as e:
                    po_number = locals().get("po_number", "Unknown_PO")  # Ensure po_number is available
                    error_message = f"Error processing email UID {email_uid_str}: {str(e)}"
                    print(error_message)
                    frappe.log_error(error_message)
                    send_error_notification(email_uid_str, str(e), po_number)
                    continue  # Continue with the next email
        except Exception as e:
            error_message = f"Error reading attachments: {str(e)}"
            print(error_message)
            frappe.log_error(error_message)
            send_error_notification("N/A", str(e))  # Trigger email notification for general errors
            return {"Status": "Failed", "Message": str(e)}

    # print("Starting email attachment processing...")
    try:
        mail = connect_to_email()
        
        result = read_attachments(mail, CardCode)
        # print(result)
        mail.logout()
        print("Finished email attachment processing.")
    except Exception as e:
        frappe.log_error(f"Error in process_email_attachments: {str(e)}")
        print(f"An error occurred: {str(e)}")

# Call the main function 
if __name__ == "__main__":
    process_email_attachments()

    #bench --site alpha.localhost execute khanal_tech_integrations.utils.B2B.Bigbasket.process_email_attachments