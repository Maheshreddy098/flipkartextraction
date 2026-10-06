"""
Mahadevpura Plant GRN APIs
Handles all GRN operations for Mahadevpura plant
"""

import frappe
import json
from khanal_tech_integrations.api.plants.base import BaseGRNAPI


class MahadevpuraGRNAPI(BaseGRNAPI):
    """Mahadevpura Plant GRN API Implementation"""
    
    def __init__(self):
        super().__init__('mahadevpura')
    
    def get_warehouse_filter(self, table_alias='POR1'):
        """
        Override warehouse filter for Mahadevpura
        Warehouses start with 'DC'
        """
        return f"AND {table_alias}.\"WhsCode\" LIKE 'DC%'"


# ============================================================================
# WHITELISTED API ENDPOINTS
# ============================================================================

@frappe.whitelist()
def get_purchase_orders(plant_id='mahadevpura', status='Open', from_date=None, to_date=None, fetch_all=False, bp_search=None):
    """
    Get open purchase orders for Mahadevpura plant with optional filters
    
    Args:
        plant_id (str): Plant identifier (default: mahadevpura)
        status (str): PO status filter (default: Open)
        from_date (str): Filter POs from this date (YYYY-MM-DD)
        to_date (str): Filter POs to this date (YYYY-MM-DD)
        fetch_all (bool/str): If True, ignore date filters (can be string "true"/"false")
        bp_search (str): Search by CardCode or CardName
        
    Returns:
        dict: Purchase orders list with success status
    """
    # Convert string "true"/"false" to boolean
    if isinstance(fetch_all, str):
        fetch_all = fetch_all.lower() == 'true'
    
    api = MahadevpuraGRNAPI()
    return api.get_purchase_orders(
        status=status,
        from_date=from_date,
        to_date=to_date,
        fetch_all=fetch_all,
        bp_search=bp_search
    )


@frappe.whitelist()
def get_po_line_items(doc_entry, plant_id='mahadevpura'):
    """
    Get line items for a specific Purchase Order
    
    Args:
        doc_entry (str/int): SAP PO DocEntry
        plant_id (str): Plant identifier
        
    Returns:
        dict: PO line items with batch numbers
    """
    api = MahadevpuraGRNAPI()
    return api.get_po_line_items(doc_entry)


