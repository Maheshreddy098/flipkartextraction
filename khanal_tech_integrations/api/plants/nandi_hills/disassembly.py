"""
Nandi Hills Plant Disassembly Report API
Fetches Goods Issue and Goods Receipt details for a given Production Order (DocNum)
Uses SAP HANA connection pool for read-only database operations
"""

import frappe
import decimal
import requests
import json
import re
from khanal_tech_integrations.utils.hana_connection_pool import HANAConnectionPool
from khanal_tech_integrations.api.sap_b1_auth import AuthenticateSAPB1


def convert_decimals(obj):
    """Convert decimal.Decimal objects to strings for JSON serialization"""
    if isinstance(obj, list):
        return [convert_decimals(item) for item in obj]
    elif isinstance(obj, dict):
        return {
            key: str(value) if isinstance(value, decimal.Decimal) else convert_decimals(value)
            for key, value in obj.items()
        }
    else:
        return obj


@frappe.whitelist(allow_guest=False)
def get_disassembly_details(doc_num):
    """
    Get disassembly details (Goods Issue & Goods Receipt) for a Production Order
    
    Args:
        doc_num (str): Production Order Document Number (e.g., "37491")
        
    Returns:
        dict: JSON response with status and data
            {
                "status": "success",
                "data": [
                    {
                        "ProdOrderEntry": ...,
                        "ProdOrderNum": ...,
                        "MovementType": "Goods Issue" | "Goods Receipt",
                        "ItemCode": ...,
                        "Quantity": ...,
                        "BatchNum": ...,
                        "BatchQty": ...,
                        "TotalBatchPrice": ...,
                        "PerBatchCost": ...,
                        "RefDocNum": ...,
                        "RefDocDate": ...
                    }
                ]
            }
    """
    conn = None
    cursor = None
    
    try:
        # Validate input
        if not doc_num:
            return {
                "status": "error",
                "message": "Production Order Document Number (doc_num) is required",
                "data": []
            }
        
        # Convert doc_num to integer for safety
        try:
            doc_num_int = int(doc_num)
            if doc_num_int <= 0:
                return {
                    "status": "error",
                    "message": "Production Order Document Number must be a positive number",
                    "data": []
                }
        except (ValueError, TypeError):
            return {
                "status": "error",
                "message": "Production Order Document Number must be a valid number",
                "data": []
            }
        
        # Get schema from SAP Settings
        try:
            sap_settings = frappe.get_single('SAP Settings')
            schema = sap_settings.hana_schema
            if not schema:
                return {
                    "status": "error",
                    "message": "HANA Schema not configured in SAP Settings",
                    "data": []
                }
        except Exception as e:
            frappe.log_error(f"Error getting SAP Settings: {str(e)}", "Disassembly SAP Settings Error")
            return {
                "status": "error",
                "message": "Failed to get SAP Settings configuration",
                "data": []
            }
        
        # Get connection from pool
        pool = HANAConnectionPool()
        conn = pool.get_connection()
        cursor = conn.cursor()
        
        # Set schema for the connection
        cursor.execute(f'SET SCHEMA "{schema}"')
        
        # Build SQL query (fixed to handle negative quantities correctly)
        query = f"""
            -- GOODS ISSUE (CONSUMPTION) - Only items with POSITIVE quantities from WOR1
            SELECT
                W."DocEntry"        AS "ProdOrderEntry",
                W."DocNum"          AS "ProdOrderNum",
                'Goods Issue'       AS "MovementType",
                L."ItemCode"        AS "ItemCode",
                IGE1."Quantity"     AS "Quantity",
                IGE1."WhsCode"      AS "WarehouseCode",
                IGE1."AcctCode"     AS "AccountCode",
                CAST(NULL AS INTEGER) AS "LocationCode",
                IBT1."BatchNum"     AS "BatchNum",
                IBT1."Quantity"     AS "BatchQty",
                OBTN."CostTotal"    AS "TotalBatchPrice",
                CASE 
                    WHEN OBTN."Quantity" > 0 THEN (OBTN."CostTotal" / OBTN."Quantity")
                    ELSE 0
                END                 AS "PerBatchCost",
                OIGE."DocNum"       AS "RefDocNum",
                OIGE."DocDate"      AS "RefDocDate"
            FROM OWOR W
            JOIN WOR1 L 
                ON W."DocEntry" = L."DocEntry"
            LEFT JOIN IGE1 
                ON TO_VARCHAR(IGE1."BaseRef") = TO_VARCHAR(W."DocNum")
               AND IGE1."ItemCode" = L."ItemCode"
            LEFT JOIN OIGE 
                ON OIGE."DocEntry" = IGE1."DocEntry"
            LEFT JOIN IBT1 
                ON IBT1."ItemCode" = L."ItemCode"
               AND (
                    (IBT1."BaseType" = 60  AND IBT1."BaseEntry" = OIGE."DocEntry")
                 OR (IBT1."BaseType" = 202 AND IBT1."BaseEntry" = W."DocEntry")
                   )
            LEFT JOIN OBTN 
                ON OBTN."ItemCode" = IBT1."ItemCode"
               AND OBTN."DistNumber" = IBT1."BatchNum"
            WHERE W."DocNum" = {doc_num_int}
              AND L."PlannedQty" > 0  -- ✅ Only include positive quantities (exclude negative like WASTE0001)
            
            UNION ALL
            
            -- GOODS RECEIPT (OUTPUT) - Include ALL items from IGN1 (main product + byproducts like WASTE0001)
            SELECT
                W."DocEntry"        AS "ProdOrderEntry",
                W."DocNum"          AS "ProdOrderNum",
                'Goods Receipt'     AS "MovementType",
                IGN1."ItemCode"     AS "ItemCode",  -- ✅ Use IGN1.ItemCode to get ALL output items (not just W.ItemCode)
                IGN1."Quantity"     AS "Quantity",
                IGN1."WhsCode"      AS "WarehouseCode",
                IGN1."AcctCode"     AS "AccountCode",
                IGN1."LocCode"      AS "LocationCode",
                IBT2."BatchNum"     AS "BatchNum",
                IBT2."Quantity"     AS "BatchQty",
                OBTN2."CostTotal"   AS "TotalBatchPrice",
                CASE 
                    WHEN OBTN2."Quantity" > 0 THEN (OBTN2."CostTotal" / OBTN2."Quantity")
                    ELSE 0
                END                 AS "PerBatchCost",
                OIGN."DocNum"       AS "RefDocNum",
                OIGN."DocDate"      AS "RefDocDate"
            FROM OWOR W
            LEFT JOIN IGN1 
                ON TO_VARCHAR(IGN1."BaseRef") = TO_VARCHAR(W."DocNum")
            LEFT JOIN OIGN 
                ON OIGN."DocEntry" = IGN1."DocEntry"
            LEFT JOIN IBT1 IBT2 
                ON IBT2."ItemCode" = IGN1."ItemCode"  -- ✅ Match on IGN1.ItemCode (not W.ItemCode)
               AND (
                    (IBT2."BaseType" = 59  AND IBT2."BaseEntry" = OIGN."DocEntry")
                 OR (IBT2."BaseType" = 202 AND IBT2."BaseEntry" = W."DocEntry")
                   )
            LEFT JOIN OBTN OBTN2
                ON OBTN2."ItemCode" = IBT2."ItemCode"
               AND OBTN2."DistNumber" = IBT2."BatchNum"
            WHERE W."DocNum" = {doc_num_int}
              AND IGN1."ItemCode" IS NOT NULL  -- ✅ Only include rows where IGN1 has data
            
            ORDER BY "MovementType", "ItemCode"
        """
        
        # Log query for debugging
        frappe.log_error(f"Disassembly Query for DocNum {doc_num_int}: {query[:500]}...", "Disassembly Query Debug")
        
        # Execute query
        cursor.execute(query)
        
        # Fetch column names (check if description exists)
        if cursor.description:
            columns = [desc[0] for desc in cursor.description]
        else:
            columns = []
        
        # Fetch all rows
        rows = cursor.fetchall()
        
        # Log results for debugging
        frappe.log_error(f"Disassembly Query returned {len(rows)} rows for DocNum {doc_num_int}", "Disassembly Query Debug")
        
        # Convert rows to list of dictionaries
        if columns and rows:
            result_array = [dict(zip(columns, row)) for row in rows]
        else:
            result_array = []
        
        # Convert decimal values for JSON serialization
        result_array = convert_decimals(result_array)
        
        # Close cursor
        cursor.close()
        cursor = None
        
        # Return success response
        return {
            "status": "success",
            "data": result_array
        }
        
    except Exception as e:
        error_msg = f"Error fetching disassembly details: {str(e)}"
        frappe.log_error(error_msg, "Disassembly Report Error")
        
        return {
            "status": "error",
            "message": error_msg,
            "data": []
        }
    
    finally:
        # Clean up: close cursor and release connection
        if cursor:
            try:
                cursor.close()
            except:
                pass
        
        if conn:
            try:
                conn.close()  # Returns connection to pool
            except:
                pass


