"""
Production Order API for Malur Plant Kiosk System
Handles crate assignments, production order creation, and approval workflow
Uses Frappe DB for crate management and SAP B1 Service Layer for production posting
"""

import frappe
import json
import requests
from datetime import datetime
from frappe import _
from frappe.utils import now, nowdate, get_datetime
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1


headersList = {
    "Accept": "*/*",
    "User-Agent": "Khanal Tech",
    "Content-Type": "application/json"
}

# Process types for Malur plant
MALUR_PROCESS_TYPES = [
    "Drying Process",
    "Churpi Process"
]


@frappe.whitelist()
def get_crate_assignments(plant_id=None, item_code=None):
    """
    Get available crate assignments for production
    Returns unconsumed crates from Crate Assignment doctype
    
    Args:
        plant_id (str): Plant filter (malur)
        item_code (str): Filter by item code
    
    Returns:
        list: Crate assignments with batch numbers and quantities
    """
    try:
        filters = {'crate_consumed': '0'}
        
        if item_code:
            filters['item_code'] = ['like', f'%{item_code}%']
        
        # Get crate assignment documents
        crate_docs = frappe.get_list(
            'Crate Assignment',
            filters=filters,
            fields=['name']
        )
        
        response_list = []
        
        for crate_item in crate_docs:
            doc = frappe.get_doc("Crate Assignment", crate_item.name)
            
            # Get unconsumed crate lines
            line_items = []
            
            for single_item in doc.crate_assignment_table:
                # Only include unconsumed and usable crates
                if not single_item.consumed and (not single_item.unconsumable or single_item.unconsumable != 1):
                    item_info = {
                        "batchnumber": single_item.crate_no,
                        "Quantity": single_item.quantity,
                        "Consumed": single_item.consumed,
                        "Key_Value": f'{doc.name}_{single_item.crate_no}',
                        "isChecked": single_item.metal_detected if single_item.metal_detected else False
                    }
                    line_items.append(item_info)
            
            # Only add if there are available crates
            if line_items:
                response_list.append({
                    "batch_number": doc.batch_number,
                    "item_code": doc.item_code,
                    "item_description": doc.item_description,
                    "name": doc.name,
                    "Lineitem": line_items
                })
        
        return {
            "success": True,
            "data": response_list,
            "count": len(response_list)
        }
        
    except Exception as e:
        frappe.log_error(f"Error fetching crate assignments: {str(e)}", "Production Crate Assignment Error")
        return {
            "success": False,
            "message": str(e),
            "data": []
        }


@frappe.whitelist()
def get_production_items():
    """
    Get items available for production
    Filters items based on naming pattern or item group
    
    Returns:
        list: Production items with code and description
    """
    try:
        # Get items with specific pattern (e.g., items containing 'rmdc' or specific item groups)
        items = frappe.get_all(
            'Item',
            filters={'item_code': ['like', '%rmdc%']},
            fields=['item_code', 'item_name', 'stock_uom']
        )
        
        return {
            "success": True,
            "data": items,
            "count": len(items)
        }
        
    except Exception as e:
        frappe.log_error(f"Error fetching production items: {str(e)}", "Production Items Error")
        return {
            "success": False,
            "message": str(e),
            "data": []
        }


@frappe.whitelist()
def get_process_types():
    """
    Get available process types for Malur plant
    
    Returns:
        list: Process type options
    """
    return {
        "success": True,
        "data": MALUR_PROCESS_TYPES
    }


