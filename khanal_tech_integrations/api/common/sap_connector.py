"""
SAP Connection Manager
Handles connections to SAP HANA (read) and SAP B1 Service Layer (write)
"""

import frappe
from frappe import _


class SAPConnector:
    """Singleton SAP connection manager for HANA and B1 Service Layer"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_hana_connection(self):
        """
        Get SAP HANA database connection for read-only operations
        
        Returns:
            tuple: (connection, cursor, schema)
        """
        try:
            import hdbcli.dbapi as hana_db
            
            sap_settings = frappe.get_single('SAP Settings')
            
            connection = hana_db.connect(
                address=sap_settings.hana_host,
                port=int(sap_settings.hana_port),
                user=sap_settings.hana_user,
                password=sap_settings.get_password('hana_password'),
                autocommit=False
            )
            
            cursor = connection.cursor()
            
            frappe.logger().info(f"HANA connection established: {sap_settings.hana_host}")
            return connection, cursor, sap_settings.hana_schema
            
        except ImportError:
            frappe.throw(_("SAP HANA driver not found. Please install hdbcli"))
        except Exception as e:
            frappe.log_error(f"HANA connection failed: {str(e)}", "SAP Connection Error")
            frappe.throw(_("Failed to connect to SAP HANA database"))
    
    def close_hana_connection(self, connection, cursor):
        """Safely close HANA database connection"""
        try:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
            frappe.logger().info("HANA connection closed")
        except Exception as e:
            frappe.log_error(f"Error closing HANA connection: {str(e)}", "SAP Connection Error")
    
    def get_service_layer_session(self):
        """
        Get SAP B1 Service Layer authenticated session
        
        Returns:
            dict: Session details with B1SESSION and ROUTEID
        """
        try:
            from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
            return AuthenticateSAPB1()
        except Exception as e:
            frappe.log_error(f"SAP B1 authentication failed: {str(e)}", "SAP B1 Auth Error")
            frappe.throw(_("Failed to authenticate with SAP Business One"))
    
    def renew_session_if_needed(self):
        """Renew SAP B1 session if expired"""
        try:
            from khanal_tech_integrations.utils.sap import renew_sap_session
            return renew_sap_session()
        except Exception as e:
            frappe.log_error(f"SAP B1 session renewal failed: {str(e)}", "SAP B1 Session Error")
            return None

