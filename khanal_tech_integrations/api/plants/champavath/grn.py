"""
Champavath Plant GRN APIs
Handles all GRN operations for Champavath plant
"""

import frappe
import json
from khanal_tech_integrations.api.plants.base import BaseGRNAPI


class ChampavathGRNAPI(BaseGRNAPI):
    """Champavath Plant GRN API Implementation"""
    
    def __init__(self):
        super().__init__('champavath')


# ============================================================================
# WHITELISTED API ENDPOINTS - Same as Malur, different plant
# ============================================================================

@frappe.whitelist()
def get_purchase_orders(plant_id='champavath', status='Open'):
    """Get open purchase orders for Champavath plant"""
    api = ChampavathGRNAPI()
    return api.get_purchase_orders(status)


@frappe.whitelist()
def get_po_line_items(doc_entry, plant_id='champavath'):
    """Get line items for a specific purchase order"""
    api = ChampavathGRNAPI()
    return api.get_po_line_items(doc_entry)


@frappe.whitelist()
def create_grn_draft(grn_data):
    """Create GRN draft in Frappe"""
    try:
        if isinstance(grn_data, str):
            grn_data = json.loads(grn_data)
        
        api = ChampavathGRNAPI()
        api.validate_data(grn_data)
        
        grn_doc = frappe.get_doc({
            "doctype": "SAP GRN Creation",
            "po_no": grn_data.get('po_number'),
            "vendor_code": grn_data.get('vendor_code'),
            "vendor_name": grn_data.get('vendor_name'),
            "invoice_number": grn_data.get('invoice_number'),
            "invoice_date": grn_data.get('invoice_date'),
            "received_date": grn_data.get('received_date'),
            "type": grn_data.get('type', 'Regular'),
            "feedback": grn_data.get('comments'),
            "itemitems": json.dumps(grn_data.get('line_items', [])),
            "owner": frappe.session.user
        })
        
        grn_doc.insert()
        frappe.db.commit()
        
        api.send_notification(
            subject=f"New GRN Created: {grn_doc.name}",
            message=f"A new GRN has been created for Champavath plant. GRN ID: {grn_doc.name}"
        )
        
        return {"success": True, "message": "GRN created successfully", "grn_id": grn_doc.name}
        
    except Exception as e:
        frappe.log_error(f"Error creating GRN: {str(e)}", "Champavath GRN Creation Error")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def get_grn_list(filters=None, page=1, page_size=20, plant_id='champavath'):
    """Get list of GRNs with pagination"""
    try:
        if isinstance(filters, str):
            filters = json.loads(filters)
        
        if not filters:
            filters = {}
        
        total_count = frappe.db.count('SAP GRN Creation', filters=filters)
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
        return {"success": False, "message": str(e), "data": []}


@frappe.whitelist()
def get_grn_details(grn_id):
    """Get complete details of a specific GRN"""
    try:
        grn_doc = frappe.get_doc('SAP GRN Creation', grn_id)
        line_items = json.loads(grn_doc.itemitems) if grn_doc.itemitems else []
        
        grn_details = {
            "name": grn_doc.name,
            "po_no": grn_doc.po_no,
            "vendor_code": grn_doc.vendor_code,
            "vendor_name": grn_doc.vendor_name,
            "invoice_number": grn_doc.invoice_number,
            "invoice_date": grn_doc.invoice_date,
            "received_date": grn_doc.received_date,
            "plant_id": "champavath",
            "status": grn_doc.get("sap_status", "Draft"),
            "created_by": grn_doc.owner,
            "creation": grn_doc.creation,
            "sap_doc_entry": grn_doc.grn_docentry,
            "sap_doc_num": grn_doc.grn_docnum,
            "comments": grn_doc.get("feedback"),
            "line_items": line_items
        }
        
        return {"success": True, "data": grn_details}
        
    except Exception as e:
        frappe.log_error(f"Error fetching GRN details: {str(e)}", "GRN Details Error")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def approve_grn(grn_id):
    """Approve GRN and post to SAP B1 Service Layer"""
    try:
        # TODO: Implement SAP B1 posting logic
        return {"success": True, "message": "GRN approval pending - SAP posting to be implemented"}
    except Exception as e:
        frappe.log_error(f"Error approving GRN: {str(e)}", "GRN Approval Error")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def reject_grn(grn_id, rejection_reason):
    """Reject a GRN with reason"""
    try:
        grn_doc = frappe.get_doc('SAP GRN Creation', grn_id)
        grn_doc.feedback = f"REJECTED: {rejection_reason}"
        grn_doc.save()
        frappe.db.commit()
        
        api = ChampavathGRNAPI()
        api.send_notification(
            subject=f"GRN Rejected: {grn_id}",
            message=f"GRN {grn_id} has been rejected. Reason: {rejection_reason}"
        )
        
        return {"success": True, "message": "GRN rejected successfully"}
        
    except Exception as e:
        frappe.log_error(f"Error rejecting GRN: {str(e)}", "GRN Rejection Error")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def get_grn_statistics(plant_id='champavath', date_range=None):
    """Get GRN statistics for dashboard"""
    try:
        filters = {}
        
        if date_range:
            if isinstance(date_range, str):
                date_range = json.loads(date_range)
            
            if date_range.get('from_date'):
                filters['creation'] = ['>=', date_range['from_date']]
            if date_range.get('to_date'):
                filters['creation'] = ['<=', date_range['to_date']]
        
        total = frappe.db.count('SAP GRN Creation', filters)
        approved = frappe.db.count('SAP GRN Creation', {**filters, 'grn_docentry': ['!=', '']})
        pending = total - approved
        
        return {
            "success": True,
            "data": {
                "total": total,
                "approved": approved,
                "pending": pending,
                "rejected": 0
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Error fetching GRN statistics: {str(e)}", "GRN Stats Error")
        return {"success": False, "message": str(e)}