@frappe.whitelist()
def create_pre_production(crate_details, process_type, employee_count, user_email, plant_id='malur'):
    """
    Create pre-production order (input submission)
    Marks crates as consumed and creates Production Kiosk document
    Status: Input Submitted (awaiting output recording)
    
    Args:
        crate_details (str/list): Crate consumption details
        process_type (str): Type of production process
        employee_count (int): Number of employees
        user_email (str): User creating the order
        plant_id (str): Plant identifier
    
    Returns:
        dict: Created production order details
    """
    try:
        if isinstance(crate_details, str):
            crate_details = json.loads(crate_details)
        
        if isinstance(process_type, str):
            process_type = json.loads(process_type)
        
        # Extract relevant information from crate details
        crate_details_needed = []
        for cd in crate_details:
            crate_data = []
            for d in cd.get('CrateData', []):
                if 'EnteredInput' in d and d.get('EnteredInput'):
                    crate_data.append({
                        'batchnumber': d['batchnumber'],
                        'Quantity': d['Quantity'],
                        'Consumed': d.get('Consumed', False),
                        'Key_Value': d['Key_Value'],
                        'isChecked': d.get('isChecked', False),
                        'EnteredInput': d['EnteredInput']
                    })
            
            if crate_data:
                crate_details_needed.append({
                    'ItemCode': cd['ItemCode'],
                    'ItemDescription': cd['ItemDescription'],
                    'Frappe_key': cd['Frappe_key'],
                    'CrateData': crate_data
                })
        
        # Create Production Kiosk document
        production_doc = frappe.new_doc('Production Kiosk')
        production_doc.created_date = datetime.now()
        production_doc.process_type = process_type.get('ProcessTyp') if isinstance(process_type, dict) else process_type
        production_doc.employee_count = employee_count
        production_doc.user_email = user_email
        production_doc.status = 'Input Submitted'
        production_doc.plant_id = plant_id
        
        # Process crate consumption
        for single_crate_details in crate_details_needed:
            crate_doc = frappe.get_doc("Crate Assignment", single_crate_details['Frappe_key'])
            line_item_list = []
            
            # Mark crates as consumed
            for single_item in crate_doc.crate_assignment_table:
                crate_no = single_item.crate_no
                
                for line_details in single_crate_details['CrateData']:
                    if line_details['batchnumber'] == crate_no:
                        single_item.consumed = 1
                        line_item_list.append({
                            "crate_assignment": single_crate_details['Frappe_key'],
                            "crate_number": crate_no,
                            "input_quantity": line_details['EnteredInput'],
                            "crate_quantity": single_item.quantity,
                        })
            
            # Append to production document
            for line_item in line_item_list:
                production_doc.append("pre_pro_associate_table_tab", line_item)
            
            crate_doc.save()
        
        # Save production document
        production_doc.save()
        frappe.db.commit()
        
        # Send notification
        send_production_notification(production_doc, 'created')
        
        return {
            "success": True,
            "message": "Pre-production order created successfully",
            "production_id": production_doc.name
        }
        
    except Exception as e:
        frappe.log_error(f"Error creating pre-production: {str(e)}", "Production Pre-Production Error")
        frappe.db.rollback()
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def get_production_orders(filters=None, page=1, page_size=20, plant_id=None):
    """
    Get list of production orders with pagination
    
    Args:
        filters (dict): Filter criteria
        page (int): Page number
        page_size (int): Records per page
        plant_id (str): Plant filter
    
    Returns:
        dict: List of production orders with pagination info
    """
    try:
        if isinstance(filters, str):
            filters = json.loads(filters)
        
        if not filters:
            filters = {}
        
        # Note: plant_id field doesn't exist in Production Kiosk doctype
        # Skip plant_id filter for now
        # Future: Add plant_id custom field if needed
        
        # Get total count
        total_count = frappe.db.count('Production Kiosk', filters=filters)
        
        # Get production order list with pagination
        start = (int(page) - 1) * int(page_size)
        
        production_list = frappe.get_all(
            'Production Kiosk',
            filters=filters,
            fields=[
                'name', 'process_type', 'status', 'created_date',
                'user_email', 'user_name', 'employee_count', 
                'sap_status', 'sap_production_number', 'output_created_data'
            ],
            order_by='created_date desc',
            start=start,
            page_length=page_size
        )
        
        return {
            "success": True,
            "data": production_list,
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": (total_count + int(page_size) - 1) // int(page_size)
        }
        
    except Exception as e:
        frappe.log_error(f"Error fetching production orders: {str(e)}", "Production List Error")
        return {
            "success": False,
            "message": str(e),
            "data": []
        }


