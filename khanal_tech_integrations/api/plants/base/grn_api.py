"""
Base GRN API class with common GRN functionality
"""

import frappe
import json
from datetime import datetime, date
from .plant_api import BasePlantAPI
from khanal_tech_integrations.api.common import validate_grn_data


class BaseGRNAPI(BasePlantAPI):
    """Base class for GRN operations across all plants"""
    
    def validate_data(self, grn_data):
        """Validate GRN data"""
        is_valid, error_msg = validate_grn_data(grn_data)
        if not is_valid:
            frappe.throw(error_msg)
        return True
    
    def get_purchase_orders(self, status='Open', from_date=None, to_date=None, fetch_all=False, bp_search=None):
        """
        Get purchase orders for this plant from SAP HANA
        
        Args:
            status (str): PO status filter
            from_date (str): Filter POs from this date (YYYY-MM-DD)
            to_date (str): Filter POs to this date (YYYY-MM-DD)
            fetch_all (bool): If True, ignore date filters
            bp_search (str): Search by CardCode or CardName
            
        Returns:
            dict: Purchase orders list
        """
        try:
            connection, cursor, schema = self.sap.get_hana_connection()
            
            warehouse_filter = self.get_warehouse_filter()
            
            # Build date filter
            date_filter = ""
            if not fetch_all and from_date and to_date:
                date_filter = f"AND OPOR.\"DocDate\" BETWEEN '{from_date}' AND '{to_date}'"
            
            # Build BP (Business Partner) search filter (case-insensitive)
            bp_filter = ""
            if bp_search:
                bp_search_escaped = bp_search.replace("'", "''").upper()  # Escape quotes and convert to uppercase
                bp_filter = f"AND (UPPER(OPOR.\"CardCode\") LIKE '%{bp_search_escaped}%' OR UPPER(OPOR.\"CardName\") LIKE '%{bp_search_escaped}%')"
            
            query = f"""
                SELECT DISTINCT
                    OPOR."DocEntry",
                    OPOR."DocNum",
                    OPOR."CardCode",
                    OPOR."CardName",
                    OPOR."DocDate",
                    OPOR."DocDueDate",
                    OPOR."DocTotal",
                    OPOR."Comments",
                    OPOR."NumAtCard"
                FROM {schema}.OPOR
                INNER JOIN {schema}.POR1 ON OPOR."DocEntry" = POR1."DocEntry"
                WHERE OPOR."DocStatus" = 'O'
                    {warehouse_filter}
                    {date_filter}
                    {bp_filter}
                ORDER BY OPOR."DocDate" DESC
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
            
            self.sap.close_hana_connection(connection, cursor)
            
            # Debug logging
            if po_list:
                frappe.log_error(
                    f"Purchase Orders Retrieved:\n{json.dumps(po_list[:2], indent=2, default=str)}", 
                    "GRN Debug - PO List Sample"
                )
            
            return {
                "success": True,
                "data": po_list,
                "count": len(po_list)
            }
            
        except Exception as e:
            frappe.log_error(f"Error fetching POs for {self.plant_id}: {str(e)}", "GRN Get PO Error")
            return {
                "success": False,
                "message": str(e),
                "data": []
            }
    
    def get_po_line_items(self, doc_entry):
        """
        Get line items for a specific purchase order
        
        Args:
            doc_entry (str/int): SAP Purchase Order DocEntry
            
        Returns:
            dict: Line items with batch number suggestions
        """
        try:
            connection, cursor, schema = self.sap.get_hana_connection()
            
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
            warehouse_filter = self.get_warehouse_filter()
            
            lines_query = f"""
                SELECT
                    POR1."LineNum",
                    POR1."ItemCode",
                    POR1."Dscription",
                    POR1."Quantity",
                    POR1."OpenQty",
                    POR1."Price",
                    POR1."WhsCode",
                    POR1."AcctCode",
                    POR1."LineTotal"
                FROM {schema}.POR1
                WHERE POR1."DocEntry" = {doc_entry}
                    AND POR1."LineStatus" = 'O'
                    {warehouse_filter}
                ORDER BY POR1."LineNum"
            """
            
            cursor.execute(lines_query)
            line_rows = cursor.fetchall()
            
            # Generate batch numbers for each line
            line_items = []
            current_date = datetime.now()
            
            # Get vendor mapping for batch number generation
            vendor_short_code = self.get_vendor_short_code(card_code)
            
            for row in line_rows:
                line_num, item_code, description, quantity, open_qty, price, whs_code, acct_code, line_total = row
                
                # Get item variant code for batch number
                item_variant_code = self.get_item_variant_code(item_code)
                
                # Generate batch number
                batch_number = self.generate_batch_number(vendor_short_code, item_variant_code, current_date)
                
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
            
            self.sap.close_hana_connection(connection, cursor)
            
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
    
    def get_vendor_short_code(self, card_code):
        """Get vendor short code from mapping or return default"""
        try:
            # Try to get from SAP Vendor Mapping doctype
            mapping = frappe.get_value(
                'SAP Vendor Mapping',
                {'vendor_code': card_code},
                'short_code'
            )
            return mapping if mapping else card_code[:4].upper()
        except:
            return card_code[:4].upper() if card_code else "VEND"
    
    def get_item_variant_code(self, item_code):
        """Extract item variant code from item code"""
        # Example: RMHN0025 -> 0025
        try:
            # Try to extract numbers from item code
            import re
            numbers = re.findall(r'\d+', item_code)
            return numbers[0] if numbers else item_code[-4:]
        except:
            return item_code[-4:] if len(item_code) >= 4 else item_code
    
    def generate_batch_number(self, vendor_code, item_code, date_obj):
        """Generate batch number based on vendor, item, and date"""
        month_char = chr(65 + date_obj.month - 1)  # A=Jan, B=Feb, etc.
        year = str(date_obj.year)[-2:]  # Last 2 digits of year
        
        return f"{vendor_code[:4]}{item_code}{month_char}{year}"
    
    def post_grn_to_sap(self, grn_data):
        """
        Post GRN directly to SAP B1 via Service Layer
        
        Args:
            grn_data (dict): GRN data with PO info, line items, invoice details
            
        Returns:
            dict: SAP response with DocEntry and DocNum, or error
        """
        try:
            import requests
            from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
            from frappe.utils import add_to_date, nowdate
            
            # Get SAP settings
            sap_settings = frappe.get_doc('SAP Settings')
            
            # Get PO header details
            connection, cursor, schema = self.sap.get_hana_connection()
            
            po_query = f"""
                SELECT "CardCode", "CardName"
                FROM {schema}.OPOR
                WHERE "DocEntry" = '{grn_data['po_doc_entry']}'
            """
            cursor.execute(po_query)
            po_row = cursor.fetchone()
            
            if not po_row:
                raise Exception(f"Purchase Order {grn_data['po_doc_entry']} not found")
            
            card_code, card_name = po_row
            self.sap.close_hana_connection(connection, cursor)
            
            # Build SAP payload for PurchaseDeliveryNotes (Goods Receipt PO)
            today = nowdate()
            filter_date = add_to_date(today, days=365)  # Expiry date
            
            payload = {
                "CardCode": card_code,
                "CardName": card_name,
                "NumAtCard": grn_data.get('invoice_number'),
                "DocObjectCode": 20,  # Goods Receipt PO
                "DocDate": grn_data.get('received_date'),
                "TaxDate": grn_data.get('received_date'),
                "U_FrappeGRNKey": "",  # Will be updated after Frappe doc creation
                "Comments": f"Posted from Kiosk - {self.plant_id.upper()}",
                "DocumentLines": []
            }
            
            # Build document lines (frontend sends 'lines', not 'line_items')
            for line_item in grn_data.get('lines') or grn_data.get('line_items', []):
                doc_line = {
                    "ItemCode": line_item.get('item_code'),
                    "Quantity": float(line_item.get('received_quantity')),
                    "BaseType": 22,  # Base type PO
                    "BaseLine": int(line_item.get('line_num')),
                    "BaseEntry": int(grn_data['po_doc_entry']),
                    "BatchNumbers": []
                }
                
                # Only add WarehouseCode if provided (SAP will use PO warehouse if not specified)
                if line_item.get('warehouse_code'):
                    doc_line["WarehouseCode"] = line_item.get('warehouse_code')
                
                # DO NOT set AccountCode or LineNum - these are read-only for Goods Receipt PO
                # AccountCode is inherited from the Purchase Order automatically
                
                # Add moisture value if present
                if line_item.get('moisture_value'):
                    doc_line["U_Moist_Qty"] = float(line_item.get('moisture_value'))
                
                # Build batch numbers (frontend sends 'batch_lines', not 'batches')
                for batch in line_item.get('batch_lines') or line_item.get('batches', []):
                    batch_detail = {
                        "BatchNumber": batch.get('batch_number'),
                        "ExpiryDate": filter_date,
                        "ManufacturingDate": today,
                        "AddmisionDate": today,
                        "Quantity": float(batch.get('quantity')),
                        "BaseLineNumber": int(line_item.get('line_num')),
                        "ItemCode": line_item.get('item_code')
                    }
                    doc_line["BatchNumbers"].append(batch_detail)
                
                payload["DocumentLines"].append(doc_line)
            
            # Post to SAP B1 Service Layer
            # Force fresh login for critical GRN posting operation
            from khanal_tech_integrations.utils.sap import renew_sap_session
            
            try:
                session = renew_sap_session()  # Force fresh session
                frappe.db.commit()  # Commit the new session to DB
            except Exception as auth_error:
                frappe.log_error(f"SAP Authentication failed: {str(auth_error)}", "GRN SAP Auth Error")
                return {
                    "success": False,
                    "message": f"SAP Authentication failed: {str(auth_error)}"
                }
            
            url = sap_settings.sap_b1_url + "PurchaseDeliveryNotes"
            headers = {
                "Accept": "*/*",
                "User-Agent": "Khanal Tech",
                "Content-Type": "application/json"
            }
            
            frappe.log_error(
                f"Posting GRN to SAP:\nURL: {url}\nPayload: {json.dumps(payload, indent=2, default=str)}", 
                "GRN SAP Post Request"
            )
            
            response = session.request("POST", url, json=payload, headers=headers, verify=False)
            
            if response.status_code == 201:
                sap_response = response.json()
                return {
                    "success": True,
                    "doc_entry": sap_response.get('DocEntry'),
                    "doc_num": sap_response.get('DocNum'),
                    "message": "GRN posted to SAP successfully"
                }
            else:
                error_response = response.json().get('error', {})
                error_message = error_response.get('message', {}).get('value', 'Unknown SAP error')
                frappe.log_error(
                    f"SAP Posting Error: {error_message}\nPayload: {json.dumps(payload, indent=2)}",
                    "GRN SAP Posting Error"
                )
                return {
                    "success": False,
                    "message": error_message
                }
                
        except Exception as e:
            frappe.log_error(f"Error posting GRN to SAP: {str(e)}", "GRN SAP Post Error")
            return {
                "success": False,
                "message": str(e)
            }

