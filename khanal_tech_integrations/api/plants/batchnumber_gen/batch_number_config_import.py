import frappe
import pandas as pd
from io import BytesIO


@frappe.whitelist(allow_guest=False)
def import_from_excel(file_url: str = None, file_content: str = None):
    """
    Import Batch Number Configuration data from Excel file.
    
    Expected Excel columns:
    - Category (required)
    - Item Code (required)
    - Variant (required)
    - Warehouse (required)
    - Grams SKU (optional)
    - SKU Code (required)
    
    Args:
        file_url: URL of the uploaded Excel file
        file_content: Base64 encoded file content (alternative to file_url)
    
    Returns:
        Dictionary with import results
    """
    try:
        # Read Excel file
        if file_url:
            # Handle Frappe file URL format
            file_url = file_url.strip()
            if file_url.startswith('/files/'):
                file_url = file_url[1:]  # Remove leading /
            
            # Get file path using Frappe's file handling
            try:
                # Try to get file document
                file_doc = frappe.get_doc("File", {"file_url": file_url})
                file_path = file_doc.get_full_path()
            except:
                # Fallback to direct path
                if file_url.startswith('files/'):
                    file_path = frappe.get_site_path('public', file_url)
                else:
                    file_path = frappe.get_site_path('public', 'files', file_url)
            
            df = pd.read_excel(file_path, engine='openpyxl')
        elif file_content:
            # Handle base64 content if needed
            import base64
            file_data = base64.b64decode(file_content)
            df = pd.read_excel(BytesIO(file_data), engine='openpyxl')
        else:
            return {
                "success": False,
                "message": "Either file_url or file_content must be provided"
            }
        
        # Validate required columns
        required_columns = ['Category', 'Item Code', 'Variant', 'Warehouse', 'SKU Code']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return {
                "success": False,
                "message": f"Missing required columns: {', '.join(missing_columns)}"
            }
        
        # Process each row
        success_count = 0
        error_count = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                # Get values, handling NaN/None
                category = str(row.get('Category', '')).strip()
                item_code = str(row.get('Item Code', '')).strip()
                variant = str(row.get('Variant', '')).strip()
                warehouse_raw = str(row.get('Warehouse', '')).strip()
                grams_sku = str(row.get('Grams SKU', '')).strip() if pd.notna(row.get('Grams SKU')) else ''
                sku_code = str(row.get('SKU Code', '')).strip()
                
                # Handle multiple warehouses (comma-separated or newline-separated)
                # Normalize warehouse value - accept comma or newline separated
                if warehouse_raw:
                    # Split by comma or newline, then join with newline (Frappe MultiSelectPill format)
                    warehouses = [w.strip() for w in warehouse_raw.replace(',', '\n').split('\n') if w.strip()]
                    warehouse = '\n'.join(warehouses)  # MultiSelectPill stores as newline-separated
                else:
                    warehouse = ''
                
                # Validate required fields
                if not all([category, item_code, variant, warehouse, sku_code]):
                    error_count += 1
                    errors.append({
                        "row": index + 2,  # +2 because Excel rows start at 1 and header is row 1
                        "error": "Missing required fields"
                    })
                    continue
                
                # Check if record already exists
                existing = frappe.get_all(
                    "Batch Number Configuration",
                    filters={"item_code": item_code},
                    fields=["name"],
                    limit=1
                )
                
                if existing:
                    # Update existing record
                    doc = frappe.get_doc("Batch Number Configuration", existing[0].name)
                    doc.category = category
                    doc.variant = variant
                    doc.warehouse = warehouse
                    doc.grams_sku = grams_sku
                    doc.sku_code = sku_code
                    doc.save(ignore_permissions=True)
                else:
                    # Create new record
                    doc = frappe.get_doc({
                        "doctype": "Batch Number Configuration",
                        "category": category,
                        "item_code": item_code,
                        "variant": variant,
                        "warehouse": warehouse,
                        "grams_sku": grams_sku,
                        "sku_code": sku_code
                    })
                    doc.insert(ignore_permissions=True)
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                errors.append({
                    "row": index + 2,
                    "error": str(e)
                })
        
        frappe.db.commit()
        
        return {
            "success": True,
            "message": f"Import completed: {success_count} records processed successfully, {error_count} errors",
            "success_count": success_count,
            "error_count": error_count,
            "errors": errors[:10]  # Return first 10 errors
        }
        
    except Exception as e:
        frappe.log_error(f"Batch Number Config Import Error: {frappe.get_traceback()}", "Batch Number Config Import")
        return {
            "success": False,
            "message": f"Import failed: {str(e)}"
        }


@frappe.whitelist(allow_guest=False)
def download_template():
    """
    Download Excel template for Batch Number Configuration import.
    
    Returns:
        Excel file as base64 encoded string
    """
    try:
        # Create template DataFrame with example rows
        template_data = {
            'Category': ['Hardened Cheese Bread', 'Hardened Cheese Bar', ''],
            'Item Code': ['EXAMPLE001', 'EXAMPLE002', ''],
            'Variant': ['JL', 'V1', ''],
            'Warehouse': ['NH', 'KG', 'NH\nKG'],  # Show example with single and multiple warehouses
            'Grams SKU': ['100', '', ''],
            'SKU Code': ['01', '02', '']
        }
        df = pd.DataFrame(template_data)
        
        # Create Excel in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Batch Number Configuration')
            # Get workbook to format
            workbook = writer.book
            worksheet = writer.sheets['Batch Number Configuration']
            
            # Make header row bold
            from openpyxl.styles import Font, PatternFill
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            header_font = Font(bold=True, color="FFFFFF")
            
            for cell in worksheet[1]:
                cell.font = header_font
                cell.fill = header_fill
        
        # Close writer and get content
        output.seek(0)
        file_content = output.getvalue()
        output.close()
        
        import base64
        file_base64 = base64.b64encode(file_content).decode('utf-8')
        
        return {
            "success": True,
            "file_content": file_base64,
            "filename": "Batch_Number_Configuration_Template.xlsx"
        }
        
    except Exception as e:
        frappe.log_error(f"Template Download Error: {frappe.get_traceback()}", "Batch Number Config Import")
        return {
            "success": False,
            "message": f"Failed to generate template: {str(e)}"
        }