@frappe.whitelist()
def get_production_order_details(production_id):
    """
    Get complete details of a specific production order
    
    Args:
        production_id (str): Production Kiosk document name
    
    Returns:
        dict: Complete production order details
    """
    try:
        production_doc = frappe.get_doc('Production Kiosk', production_id)
        
        # Get crate input details
        crate_inputs = []
        for item in production_doc.pre_pro_associate_table_tab:
            crate_inputs.append({
                "crate_assignment": item.crate_assignment,
                "crate_number": item.crate_number,
                "input_quantity": item.input_quantity,
                "crate_quantity": item.crate_quantity
            })
        
        # Get output details if available
        output_details = []
        if hasattr(production_doc, 'production_output_table'):
            for item in production_doc.production_output_table:
                output_details.append({
                    "item_code": item.item_code,
                    "item_description": item.item_description,
                    "output_quantity": item.output_quantity,
                    "batch_number": item.batch_number
                })
        
        production_details = {
            "name": production_doc.name,
            "process_type": production_doc.process_type,
            "status": production_doc.status,
            "created_date": production_doc.created_date,
            "user_email": production_doc.user_email,
            "employee_count": production_doc.employee_count,
            "plant_id": production_doc.plant_id,
            "approved_by": production_doc.approved_by,
            "approved_on": production_doc.approved_on,
            "rejected_by": production_doc.rejected_by,
            "rejected_on": production_doc.rejected_on,
            "rejection_reason": production_doc.rejection_reason,
            "sap_doc_entry": production_doc.sap_doc_entry,
            "sap_doc_num": production_doc.sap_doc_num,
            "crate_inputs": crate_inputs,
            "output_details": output_details
        }
        
        return {
            "success": True,
            "data": production_details
        }
        
    except Exception as e:
        frappe.log_error(f"Error fetching production order details: {str(e)}", "Production Details Error")
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def submit_production_output(production_id, output_data):
    """
    Submit production output (post-production)
    Records actual output quantities and batch numbers
    Status changes to: Output Submitted (awaiting approval)
    
    Args:
        production_id (str): Production Kiosk document name
        output_data (str/list): Output details with items, quantities, batches
    
    Returns:
        dict: Success status
    """
    try:
        if isinstance(output_data, str):
            output_data = json.loads(output_data)
        
        production_doc = frappe.get_doc('Production Kiosk', production_id)
        
        if production_doc.status != 'Input Submitted':
            frappe.throw(_("Production order is not in correct status for output submission"))
        
        # Clear existing output data if any
        production_doc.production_output_table = []
        
        # Add output data
        for item in output_data:
            production_doc.append("production_output_table", {
                "item_code": item['item_code'],
                "item_description": item.get('item_description', ''),
                "output_quantity": item['output_quantity'],
                "batch_number": item.get('batch_number', ''),
                "uom": item.get('uom', 'Kg')
            })
        
        production_doc.status = 'Output Submitted'
        production_doc.output_submitted_by = frappe.session.user
        production_doc.output_submitted_on = now()
        production_doc.save()
        frappe.db.commit()
        
        # Send notification
        send_production_notification(production_doc, 'output_submitted')
        
        return {
            "success": True,
            "message": "Production output submitted successfully. Awaiting approval."
        }
        
    except Exception as e:
        frappe.log_error(f"Error submitting production output: {str(e)}", "Production Output Error")
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def approve_production_order(production_id):
    """
    Approve production order and post to SAP B1
    Creates production order or inventory movement in SAP
    
    Args:
        production_id (str): Production Kiosk document name
    
    Returns:
        dict: SAP response with DocEntry and DocNum
    """
    try:
        # Check user permission
        if not has_production_approval_permission():
            frappe.throw(_("You don't have permission to approve production orders"))
        
        production_doc = frappe.get_doc('Production Kiosk', production_id)
        
        if production_doc.status != 'Output Submitted':
            frappe.throw(_("Production order is not in correct status for approval"))
        
        # Build SAP payload
        sap_payload = build_production_sap_payload(production_doc)
        
        # Post to SAP B1 Service Layer
        sap_response = post_production_to_sap(sap_payload, production_doc.process_type)
        
        if sap_response.get('success'):
            # Update production document
            production_doc.status = 'Approved'
            production_doc.approved_by = frappe.session.user
            production_doc.approved_on = now()
            production_doc.sap_doc_entry = sap_response.get('DocEntry')
            production_doc.sap_doc_num = sap_response.get('DocNum')
            production_doc.sap_response = json.dumps(sap_response)
            production_doc.save()
            frappe.db.commit()
            
            # Send notification
            send_production_notification(production_doc, 'approved')
            
            return {
                "success": True,
                "message": "Production order approved and posted to SAP successfully",
                "sap_doc_entry": sap_response.get('DocEntry'),
                "sap_doc_num": sap_response.get('DocNum')
            }
        else:
            return {
                "success": False,
                "message": sap_response.get('message', 'Failed to post to SAP')
            }
        
    except Exception as e:
        frappe.log_error(f"Error approving production order: {str(e)}", "Production Approval Error")
        return {
            "success": False,
            "message": str(e)
        }