@frappe.whitelist()
def create_grn_draft(grn_data):
    """
    Create GRN by posting directly to SAP, then saving in Frappe for tracking
    (Mahadevpura plant: No draft approval, direct SAP posting)
    
    Args:
        grn_data (str/dict): GRN data (JSON string or dict)
        
    Returns:
        dict: Created GRN details with SAP DocEntry and DocNum
    """
    try:
        # Parse JSON if string
        if isinstance(grn_data, str):
            grn_data = json.loads(grn_data)
        
        api = MahadevpuraGRNAPI()
        
        # Validate data
        api.validate_data(grn_data)
        
        # STEP 1: Post directly to SAP B1 Service Layer
        sap_result = api.post_grn_to_sap(grn_data)
        
        if not sap_result.get('success'):
            return {
                "success": False,
                "message": f"SAP Posting Failed: {sap_result.get('message')}"
            }
        
        # STEP 2: Save to Frappe for tracking (after successful SAP posting)
        grn_doc = frappe.get_doc({
            "doctype": "SAP GRN Creation",
            "po_no": grn_data.get('po_doc_entry'),  # SAP DocEntry
            "vendor_code": grn_data.get('vendor_code'),
            "vendor_name": grn_data.get('vendor_name'),
            "invoice_number": grn_data.get('invoice_number'),
            "invoice_date": grn_data.get('invoice_date'),
            "received_date": grn_data.get('received_date'),
            "type": "mahadevpura",  # ✅ Store plant_id in type field for filtering
            "feedback": grn_data.get('comments', ''),
            "itemitems": json.dumps(grn_data.get('lines', [])),  # Frontend sends 'lines', not 'line_items'
            "grn_docentry": sap_result.get('doc_entry'),  # SAP DocEntry from response
            "grn_docnum": sap_result.get('doc_num'),      # SAP DocNum from response
            "moist_select": "Sent to SAP",  # Valid status: "", "Approved", "QA Approval Pending", "Sent to SAP", "Rejected"
            "owner": frappe.session.user
        })
        
        grn_doc.insert()
        frappe.db.commit()
        
        # Update SAP with Frappe GRN Key (optional - for back-reference)
        try:
            from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
            sap_settings = frappe.get_doc('SAP Settings')
            session = AuthenticateSAPB1()
            update_url = f"{sap_settings.sap_b1_url}PurchaseDeliveryNotes({sap_result.get('doc_entry')})"
            update_payload = {"U_FrappeGRNKey": grn_doc.name}
            session.request("PATCH", update_url, json=update_payload, verify=False)
        except Exception as update_error:
            frappe.log_error(f"Could not update SAP with Frappe key: {str(update_error)}", "GRN SAP Update")
        
        # Send notification
        send_grn_notification(grn_doc, sap_result)
        
        return {
            "success": True,
            "message": "GRN posted to SAP and saved in Frappe successfully",
            "grn_id": grn_doc.name,
            "sap_doc_entry": sap_result.get('doc_entry'),
            "sap_doc_num": sap_result.get('doc_num')
        }
        
    except Exception as e:
        frappe.log_error(f"Error creating GRN: {str(e)}", "Mahadevpura GRN Creation Error")
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def get_grn_list(filters=None, page=1, page_size=20, plant_id='mahadevpura'):
    """
    Get list of GRNs with pagination
    
    Args:
        filters (str/dict): Filter criteria
        page (int): Page number
        page_size (int): Records per page
        plant_id (str): Plant identifier
        
    Returns:
        dict: List of GRNs with pagination info
    """
    try:
        if isinstance(filters, str):
            filters = json.loads(filters)
        
        if not filters:
            filters = {}
        
        # ✅ ADD PLANT FILTER - Only show GRNs from this plant
        filters['type'] = plant_id
        
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
                'type', 'feedback', 'owner', 'creation', 'moist_select'
            ],
            order_by='creation desc',
            start=start,
            page_length=page_size
        )
        
        # Add computed status based on grn_docentry
        for grn in grn_list:
            grn['status'] = 'Posted' if grn.get('grn_docentry') else 'Draft'
        
        return {
            "success": True,
            "data": grn_list,
            "total": total_count,
            "page": int(page),
            "page_size": int(page_size),
            "total_pages": (total_count + int(page_size) - 1) // int(page_size)
        }
        
    except Exception as e:
        frappe.log_error(f"Error fetching GRN list: {str(e)}", "Mahadevpura GRN List Error")
        return {
            "success": False,
            "message": str(e),
            "data": []
        }