# SAP B1 Production Operations
headersList = {
    "Accept": "*/*",
    "User-Agent": "Khanal Tech",
    "Content-Type": "application/json"
}



@frappe.whitelist(allow_guest=False)
def create_goods_issue(doc_date, production_order_docnum, production_order_docentry=None, document_lines=None):
    """
    Create a Goods Issue document in SAP B1 (InventoryGenExits)
    Transforms frontend table data to SAP B1 format
    All values are fetched from database tables (IGE1, OWOR) - no hardcoding
    
    Args:
        doc_date (str): Document date in YYYY-MM-DD format
        production_order_docnum (str): Production Order Document Number for JournalMemo
        production_order_docentry (str): Production Order DocEntry (optional)
        document_lines (list): List of document line items from frontend table with format:
            [
                {
                    "ItemCode": str,              # Item code
                    "WarehouseCode": str,          # Warehouse code (from IGE1.WhsCode)
                    "AccountCode": str,            # Account code (from IGE1.AcctCode)
                    "ProductionOrderDocEntry": int, # Production order entry (from OWOR.DocEntry)
                    "Quantity": float,             # Quantity
                    "BatchNumber": str,            # Batch number
                    "UnitCost": float,             # Unit cost per batch
                    "TotalValue": float            # Total value (Quantity * UnitCost)
                },
                ...
            ]
        
    Returns:
        dict: Response with status and data
    """
    try:
        # Validate inputs
        if not doc_date:
            return {
                "status": "error",
                "message": "Document date (doc_date) is required"
            }
        
        if not production_order_docnum:
            return {
                "status": "error",
                "message": "Production Order Document Number (production_order_docnum) is required"
            }
        
        if not document_lines:
            return {
                "status": "error",
                "message": "Document lines are required"
            }
        
        # Parse document_lines if it's a string
        if isinstance(document_lines, str):
            document_lines = json.loads(document_lines)
        
        # Authenticate SAP B1
        b1_session = AuthenticateSAPB1()
        doc = frappe.get_doc('SAP Test Layer')
        b1_url = doc.sap_b1_url

        # Transform document_lines to SAP B1 format
        sap_document_lines = []
        for line in document_lines:
            sap_line = {
                "ItemCode": str(line.get("ItemCode", "")),
                "Quantity": float(line.get("Quantity", 0)),
                "WarehouseCode": str(line.get("WarehouseCode", "")),
                "AccountCode": str(line.get("AccountCode", "")),
                "UseBaseUnits": "tYES"
            }
            
            # Add BatchNumbers if BatchNumber exists
            batch_number = line.get("BatchNumber")
            if batch_number and batch_number != "-" and batch_number.strip():
                sap_line["BatchNumbers"] = [
                    {
                        "BatchNumber": str(batch_number),
                        "Quantity": float(line.get("Quantity", 0)),
                        "ItemCode": str(line.get("ItemCode", ""))
                    }
                ]
            
            sap_document_lines.append(sap_line)

        # Build JournalMemo with Production Order DocNum
        journal_memo = f"Reversal of Production Order {production_order_docnum} - Raw Material Return"

        # Build payload
        payload = {
            "DocDate": doc_date,
            "JournalMemo": journal_memo,
            "DocObjectCode": "oInventoryGenExit",
            "DocumentLines": sap_document_lines
        }

        reqUrl = b1_url + "InventoryGenExits"
        response = b1_session.request("POST", reqUrl, data=json.dumps(payload), headers=headersList, verify=False)

        if response.status_code in [200, 201]:
            response_data = response.json()
            doc_entry = response_data.get('DocEntry')
            doc_num = response_data.get('DocNum')
            
            # Save response to Disassembly DocType - update if exists, create if not
            try:
                # Check if record already exists by production_order_docnum (unique field)
                existing_doc = frappe.db.exists("Disassembly", {
                    "production_order_docnum": str(production_order_docnum)
                })
                
                if existing_doc:
                    # Update existing record
                    disassembly_doc = frappe.get_doc("Disassembly", existing_doc)
                    # Update Goods Issue specific fields
                    disassembly_doc.goods_issue_response = json.dumps(response_data, indent=2)
                    # Extract and store Goods Issue DocNum and DocEntry
                    disassembly_doc.sap_goods_issue_docnum = str(doc_num) if doc_num else None
                    disassembly_doc.sap_goods_issue_docentry = str(doc_entry) if doc_entry else None
                    # Update common fields if not already set
                    if not disassembly_doc.doc_date:
                        disassembly_doc.doc_date = doc_date
                    if not disassembly_doc.production_order_docentry:
                        disassembly_doc.production_order_docentry = str(production_order_docentry) if production_order_docentry else None
                    if not disassembly_doc.journal_memo:
                        disassembly_doc.journal_memo = journal_memo
                    # Update transaction type if not set or keep existing
                    if not disassembly_doc.transaction_type:
                        disassembly_doc.transaction_type = "Goods Issue"
                    elif disassembly_doc.transaction_type == "Goods Receipt":
                        disassembly_doc.transaction_type = "Both"
                    # Update status if both transactions are successful
                    if disassembly_doc.goods_receipt_response and disassembly_doc.status != "Error":
                        disassembly_doc.status = "Success"
                    elif not disassembly_doc.status:
                        disassembly_doc.status = "Success"
                    disassembly_doc.save(ignore_permissions=True)
                else:
                    # Create new record
                    disassembly_doc = frappe.get_doc({
                        "doctype": "Disassembly",
                        "production_order_docnum": str(production_order_docnum),
                        "production_order_docentry": str(production_order_docentry) if production_order_docentry else None,
                        "transaction_type": "Goods Issue",
                        "doc_date": doc_date,
                        "sap_goods_issue_docnum": str(doc_num) if doc_num else None,
                        "sap_goods_issue_docentry": str(doc_entry) if doc_entry else None,
                        "status": "Success",
                        "journal_memo": journal_memo,
                        "goods_issue_response": json.dumps(response_data, indent=2)
                    })
                    disassembly_doc.insert(ignore_permissions=True)
                
                frappe.db.commit()
            except Exception as save_error:
                frappe.log_error(f"Error saving Disassembly record: {str(save_error)}", "Disassembly Save Error")
            
            return {
                "status": "success",
                "message": "Goods Issue created successfully",
                "data": response_data,
                "doc_entry": doc_entry,
                "doc_num": doc_num
            }
        else:
            error_msg = f"Failed to create Goods Issue: {response.status_code} - {response.text}"
            frappe.log_error(error_msg, "SAP B1 Create Goods Issue Error")
            
            # Save error response to Disassembly DocType - update if exists, create if not
            try:
                error_response_data = {}
                try:
                    error_response_data = response.json()
                except:
                    error_response_data = {"error": response.text}
                
                # Check if record already exists by production_order_docnum (unique field)
                existing_doc = frappe.db.exists("Disassembly", {
                    "production_order_docnum": str(production_order_docnum)
                })
                
                if existing_doc:
                    # Update existing record
                    disassembly_doc = frappe.get_doc("Disassembly", existing_doc)
                    disassembly_doc.goods_issue_response = json.dumps(error_response_data, indent=2)
                    disassembly_doc.status = "Error"
                    if not disassembly_doc.journal_memo:
                        disassembly_doc.journal_memo = journal_memo
                    disassembly_doc.save(ignore_permissions=True)
                else:
                    # Create new record
                    disassembly_doc = frappe.get_doc({
                        "doctype": "Disassembly",
                        "production_order_docnum": str(production_order_docnum),
                        "production_order_docentry": str(production_order_docentry) if production_order_docentry else None,
                        "transaction_type": "Goods Issue",
                        "doc_date": doc_date,
                        "status": "Error",
                        "journal_memo": journal_memo,
                        "goods_issue_response": json.dumps(error_response_data, indent=2)
                    })
                    disassembly_doc.insert(ignore_permissions=True)
                
                frappe.db.commit()
            except Exception as save_error:
                frappe.log_error(f"Error saving Disassembly error record: {str(save_error)}", "Disassembly Save Error")
            
            return {
                "status": "error",
                "message": error_msg
            }

    except Exception as e:
        error_msg = f"Error creating Goods Issue: {str(e)}"
        frappe.log_error(error_msg, "SAP B1 Create Goods Issue Error")
        
        # Save exception error to Disassembly DocType - update if exists, create if not
        try:
            # Check if record already exists
            existing_doc = None
            if production_order_docnum:
                existing_doc = frappe.db.exists("Disassembly", {
                    "production_order_docnum": str(production_order_docnum),
                    "transaction_type": "Goods Issue",
                    "doc_date": doc_date if doc_date else frappe.utils.today()
                })
            
            if existing_doc:
                # Update existing record
                disassembly_doc = frappe.get_doc("Disassembly", existing_doc)
                disassembly_doc.status = "Error"
                disassembly_doc.journal_memo = f"Exception: {error_msg}"
                disassembly_doc.response_json = json.dumps({"exception": str(e)}, indent=2)
                disassembly_doc.save(ignore_permissions=True)
            else:
                # Create new record
                disassembly_doc = frappe.get_doc({
                    "doctype": "Disassembly",
                    "production_order_docnum": str(production_order_docnum) if production_order_docnum else "N/A",
                    "production_order_docentry": str(production_order_docentry) if production_order_docentry else None,
                    "transaction_type": "Goods Issue",
                    "doc_date": doc_date if doc_date else frappe.utils.today(),
                    "status": "Error",
                    "journal_memo": f"Exception: {error_msg}",
                    "response_json": json.dumps({"exception": str(e)}, indent=2)
                })
                disassembly_doc.insert(ignore_permissions=True)
            
            frappe.db.commit()
        except Exception as save_error:
            frappe.log_error(f"Error saving Disassembly exception record: {str(save_error)}", "Disassembly Save Error")
        
        return {
            "status": "error",
            "message": error_msg
        }