def build_production_sap_payload(production_doc):
    """Build SAP B1 payload for Production Order or Inventory Transfer"""
    
    # Get input materials from crate assignments
    input_lines = []
    for item in production_doc.pre_pro_associate_table_tab:
        input_lines.append({
            "crate_number": item.crate_number,
            "quantity": item.input_quantity,
            "warehouse": "HN01"  # Default Malur warehouse
        })
    
    # Get output products
    output_lines = []
    for item in production_doc.production_output_table:
        output_lines.append({
            "ItemCode": item.item_code,
            "PlannedQuantity": item.output_quantity,
            "BatchNumber": item.batch_number,
            "UoMCode": item.uom
        })
    
    # Build payload for Inventory Gen Entry (simpler than Production Order)
    payload = {
        "DocDate": str(production_doc.created_date.date()),
        "Comments": f"Production from Malur Kiosk - {production_doc.name}",
        "DocumentLines": []
    }
    
    # Add output lines (receipts)
    for output in output_lines:
        payload["DocumentLines"].append({
            "ItemCode": output["ItemCode"],
            "Quantity": output["PlannedQuantity"],
            "WarehouseCode": "HN01",  # Malur warehouse
            "BatchNumbers": [{
                "BatchNumber": output.get("BatchNumber", ""),
                "Quantity": output["PlannedQuantity"]
            }] if output.get("BatchNumber") else []
        })
    
    return payload


