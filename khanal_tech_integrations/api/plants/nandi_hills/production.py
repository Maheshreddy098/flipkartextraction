"""
Nandi Hills Plant Production APIs
Handles all Production operations for Nandi Hills plant
"""

import frappe
import json
from khanal_tech_integrations.api.plants.base import BasePlantAPI


class NandiHillsProductionAPI(BasePlantAPI):
    """Nandi Hills Plant Production API Implementation"""
    
    def __init__(self):
        super().__init__('nandi_hills')
    
    def validate_data(self, production_data):
        """Validate production data"""
        # Basic validation - can be extended
        if not production_data:
            frappe.throw("Production data is required")
        return True
    
    def search_bom_in_sap(self, search_query):
        """
        Search BOM Header (OITT) in SAP HANA by Name or Code
        Searches at header level only. ITT1 components are fetched separately via get_itt1_components.
        
        Args:
            search_query (str): Search term (minimum 2 characters)
            
        Returns:
            dict: List of matching BOM records from OITT (Header level)
        """
        try:
            # Sanitize search query to prevent SQL injection
            search_query = search_query.strip().replace("'", "''")  # Escape single quotes
            if not search_query or len(search_query) < 2:
                return {
                    "success": False,
                    "message": "Search query must be at least 2 characters",
                    "data": []
                }
            
            connection, cursor, schema = self.sap.get_hana_connection()
            
            results = []
            
            # Optimized query: Use TOP for early termination, proper escaping for security
            # Using LIKE with leading wildcard can be slow on large tables, but we limit results
            search_pattern = f'%{search_query}%'
            oitt_query = f"""
                SELECT TOP 20
                    'OITT' as Type,
                    \"Code\",
                    \"Name\",
                    \"TreeType\",
                    \"ToWH\",
                    \"PriceList\"
                FROM {schema}.OITT
                WHERE \"Name\" LIKE '{search_pattern}'
                    OR \"Code\" LIKE '{search_pattern}'
                ORDER BY \"Name\"
            """
            cursor.execute(oitt_query)
            oitt_rows = cursor.fetchall()
            
            for row in oitt_rows:
                results.append({
                    'Type': row[0],
                    'Code': row[1],
                    'Name': row[2],
                    'TreeType': row[3],
                    'ToWH': row[4],
                    'PriceList': row[5]
                })
            
            # Search only OITT (Header level) - ITT1 components are fetched separately when user selects a BOM
            self.sap.close_hana_connection(connection, cursor)
            
            return {
                "success": True,
                "data": results
            }
            
        except Exception as e:
            frappe.log_error(f"Error searching BOM: {str(e)}", "Nandi Hills BOM Search Error")
            return {
                "success": False,
                "message": str(e),
                "data": []
            }
    
    def get_itt1_components(self, father_code):
        """
        Get ITT1 components for a given BOM (father code)
        
        Args:
            father_code (str): Father/BOM code from OITT
            
        Returns:
            dict: List of ITT1 components
        """
        try:
            # Sanitize father_code to prevent SQL injection
            father_code = father_code.strip().replace("'", "''")
            if not father_code:
                return {
                    "success": False,
                    "message": "Father code is required",
                    "data": []
                }
            
            connection, cursor, schema = self.sap.get_hana_connection()
            
            # Use proper escaping for security (HANA uses string interpolation)
            query = f"""
                SELECT 
                    \"Code\",
                    \"ItemName\",
                    \"Quantity\",
                    \"Warehouse\",
                    \"U_BaseQty\",
                    \"U_Scrap\",
                    \"U_MatType\",
                    \"Father\",
                    \"VisOrder\",
                    \"IssueMthd\",
                    \"Price\",
                    \"Currency\"
                FROM {schema}.ITT1
                WHERE \"Father\" = '{father_code}'
                ORDER BY \"VisOrder\"
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            
            components = []
            for row in rows:
                components.append({
                    'Code': row[0],
                    'ItemName': row[1],
                    'Quantity': float(row[2]) if row[2] else 0,
                    'Warehouse': row[3],
                    'U_BaseQty': float(row[4]) if row[4] else 0,
                    'U_Scrap': float(row[5]) if row[5] else 0,
                    'U_MatType': row[6],
                    'Father': row[7],
                    'VisOrder': row[8],
                    'IssueMthd': row[9],
                    'Price': float(row[10]) if row[10] else 0,
                    'Currency': row[11],
                    'inputQuantity': float(row[2]) if row[2] else 0,
                    'batchNumber': '',
                    'warehouse': row[3] if row[3] else ''
                })
            
            self.sap.close_hana_connection(connection, cursor)
            
            return {
                "success": True,
                "data": components
            }
            
        except Exception as e:
            frappe.log_error(f"Error fetching ITT1 components: {str(e)}", "Nandi Hills ITT1 Error")
            return {
                "success": False,
                "message": str(e),
                "data": []
            }
    
    def get_oitt_header(self, bom_code):
        """
        Get OITT header for a given BOM code
        
        Args:
            bom_code (str): BOM code from OITT
            
        Returns:
            dict: OITT header details
        """
        try:
            connection, cursor, schema = self.sap.get_hana_connection()
            
            query = f"""
                SELECT 
                    \"Code\",
                    \"Name\",
                    \"TreeType\",
                    \"ToWH\",
                    \"PriceList\",
                    \"Status\",
                    \"CreateDate\"
                FROM {schema}.OITT
                WHERE \"Code\" = '{bom_code}'
            """
            cursor.execute(query)
            row = cursor.fetchone()
            
            self.sap.close_hana_connection(connection, cursor)
            
            if not row:
                return {
                    "success": False,
                    "message": "BOM not found",
                    "data": None
                }
            
            header = {
                'Code': row[0],
                'Name': row[1],
                'TreeType': row[2],
                'ToWH': row[3],
                'PriceList': row[4],
                'Status': row[5],
                'CreateDate': str(row[6]) if row[6] else None
            }
            
            return {
                "success": True,
                "data": header
            }
            
        except Exception as e:
            frappe.log_error(f"Error fetching OITT header: {str(e)}", "Nandi Hills OITT Error")
            return {
                "success": False,
                "message": str(e),
                "data": None
            }
    
    def get_batch_numbers(self, item_code, warehouse=None, date_from=None, date_to=None):
        """
        Get batch numbers for an item from OBTQ and OBTN tables
        
        Args:
            item_code (str): Item code
            warehouse (str): Warehouse code (optional)
            date_from (str): From date for filtering (optional)
            date_to (str): To date for filtering (optional)
            
        Returns:
            dict: List of batch numbers with available quantities
        """
        try:
            connection, cursor, schema = self.sap.get_hana_connection()
            
            # Build WHERE clause
            where_clause = f'T0."ItemCode" = \'{item_code}\' AND T0."Quantity" <> 0 AND T2."validFor" = \'Y\''
            
            # Note: NOT filtering by warehouse parameter - we want to show batches from ALL warehouses
            # User can see all available batches regardless of warehouse
            
            # Date filter on InDate
            if date_from and date_to:
                where_clause += f' AND T1."InDate" >= \'{date_from}\' AND T1."InDate" <= \'{date_to}\''
            elif date_from:
                where_clause += f' AND T1."InDate" >= \'{date_from}\''
            elif date_to:
                where_clause += f' AND T1."InDate" <= \'{date_to}\''
            
            query = f"""
                SELECT 
                    T0."ItemCode",
                    (SELECT "ItemName" FROM {schema}.OITM WHERE T0."ItemCode" = "ItemCode") AS "ItemName",
                    T0."WhsCode",
                    T1."DistNumber",
                    T1."MnfDate",
                    T1."ExpDate",
                    T0."Quantity",
                    DAYS_BETWEEN(CURRENT_DATE, T1."ExpDate") AS "RemainingShelfLife",
                    T1."InDate"
                FROM {schema}.OBTQ T0
                LEFT JOIN {schema}.OBTN T1 ON T1."ItemCode" = T0."ItemCode" AND T0."SysNumber" = T1."SysNumber"
                INNER JOIN {schema}.OITM T2 ON T1."ItemCode" = T2."ItemCode"
                WHERE {where_clause}
                ORDER BY T1."InDate" DESC
            """
            
            # Log the query for debugging
            frappe.log_error(f"Batch Query: {query}", "Batch Query Debug")
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            # Log results
            frappe.log_error(f"Found {len(rows)} batch records", "Batch Query Debug")
            
            batches = []
            for row in rows:
                batches.append({
                    'ItemCode': row[0],
                    'ItemName': row[1],
                    'Warehouse': row[2],
                    'BatchNumber': row[3],
                    'ManufacturingDate': str(row[4]) if row[4] else None,
                    'ExpiryDate': str(row[5]) if row[5] else None,
                    'Quantity': float(row[6]) if row[6] else 0,
                    'RemainingShelfLife': int(row[7]) if row[7] else 0,
                    'InDate': str(row[8]) if row[8] else None
                })
            
            self.sap.close_hana_connection(connection, cursor)
            
            return {
                "success": True,
                "data": batches
            }
            
        except Exception as e:
            frappe.log_error(f"Error fetching batch numbers: {str(e)}", "Nandi Hills Batch Error")
            return {
                "success": False,
                "message": str(e),
                "data": []
            }


# ============================================================================
# WHITELISTED API ENDPOINTS
# ============================================================================

@frappe.whitelist(allow_guest=False)
def search_bom(search_query, plant_id='nandi_hills'):
    """
    Search BOM tables (OITT and ITT1) in SAP
    
    Args:
        search_query (str): Search term (minimum 2 characters)
        plant_id (str): Plant identifier
        
    Returns:
        dict: List of matching BOM records
    """
    if not search_query or len(search_query) < 2:
        return {
            "success": False,
            "message": "Search query must be at least 2 characters",
            "data": []
        }
    
    api = NandiHillsProductionAPI()
    return api.search_bom_in_sap(search_query)


@frappe.whitelist(allow_guest=False)
def get_itt1_components(bom_code, plant_id='nandi_hills'):
    """
    Get ITT1 components for a BOM
    
    Args:
        bom_code (str): Father/BOM code
        plant_id (str): Plant identifier
        
    Returns:
        dict: List of ITT1 components
    """
    if not bom_code:
        return {
            "success": False,
            "message": "BOM code is required",
            "data": []
        }
    
    api = NandiHillsProductionAPI()
    return api.get_itt1_components(bom_code)


@frappe.whitelist(allow_guest=False)
def get_oitt_header(bom_code, plant_id='nandi_hills'):
    """
    Get OITT header for a BOM
    
    Args:
        bom_code (str): BOM code
        plant_id (str): Plant identifier
        
    Returns:
        dict: OITT header details
    """
    if not bom_code:
        return {
            "success": False,
            "message": "BOM code is required",
            "data": None
        }
    
    api = NandiHillsProductionAPI()
    return api.get_oitt_header(bom_code)


@frappe.whitelist(allow_guest=False)
def get_batch_numbers(item_code, plant_id='nandi_hills', warehouse=None, date_from=None, date_to=None):
    """
    Get batch numbers for an item
    
    Args:
        item_code (str): Item code
        plant_id (str): Plant identifier
        warehouse (str): Warehouse code (optional)
        date_from (str): From date (optional)
        date_to (str): To date (optional)
        
    Returns:
        dict: List of batch numbers with quantities
    """
    if not item_code:
        return {
            "success": False,
            "message": "Item code is required",
            "data": []
        }
    
    api = NandiHillsProductionAPI()
    return api.get_batch_numbers(item_code, warehouse, date_from, date_to)


@frappe.whitelist(allow_guest=False)
def get_batch_numbers_from_batch_date_item(item_code, date_from=None, date_to=None, plant_id='nandi_hills'):
    """
    Get batch numbers from Batch Date Item doctype for an item code.
    If date_from and date_to are provided, filter by date range. Otherwise, return the latest batch numbers.
    
    Args:
        item_code: Item code to search for
        date_from: Optional from date in YYYY-MM-DD format
        date_to: Optional to date in YYYY-MM-DD format. Defaults to current date if date_from is provided
        plant_id: Plant identifier (optional, for future use)
    
    Returns:
        Dictionary with success status and list of batch numbers
    """
    from khanal_tech_integrations.api.plants.batchnumber_gen.batch_date_item_lookup import get_batch_numbers_by_item_code
    return get_batch_numbers_by_item_code(item_code, date_from=date_from, date_to=date_to)


