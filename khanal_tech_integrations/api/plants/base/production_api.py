"""
Base Production API class with common production functionality
"""

import frappe
from .plant_api import BasePlantAPI
from khanal_tech_integrations.api.common import validate_production_data


class BaseProductionAPI(BasePlantAPI):
    """Base class for Production operations across all plants"""
    
    def validate_data(self, production_data):
        """Validate production data"""
        is_valid, error_msg = validate_production_data(production_data)
        if not is_valid:
            frappe.throw(error_msg)
        return True
    
    def get_crate_assignments(self, item_code=None):
        """
        Get available crate assignments for production
        
        Args:
            item_code (str): Filter by item code
            
        Returns:
            dict: Crate assignments with batch numbers and quantities
        """
        # Base implementation - can be overridden by specific plants
        try:
            filters = {'crate_consumed': '0'}
            
            if item_code:
                filters['item_code'] = ['like', f'%{item_code}%']
            
            crate_docs = frappe.get_list(
                'Crate Assignment',
                filters=filters,
                fields=['name', 'crate_id', 'batch_number', 'quantity', 'item_code'],
                limit=100
            )
            
            return {
                "success": True,
                "data": crate_docs
            }
            
        except Exception as e:
            frappe.log_error(f"Error fetching crate assignments: {str(e)}", "Production Crate Error")
            return {
                "success": False,
                "message": str(e),
                "data": []
            }

