import frappe
from datetime import datetime, timedelta


# Month code mapping
MONTH_CODE = {
    1: "A", 2: "B", 3: "C", 4: "D", 5: "E", 6: "F",
    7: "G", 8: "H", 9: "I", 10: "J", 11: "K", 12: "L",
}

# Warehouse to code mapping
WAREHOUSE_CODE = {
    "NH": "N1",
    "KG": "K1",
}


def _format_day(dt: datetime) -> str:
    return f"{dt.day:02d}"


def _format_year(dt: datetime) -> str:
    return f"{dt.year % 100:02d}"


def _build_batch_number(warehouse_prefix: str, variant: str, dt: datetime, sku: str, grams_sku: str | None = None) -> str:
    month_code = MONTH_CODE.get(dt.month, "")
    day = _format_day(dt)
    year = _format_year(dt)
    base = f"{warehouse_prefix}{variant}{day}{month_code}{year}{sku}"
    if grams_sku:
        base = f"{base}{grams_sku}"
    return base


def _get_today_key(dt: datetime | None = None) -> str:
    dt = dt or frappe.utils.now_datetime()
    return dt.strftime("%Y-%m-%d")


def _parse_multi_select_warehouse(warehouse_value: str | None) -> list[str]:
    """
    Parse warehouse value from Small Text field.
    Handles multiple formats: space-separated, comma-separated, or newline-separated.
    Returns a list of warehouse codes.
    """
    if not warehouse_value:
        return ["NH"]  # Default to NH if empty
    
    # Handle if it's already a list
    if isinstance(warehouse_value, list):
        return [w.strip() for w in warehouse_value if w.strip()]
    
    warehouse_value = str(warehouse_value).strip()
    
    # Try splitting by different separators
    # First try newline (most common for multi-select)
    if "\n" in warehouse_value:
        warehouses = [w.strip() for w in warehouse_value.split("\n") if w.strip()]
    # Then try comma
    elif "," in warehouse_value:
        warehouses = [w.strip() for w in warehouse_value.split(",") if w.strip()]
    # Then try space (for "NH KG" format)
    elif " " in warehouse_value and len(warehouse_value.split()) > 1:
        # Check if it looks like multiple warehouses (NH, KG, etc.)
        parts = warehouse_value.split()
        # If we have known warehouse codes, split by space
        known_warehouses = ["NH", "KG"]
        warehouses = []
        current = ""
        for part in parts:
            if part in known_warehouses:
                if current:
                    warehouses.append(current.strip())
                warehouses.append(part)
                current = ""
            else:
                current += " " + part if current else part
        if current:
            warehouses.append(current.strip())
    else:
        # Single value
        warehouses = [warehouse_value]
    
    # Filter out empty strings and clean up
    warehouses = [w.strip() for w in warehouses if w.strip()]
    
    # If empty after parsing, default to NH
    if not warehouses:
        return ["NH"]
    
    return warehouses


def _fetch_config_rows():
    try:
        return frappe.get_all(
            "Batch Number Configuration",
            fields=[
                "category",
                "item_code",
                "variant",
                "warehouse",
                "grams_sku",
                "sku_code as sku"
            ],
            order_by="modified desc",
            limit=1000,
        )
    except Exception:
        return []


def _generate_for_date(dt: datetime) -> list[dict]:
    rows = _fetch_config_rows()
    generated: list[dict] = []

    for item in rows:
        category = item.get("category")
        warehouse_value = item.get("warehouse", "NH")
        warehouses = _parse_multi_select_warehouse(warehouse_value)
        variant = item.get("variant", "")
        sku = (item.get("sku") or "").zfill(2)
        grams_sku = (item.get("grams_sku") or "").zfill(2) if item.get("grams_sku") else None

        # Generate batch number for each warehouse
        for warehouse in warehouses:
            warehouse_code = WAREHOUSE_CODE.get(warehouse, "N1")
            
            if category == "Hardened Cheese Bar":
                batch = _build_batch_number(warehouse_code, variant, dt, sku, grams_sku)
            else:
                batch = _build_batch_number(warehouse_code, variant, dt, sku)

            generated.append({
                "category": category,
                "item_code": item.get("item_code"),
                "variant": variant,
                "warehouse": warehouse,
                "grams_sku": grams_sku or "",
                "batch_number": batch,
                "date": dt.strftime("%Y-%m-%d"),
            })

    return generated


