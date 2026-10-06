"""
API to lookup batch numbers from Batch Date Item doctype
"""
import frappe
from frappe.utils import getdate, formatdate


@frappe.whitelist(allow_guest=False)
def get_batch_numbers_by_item_code(item_code: str, date_from: str = None, date_to: str = None):
    """
    Get batch numbers for an item code from Batch Date Item doctype.
    If date_from and date_to are provided, filter by date range. Otherwise, return the latest batch numbers.
    
    Args:
        item_code: Item code to search for
        date_from: Optional from date in YYYY-MM-DD format
        date_to: Optional to date in YYYY-MM-DD format. Defaults to current date if date_from is provided
    
    Returns:
        Dictionary with success status and list of batch numbers
    """
    try:
        if not item_code:
            return {
                "success": False,
                "message": "Item code is required",
                "data": []
            }
        
        # If date_from is provided but date_to is not, default to today
        if date_from and not date_to:
            from datetime import datetime
            date_to = datetime.now().strftime("%Y-%m-%d")
        
        # Build filters
        filters = {
            "item_code": item_code
        }
        
        # Build date range filter
        if date_from or date_to:
            if date_from and date_to:
                # Both dates provided - use between filter
                try:
                    date_from_obj = getdate(date_from)
                    date_to_obj = getdate(date_to)
                    filters["batch_date"] = ["between", [date_from_obj.strftime("%Y-%m-%d"), date_to_obj.strftime("%Y-%m-%d")]]
                except:
                    return {
                        "success": False,
                        "message": f"Invalid date format. Please use YYYY-MM-DD format",
                        "data": []
                    }
            elif date_from:
                # Only from date provided
                try:
                    date_from_obj = getdate(date_from)
                    filters["batch_date"] = [">=", date_from_obj.strftime("%Y-%m-%d")]
                except:
                    return {
                        "success": False,
                        "message": f"Invalid from date format. Please use YYYY-MM-DD format",
                        "data": []
                    }
            elif date_to:
                # Only to date provided
                try:
                    date_to_obj = getdate(date_to)
                    filters["batch_date"] = ["<=", date_to_obj.strftime("%Y-%m-%d")]
                except:
                    return {
                        "success": False,
                        "message": f"Invalid to date format. Please use YYYY-MM-DD format",
                        "data": []
                    }
        
        # Fetch records
        if date_from or date_to:
            # Get batches for date range
            records = frappe.get_all(
                "Batch Date Item",
                filters=filters,
                fields=[
                    "name",
                    "item_code",
                    "variant",
                    "warehouse",
                    "batch_number",
                    "batch_date",
                    "category",
                    "grams_sku"
                ],
                order_by="batch_date desc, creation desc"
            )
        else:
            # Get latest batch numbers (most recent date for each item)
            # First, get the most recent date for this item
            latest_date = frappe.db.sql("""
                SELECT MAX(batch_date) as max_date
                FROM `tabBatch Date Item`
                WHERE item_code = %s
            """, (item_code,), as_dict=True)
            
            if latest_date and latest_date[0].get('max_date'):
                filters["batch_date"] = latest_date[0]['max_date']
                records = frappe.get_all(
                    "Batch Date Item",
                    filters=filters,
                    fields=[
                        "name",
                        "item_code",
                        "variant",
                        "warehouse",
                        "batch_number",
                        "batch_date",
                        "category",
                        "grams_sku"
                    ],
                    order_by="creation desc"
                )
            else:
                records = []
        
        # Format results
        results = []
        for record in records:
            results.append({
                "batch_number": record.get("batch_number"),
                "warehouse": record.get("warehouse"),
                "variant": record.get("variant"),
                "date": formatdate(record.get("batch_date"), "dd-MM-yyyy") if record.get("batch_date") else "",
                "category": record.get("category"),
                "grams_sku": record.get("grams_sku") or ""
            })
        
        # Build message
        if date_from and date_to:
            message = f"Found {len(results)} batch number(s) for item {item_code} from {date_from} to {date_to}"
        elif date_from:
            message = f"Found {len(results)} batch number(s) for item {item_code} from {date_from}"
        else:
            message = f"Found {len(results)} batch number(s) for item {item_code} (latest)"
        
        return {
            "success": True,
            "data": results,
            "message": message
        }
        
    except Exception as e:
        frappe.log_error(f"Batch Lookup Error: {frappe.get_traceback()}", "Batch Date Item Lookup")
        return {
            "success": False,
            "message": str(e),
            "data": []
        }