@frappe.whitelist(allow_guest=False)
def create_goods_receipt(doc_date, production_order_docnum, production_order_docentry=None, document_lines=None):
    """
    Create a Goods Receipt document in SAP B1 (InventoryGenEntries)
    Transforms frontend table data to SAP B1 format
    All values are fetched from database tables (IGN1, OWOR) - no hardcoding
    
    Args:
        doc_date (str): Document date in YYYY-MM-DD format
        production_order_docnum (str): Production Order Document Number for JournalMemo
        production_order_docentry (str): Production Order DocEntry (optional)
        document_lines (list): List of document line items from frontend table with format:
            [
                {
                    "ItemCode": str,              # Item code
                    "WarehouseCode": str,          # Warehouse code (from IGN1.WhsCode)
                    "AccountCode": str,            # Account code (from IGN1.AcctCode)
                    "ProductionOrderDocEntry": int, # Production order entry (from OWOR.DocEntry)
                    "Quantity": float,             # Quantity
                    "BatchNumber": str,            # Batch number
                    "LocationCode": int,          # Location code (from IGN1.LocCode)
                    "UnitCost": float,             # Unit cost per batch
                    "TotalValue": float           # Total value (Quantity * UnitCost)
                },
                ...
            ]
        
    Returns:
        dict: Response with status and data
    """
    try:
        # Validate inputs
        if not doc_date:
            return {
                "status": "error",
                "message": "Document date (doc_date) is required"
            }
        
        if not production_order_docnum:
            return {
                "status": "error",
                "message": "Production Order Document Number (production_order_docnum) is required"
            }
        
        if not document_lines:
            return {
                "status": "error",
                "message": "Document lines are required"
            }
        
        # Parse document_lines if it's a string
        if isinstance(document_lines, str):
            document_lines = json.loads(document_lines)
        
        # Authenticate SAP B1
        b1_session = AuthenticateSAPB1()
        doc = frappe.get_doc('SAP Test Layer')
        b1_url = doc.sap_b1_url

        # Transform document_lines to SAP B1 format
        # Manual Goods Receipt - no BaseEntry reference to production order
        # Production order is only mentioned in JournalMemo
        sap_document_lines = []
        for line in document_lines:
            sap_line = {
                "ItemCode": str(line.get("ItemCode", "")),
                "Quantity": float(line.get("Quantity", 0)),
                "WarehouseCode": str(line.get("WarehouseCode", "")),
                "AccountCode": str(line.get("AccountCode", "")),
                "UseBaseUnits": "tYES"
            }
            
            # Add LocationCode if it exists
            location_code = line.get("LocationCode")
            if location_code and location_code != "-" and str(location_code).strip():
                # Convert to integer if it's a string number
                try:
                    sap_line["LocationCode"] = int(float(str(location_code)))
                except:
                    sap_line["LocationCode"] = int(location_code) if location_code else None
            
            # Add BatchNumbers if BatchNumber exists
            batch_number = line.get("BatchNumber")
            if batch_number and batch_number != "-" and batch_number.strip():
                sap_line["BatchNumbers"] = [
                    {
                        "BatchNumber": str(batch_number),
                        "Quantity": float(line.get("Quantity", 0)),
                        "ItemCode": str(line.get("ItemCode", ""))
                    }
                ]
            
            sap_document_lines.append(sap_line)

        # Build JournalMemo with Production Order DocNum
        journal_memo = f"Reversal of Production Order {production_order_docnum} - Raw Material Return"

        # Build payload
        payload = {
            "DocDate": doc_date,
            "JournalMemo": journal_memo,
            "DocObjectCode": "oInventoryGenEntry",
            "DocumentLines": sap_document_lines
        }

        reqUrl = b1_url + "InventoryGenEntries"
        response = b1_session.request("POST", reqUrl, data=json.dumps(payload), headers=headersList, verify=False)

        if response.status_code in [200, 201]:
            response_data = response.json()
            doc_entry = response_data.get('DocEntry')
            doc_num = response_data.get('DocNum')
            
            # Save response to Disassembly DocType - update if exists, create if not
            try:
                # Check if record already exists by production_order_docnum (unique field)
                existing_doc = frappe.db.exists("Disassembly", {
                    "production_order_docnum": str(production_order_docnum)
                })
                
                if existing_doc:
                    # Update existing record
                    disassembly_doc = frappe.get_doc("Disassembly", existing_doc)
                    # Update Goods Receipt specific fields
                    disassembly_doc.goods_receipt_response = json.dumps(response_data, indent=2)
                    # Extract and store Goods Receipt DocNum and DocEntry
                    disassembly_doc.sap_goods_receipt_docnum = str(doc_num) if doc_num else None
                    disassembly_doc.sap_goods_receipt_docentry = str(doc_entry) if doc_entry else None
                    # Update common fields if not already set
                    if not disassembly_doc.doc_date:
                        disassembly_doc.doc_date = doc_date
                    if not disassembly_doc.production_order_docentry:
                        disassembly_doc.production_order_docentry = str(production_order_docentry) if production_order_docentry else None
                    if not disassembly_doc.journal_memo:
                        disassembly_doc.journal_memo = journal_memo
                    # Update transaction type if not set or keep existing
                    if not disassembly_doc.transaction_type:
                        disassembly_doc.transaction_type = "Goods Receipt"
                    elif disassembly_doc.transaction_type == "Goods Issue":
                        disassembly_doc.transaction_type = "Both"
                    # Update status if both transactions are successful
                    if disassembly_doc.goods_issue_response and disassembly_doc.status != "Error":
                        disassembly_doc.status = "Success"
                    elif not disassembly_doc.status:
                        disassembly_doc.status = "Success"
                    disassembly_doc.save(ignore_permissions=True)
                else:
                    # Create new record
                    disassembly_doc = frappe.get_doc({
                        "doctype": "Disassembly",
                        "production_order_docnum": str(production_order_docnum),
                        "production_order_docentry": str(production_order_docentry) if production_order_docentry else None,
                        "transaction_type": "Goods Receipt",
                        "doc_date": doc_date,
                        "sap_goods_receipt_docnum": str(doc_num) if doc_num else None,
                        "sap_goods_receipt_docentry": str(doc_entry) if doc_entry else None,
                        "status": "Success",
                        "journal_memo": journal_memo,
                        "goods_receipt_response": json.dumps(response_data, indent=2)
                    })
                    disassembly_doc.insert(ignore_permissions=True)
                
                frappe.db.commit()
            except Exception as save_error:
                frappe.log_error(f"Error saving Disassembly record for Goods Receipt: {str(save_error)}", "Disassembly Save Error")
            
            # After successful Goods Receipt, check if both Goods Issue and Goods Receipt are complete
            # If yes, update Production Order with U_disassemble field
            if production_order_docentry and doc_num:
                try:
                    # Fetch the Disassembly record (now contains both responses)
                    disassembly_record = frappe.db.get_value("Disassembly", {
                        "production_order_docnum": str(production_order_docnum)
                    }, ["sap_goods_issue_docnum", "sap_goods_receipt_docnum"], as_dict=True)
                    
                    # Get DocNums from the new fields
                    issue_docnum = disassembly_record.get("sap_goods_issue_docnum") if disassembly_record else None
                    receipt_docnum = doc_num  # Current receipt doc_num
                    
                    # If both responses exist and have SAP DocNums, update Production Order
                    if issue_docnum and receipt_docnum:
                        # Build U_disassemble value with receipts and issues
                        u_disassemble_value = f"📥 Receipt {receipt_docnum} and 📤 Issue {issue_docnum}"
                        
                        # PATCH Production Order with U_disassemble field
                        patch_url = f"{b1_url}ProductionOrders({production_order_docentry})"
                        patch_payload = {
                            "U_disassemble": u_disassemble_value
                        }
                        
                        patch_response = b1_session.request("PATCH", patch_url, 
                                                            data=json.dumps(patch_payload), 
                                                            headers=headersList, verify=False)
                        
                        if patch_response.status_code in [200, 201, 204]:
                            frappe.log_error(f"Successfully updated Production Order {production_order_docentry} with U_disassemble: {u_disassemble_value}", "Production Order Update")
                        else:
                            frappe.log_error(f"Failed to update Production Order {production_order_docentry}: {patch_response.status_code} - {patch_response.text}", "Production Order Update Error")
                    
                except Exception as patch_error:
                    frappe.log_error(f"Error updating Production Order with U_disassemble: {str(patch_error)}", "Production Order Update Error")
            
            return {
                "status": "success",
                "message": "Goods Receipt created successfully",
                "data": response_data,
                "doc_entry": doc_entry,
                "doc_num": doc_num
            }
        else:
            error_msg = f"Failed to create Goods Receipt: {response.status_code} - {response.text}"
            frappe.log_error(error_msg, "SAP B1 Create Goods Receipt Error")
            
            # Save error response to Disassembly DocType - update if exists, create if not
            try:
                error_response_data = {}
                try:
                    error_response_data = response.json()
                except:
                    error_response_data = {"error": response.text}
                
                # Check if record already exists by production_order_docnum (unique field)
                existing_doc = frappe.db.exists("Disassembly", {
                    "production_order_docnum": str(production_order_docnum) if production_order_docnum else "N/A"
                })
                
                if existing_doc:
                    # Update existing record
                    disassembly_doc = frappe.get_doc("Disassembly", existing_doc)
                    disassembly_doc.goods_receipt_response = json.dumps(error_response_data, indent=2)
                    disassembly_doc.status = "Error"
                    if not disassembly_doc.journal_memo:
                        disassembly_doc.journal_memo = journal_memo
                    disassembly_doc.save(ignore_permissions=True)
                else:
                    # Create new record
                    disassembly_doc = frappe.get_doc({
                        "doctype": "Disassembly",
                        "production_order_docnum": str(production_order_docnum) if production_order_docnum else "N/A",
                        "production_order_docentry": str(production_order_docentry) if production_order_docentry else None,
                        "transaction_type": "Goods Receipt",
                        "doc_date": doc_date if doc_date else frappe.utils.today(),
                        "status": "Error",
                        "journal_memo": journal_memo,
                        "goods_receipt_response": json.dumps(error_response_data, indent=2)
                    })
                    disassembly_doc.insert(ignore_permissions=True)
                
                frappe.db.commit()
            except Exception as save_error:
                frappe.log_error(f"Error saving Disassembly error record for Goods Receipt: {str(save_error)}", "Disassembly Save Error")
            
            return {
                "status": "error",
                "message": error_msg
            }

    except Exception as e:
        error_msg = f"Error creating Goods Receipt: {str(e)}"
        frappe.log_error(error_msg, "SAP B1 Create Goods Receipt Error")
        
        # Save exception error to Disassembly DocType - update if exists, create if not
        try:
            # Check if record already exists
            existing_doc = None
            if production_order_docnum:
                existing_doc = frappe.db.exists("Disassembly", {
                    "production_order_docnum": str(production_order_docnum),
                    "transaction_type": "Goods Receipt",
                    "doc_date": doc_date if doc_date else frappe.utils.today()
                })
            
            if existing_doc:
                # Update existing record
                disassembly_doc = frappe.get_doc("Disassembly", existing_doc)
                disassembly_doc.status = "Error"
                disassembly_doc.journal_memo = f"Exception: {error_msg}"
                disassembly_doc.response_json = json.dumps({"exception": str(e)}, indent=2)
                disassembly_doc.save(ignore_permissions=True)
            else:
                # Create new record
                disassembly_doc = frappe.get_doc({
                    "doctype": "Disassembly",
                    "production_order_docnum": str(production_order_docnum) if production_order_docnum else "N/A",
                    "production_order_docentry": str(production_order_docentry) if production_order_docentry else None,
                    "transaction_type": "Goods Receipt",
                    "doc_date": doc_date if doc_date else frappe.utils.today(),
                    "status": "Error",
                    "journal_memo": f"Exception: {error_msg}",
                    "response_json": json.dumps({"exception": str(e)}, indent=2)
                })
                disassembly_doc.insert(ignore_permissions=True)
            
            frappe.db.commit()
        except Exception as save_error:
            frappe.log_error(f"Error saving Disassembly exception record for Goods Receipt: {str(save_error)}", "Disassembly Save Error")
        
        return {
            "status": "error",
            "message": error_msg
        }