def post_production_to_sap(payload, process_type):
    """Post production to SAP B1 Service Layer"""
    try:
        session = AuthenticateSAPB1()
        sap_settings = frappe.get_single('SAP Settings')
        
        base_url = sap_settings.sap_b1_url.rstrip('/')
        if not base_url.endswith('/b1s/v1'):
            base_url = f"{base_url}/b1s/v1"
        
        # Use InventoryGenEntries for simpler inventory movements
        endpoint = f"{base_url}/InventoryGenEntries"
        
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
            frappe.log_error(f"SAP API Error: {error_message}", "Production SAP Post Error")
            return {
                "success": False,
                "message": error_message
            }
            
    except Exception as e:
        frappe.log_error(f"Error posting production to SAP: {str(e)}", "Production SAP Post Error")
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def reject_production_order(production_id, rejection_reason):
    """
    Reject production order with reason
    
    Args:
        production_id (str): Production Kiosk document name
        rejection_reason (str): Reason for rejection
    
    Returns:
        dict: Success status
    """
    try:
        # Check user permission
        if not has_production_approval_permission():
            frappe.throw(_("You don't have permission to reject production orders"))
        
        production_doc = frappe.get_doc('Production Kiosk', production_id)
        
        if production_doc.status not in ['Input Submitted', 'Output Submitted']:
            frappe.throw(_("Production order is not in correct status for rejection"))
        
        production_doc.status = 'Rejected'
        production_doc.rejected_by = frappe.session.user
        production_doc.rejected_on = now()
        production_doc.rejection_reason = rejection_reason
        production_doc.save()
        frappe.db.commit()
        
        # Send notification
        send_production_notification(production_doc, 'rejected')
        
        return {
            "success": True,
            "message": "Production order rejected successfully"
        }
        
    except Exception as e:
        frappe.log_error(f"Error rejecting production order: {str(e)}", "Production Rejection Error")
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def get_production_statistics(plant_id=None, date_range=None):
    """
    Get production order statistics for dashboard
    
    Args:
        plant_id (str): Plant filter
        date_range (str): Date range filter
    
    Returns:
        dict: Statistics including active, completed, pending, delayed counts
    """
    try:
        filters = {}
        if plant_id:
            filters['plant_id'] = plant_id
        
        if date_range:
            from khanal_tech_integrations.api.grn import get_date_range_filter
            date_filter = get_date_range_filter(date_range)
            if date_filter:
                filters['created_date'] = date_filter
        
        # Active orders (Input/Output Submitted)
        active_filters = filters.copy()
        active_filters['status'] = ['in', ['Input Submitted', 'Output Submitted']]
        active_count = frappe.db.count('Production Kiosk', filters=active_filters)
        
        # Completed orders
        completed_filters = filters.copy()
        completed_filters['status'] = 'Approved'
        completed_count = frappe.db.count('Production Kiosk', filters=completed_filters)
        
        # Pending approval
        pending_filters = filters.copy()
        pending_filters['status'] = 'Output Submitted'
        pending_count = frappe.db.count('Production Kiosk', filters=pending_filters)
        
        # Rejected
        rejected_filters = filters.copy()
        rejected_filters['status'] = 'Rejected'
        rejected_count = frappe.db.count('Production Kiosk', filters=rejected_filters)
        
        total_count = active_count + completed_count + rejected_count
        
        return {
            "success": True,
            "data": {
                "total": total_count,
                "active": active_count,
                "completed": completed_count,
                "pending": pending_count,
                "rejected": rejected_count
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting production statistics: {str(e)}", "Production Statistics Error")
        return {
            "success": False,
            "message": str(e)
        }


def has_production_approval_permission():
    """Check if user has permission to approve production orders"""
    user_roles = frappe.get_roles(frappe.session.user)
    approval_roles = ['System Manager', 'Malur Plant Manager', 'Production Approver']
    
    return any(role in approval_roles for role in user_roles)


def send_production_notification(production_doc, action):
    """Send email notification for production order actions"""
    try:
        # Get users to notify based on plant
        from khanal_tech_integrations.api.grn import get_plant_notification_users
        recipients = get_plant_notification_users(production_doc.plant_id)
        
        if not recipients:
            return
        
        # Build email content based on action
        if action == 'created':
            subject = f"New Production Order Created - {production_doc.name}"
            message = f"""
                <p>A new production order has been created.</p>
                <p><strong>Production ID:</strong> {production_doc.name}</p>
                <p><strong>Process Type:</strong> {production_doc.process_type}</p>
                <p><strong>Employee Count:</strong> {production_doc.employee_count}</p>
                <p><strong>Created By:</strong> {production_doc.user_email}</p>
                <p>Please record the output in the kiosk system.</p>
            """
        elif action == 'output_submitted':
            subject = f"Production Output Submitted - {production_doc.name}"
            message = f"""
                <p>Production output has been submitted and is awaiting approval.</p>
                <p><strong>Production ID:</strong> {production_doc.name}</p>
                <p><strong>Process Type:</strong> {production_doc.process_type}</p>
                <p>Please review and approve the production order in the kiosk system.</p>
            """
        elif action == 'approved':
            subject = f"Production Order Approved - {production_doc.name}"
            message = f"""
                <p>Production order has been approved and posted to SAP.</p>
                <p><strong>Production ID:</strong> {production_doc.name}</p>
                <p><strong>SAP Doc Number:</strong> {production_doc.sap_doc_num}</p>
                <p><strong>Approved By:</strong> {production_doc.approved_by}</p>
            """
        elif action == 'rejected':
            subject = f"Production Order Rejected - {production_doc.name}"
            message = f"""
                <p>Production order has been rejected.</p>
                <p><strong>Production ID:</strong> {production_doc.name}</p>
                <p><strong>Rejected By:</strong> {production_doc.rejected_by}</p>
                <p><strong>Reason:</strong> {production_doc.rejection_reason}</p>
            """
        else:
            return
        
        frappe.sendmail(
            recipients=recipients,
            subject=subject,
            message=message
        )
        
    except Exception as e:
        frappe.log_error(f"Error sending production notification: {str(e)}", "Production Notification Error")

