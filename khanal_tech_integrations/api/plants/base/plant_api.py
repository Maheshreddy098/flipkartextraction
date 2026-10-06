"""
Base Plant API class with common functionality
"""

import frappe
from abc import ABC, abstractmethod
from khanal_tech_integrations.api.common import SAPConnector


class BasePlantAPI(ABC):
    """Base class for all plant-specific APIs"""
    
    # Plant configurations
    PLANT_CONFIGS = {
        'malur': {
            'warehouse_prefix': 'HN',
            'plant_name': 'Malur',
            'sap_schema': 'KFL_LIVE',
            'process_types': ['Drying Process', 'Churpi Process'],
            'email_notifications': ['malur@khanalfoods.com']
        },
        'krishnagiri': {
            'warehouse_prefix': ['KG', 'DK'],  # Multiple prefixes for Krishnagiri
            'plant_name': 'Krishnagiri',
            'sap_schema': 'KFL_LIVE',
            'process_types': ['Packing', 'Processing'],
            'email_notifications': ['krishnagiri@khanalfoods.com']
        },
        'champavath': {
            'warehouse_prefix': 'CH',
            'plant_name': 'Champavath',
            'sap_schema': 'KFL_LIVE',
            'process_types': ['Processing'],
            'email_notifications': ['champavath@khanalfoods.com']
        },
        'nandi_hills': {
            'warehouse_prefix': 'NH',
            'plant_name': 'Nandi Hills',
            'sap_schema': 'KFL_LIVE',
            'process_types': ['Processing'],
            'email_notifications': ['nandihills@khanalfoods.com']
        },
        'mahadevpura': {
            'warehouse_prefix': 'DC',
            'plant_name': 'Mahadevpura',
            'sap_schema': 'KFL_LIVE',
            'process_types': ['Processing', 'Packaging'],
            'email_notifications': ['mahadevpura@khanalfoods.com']
        }
    }
    
    def __init__(self, plant_id):
        """
        Initialize plant API
        
        Args:
            plant_id (str): Plant identifier (malur, krishnagiri, etc.)
        """
        self.plant_id = plant_id
        self.plant_config = self.get_plant_config()
        self.sap = SAPConnector()
    
    def get_plant_config(self):
        """Get plant-specific configuration"""
        config = self.PLANT_CONFIGS.get(self.plant_id)
        if not config:
            frappe.throw(f"Configuration not found for plant: {self.plant_id}")
        return config
    
    def get_warehouse_prefix(self):
        """Get warehouse prefix for this plant"""
        return self.plant_config.get('warehouse_prefix')
    
    def get_warehouse_filter(self, table_alias='POR1'):
        """Generate SQL warehouse filter for this plant"""
        prefix = self.get_warehouse_prefix()
        return f"AND {table_alias}.\"WhsCode\" LIKE '{prefix}%'"
    
    def get_plant_name(self):
        """Get human-readable plant name"""
        return self.plant_config.get('plant_name')
    
    def get_process_types(self):
        """Get available process types for this plant"""
        return self.plant_config.get('process_types', [])
    
    def get_notification_emails(self):
        """Get email addresses for notifications"""
        return self.plant_config.get('email_notifications', [])
    
    def send_notification(self, subject, message, recipients=None):
        """
        Send email notification
        
        Args:
            subject (str): Email subject
            message (str): Email body
            recipients (list): List of email addresses (uses plant config if None)
        """
        if recipients is None:
            recipients = self.get_notification_emails()
        
        try:
            frappe.sendmail(
                recipients=recipients,
                subject=subject,
                message=message,
                delayed=False
            )
            frappe.logger().info(f"Notification sent: {subject}")
        except Exception as e:
            frappe.log_error(f"Failed to send notification: {str(e)}", "Notification Error")
    
    @abstractmethod
    def validate_data(self, data):
        """Validate input data - must be implemented by child class"""
        pass