@frappe.whitelist(allow_guest=False)
def get_completed_disassemblies(filters=None):
    """
    Get list of all disassemblies from the Disassembly DocType
    Shows all transactions (Goods Issue and Goods Receipt) regardless of status
    
    Args:
        filters (dict): Optional filters
            - production_order_docnum: Filter by production order docnum
            - transaction_type: Filter by transaction type (Goods Issue/Goods Receipt)
            - date_from: Filter from date (YYYY-MM-DD)
            - date_to: Filter to date (YYYY-MM-DD)
    
    Returns:
        dict: Response with status and data
    """
    try:
        # Default filters
        if filters:
            filters = json.loads(filters) if isinstance(filters, str) else filters
        else:
            filters = {}
        
        # Build query to fetch completed disassemblies
        query = """
            SELECT 
                name,
                production_order_docnum,
                production_order_docentry,
                transaction_type,
                doc_date,
                sap_goods_receipt_docnum,
                sap_goods_receipt_docentry,
                sap_goods_issue_docnum,
                sap_goods_issue_docentry,
                status,
                journal_memo,
                modified
            FROM `tabDisassembly`
            WHERE 1=1
        """
        
        conditions = []
        values = {}
        
        # Apply filters
        if filters.get("production_order_docnum"):
            conditions.append("production_order_docnum = %(prod_order_docnum)s")
            values["prod_order_docnum"] = filters["production_order_docnum"]
        
        if filters.get("transaction_type"):
            conditions.append("transaction_type = %(trans_type)s")
            values["trans_type"] = filters["transaction_type"]
        
        if filters.get("date_from"):
            conditions.append("doc_date >= %(date_from)s")
            values["date_from"] = filters["date_from"]
        
        if filters.get("date_to"):
            conditions.append("doc_date <= %(date_to)s")
            values["date_to"] = filters["date_to"]
        
        # Show all transactions (not just successful ones)
        # Remove the status filter to show all records
        # conditions.append("status = 'Success'")
        
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        # Order by modified date descending (latest first)
        query += " ORDER BY modified DESC"
        
        # Add limit for performance
        limit = filters.get("limit", 100)
        query += f" LIMIT {limit}"
        
        # Execute query
        results = frappe.db.sql(query, values, as_dict=True)
        
        return {
            "status": "success",
            "data": results,
            "count": len(results)
        }
        
    except Exception as e:
        error_msg = f"Error fetching completed disassemblies: {str(e)}"
        frappe.log_error(error_msg, "Get Completed Disassemblies Error")
        return {
            "status": "error",
            "message": error_msg,
            "data": []
        }