@frappe.whitelist()
def get_grn_details(grn_id, plant_id='mahadevpura'):
    """
    Get detailed information for a specific GRN
    
    Args:
        grn_id (str): GRN document name
        plant_id (str): Plant identifier
        
    Returns:
        dict: GRN details
    """
    try:
        grn_doc = frappe.get_doc('SAP GRN Creation', grn_id)
        
        return {
            "success": True,
            "data": {
                "name": grn_doc.name,
                "po_no": grn_doc.po_no,
                "vendor_code": grn_doc.vendor_code,
                "vendor_name": grn_doc.vendor_name,
                "invoice_number": grn_doc.invoice_number,
                "invoice_date": grn_doc.invoice_date,
                "received_date": grn_doc.received_date,
                "type": grn_doc.type,
                "comments": grn_doc.feedback,
                "grn_docentry": grn_doc.grn_docentry,
                "grn_docnum": grn_doc.grn_docnum,
                "status": "Posted" if grn_doc.grn_docentry else "Draft",
                "line_items": json.loads(grn_doc.itemitems) if grn_doc.itemitems else [],
                "created_by": grn_doc.owner,
                "created_on": grn_doc.creation
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Error fetching GRN details: {str(e)}", "Mahadevpura GRN Details Error")
        return {
            "success": False,
            "message": str(e)
        }


def send_grn_notification(grn_doc, sap_result):
    """
    Send email notification about GRN creation
    
    Args:
        grn_doc: Frappe GRN document
        sap_result: SAP posting result
    """
    try:
        # Mahadevpura-specific notification recipients
        recipients = [
            "mahadevpura.plant@khanalfoods.com",  # Update with actual email
            "operations@khanalfoods.com"
        ]
        
        subject = f"GRN Created - Mahadevpura Plant - SAP DocNum: {sap_result.get('doc_num')}"
        message = f"""
        <h3>GRN Successfully Posted to SAP</h3>
        <p><strong>Plant:</strong> Mahadevpura</p>
        <p><strong>SAP DocNum:</strong> {sap_result.get('doc_num')}</p>
        <p><strong>SAP DocEntry:</strong> {sap_result.get('doc_entry')}</p>
        <p><strong>Frappe GRN ID:</strong> {grn_doc.name}</p>
        <p><strong>PO Number:</strong> {grn_doc.po_no}</p>
        <p><strong>Vendor:</strong> {grn_doc.vendor_name}</p>
        <p><strong>Invoice Number:</strong> {grn_doc.invoice_number}</p>
        <p><strong>Received Date:</strong> {grn_doc.received_date}</p>
        <p><strong>Created By:</strong> {grn_doc.owner}</p>
        """
        
        frappe.sendmail(
            recipients=recipients,
            subject=subject,
            message=message,
            delayed=False
        )
        
    except Exception as e:
        frappe.log_error(f"Error sending GRN notification: {str(e)}", "Mahadevpura GRN Notification Error")


@frappe.whitelist(methods=['POST'])
def cancel_grn(grn_id, reason, plant_id='mahadevpura'):
    """
    Cancel a GRN that has been posted to SAP
    STEP 1: Cancels in SAP B1 Service Layer
    STEP 2: If successful, updates Frappe status to "" (Draft/Open)
    
    Args:
        grn_id (str): GRN document name
        reason (str): Mandatory cancellation reason
        plant_id (str): Plant identifier
        
    Returns:
        dict: Success status with message
    """
    try:
        # Validate inputs
        if not grn_id:
            return {"success": False, "message": "GRN ID is required"}
        
        if not reason or not reason.strip():
            return {"success": False, "message": "Cancellation reason is mandatory"}
        
        # Check user permissions (Manager or Supervisor roles)
        user_roles = frappe.get_roles(frappe.session.user)
        allowed_roles = ['System Manager', 'Manager', 'Supervisor']
        
        if not any(role in user_roles for role in allowed_roles):
            return {"success": False, "message": "Access Denied: Only Managers and Supervisors can cancel GRNs"}
        
        # Get GRN document
        grn_doc = frappe.get_doc('SAP GRN Creation', grn_id)
        
        # Validate GRN belongs to this plant
        if grn_doc.type != plant_id:
            return {"success": False, "message": f"This GRN belongs to {grn_doc.type} plant, not {plant_id}"}
        
        # Check if GRN was posted to SAP
        if not grn_doc.grn_docentry:
            return {"success": False, "message": "Cannot cancel: GRN was not posted to SAP"}
        
        # Check if already cancelled (empty status = reopened/draft)
        if not grn_doc.moist_select or grn_doc.moist_select == "":
            return {"success": False, "message": "GRN is already cancelled/reopened"}
        
        # ==================== STEP 1: Cancel in SAP B1 ====================
        try:
            from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
            
            # Get SAP session and settings
            sap_session = AuthenticateSAPB1()
            sap_settings = frappe.get_doc('SAP Settings')
            
            # Build SAP cancel URL
            base_url = sap_settings.sap_b1_url.rstrip('/')
            if not base_url.endswith('/b1s/v1'):
                base_url = f"{base_url}/b1s/v1"
            
            cancel_url = f"{base_url}/PurchaseDeliveryNotes({grn_doc.grn_docentry})/Cancel"
            
            # Prepare cancellation payload with reason/remarks
            cancel_payload = {
                "Remarks": reason.strip()[:254]  # SAP typically has 254 char limit for remarks
            }
            
            # Call SAP cancel endpoint
            frappe.log_error(
                f"Attempting SAP cancellation:\nURL: {cancel_url}\nPayload: {cancel_payload}", 
                "GRN SAP Cancel"
            )
            
            sap_response = sap_session.request(
                "POST",
                cancel_url,
                json=cancel_payload,  # Send reason as remarks to SAP
                headers={
                    "Accept": "*/*",
                    "Content-Type": "application/json"
                },
                verify=False
            )
            
            # Check SAP response
            if sap_response.status_code not in [200, 201, 204]:
                error_msg = "Unknown SAP error"
                try:
                    error_data = sap_response.json()
                    error_msg = error_data.get('error', {}).get('message', {}).get('value', str(error_data))
                except:
                    error_msg = sap_response.text or f"HTTP {sap_response.status_code}"
                
                frappe.log_error(
                    f"SAP Cancellation Failed:\nURL: {cancel_url}\nStatus: {sap_response.status_code}\nError: {error_msg}",
                    "GRN SAP Cancel Failed"
                )
                
                return {
                    "success": False,
                    "message": f"SAP Cancellation Failed: {error_msg}\n\nThe GRN remains active in SAP. Please cancel manually in SAP B1."
                }
            
            frappe.log_error(
                f"SAP Cancellation Successful for DocEntry: {grn_doc.grn_docentry}",
                "GRN SAP Cancel Success"
            )
            
        except Exception as sap_error:
            frappe.log_error(
                f"SAP Cancellation Error: {str(sap_error)}\nGRN ID: {grn_id}\nDocEntry: {grn_doc.grn_docentry}",
                "GRN SAP Cancel Error"
            )
            return {
                "success": False,
                "message": f"SAP Cancellation Failed: {str(sap_error)}\n\nPlease check SAP connection and try again."
            }
        
        # ==================== STEP 2: Update Frappe (only if SAP succeeded) ====================
        try:
            old_status = grn_doc.moist_select or "Sent to SAP"
            original_feedback = grn_doc.feedback or 'None'  # Capture BEFORE changing
            
            # Update status to empty (reopened/draft state)
            # Valid options: "", "Approved", "QA Approval Pending", "Sent to SAP", "Rejected"
            grn_doc.moist_select = ""
            
            # Store concise cancellation info (feedback field has 140 char limit)
            timestamp = frappe.utils.now_datetime().strftime('%Y-%m-%d %H:%M')
            user_name = frappe.session.user.split('@')[0]  # Just username, not full email
            
            # Truncate reason if needed to fit within 140 char total
            max_reason_length = 70
            short_reason = reason.strip()[:max_reason_length]
            if len(reason.strip()) > max_reason_length:
                short_reason += "..."
            
            cancellation_info = f"CANCELLED {timestamp} by {user_name} | SAP Doc:{grn_doc.grn_docentry} | {short_reason}"
            
            grn_doc.feedback = cancellation_info[:140]  # Ensure it fits
            
            # Save with explicit flags to bypass validations
            grn_doc.flags.ignore_validate = True
            grn_doc.flags.ignore_mandatory = True
            grn_doc.save(ignore_permissions=True)
            frappe.db.commit()
            
            frappe.logger().info(f"✅ Frappe updated successfully for GRN {grn_id}")
            
        except Exception as frappe_error:
            # SAP was cancelled, but Frappe update failed - log but still return partial success
            error_details = f"""
SAP Cancellation Successful but Frappe Update Failed:
GRN ID: {grn_id}
SAP DocEntry: {grn_doc.grn_docentry} (CANCELLED IN SAP)
Frappe Error: {str(frappe_error)}
            """.strip()
            
            frappe.log_error(error_details, "GRN Frappe Update Failed")
            
            return {
                "success": False,
                "message": f"⚠️ SAP cancelled successfully (DocEntry: {grn_doc.grn_docentry}), but Frappe update failed: {str(frappe_error)}\n\nThe GRN is cancelled in SAP but status in Frappe may not reflect this. Please contact system administrator.",
                "sap_cancelled": True,
                "frappe_updated": False
            }
        
        # Log full details for audit (since feedback field is limited to 140 chars)
        full_audit_log = f"""
GRN CANCELLATION SUCCESSFUL
===========================
Frappe GRN ID: {grn_id}
SAP DocEntry: {grn_doc.grn_docentry}
Previous Status: {old_status}
New Status: Draft (empty)
Cancelled By: {frappe.session.user}
Cancelled At: {timestamp}
Full Reason: {reason.strip()}
Original Feedback: {original_feedback}
New Feedback: {grn_doc.feedback}
        """.strip()
        
        frappe.log_error(full_audit_log, "GRN Cancellation Success")
        
        return {
            "success": True,
            "message": f"✅ GRN {grn_doc.name} has been successfully cancelled in SAP and reopened in Frappe.\n\n📝 Cancellation reason has been posted to SAP under Remarks.",
            "grn_id": grn_doc.name,
            "sap_doc_entry": grn_doc.grn_docentry,
            "new_status": "Draft",  # Empty status = Draft/Open state
            "cancelled_by": frappe.session.user,
            "sap_cancelled": True,
            "frappe_updated": True,
            "reason_posted_to_sap": True
        }
        
    except frappe.DoesNotExistError:
        return {"success": False, "message": f"GRN {grn_id} not found"}
    except Exception as e:
        frappe.log_error(f"Error cancelling GRN: {str(e)}\nGRN ID: {grn_id}", "GRN Cancellation Error")
        return {"success": False, "message": f"Error cancelling GRN: {str(e)}"}