def _save_to_doctype(date_str: str, data: list[dict]):
    """Save batch numbers for a date to Batch Date Item doctype"""
    try:
        # Create new records for this date
        # Note: We check for duplicates in generate_batches, so this should only receive new items
        for item in data:
            # Check if this specific item already exists for this date
            existing = frappe.get_all(
                "Batch Date Item",
                filters={
                    "batch_date": date_str,
                    "item_code": item.get("item_code"),
                    "variant": item.get("variant"),
                    "warehouse": item.get("warehouse"),
                    "grams_sku": item.get("grams_sku") or ""
                },
                fields=["name"],
                limit=1
            )
            
            # Only insert if it doesn't already exist
            if not existing:
                doc = frappe.get_doc({
                    "doctype": "Batch Date Item",
                    "category": item.get("category"),
                    "item_code": item.get("item_code"),
                    "variant": item.get("variant"),
                    "warehouse": item.get("warehouse"),
                    "grams_sku": item.get("grams_sku") or "",
                    "batch_number": item.get("batch_number"),
                    "batch_date": date_str,
                })
                doc.insert(ignore_permissions=True)
        
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"Error saving batch numbers to doctype: {frappe.get_traceback()}", "Batch Number Generator")
        raise


def _read_from_doctype(date_str: str) -> list[dict]:
    """Read batch numbers for a date from Batch Date Item doctype"""
    try:
        records = frappe.get_all(
            "Batch Date Item",
            filters={"batch_date": date_str},
            fields=[
                "category",
                "item_code",
                "variant",
                "warehouse",
                "grams_sku",
                "batch_number",
                "batch_date"
            ],
            order_by="creation desc"
        )
        
        # Convert to expected format
        results = []
        for record in records:
            results.append({
                "category": record.get("category"),
                "item_code": record.get("item_code"),
                "variant": record.get("variant"),
                "warehouse": record.get("warehouse"),
                "grams_sku": record.get("grams_sku") or "",
                "batch_number": record.get("batch_number"),
                "date": record.get("batch_date"),
            })
        
        return results
    except Exception:
        return []


@frappe.whitelist(allow_guest=False)
def generate_batches(date: str | None = None):
    """
    Generate batch numbers for the given date (defaults to today) and store in doctype.
    Generates batch numbers for all items in Batch Number Configuration.
    If some items already have batch numbers for that date, only generates for missing items.
    Returns all batch numbers for that date (existing + newly generated).
    """
    try:
        dt = frappe.utils.get_datetime(date) if date else frappe.utils.now_datetime()
        date_str = dt.strftime("%Y-%m-%d")
        
        # Get all items from Batch Number Configuration
        config_items = _fetch_config_rows()
        
        # Get existing batch numbers for this date
        existing = _read_from_doctype(date_str)
        
        # Create a set of existing item keys (item_code, variant, warehouse, grams_sku)
        existing_keys = set()
        for item in existing:
            key = (
                item.get("item_code", ""),
                item.get("variant", ""),
                item.get("warehouse", ""),
                item.get("grams_sku") or ""
            )
            existing_keys.add(key)
        
        # Find items that need batch numbers generated
        items_to_generate = []
        for config_item in config_items:
            item_code = config_item.get("item_code")
            variant = config_item.get("variant")
            warehouse_value = config_item.get("warehouse")
            warehouses = _parse_multi_select_warehouse(warehouse_value)
            grams_sku = (config_item.get("grams_sku") or "")
            
            # Check each warehouse individually
            for warehouse in warehouses:
                key = (item_code, variant, warehouse, grams_sku)
                if key not in existing_keys:
                    # Store config item with specific warehouse for generation
                    items_to_generate.append({
                        **config_item,
                        "_selected_warehouse": warehouse
                    })
        
        # Generate batch numbers for missing items
        newly_generated = []
        if items_to_generate:
            warehouse_code_map = WAREHOUSE_CODE
            for item in items_to_generate:
                category = item.get("category")
                item_code = item.get("item_code")
                variant = item.get("variant")
                warehouse = item.get("_selected_warehouse")  # Use the specific warehouse
                grams_sku = (item.get("grams_sku") or "").zfill(2) if item.get("grams_sku") else None
                sku = (item.get("sku") or "").zfill(2)
                
                warehouse_code = warehouse_code_map.get(warehouse, "N1")
                
                if category == "Hardened Cheese Bar":
                    batch = _build_batch_number(warehouse_code, variant, dt, sku, grams_sku)
                else:
                    batch = _build_batch_number(warehouse_code, variant, dt, sku)
                
                generated_item = {
                    "category": category,
                    "item_code": item_code,
                    "variant": variant,
                    "warehouse": warehouse,
                    "grams_sku": grams_sku or "",
                    "batch_number": batch,
                    "date": date_str,
                }
                newly_generated.append(generated_item)
            
            # Save newly generated batch numbers
            if newly_generated:
                _save_to_doctype(date_str, newly_generated)
        
        # Return all batch numbers (existing + newly generated)
        all_batches = existing + newly_generated
        
        return {"success": True, "data": all_batches, "message": f"Generated {len(newly_generated)} new batch numbers" if newly_generated else "All batch numbers already exist for this date"}
    except Exception as e:
        frappe.log_error(f"Batch Generate Error: {frappe.get_traceback()}", "Batch Number Generator")
        return {"success": False, "message": str(e)}


