"""
GRN (Goods Receipt Note) API for Malur Plant Kiosk System
Handles purchase order retrieval, GRN creation, and approval workflow
Uses HANA DB for read operations and SAP B1 Service Layer for write operations
"""

import frappe
import json
import requests
from datetime import datetime, date
from frappe import _
from frappe.utils import now, nowdate, add_to_date, get_datetime
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1


headersList = {
    "Accept": "*/*",
    "User-Agent": "Khanal Tech",
    "Content-Type": "application/json"
}


def get_hana_connection():
    """
    Get HANA database connection using SAP Settings
    Returns connection and cursor for read-only operations
    """
    try:
        import hdbcli.dbapi as hana_db
        
        sap_settings = frappe.get_single('SAP Settings')
        
        # Connect with parameters (similar to working code)
        connection = hana_db.connect(
            address=sap_settings.hana_host,
            port=int(sap_settings.hana_port),
            user=sap_settings.hana_user,
            password=sap_settings.get_password('hana_password'),
            autocommit=False
        )
        
        cursor = connection.cursor()
        
        # Use schema prefix in queries instead of SET SCHEMA
        frappe.logger().info(f"HANA connection established for GRN operations")
        return connection, cursor, sap_settings.hana_schema
        
    except ImportError:
        frappe.throw(_("SAP HANA driver not found. Please install hdbcli"))
    except Exception as e:
        frappe.log_error(f"HANA connection failed: {str(e)}", "GRN HANA Connection Error")
        frappe.throw(_("Failed to connect to SAP HANA database"))


def close_hana_connection(connection, cursor):
    """Safely close HANA database connection"""
    try:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
        frappe.logger().info("HANA connection closed")
    except Exception as e:
        frappe.log_error(f"Error closing HANA connection: {str(e)}", "GRN HANA Close Error")


@frappe.whitelist()
def get_purchase_orders(plant_id=None, status='Open'):
    """
    Get list of purchase orders from SAP B1 via HANA
    Filters by plant warehouse codes (HN* for Malur)
    
    Args:
        plant_id (str): Plant identifier (e.g., 'malur')
        status (str): PO status filter (Open, Closed, Cancelled)
    
    Returns:
        list: Purchase orders with DocEntry, DocNum, CardCode, CardName
    """
    try:
        connection, cursor, schema = get_hana_connection()
        
        # Build warehouse filter for Malur plant
        warehouse_filter = ""
        if plant_id and plant_id.lower() == 'malur':
            warehouse_filter = f"AND EXISTS (SELECT 1 FROM {schema}.POR1 P1 WHERE P1.\"DocEntry\" = OPOR.\"DocEntry\" AND P1.\"WhsCode\" LIKE 'HN%')"
        
        # Query to get open purchase orders with schema prefix
        query = f"""
            SELECT DISTINCT
                OPOR.\"DocEntry\",
                OPOR.\"DocNum\",
                OPOR.\"CardCode\",
                OPOR.\"CardName\",
                OPOR.\"DocDate\",
                OPOR.\"DocDueDate\",
                OPOR.\"DocTotal\",
                OPOR.\"Comments\"
            FROM {schema}.OPOR
            WHERE OPOR.\"CANCELED\" = 'N'
                AND OPOR.\"DocStatus\" = 'O'
                {warehouse_filter}
            ORDER BY OPOR.\"DocDate\" DESC
        """
        
        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        
        po_list = []
        for row in rows:
            po_dict = dict(zip(columns, row))
            # Convert date objects to strings
            for key, value in po_dict.items():
                if isinstance(value, (datetime, date)):
                    po_dict[key] = value.strftime('%Y-%m-%d')
            po_list.append(po_dict)
        
        close_hana_connection(connection, cursor)
        
        return {
            "success": True,
            "data": po_list,
            "count": len(po_list)
        }
        
    except Exception as e:
        frappe.log_error(f"Error fetching purchase orders: {str(e)}", "GRN Get PO Error")
        return {
            "success": False,
            "message": str(e),
            "data": []
        }


