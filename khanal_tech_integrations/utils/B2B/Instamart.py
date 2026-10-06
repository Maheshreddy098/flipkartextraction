from email.header import decode_header
from datetime import datetime
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
from botocore.exceptions import NoCredentialsError
from bs4 import BeautifulSoup
from typing import Dict, List, Any, Optional
import frappe
import re
import email
import imaplib
import io
import boto3
import openpyxl
import pdfplumber
from difflib import SequenceMatcher
import requests
import json
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
            LABEL_NAME = "Instamart"
        else:
            frappe.throw("Email record not found in the database.")
    else:
        print("Table 'B2B_EMAIL' does not exist.")
        frappe.throw("Email table does not exist.")
    
     # Fetch CardCode and SalesPersonCode from B2B-Customer-Details
    customer_details_record = frappe.db.get_value(
        "B2B_Customer_Details", 
        None, 
        ["cardcode2", "salespersoncode2"], 
        as_dict=True
    )
    
    if customer_details_record:
        CardCode = customer_details_record.get('cardcode2')
        SalesPersonCode = customer_details_record.get('salespersoncode2')
        print("CardCode:", CardCode)    
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

    def normalize_extracted_text(text):
        """Normalize PDF/Excel text. New Instamart PDFs use tabs between words."""
        if not text:
            return ""
        text = text.replace("\t", " ")
        text = re.sub(r"[ ]{2,}", " ", text)
        return text

    def extract_pdf_text(pdf_data):
        """Extract PDF text with pdfplumber (works on live PyPDF2 2.x and new OTB PDFs)."""
        print("Extracting text from PDF...")
        if isinstance(pdf_data, dict):
            pdf_data = pdf_data.get("pdf", b"")
        if not isinstance(pdf_data, bytes):
            raise TypeError(f"Expected bytes, got {type(pdf_data)}")
        try:
            pdf_file = io.BytesIO(pdf_data)
            extracted_text = ""
            with pdfplumber.open(pdf_file) as pdf:
                print(f"PDF pages: {len(pdf.pages)}")
                if not pdf.pages:
                    print("Warning: No pages found in the PDF.")
                    return ""
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    if text:
                        extracted_text += text + "\n"
            return normalize_extracted_text(extracted_text)
        except Exception as e:
            print(f"Error extracting text: {e}")
            return ""

    def is_valid_instamart_pdf(pdf_text):
        """Accept both old and new Instamart PO PDF formats."""
        text = normalize_extracted_text(pdf_text)
        has_company = bool(re.search(r"SCOOTSY\s+LOGISTICS\s+PRIVATE\s+LIMITED", text, re.I))
        has_po = bool(re.search(r"PO\s+No", text, re.I))
        return has_company and has_po

    def extract_data(text):
        """Extract specific data from PDF text using regex."""
        text = normalize_extracted_text(text)
        data = {}
        company_name_regex = r"SCOOTSY\s+LOGISTICS\s+PRIVATE\s+LIMITED"
        po_number_regex = r"PO\s+No\s*:\s*([A-Za-z0-9]+)"
        po_expiry_date_regex = r"PO\s+Expiry\s+Date\s*[:\-]?\s*([A-Za-z]{3,9}\s+\d{1,2},\s*\d{4})"

        company_match = re.search(company_name_regex, text, re.I)
        data["company_name"] = "SCOOTSY LOGISTICS PRIVATE LIMITED" if company_match else "Not Found"

        data["po_number"] = re.search(po_number_regex, text, re.I).group(1) if re.search(po_number_regex, text, re.I) else "Not Found"

        po_expiry_date_match = re.search(po_expiry_date_regex, text, re.I)
        if po_expiry_date_match:
            po_expiry_date = re.sub(r"\s+", " ", po_expiry_date_match.group(1)).strip()
            try:
                datetime_object = datetime.strptime(po_expiry_date, "%b %d, %Y")
                formatted_date = datetime_object.strftime("%Y-%m-%d")
                data["po_expiry_date"] = formatted_date
            except ValueError:
                data["po_expiry_date"] = "Invalid Date Format"
        else:
            data["po_expiry_date"] = "Not Found"

        return data

    def read_xml_excel(xml_data: str) -> Dict[str, Any]:
        """Read and parse XML content."""
        try:
            soup = BeautifulSoup(xml_data, "xml")
            rows = soup.find_all("Row")

            def clean_text(text: str) -> str:
                """Clean and normalize text content."""
                return re.sub(r'\s+', ' ', text).strip() if text else ''

            def process_address(address_lines: List[str]) -> str:
                """Process and clean address lines."""
                return '\n'.join([line.strip() for line in address_lines if line.strip()])

            # Initialize data structures
            po_details: Dict[str, str] = {}
            vendor_name_found = False
            po_number_found = False

            # First pass: Extract PO details
            for row in rows:
                cells = [cell.get_text(strip=True) for cell in row.find_all("Data")]
                if not cells:
                    continue

                # Look for PO number in multiple formats
                for i, cell in enumerate(cells):
                    if "PO No" in cell or "PO Number" in cell:
                        if i + 1 < len(cells):
                            po_details["PO No"] = clean_text(cells[i + 1])
                        else:
                            po_number = cell.split(":")[-1].strip()
                            po_details["PO No"] = clean_text(po_number)
                        po_number_found = True

                if "Vendor Name :" in cells[0] and len(cells) >= 2:
                    po_details["Vendor Name"] = clean_text(cells[1])
                    vendor_name_found = True
                elif "PO Date :" in cells[0] and len(cells) > 1:
                    po_details["PO Date"] = clean_text(cells[1])
                elif "PO Release Date :" in cells[0] and len(cells) > 1:
                    po_details["PO Release Date"] = clean_text(cells[1])
                elif "Expected Delivery Date:" in cells[0] and len(cells) > 1:
                    po_details["Expected Delivery Date"] = clean_text(cells[1])
                elif "PO Expiry Date:" in cells[0] and len(cells) > 1:
                    po_details["PO Expiry Date"] = clean_text(cells[1])

                if vendor_name_found and po_number_found:
                    break

            # Extract addresses
            billing_address = []
            shipping_address = []
            address_section = False

            for row in rows:
                cells = [clean_text(cell.get_text()) for cell in row.find_all("Data")]
                if not cells:
                    continue

                if "Billing Address" in cells[0]:
                    address_section = True
                    continue

                if address_section:
                    if len(cells) >= 2:
                        billing_address = cells[0].split('\n')
                        shipping_address = cells[1].split('\n')
                    break

            billing_address_clean = process_address(billing_address)
            shipping_address_clean = process_address(shipping_address)

            # Extract main address from shipping address (supports old " - 123456" and new ", 123456")
            main_address_match = re.search(
                r"SCOOTSY LOGISTICS PRIVATE LIMITED.*?(?: - |,\s*)\d{6}",
                shipping_address_clean,
                re.DOTALL | re.IGNORECASE,
            )
            main_address = main_address_match.group(0) if main_address_match else (shipping_address_clean or "Not Found")

            # Extract item details
            items: List[Dict[str, Any]] = []
            headers = []
            item_section = False
            total_section = False

            for row in rows:
                cells = [clean_text(cell.get_text()) for cell in row.find_all("Data")]
                if not cells:
                    continue

                if any("S." in cell for cell in cells):
                    headers = [cell.replace('\n', ' ') for cell in cells]
                    item_section = True
                    continue

                if item_section and not total_section:
                    if "Total Amount (INR)" in cells[0]:
                        total_section = True
                        continue

                    if len(cells) >= 15 and cells[0].isdigit():
                        try:
                            item = {
                                "Item Code": cells[1],
                                "Item Description": ' '.join(cells[2].split()),
                                "HSN Code": cells[3],
                                "Quantity": int(float(cells[4])),
                                "MRP": float(cells[5]),
                                "Unit Base Cost (INR)": float(cells[6]),
                                "Taxable Value (INR)": float(cells[7]),
                                "CGST": float(cells[8]),
                                "SGST/UGST": float(cells[10]),
                                "IGST": float(cells[12]),
                                "CESS": float(cells[14]),
                                "Additional CESS": float(cells[16]),
                                "Total (INR)": float(cells[17])
                            }
                            items.append(item)
                        except (ValueError, IndexError) as e:
                            frappe.log_error(f"Error processing item row: {str(e)}")
                            continue

            # Extract total details
            total_details: Dict[str, Any] = {}
            for row in rows:
                cells = [clean_text(cell.get_text()) for cell in row.find_all("Data")]
                if not cells:
                    continue

                try:
                    if "Total Amount (INR)" in cells[0]:
                        total_details["Total Amount (INR)"] = float(cells[1]) if len(cells) > 1 else 0.0
                    elif "GST Compensation Cess" in cells[0]:
                        total_details["GST Compensation Cess"] = float(cells[-1]) if cells else 0.0
                    elif "GST Additional Cess" in cells[0]:
                        total_details["GST Additional Cess"] = float(cells[-1]) if cells else 0.0
                    elif "Total Tax (INR)" in cells[0]:
                        total_details["Total Tax (INR)"] = float(cells[-1]) if cells else 0.0
                    elif "Grand Total (INR)" in cells[0]:
                        total_details["Grand Total (INR)"] = float(cells[-1]) if cells else 0.0
                    elif "Amount in Words" in cells[0]:
                        total_details["Amount in Words"] = cells[-1] if cells else ""
                except ValueError as e:
                    frappe.log_error(f"Error processing total details: {str(e)}")
                    continue

            return {
                "PO Details": po_details,
                "Shipping Address": shipping_address_clean,
                "Billing Address": billing_address_clean,
                "Main Address": main_address,
                "Item Details": items,
                "Total Details": total_details
            }

        except Exception as e:
            frappe.log_error(f"Error processing file: {str(e)}")
            raise

    def read_xlsx_excel(xlsx_data: bytes) -> Dict[str, Any]:
        """Parse new Instamart OTB .xlsx attachments into the same structure as read_xml_excel."""
        try:
            def clean_text(text: str) -> str:
                return re.sub(r"\s+", " ", text).strip() if text else ""

            def to_float(value, default=0.0):
                try:
                    if value is None or value == "":
                        return default
                    return float(str(value).replace(",", "").strip())
                except (TypeError, ValueError):
                    return default

            def to_int(value, default=0):
                try:
                    return int(float(str(value).replace(",", "").strip()))
                except (TypeError, ValueError):
                    return default

            workbook = openpyxl.load_workbook(io.BytesIO(xlsx_data), data_only=True)
            sheet = workbook.active
            rows = [list(row) for row in sheet.iter_rows(values_only=True)]

            po_details: Dict[str, str] = {}
            label_keys = [
                ("PO No", "PO No"),
                ("PO Number", "PO No"),
                ("Vendor Name", "Vendor Name"),
                ("PO Date", "PO Date"),
                ("PO Release Date", "PO Release Date"),
                ("Expected Delivery Date", "Expected Delivery Date"),
                ("PO Expiry Date", "PO Expiry Date"),
            ]
            known_labels = {label.lower() for label, _ in label_keys}

            def looks_like_label(value: str) -> bool:
                text = clean_text(value).rstrip(":").strip().lower()
                return any(text == label or text.startswith(label) for label in known_labels)

            for row in rows:
                for idx, cell in enumerate(row):
                    if cell is None:
                        continue
                    cell_text = clean_text(str(cell))
                    for label, key in label_keys:
                        if key in po_details:
                            continue
                        # Require label-like cell (avoid matching free text)
                        if not re.search(rf"^{re.escape(label)}\s*:?\s*$", cell_text, re.I):
                            # Also allow "PO No : value" inline
                            inline_match = re.match(
                                rf"^{re.escape(label)}\s*:\s*(.+)$", cell_text, re.I
                            )
                            if inline_match and not looks_like_label(inline_match.group(1)):
                                po_details[key] = clean_text(inline_match.group(1))
                            continue

                        for next_cell in row[idx + 1:]:
                            if next_cell is None or str(next_cell).strip() == "":
                                continue
                            next_text = clean_text(str(next_cell))
                            # Stop at the next label; do not steal another field's value
                            if looks_like_label(next_text):
                                break
                            po_details[key] = next_text
                            break
                        break

            # New format often puts vendor company in its own block under Vendor Name
            if "Vendor Name" not in po_details:
                for row in rows:
                    for cell in row:
                        if cell is None:
                            continue
                        text = str(cell).strip()
                        upper = text.upper()
                        if "PRIVATE LIMITED" in upper and "SCOOTSY" not in upper:
                            po_details["Vendor Name"] = clean_text(text.split("\n")[0])
                            break
                    if "Vendor Name" in po_details:
                        break

            billing_address_clean = ""
            shipping_address_clean = ""
            for row_idx, row in enumerate(rows):
                cells = [clean_text(str(c)) if c is not None else "" for c in row]
                if any(c == "Billing Address" for c in cells) and row_idx + 1 < len(rows):
                    next_row = rows[row_idx + 1]
                    non_empty = [c for c in next_row if c is not None and str(c).strip()]
                    if len(non_empty) >= 1:
                        billing_address_clean = str(non_empty[0]).strip()
                    if len(non_empty) >= 2:
                        shipping_address_clean = str(non_empty[1]).strip()
                    elif len(non_empty) == 1:
                        shipping_address_clean = billing_address_clean
                    break

            # Keep newlines from Excel cells for address matching
            if not shipping_address_clean and billing_address_clean:
                shipping_address_clean = billing_address_clean

            main_address_match = re.search(
                r"SCOOTSY LOGISTICS PRIVATE LIMITED.*?(?: - |,\s*)\d{6}",
                shipping_address_clean,
                re.DOTALL | re.IGNORECASE,
            )
            main_address = main_address_match.group(0) if main_address_match else (shipping_address_clean or "Not Found")

            # Find item header row
            header_row_idx = None
            header_map: Dict[str, int] = {}
            for row_idx, row in enumerate(rows):
                cells = [clean_text(str(c)) if c is not None else "" for c in row]
                if "Item Code" in cells and "Qty" in cells:
                    header_row_idx = row_idx
                    for col_idx, cell in enumerate(cells):
                        if cell:
                            header_map[cell] = col_idx
                    break

            items: List[Dict[str, Any]] = []
            if header_row_idx is not None:
                # Skip possible sub-header row ("No", "Rate", "Amt")
                start_idx = header_row_idx + 1
                if start_idx < len(rows):
                    first_cells = [clean_text(str(c)) if c is not None else "" for c in rows[start_idx]]
                    if first_cells and first_cells[0] in {"No", "Rate"}:
                        start_idx += 1

                def col(name, default=None):
                    return header_map.get(name, default)

                for row in rows[start_idx:]:
                    cells = list(row)
                    serial = clean_text(str(cells[0])) if cells and cells[0] is not None else ""
                    if not serial.isdigit():
                        # Stop at totals section
                        row_text = " ".join(clean_text(str(c)) for c in cells if c is not None)
                        if "Total Amount" in row_text or row_text.startswith("Total"):
                            break
                        continue

                    item_code_idx = col("Item Code", 1)
                    desc_idx = col("Item Desc", 2)
                    hsn_idx = col("HSN Code", 3)
                    qty_idx = col("Qty", 5)
                    mrp_idx = col("MRP", 6)
                    unit_idx = col("Unit Base Cost (INR)", 7)
                    taxable_idx = col("Taxable Value (INR)", 9)
                    cgst_idx = col("CGST", 10)
                    sgst_idx = col("SGST/UGST", 13)
                    igst_idx = col("IGST", 16)
                    cess_idx = col("CESS", 19)
                    add_cess_idx = col("Additional CESS", 21)
                    total_idx = col("Total (INR)", 22)

                    def at(idx):
                        if idx is None or idx >= len(cells):
                            return None
                        return cells[idx]

                    items.append({
                        "Item Code": clean_text(str(at(item_code_idx) or "")),
                        "Item Description": clean_text(str(at(desc_idx) or "")),
                        "HSN Code": clean_text(str(at(hsn_idx) or "")),
                        "Quantity": to_int(at(qty_idx)),
                        "MRP": to_float(at(mrp_idx)),
                        "Unit Base Cost (INR)": to_float(at(unit_idx)),
                        "Taxable Value (INR)": to_float(at(taxable_idx)),
                        "CGST": to_float(at(cgst_idx)),
                        "SGST/UGST": to_float(at(sgst_idx)),
                        "IGST": to_float(at(igst_idx)),
                        "CESS": to_float(at(cess_idx)),
                        "Additional CESS": to_float(at(add_cess_idx)),
                        "Total (INR)": to_float(at(total_idx)),
                    })

            total_details: Dict[str, Any] = {}
            total_labels = [
                "Total Amount (INR)",
                "GST Compensation Cess",
                "GST Additional Cess",
                "Total Tax (INR)",
                "Grand Total (INR)",
                "Amount in Words",
            ]
            for row in rows:
                cells = [clean_text(str(c)) if c is not None else "" for c in row]
                for label in total_labels:
                    for idx, cell in enumerate(cells):
                        if label in cell:
                            if label == "Amount in Words":
                                total_details[label] = cells[idx].split(":", 1)[-1].strip() if ":" in cells[idx] else (
                                    next((c for c in cells[idx + 1:] if c), "")
                                )
                            else:
                                value = None
                                for c in cells[idx + 1:]:
                                    if c:
                                        value = c
                                        break
                                total_details[label] = to_float(value) if label != "Amount in Words" else (value or "")
                            break

            return {
                "PO Details": po_details,
                "Shipping Address": shipping_address_clean,
                "Billing Address": billing_address_clean,
                "Main Address": main_address,
                "Item Details": items,
                "Total Details": total_details,
            }
        except Exception as e:
            frappe.log_error(f"Error processing xlsx file: {str(e)}")
            raise

    def parse_excel_attachment(excel_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Route old XML .xls and new .xlsx Instamart attachments to the right parser."""
        name = (filename or "").lower()
        if name.endswith(".xlsx"):
            return read_xlsx_excel(excel_bytes)
        return read_xml_excel(excel_bytes.decode("utf-8"))

    def move_email_to_processed(mail, email_uid):
        """Move an email to the Processed folder using IMAP UIDs."""
        try:
            # Ensure the "Processed" folder exists
            mail.create('Instamart-Processed')
        except imaplib.IMAP4.error:
            pass  # Folder already exists, no need to create it

        try:
            # Copy the email using UID
            copy_result = mail.uid('copy', email_uid, 'Instamart-Processed')
            if copy_result[0] == 'OK':
                # Mark the original email for deletion using UID
                store_result = mail.uid('store', email_uid, '+FLAGS', '\\Deleted')
                if store_result[0] == 'OK':
                    mail.expunge()  # Permanently delete the email
                    print(f"Moved email UID {email_uid} to Instamart-Processed folder.")
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

    def save_pdf_to_file(pdf_data, po_number):
        """Save the PDF to S3 inside a dynamically set folder."""
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
                folder_name = (aws_record.folder_insta or "InstaMart").strip().strip('/')
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

        file_name = f"{folder_name}/Instamart_{po_number}.pdf"  # Ensure proper path format

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
    def Get_CustomerDetails(CardCode, item_list):
        try:
            # print(f"Received CardCode: {CardCode}")
            # print(f"Item List: {item_list}")

            def similar(a, b):
                return SequenceMatcher(None, a.lower(), b.lower()).ratio()

            # Extract PO No and Main Address from item_list
            po_number = item_list.get("PO Details", {}).get("PO No")
            delivered_to = item_list.get("Main Address", "")
            print(f"PO Number: {po_number}")
            # print(f"Delivered To (raw): {delivered_to}")

            zip_match = re.search(r'\b\d{6}\b', delivered_to)
            delivered_zip = zip_match.group() if zip_match else None
            # print(f"Extracted ZIP code: {delivered_zip}")

            address_entries = []
            ada_docs = frappe.get_all("ADA_2", fields=["name"])
            for ada_doc in ada_docs:
                ada_record = frappe.get_doc("ADA_2", ada_doc.name)
                if hasattr(ada_record, "address_table2") and ada_record.address_table2:
                    for address in ada_record.address_table2:
                        address_entries.append({
                            'address_id': address.address_id, 
                            'address_entry': address.address_entry
                        })
            print("Address Entries.............")
            # print(f"Address Entries: {address_entries}")

            best_match = None
            max_similarity = 0
            for entry in address_entries:
                similarity_score = similar(delivered_to, entry['address_entry'])
                # print(f"Comparing with Address ID: {entry['address_id']}, Similarity Score: {similarity_score}")  # Debugging
                if similarity_score > max_similarity:
                    max_similarity = similarity_score
                    best_match = entry

            if best_match and max_similarity > 0.6:
                matched_address_id = best_match['address_id']
                print(f"Best Matching Address ID: {matched_address_id} with similarity {max_similarity}")
            else:
                print(f"No sufficiently similar address found. Max similarity: {max_similarity}")  # Debugging
                return {'Status': 'Error', 'Message': "No sufficiently similar address entry found."}

            # Add a check to ensure matched_address_id is not empty
            if not matched_address_id:
                error_message = "Best Matching Address ID is empty. Stopping further processing."
                print(error_message)
                frappe.log_error(error_message)
                return {'Status': 'Error', 'Message': error_message}

            # Fetch SAP Customer Details
            try:
                print("Fetching SAP Settings...")
                doc_settings = frappe.get_doc('SAP Settings')

                print("Authenticating with SAP B1...")
                session = AuthenticateSAPB1()

                Url = doc_settings.sap_b1_url + f"BusinessPartners?$filter=CardCode eq '{CardCode}'"
                # print(f"Requesting SAP API: {Url}")

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

    def fetch_item_sap_mapping():
        print("Fetching Itemmap records...")
        item_sap_map = []
        
        # Fetch all Itemmap2 documents
        itemmap_records = frappe.get_all('Itemmap2')
        print(f"Found {len(itemmap_records)} Itemmap2 records")
        
        for record in itemmap_records:
            itemmap_doc = frappe.get_doc("Itemmap2", record.name)
            if hasattr(itemmap_doc, "map_item") and itemmap_doc.map_item:
                for mapping in itemmap_doc.map_item:
                    item_sap_map.append({
                        'item_code': str(mapping.item_code).strip(),  # Ensure string and clean whitespace
                        'sap_code': str(mapping.sap_code).strip()
                    })
        
        # print("Mapped Items:", item_sap_map)
        return item_sap_map



    @frappe.whitelist()
    def itemmaster(item_list, code_sheet_data):
        """Fetch from item master using a list of item codes, mapping to SAP codes."""
        print("Received item_list:......................")
        # print("Received item_list:......................", item_list)
        print("Received code_sheet_data...................")

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

        for item in item_list:
            item_code = str(item['Item Code'])  # Ensure it's a string for dictionary lookup
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
                print(f"No mapping found for item code {item_code}, skipping...")

        if results:
            return {"data": results}
        else:
            error_message = "No matching records found for any item codes."
            print(error_message)
            frappe.log_error(error_message)
            send_error_email(po_number, error_message)  # Send error email with PO Number and error message
            return None


    @frappe.whitelist()
    def process_b2b_data(json_data,email_uid_str):
        """
        Process the JSON data and store it in the InstaMart doctype.
        """
        try:
            # Ensure json_data is not None
            if not json_data:
                print("Error: JSON data is None or empty.")
                return

            # Ensure json_data is a dictionary (if it's passed as a string, parse it)
            if isinstance(json_data, str):
                json_data = frappe.parse_json(json_data)

            # Safely extract data from JSON with default values
            po_number = json_data.get("po_number", "N/A")  
            email_id = json_data.get("email_id", "N/A")  
            extracted_data = json_data.get("extracted_data", {})
            customer_details = json_data.get("customer_details", {})
            file_url = json_data.get("file_url", "")
            item_data_response = json_data.get("item_data_response", {}).get("data", [])
            delivered_to = json_data.get("delivered_to", "Unknown Address")  

            # Check if B2B doctype exists
            if not frappe.db.table_exists("InstaMart"):
                print('Doctype "InstaMart" does not exist.')
                return

            # Check if the record already exists
            existing_record_name = frappe.db.exists("InstaMart", {"po_number": po_number})
            updated = False

            if existing_record_name:
                # Fetch and print the existing record's data
                try:
                    # Ensure the correct doctype is used
                    existing_record = frappe.get_doc("InstaMart", existing_record_name)  # Changed from "Bigbasket" to "InstaMart"
                    print(f"Existing Record Data for P.O. Number {po_number}: {existing_record}")
                except frappe.DoesNotExistError:
                    error_message = f"Record not found for P.O. Number: {po_number}."
                    print(error_message)
                    send_error_email(po_number, error_message, file_url)
                    return  # Stop further processing

                # Fetch the email subject directly from the email server
                email_subject = fetch_email_subject(mail, email_id)
                print(f"Email Subject: {email_subject}")  # Debugging

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

                    existing_record.append("duplicate_records_insta", duplicate_record)  # Append to the child table

                    # Update the duplicate_records_status field
                    duplicate_count = len(existing_record.duplicate_records_insta)
                    existing_record.duplicate_records_status = f"Amended/{duplicate_count}"

                    # Clear specific fields
                    fields_to_clear = [
                        "docstatus", "docnum", "docentry", "sap_status", "update_status", "document_status"
                    ]
                    for field in fields_to_clear:
                        existing_record.set(field, None)

                    # Clear child table data
                    existing_record.insta_table = []

                    # Save the cleared record
                    existing_record.save()
                else:
                    print(f"Email subject does not contain 'Amend' or 'Revised'. Skipping email UID {email_id}.")
                    error_message = f"Email subject does not contain 'Amend' or 'Revised'. Skipping email UID {email_id}."

                    # Send error email
                    send_error_email(po_number, error_message, file_url)
                   
                    return  # Skip processing this email

                updated = True
                # Proceed with updating the record
                doc = existing_record
            else:
                # Create new record
                doc = frappe.new_doc("InstaMart")
                doc.duplicate_records_status = "False/0"  # Default value for new records


            if existing_record_name:
                # Update existing record
                doc = frappe.get_doc("InstaMart", existing_record_name)
                updated = True
            else:
                # Create new record
                doc = frappe.new_doc("InstaMart")

            # Update fields from extracted_data
            if extracted_data:
                for field, value in extracted_data.items():
                    if hasattr(doc, field):
                        setattr(doc, field, value)

            # Update fields from customer_details
            if customer_details:
                doc.customer_code = customer_details.get("CardCode", "")
                # doc.employee_id = customer_details.get("SalesPersonCode", "")

                # Handle MatchedAddress (it can be None)
                matched_address = customer_details.get("MatchedAddress")
                if matched_address is not None:
                    doc.matched_address_name = matched_address.get("AddressName", "")
                else:
                    doc.matched_address_name = None  

                # Handle MatchedState (it can be None)
                matched_state = customer_details.get("MatchedState")
                doc.matched_state = matched_state

            # Update file URL
            doc.po_url = file_url

            # Set default values for Billing_from and Billto
            doc.billing_from = "KT"  
            doc.billto = "Local" if matched_state == "KT" else "Central"

            # Set email_id field
            doc.email_id = email_id  

            # Update delivered_to field
            doc.delivered_to = delivered_to  

            # Initialize totals
            total_quantity = 0
            total_amount = 0
            total_taxable_value = 0  # Initialize total taxable value
            main_total_tax = 0  # Initialize main total tax
            unique_items = set()
            

            # Clear existing child table rows (if updating)
            if updated:
                doc.insta_table = []

            # Add item details to the child table and accumulate totals
            if item_data_response:
                for item in item_data_response:
                    quantity = item.get("Quantity", 0)
                    basic_cost_price = float(item.get("BasicCostPrice") or 0.0)  # Ensure basic_cost_price is a float
                    taxable_value = basic_cost_price * quantity  # Calculate taxable value
                    total_taxable_value += taxable_value  # Accumulate total taxable value
                    main_total_tax += taxable_value  # Accumulate main total tax
                    # print("total_taxable_value", total_taxable_value)
                    total_item_amount = item.get("TotalAmount", 0)
                    item_code = item.get("ItemCode", "")
                    
                    # Determine the taxcode format based on matched_state
                    tax_prefix = "KACS" if matched_state == "KT" else "KAIG"
                    
                    # Get the tax_rate from the current item
                    tax_rate = int(item.get("U_TaxRate", 0))  
                    
                    # Format the taxcode
                    taxcode = f"{tax_prefix}{tax_rate}"

                    # Append item to child table
                    doc.append("insta_table", {
                        "item_code": item_code,
                        "sap_code": item.get("SAPCode", ""),
                        "item_name": item.get("ItemName", ""),
                        "quantity": quantity,
                        "discount": item.get("Discount", 0),
                        "product_description": item.get("ProductDescription", ""),
                        "basic_cost_price": basic_cost_price,
                        "igst_percentage": item.get("IGSTPercentage", 0),
                        "tax_amount": item.get("TaxAmount", 0),
                        "landing_rate": item.get("LandingRate", 0),
                        "mrp": item.get("MRP", 0),
                        "total_amount": total_item_amount,
                        "tax_rate": item.get("U_TaxRate", 0),
                        "gst_tax": item.get("U_GstTax", ""),
                        "igst_tax": item.get("U_IgstTax", ""),
                        "brand": item.get("U_BN", ""),
                        "taxcode": taxcode,
                        "taxable_value": taxable_value 
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
            doc.main_total_tax = main_total_tax 

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
            po_number = json_data.get("po_number", "N/A")
            file_url = json_data.get("file_url", "None")
            error_message = f"Error processing Instamart_table data: {str(e)}"
            print(error_message)
            frappe.log_error(f"Error in Instamart_table: {str(e)}")
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
                            if msg.is_multipart():
                                pdf_data = excel_data = None
                                excel_filename = None
                                found_valid_pdf = False
                                pdf_text = "" 
                                
                                for part in msg.walk():
                                    content_type = part.get_content_type()
                                    filename = part.get_filename()

                                    if filename:
                                        if filename.lower().endswith(".pdf"):
                                            pdf_data = part.get_payload(decode=True)
                                            if isinstance(pdf_data, bytes):
                                                print(f"Found PDF attachment: {filename}")
                                                pdf_text = extract_pdf_text(pdf_data)
                                                if is_valid_instamart_pdf(pdf_text):
                                                    found_valid_pdf = True
                                                    print("Found valid PDF:", filename)
                                                else:
                                                    print("Invalid PDF: Missing required text.")
                                            else:
                                                print(f"Error: PDF data is not bytes-like for {filename}")
                                                pdf_data = None  # Reset pdf_data to None if it's not bytes-like
                                        elif filename.lower().endswith((".xls", ".xlsx")):
                                            print(f"Found Excel attachment: {filename}")
                                            excel_data = part.get_payload(decode=True)
                                            excel_filename = filename
                                            if not isinstance(excel_data, bytes):
                                                print(f"Error: Excel data is not bytes-like for {filename}")
                                                excel_data = None
                                                excel_filename = None

                                if pdf_data and found_valid_pdf:
                                    print("Processing PDF and Excel data...")
                                    extracted_data = extract_data(pdf_text)
                                    po_number = extracted_data.get("po_number")

                                    item_data = parse_excel_attachment(excel_data, excel_filename) if excel_data else {}
                                    print("Extracted Data:...........") 
                                    print("PO Number:", extracted_data.get("po_number", "Not Found"))
                                    
                                    # Call Get_CustomerDetails with the provided CardCode and item_data
                                    customer_details = Get_CustomerDetails(CardCode, item_data)
                                    print("Customer Details:...........")

                                    if po_number:
                                        file_url = save_pdf_to_file(pdf_data, po_number)
                                        print(f"File saved at: {file_url}")
                                        
                                        # Fetch item mapping data
                                        code_sheet_data = fetch_item_sap_mapping()
                                        
                                        # Call itemmaster with item_list and code_sheet_data
                                        item_data_response = itemmaster(item_data.get("Item Details", []), code_sheet_data)
                                        
                                        # Create a dictionary from item_data_response for easy lookup
                                        item_response_dict = {item["ItemCode"]: item for item in item_data_response.get("data", [])}
                                        merged_item_data = []
                                        
                                        for item in item_data.get("Item Details", []):
                                            item_code = item["Item Code"]
                                            if str(item_code) in item_response_dict:
                                                merged_item = {
                                                    **item_response_dict[str(item_code)],
                                                    "Quantity": item["Quantity"],
                                                    "Discount": item.get("Discount", 0),
                                                    "ProductDescription": item["Item Description"],
                                                    "BasicCostPrice": item["Unit Base Cost (INR)"],
                                                    "IGSTPercentage": item.get("IGST", 0),
                                                    "SGSTPercentage": item.get("SGST/UGST", 0),
                                                    "HSNCode": item.get("HSN Code", ""),
                                                    "TaxAmount": item.get("Taxable Value (INR)", 0),
                                                    "LandingRate": item.get("LandingRate", 0),
                                                    "MRP": item["MRP"],
                                                    "TotalAmount": item.get("Total (INR)", 0)
                                                }
                                                merged_item_data.append(merged_item)
                                            else:
                                                merged_item_data.append({
                                                    "ItemCode": item["Item Code"],
                                                    "Quantity": item["Quantity"],
                                                    "Discount": item.get("Discount", 0),
                                                    "ProductDescription": item["Item Description"],
                                                    "BasicCostPrice": item["Unit Base Cost (INR)"],
                                                    "IGSTPercentage": item.get("IGST", 0),
                                                    "SGSTPercentage": item.get("SGST/UGST", 0),
                                                    "HSNCode": item.get("HSN Code", ""),
                                                    "TaxAmount": item.get("Taxable Value (INR)", 0),
                                                    "LandingRate": item.get("LandingRate", 0),
                                                    "MRP": item["MRP"],
                                                    "TotalAmount": item.get("Total (INR)", 0)
                                                })
                                        
                                        item_data_response["data"] = merged_item_data

                                        matched_address = None
                                        if customer_details['Status'] == 'Success':
                                            matched_address = next((address for address in customer_details['Result']['Addresses'] 
                                                                if address['AddressName'] == customer_details['Result']['MatchedAddressName']), None)
                                            if matched_address:
                                                matched_address = {
                                                    "AddressName": matched_address["AddressName"],
                                                    "State": matched_address["State"]
                                                }

                                        po_number = item_data.get("PO Details", {}).get("PO No", "Not Found")
                                        delivered_to = item_data.get("Main Address", "Not Available")

                                        json_data = {
                                            "po_number": po_number,
                                            "email_id": email_uid_str,
                                            "extracted_data": extracted_data,
                                            "delivered_to": delivered_to,
                                            "customer_details": {
                                                "CardCode": customer_details['Result']['CardCode'],
                                                "SalesPersonCode": SalesPersonCode,
                                                "CustomerName": customer_details['Result']['CustomerName'],
                                                "MatchedAddress": matched_address,
                                                "MatchedState": customer_details['Result']['MatchedState']
                                            },
                                            "file_url": file_url,
                                            "item_data_response": item_data_response
                                        }

                                        process_b2b_data(json_data,email_uid_str)

                                        
                                        # with open(f"{po_number}.json", "w") as json_file:
                                        #     json.dump(json_data, json_file, indent=4)

                                    else:
                                        error_message = f"Error: Extracted data is not a dictionary for {filename}"
                                        print(f"Calling send_error_email for UID {email_uid_str}")
                                        send_error_email(po_number or "N/A", error_message, file_url or "None")  # Ensure email notification is sent
                                        continue

                except Exception as e:
                    error_message = f"Error processing email UID {email_uid_str}: {str(e)}"
                    print(f"Calling send_error_email for UID {email_uid_str} with error: {error_message}")
                    send_error_email(po_number or "N/A", error_message, file_url or "None")  # Ensure email notification is sent
                    continue  # Continue with the next email

        except Exception as e:
            error_message = f"Error occurred while reading attachments: {str(e)}"
            print(f"Calling send_error_email for general error: {error_message}")
            send_error_email("N/A", error_message, "None")  # Ensure email notification is sent
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


def send_error_email(po_number, error_message, file_url=None, channel_name="Instamart"):
    """Send an error email using the HTML template."""
    try:
        # Debugging: Ensure the function is called
        print(f"send_error_email called with po_number: {po_number}, error_message: {error_message}, file_url: {file_url}, channel_name: {channel_name}")

        # Fetch all users with the role 'B2B_Instamart'
        recipients = frappe.get_all(
            "Has Role",
            filters={"role": "B2B_Instamart"},
            fields=["parent"],
        )
        if not recipients:
            frappe.log_error("No recipients found with the role 'B2B_Instamart'.")
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

# Call the main function 
if __name__ == "__main__":
    process_email_attachments()



#     # bench --site beta.localhost execute khanal_tech_integrations.utils.B2B.Instamart.process_email_attachments