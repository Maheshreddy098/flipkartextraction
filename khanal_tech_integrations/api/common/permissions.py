"""
Common permission checking functions
"""

import frappe
from frappe import _


def has_plant_access(user, plant_id):
    """
    Check if user has access to specific plant
    
    Args:
        user (str): User email
        plant_id (str): Plant identifier
        
    Returns:
        bool: True if user has access
    """
    # System Manager has access to all plants
    if 'System Manager' in frappe.get_roles(user):
        return True
    
    # Check plant-specific access
    # This would query User Plant Access doctype
    try:
        plant_access = frappe.get_all(
            'User Plant Access',
            filters={
                'user': user,
                'plant_id': plant_id,
                'enabled': 1
            },
            limit=1
        )
        return len(plant_access) > 0
    except:
        # If doctype doesn't exist, fall back to role-based
        plant_roles = {
            'malur': 'Malur Plant Manager',
            'krishnagiri': 'Krishnagiri Plant Manager',
            'champavath': 'Champavath Plant Manager',
            'nandi_hills': 'Nandi Hills Plant Manager'
        }
        
        required_role = plant_roles.get(plant_id)
        if required_role:
            return required_role in frappe.get_roles(user)
        
        return False


def has_approval_permission(user, approval_type='GRN'):
    """
    Check if user has approval permission
    
    Args:
        user (str): User email
        approval_type (str): Type of approval (GRN, Production, etc.)
        
    Returns:
        bool: True if user can approve
    """
    user_roles = frappe.get_roles(user)
    
    approval_roles = {
        'GRN': ['GRN Approver', 'Plant Manager', 'System Manager'],
        'Production': ['Production Approver', 'Plant Manager', 'System Manager'],
        'Inventory': ['Inventory Manager', 'Plant Manager', 'System Manager']
    }
    
    required_roles = approval_roles.get(approval_type, ['System Manager'])
    
    return any(role in user_roles for role in required_roles)


def check_plant_permission(plant_id):
    """
    Decorator-friendly permission check
    Throws exception if user doesn't have access
    
    Args:
        plant_id (str): Plant identifier
        
    Raises:
        PermissionError: If user doesn't have access
    """
    if not has_plant_access(frappe.session.user, plant_id):
        frappe.throw(
            _("You don't have permission to access {0} plant").format(plant_id),
            frappe.PermissionError
        )
    
    return True