@frappe.whitelist()
def get_po_line_items(doc_entry, plant_id=None):
    """
    Get line items for a specific purchase order with batch number suggestions
    
    Args:
        doc_entry (str/int): SAP Purchase Order DocEntry
        plant_id (str): Plant identifier for warehouse filtering
    
    Returns:
        dict: Line items with batch number suggestions
    """
    try:
        connection, cursor, schema = get_hana_connection()
        
        # Get PO header info
        header_query = f"""
            SELECT "CardCode", "CardName", "DocNum", "DocDate"
            FROM {schema}.OPOR
            WHERE "DocEntry" = {doc_entry}
        """
        cursor.execute(header_query)
        header_row = cursor.fetchone()
        
        if not header_row:
            return {
                "success": False,
                "message": "Purchase Order not found"
            }
        
        card_code = header_row[0]
        card_name = header_row[1]
        doc_num = header_row[2]
        
        # Get line items
        warehouse_filter = ""
        if plant_id and plant_id.lower() == 'malur':
            warehouse_filter = "AND \"WhsCode\" LIKE 'HN%'"
        
        lines_query = f"""
            SELECT
                "LineNum",
                "ItemCode",
                "Dscription",
                "Quantity",
                "OpenQty",
                "Price",
                "WhsCode",
                "AcctCode",
                "LineTotal"
            FROM {schema}.POR1
            WHERE "DocEntry" = {doc_entry}
                AND "LineStatus" = 'O'
                {warehouse_filter}
            ORDER BY "LineNum"
        """
        
        cursor.execute(lines_query)
        line_rows = cursor.fetchall()
        
        # Generate batch numbers for each line
        line_items = []
        current_date = datetime.now()
        
        # Get vendor mapping for batch number generation
        vendor_short_code = get_vendor_short_code(card_code)
        
        for row in line_rows:
            line_num, item_code, description, quantity, open_qty, price, whs_code, acct_code, line_total = row
            
            # Get item variant code for batch number
            item_variant_code = get_item_variant_code(item_code)
            
            # Generate batch number
            batch_number = generate_batch_number(vendor_short_code, item_variant_code, current_date)
            
            line_items.append({
                "LineNum": line_num,
                "ItemCode": item_code,
                "ItemDescription": description,
                "OrderedQuantity": float(quantity),
                "OpenQuantity": float(open_qty),
                "Price": float(price),
                "WarehouseCode": whs_code,
                "AccountCode": acct_code,
                "LineTotal": float(line_total),
                "SuggestedBatchNumber": batch_number,
                "BatchLines": [
                    {
                        "BatchNumber": batch_number,
                        "Quantity": None,
                        "MoistureValue": None
                    }
                ]
            })
        
        close_hana_connection(connection, cursor)
        
        return {
            "success": True,
            "data": {
                "DocEntry": doc_entry,
                "DocNum": doc_num,
                "CardCode": card_code,
                "CardName": card_name,
                "LineItems": line_items
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Error fetching PO line items: {str(e)}", "GRN Get Line Items Error")
        return {
            "success": False,
            "message": str(e)
        }


def get_vendor_short_code(card_code):
    """Get vendor short code from SAP Vendor Mapping or return default"""
    try:
        if frappe.db.exists("SAP Vendor Mapping", card_code):
            vendor_doc = frappe.get_doc("SAP Vendor Mapping", card_code)
            return vendor_doc.vendor_short_code
        else:
            return 'NA'
    except:
        return 'NA'


def get_item_variant_code(item_code):
    """Get item variant code from SAP Mapping or return default"""
    try:
        if frappe.db.exists("SAP Mapping", item_code):
            item_doc = frappe.get_doc("SAP Mapping", item_code)
            return item_doc.variant_product_code or 'NA00'
        else:
            return 'NA00'
    except:
        return 'NA00'


def generate_batch_number(vendor_code, item_variant_code, current_date=None):
    """
    Generate batch number based on vendor, item, and date
    Format: VendorCode + ItemVariant + Day + MonthLetter + Year
    Example: DTNA00221A25 (DT + NA00 + 22 + 1 + A + 25)
    """
    if not current_date:
        current_date = datetime.now()
    
    day = current_date.strftime("%d")
    month_letter_map = {
        'JAN': 'A', 'FEB': 'B', 'MAR': 'C', 'APR': 'D',
        'MAY': 'E', 'JUN': 'F', 'JUL': 'G', 'AUG': 'H',
        'SEP': 'I', 'OCT': 'J', 'NOV': 'K', 'DEC': 'L'
    }
    month_abbr = current_date.strftime("%b").upper()
    month_letter = month_letter_map.get(month_abbr, 'X')
    year_last_two = current_date.strftime("%y")
    
    batch_number = f"{vendor_code}{item_variant_code}{day}{month_letter}{year_last_two}"
    return batch_number


@frappe.whitelist()
def create_grn_draft(grn_data):
    """
    Create a draft GRN in Frappe for approval workflow
    Does NOT post to SAP B1 yet - requires approval
    
    Args:
        grn_data (str/dict): GRN details including PO info, line items, invoice details
    
    Returns:
        dict: Created GRN document name and details
    """
    try:
        if isinstance(grn_data, str):
            grn_data = json.loads(grn_data)
        
        # Validate required fields
        required_fields = ['po_doc_entry', 'invoice_number', 'invoice_date', 'received_date', 'line_items']
        for field in required_fields:
            if field not in grn_data:
                frappe.throw(_(f"Missing required field: {field}"))
        
        # Get PO details from HANA
        po_details = get_po_header_details(grn_data['po_doc_entry'])
        
        # Create GRN document in Frappe
        grn_doc = frappe.new_doc('SAP GRN Creation')
        grn_doc.vendor_code = po_details['CardCode']
        grn_doc.vendor_name = po_details['CardName']
        grn_doc.po_doc_entry = grn_data['po_doc_entry']
        grn_doc.po_no = po_details['DocNum']
        grn_doc.invoice_number = grn_data['invoice_number']
        grn_doc.invoice_date = grn_data['invoice_date']
        grn_doc.received_date = grn_data['received_date']
        grn_doc.plant_id = grn_data.get('plant_id', 'malur')
        grn_doc.status = 'Pending Approval'
        grn_doc.created_by = frappe.session.user
        grn_doc.create_cn_for_leftover = grn_data.get('create_cn_for_leftover', 0)
        grn_doc.comments = grn_data.get('comments', '')
        
        # Store line items as JSON
        grn_doc.line_items = json.dumps(grn_data['line_items'])
        
        grn_doc.insert()
        frappe.db.commit()
        
        # Send notification email
        send_grn_notification(grn_doc, 'created')
        
        return {
            "success": True,
            "message": "GRN draft created successfully. Awaiting approval.",
            "grn_id": grn_doc.name,
            "grn_number": grn_doc.name
        }
        
    except Exception as e:
        frappe.log_error(f"Error creating GRN draft: {str(e)}", "GRN Create Draft Error")
        return {
            "success": False,
            "message": str(e)
        }


def get_po_header_details(doc_entry):
    """Get PO header details from HANA"""
    connection, cursor, schema = get_hana_connection()
    
    query = f"""
        SELECT "CardCode", "CardName", "DocNum"
        FROM {schema}.OPOR
        WHERE "DocEntry" = {doc_entry}
    """
    
    cursor.execute(query)
    row = cursor.fetchone()
    
    close_hana_connection(connection, cursor)
    
    if row:
        return {
            "CardCode": row[0],
            "CardName": row[1],
            "DocNum": row[2]
        }
    else:
        frappe.throw(_("Purchase Order not found"))


@frappe.whitelist()
def approve_grn(grn_id):
    """
    Approve GRN and post to SAP B1 Service Layer
    Creates Purchase Delivery Note (Goods Receipt PO)
    
    Args:
        grn_id (str): Frappe GRN document name
    
    Returns:
        dict: SAP response with DocEntry and DocNum
    """
    try:
        # Check user permission
        if not has_grn_approval_permission():
            frappe.throw(_("You don't have permission to approve GRNs"))
        
        # Get GRN document
        grn_doc = frappe.get_doc('SAP GRN Creation', grn_id)
        
        if grn_doc.status != 'Pending Approval':
            frappe.throw(_("GRN is not in pending approval status"))
        
        # Parse line items
        line_items = json.loads(grn_doc.line_items)
        
        # Build SAP payload
        sap_payload = build_grn_sap_payload(grn_doc, line_items)
        
        # Post to SAP B1 Service Layer
        sap_response = post_grn_to_sap(sap_payload)
        
        if sap_response.get('success'):
            # Update GRN document
            grn_doc.status = 'Approved'
            grn_doc.approved_by = frappe.session.user
            grn_doc.approved_on = now()
            grn_doc.sap_doc_entry = sap_response.get('DocEntry')
            grn_doc.sap_doc_num = sap_response.get('DocNum')
            grn_doc.sap_response = json.dumps(sap_response)
            grn_doc.save()
            frappe.db.commit()
            
            # Send notification
            send_grn_notification(grn_doc, 'approved')
            
            # Handle credit note creation if requested
            if grn_doc.create_cn_for_leftover:
                create_credit_note_for_leftover(grn_doc, line_items)
            
            return {
                "success": True,
                "message": "GRN approved and posted to SAP successfully",
                "sap_doc_entry": sap_response.get('DocEntry'),
                "sap_doc_num": sap_response.get('DocNum')
            }
        else:
            return {
                "success": False,
                "message": sap_response.get('message', 'Failed to post to SAP')
            }
        
    except Exception as e:
        frappe.log_error(f"Error approving GRN: {str(e)}", "GRN Approval Error")
        return {
            "success": False,
            "message": str(e)
        }


def build_grn_sap_payload(grn_doc, line_items):
    """Build SAP B1 payload for Purchase Delivery Note"""
    payload = {
        "CardCode": grn_doc.vendor_code,
        "DocDate": grn_doc.received_date,
        "NumAtCard": grn_doc.invoice_number,
        "Comments": f"GRN from Malur Kiosk - {grn_doc.name}",
        "DocumentLines": []
    }
    
    for item in line_items:
        line = {
            "ItemCode": item['ItemCode'],
            "Quantity": item['ReceivedQuantity'],
            "Price": item.get('Price', 0),
            "WarehouseCode": item['WarehouseCode'],
            "BaseType": 22,  # Purchase Order
            "BaseEntry": grn_doc.po_doc_entry,
            "BaseLine": item['LineNum']
        }
        
        # Add batch numbers if provided
        if item.get('BatchLines'):
            line["BatchNumbers"] = []
            for batch in item['BatchLines']:
                if batch.get('Quantity') and batch.get('Quantity') > 0:
                    line["BatchNumbers"].append({
                        "BatchNumber": batch['BatchNumber'],
                        "Quantity": batch['Quantity']
                    })
        
        payload["DocumentLines"].append(line)
    
    return payload


def post_grn_to_sap(payload):
    """Post GRN to SAP B1 Service Layer"""
    try:
        session = AuthenticateSAPB1()
        sap_settings = frappe.get_single('SAP Settings')
        
        base_url = sap_settings.sap_b1_url.rstrip('/')
        if not base_url.endswith('/b1s/v1'):
            base_url = f"{base_url}/b1s/v1"
        
        endpoint = f"{base_url}/PurchaseDeliveryNotes"
        
        response = session.post(endpoint, json=payload, headers=headersList, verify=False)
        
        if response.status_code in [200, 201]:
            sap_data = response.json()
            return {
                "success": True,
                "DocEntry": sap_data.get('DocEntry'),
                "DocNum": sap_data.get('DocNum'),
                "response": sap_data
            }
        else:
            error_message = response.text
            frappe.log_error(f"SAP API Error: {error_message}", "GRN SAP Post Error")
            return {
                "success": False,
                "message": error_message
            }
            
    except Exception as e:
        frappe.log_error(f"Error posting to SAP: {str(e)}", "GRN SAP Post Error")
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def reject_grn(grn_id, rejection_reason):
    """
    Reject GRN with reason
    
    Args:
        grn_id (str): Frappe GRN document name
        rejection_reason (str): Reason for rejection
    
    Returns:
        dict: Success status
    """
    try:
        # Check user permission
        if not has_grn_approval_permission():
            frappe.throw(_("You don't have permission to reject GRNs"))
        
        grn_doc = frappe.get_doc('SAP GRN Creation', grn_id)
        
        if grn_doc.status != 'Pending Approval':
            frappe.throw(_("GRN is not in pending approval status"))
        
        grn_doc.status = 'Rejected'
        grn_doc.rejected_by = frappe.session.user
        grn_doc.rejected_on = now()
        grn_doc.rejection_reason = rejection_reason
        grn_doc.save()
        frappe.db.commit()
        
        # Send notification
        send_grn_notification(grn_doc, 'rejected')
        
        return {
            "success": True,
            "message": "GRN rejected successfully"
        }
        
    except Exception as e:
        frappe.log_error(f"Error rejecting GRN: {str(e)}", "GRN Rejection Error")
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def get_grn_list(filters=None, page=1, page_size=20, plant_id=None):
    """
    Get list of GRNs with filters and pagination
    
    Args:
        filters (dict): Filter criteria
        page (int): Page number
        page_size (int): Records per page
        plant_id (str): Plant filter
    
    Returns:
        dict: List of GRNs with pagination info
    """
    try:
        if isinstance(filters, str):
            filters = json.loads(filters)
        
        if not filters:
            filters = {}
        
        # Note: plant_id field doesn't exist in SAP GRN Creation doctype
        # Skip plant_id filter for now
        # Future: Add plant_id custom field if needed
        
        # Get total count
        total_count = frappe.db.count('SAP GRN Creation', filters=filters)
        
        # Get GRN list with pagination
        start = (int(page) - 1) * int(page_size)
        
        grn_list = frappe.get_all(
            'SAP GRN Creation',
            filters=filters,
            fields=[
                'name', 'po_no', 'vendor_name', 'vendor_code', 'invoice_number',
                'invoice_date', 'received_date', 'grn_docentry', 'grn_docnum',
                'type', 'feedback', 'owner', 'creation'
            ],
            order_by='creation desc',
            start=start,
            page_length=page_size
        )
        
        # Add computed status based on grn_docentry
        for grn in grn_list:
            grn['status'] = 'Completed' if grn.get('grn_docentry') else 'Draft'
            grn['created_by'] = grn.get('owner')
        
        return {
            "success": True,
            "data": grn_list,
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": (total_count + int(page_size) - 1) // int(page_size)
        }
        
    except Exception as e:
        frappe.log_error(f"Error fetching GRN list: {str(e)}", "GRN List Error")
        return {
            "success": False,
            "message": str(e),
            "data": []
        }


@frappe.whitelist()
def get_grn_details(grn_id):
    """
    Get complete details of a specific GRN
    
    Args:
        grn_id (str): Frappe GRN document name
    
    Returns:
        dict: Complete GRN details
    """
    try:
        grn_doc = frappe.get_doc('SAP GRN Creation', grn_id)
        
        # Parse line items
        line_items = json.loads(grn_doc.line_items) if grn_doc.line_items else []
        
        grn_details = {
            "name": grn_doc.name,
            "po_doc_entry": grn_doc.get("po_doc_entry"),
            "po_no": grn_doc.po_no,
            "vendor_code": grn_doc.vendor_code,
            "vendor_name": grn_doc.vendor_name,
            "invoice_number": grn_doc.invoice_number,
            "invoice_date": grn_doc.invoice_date,
            "received_date": grn_doc.received_date,
            "plant_id": "malur",  # Hardcode for now since field doesn't exist
            "status": grn_doc.get("sap_status", "Draft"),
            "created_by": grn_doc.owner,
            "creation": grn_doc.creation,
            "approved_by": grn_doc.get("approved_by"),
            "approved_on": grn_doc.get("approved_on"),
            "rejected_by": grn_doc.get("rejected_by"),
            "rejected_on": grn_doc.get("rejected_on"),
            "rejection_reason": grn_doc.get("rejection_reason"),
            "sap_doc_entry": grn_doc.grn_docentry,
            "sap_doc_num": grn_doc.grn_docnum,
            "comments": grn_doc.get("feedback"),
            "create_cn_for_leftover": grn_doc.create_cn_for_leftover,
            "line_items": line_items
        }
        
        return {
            "success": True,
            "data": grn_details
        }
        
    except Exception as e:
        frappe.log_error(f"Error fetching GRN details: {str(e)}", "GRN Details Error")
        return {
            "success": False,
            "message": str(e)
        }


def has_grn_approval_permission():
    """Check if user has permission to approve GRNs"""
    # Check if user has specific role or is System Manager
    user_roles = frappe.get_roles(frappe.session.user)
    approval_roles = ['System Manager', 'Malur Plant Manager', 'GRN Approver']
    
    return any(role in approval_roles for role in user_roles)


def send_grn_notification(grn_doc, action):
    """Send email notification for GRN actions"""
    try:
        # Get users to notify based on plant
        recipients = get_plant_notification_users(grn_doc.plant_id)
        
        if not recipients:
            return
        
        # Build email content based on action
        if action == 'created':
            subject = f"New GRN Created - {grn_doc.name}"
            message = f"""
                <p>A new GRN has been created and is awaiting approval.</p>
                <p><strong>GRN ID:</strong> {grn_doc.name}</p>
                <p><strong>PO Number:</strong> {grn_doc.po_no}</p>
                <p><strong>Vendor:</strong> {grn_doc.vendor_name}</p>
                <p><strong>Invoice Number:</strong> {grn_doc.invoice_number}</p>
                <p><strong>Created By:</strong> {grn_doc.created_by}</p>
                <p>Please review and approve the GRN in the kiosk system.</p>
            """
        elif action == 'approved':
            subject = f"GRN Approved - {grn_doc.name}"
            message = f"""
                <p>GRN has been approved and posted to SAP.</p>
                <p><strong>GRN ID:</strong> {grn_doc.name}</p>
                <p><strong>SAP Doc Number:</strong> {grn_doc.sap_doc_num}</p>
                <p><strong>Approved By:</strong> {grn_doc.approved_by}</p>
            """
        elif action == 'rejected':
            subject = f"GRN Rejected - {grn_doc.name}"
            message = f"""
                <p>GRN has been rejected.</p>
                <p><strong>GRN ID:</strong> {grn_doc.name}</p>
                <p><strong>Rejected By:</strong> {grn_doc.rejected_by}</p>
                <p><strong>Reason:</strong> {grn_doc.rejection_reason}</p>
            """
        else:
            return
        
        frappe.sendmail(
            recipients=recipients,
            subject=subject,
            message=message
        )
        
    except Exception as e:
        frappe.log_error(f"Error sending GRN notification: {str(e)}", "GRN Notification Error")


def get_plant_notification_users(plant_id):
    """Get list of users to notify for a specific plant"""
    try:
        # Get plant document
        plants = frappe.get_all('Plant', filters={'plant_id': plant_id}, fields=['name'])
        if not plants:
            return []
        
        plant_name = plants[0]['name']
        
        # Get users with access to this plant
        user_access = frappe.get_all(
            'User Plant Access',
            filters={'plant': plant_name, 'enabled': 1},
            fields=['user']
        )
        
        users = [access['user'] for access in user_access]
        
        return users
        
    except Exception as e:
        frappe.log_error(f"Error getting plant notification users: {str(e)}", "GRN Notification Users Error")
        return []


def create_credit_note_for_leftover(grn_doc, line_items):
    """Create credit note for leftover quantities if requested"""
    try:
        # This is a placeholder for credit note logic
        # Implement based on your business requirements
        frappe.logger().info(f"Credit note creation requested for GRN {grn_doc.name}")
        
        # TODO: Implement credit note creation logic
        
    except Exception as e:
        frappe.log_error(f"Error creating credit note: {str(e)}", "GRN Credit Note Error")


@frappe.whitelist()
def get_grn_statistics(plant_id=None, date_range=None):
    """
    Get GRN statistics for dashboard
    
    Args:
        plant_id (str): Plant filter
        date_range (str): Date range filter (today, week, month, year)
    
    Returns:
        dict: Statistics including total, approved, pending, rejected counts
    """
    try:
        filters = {}
        if plant_id:
            filters['plant_id'] = plant_id
        
        if date_range:
            date_filter = get_date_range_filter(date_range)
            if date_filter:
                filters['creation'] = date_filter
        
        total_count = frappe.db.count('SAP GRN Creation', filters=filters)
        
        approved_filters = filters.copy()
        approved_filters['status'] = 'Approved'
        approved_count = frappe.db.count('SAP GRN Creation', filters=approved_filters)
        
        pending_filters = filters.copy()
        pending_filters['status'] = 'Pending Approval'
        pending_count = frappe.db.count('SAP GRN Creation', filters=pending_filters)
        
        rejected_filters = filters.copy()
        rejected_filters['status'] = 'Rejected'
        rejected_count = frappe.db.count('SAP GRN Creation', filters=rejected_filters)
        
        return {
            "success": True,
            "data": {
                "total": total_count,
                "approved": approved_count,
                "pending": pending_count,
                "rejected": rejected_count
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting GRN statistics: {str(e)}", "GRN Statistics Error")
        return {
            "success": False,
            "message": str(e)
        }


def get_date_range_filter(date_range):
    """Get date filter based on range"""
    from frappe.utils import today, add_days, add_months
    
    if date_range == 'today':
        return ['>=', today()]
    elif date_range == 'week':
        return ['>=', add_days(today(), -7)]
    elif date_range == 'month':
        return ['>=', add_months(today(), -1)]
    elif date_range == 'year':
        return ['>=', add_months(today(), -12)]
    else:
        return None