def _get_all_batches_for_item(item_code: str, variant: str, warehouse: str, grams_sku: str = "") -> list[dict]:
    """Get all batch numbers for a specific item configuration across all dates"""
    try:
        # Build filters
        filters = {
            "item_code": item_code,
            "variant": variant,
            "warehouse": warehouse
        }
        
        # Fetch all records matching item_code, variant, warehouse
        records = frappe.get_all(
            "Batch Date Item",
            filters=filters,
            fields=[
                "batch_number",
                "batch_date",
                "grams_sku"
            ],
            order_by="batch_date desc, creation desc"
        )
        
        # Filter by grams_sku if specified
        results = []
        for record in records:
            record_grams_sku = record.get("grams_sku") or ""
            if grams_sku:
                # Match exact grams_sku
                if record_grams_sku == grams_sku:
                    results.append({
                        "batch_number": record.get("batch_number"),
                        "date": record.get("batch_date"),
                    })
            else:
                # Match empty grams_sku
                if not record_grams_sku or record_grams_sku == "":
                    results.append({
                        "batch_number": record.get("batch_number"),
                        "date": record.get("batch_date"),
                    })
        
        return results
    except Exception:
        return []


@frappe.whitelist(allow_guest=False)
def get_batches(date: str | None = None, days: int | None = 1):
    """
    Fetch batches grouped by item configuration.
    For each item in Batch Number Configuration, returns all batch numbers generated for it.
    """
    try:
        # Get all items from Batch Number Configuration
        config_items = _fetch_config_rows()
        
        # Group batch numbers by item configuration
        grouped_results = []
        
        for config_item in config_items:
            category = config_item.get("category")
            item_code = config_item.get("item_code")
            variant = config_item.get("variant")
            warehouse_value = config_item.get("warehouse")
            warehouses = _parse_multi_select_warehouse(warehouse_value)
            grams_sku = config_item.get("grams_sku") or ""
            
            # Get all batch numbers for each warehouse in this configuration
            all_batches = []
            for warehouse in warehouses:
                batches = _get_all_batches_for_item(item_code, variant, warehouse, grams_sku)
                all_batches.extend(batches)
            
            grouped_results.append({
                "category": category,
                "item_code": item_code,
                "variant": variant,
                "warehouse": warehouse_value,  # Keep the original multi-select value
                "grams_sku": grams_sku or "-",
                "batches": all_batches  # List of {batch_number, date}
            })
        
        return {"success": True, "data": grouped_results}
    except Exception as e:
        frappe.log_error(f"Batch Get Error: {frappe.get_traceback()}", "Batch Number Generator")
        return {"success": False, "message": str(e), "data": []}


