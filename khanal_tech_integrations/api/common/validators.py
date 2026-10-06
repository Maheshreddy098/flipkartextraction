"""
Common validation functions for plant APIs
"""

import frappe
from frappe import _


def validate_grn_data(grn_data):
    """
    Validate GRN data before creation
    
    Args:
        grn_data (dict): GRN data to validate
        
    Returns:
        tuple: (bool, str) - (is_valid, error_message)
    """
    # Check basic required fields (excluding line items for now)
    required_fields = [
        'po_doc_entry', 'invoice_number', 'invoice_date', 'received_date'
    ]
    
    for field in required_fields:
        if not grn_data.get(field):
            return False, f"Missing required field: {field}"
    
    # Validate line items (frontend sends 'lines', some APIs send 'line_items')
    line_items = grn_data.get('lines') or grn_data.get('line_items', [])
    if not line_items:
        return False, "GRN must have at least one line item"
    
    for item in line_items:
        # Check for both snake_case (from frontend) and PascalCase (from direct API calls)
        item_code = item.get('item_code') or item.get('ItemCode')
        if not item_code:
            return False, "Item code is required for all line items"
        
        received_qty = item.get('received_quantity') or item.get('ReceivedQuantity')
        if not received_qty or received_qty <= 0:
            return False, f"Invalid received quantity for item {item_code}"
    
    return True, ""


def validate_production_data(production_data):
    """
    Validate Production Order data before creation
    
    Args:
        production_data (dict): Production data to validate
        
    Returns:
        tuple: (bool, str) - (is_valid, error_message)
    """
    required_fields = [
        'process_type', 'crate_details', 'employee_count'
    ]
    
    for field in required_fields:
        if not production_data.get(field):
            return False, f"Missing required field: {field}"
    
    # Validate crate details
    crate_details = production_data.get('crate_details', [])
    if not crate_details:
        return False, "At least one crate is required"
    
    for crate in crate_details:
        if not crate.get('crate_id'):
            return False, "Crate ID is required"
        
        if not crate.get('quantity') or crate.get('quantity') <= 0:
            return False, f"Invalid quantity for crate {crate.get('crate_id')}"
    
    return True, ""


def validate_plant_id(plant_id):
    """
    Validate if plant ID is valid
    
    Args:
        plant_id (str): Plant identifier
        
    Returns:
        bool: True if valid, raises exception if invalid
    """
    valid_plants = ['malur', 'krishnagiri', 'champavath', 'nandi_hills']
    
    if plant_id not in valid_plants:
        frappe.throw(_("Invalid plant ID: {0}").format(plant_id))
    
    return True

