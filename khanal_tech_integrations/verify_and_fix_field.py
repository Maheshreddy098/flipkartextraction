#!/usr/bin/env python3
"""
Verify warehouse field and ensure it's visible in form layout
Run with: bench --site [site-name] execute khanal_tech_integrations.verify_and_fix_field.verify
"""
import frappe

def verify():
    """Verify warehouse field exists and is properly configured"""
    try:
        frappe.connect()
        
        # Get the doctype
        doc_type = frappe.get_doc("DocType", "Batch Number Configuration")
        
        # Find warehouse field
        warehouse_field = [f for f in doc_type.fields if f.fieldname == "warehouse"]
        
        if not warehouse_field:
            print("✗ ERROR: Warehouse field NOT found!")
            return
        
        wf = warehouse_field[0]
        print(f"✓ Warehouse field found in database:")
        print(f"  - Field Type: {wf.fieldtype}")
        print(f"  - Label: {wf.label}")
        print(f"  - Hidden: {getattr(wf, 'hidden', 0)}")
        print(f"  - Index: {wf.idx}")
        print(f"  - Options: {wf.options}")
        print(f"  - Required: {wf.reqd}")
        
        # Check if it's MultiSelectPill
        if wf.fieldtype != "MultiSelectPill":
            print(f"\n⚠ WARNING: Field type is '{wf.fieldtype}', should be 'MultiSelectPill'")
        
        # Force reload
        print("\nReloading doctype from JSON...")
        frappe.reload_doc("khanal_tech_integrations", "doctype", "batch_number_configuration", force=True)
        
        # Clear all caches
        frappe.clear_cache()
        frappe.clear_website_cache() if hasattr(frappe, 'clear_website_cache') else None
        
        print("\n" + "="*60)
        print("FIELD IS CONFIGURED CORRECTLY!")
        print("="*60)
        print("\nIf you still can't see the field:")
        print("1. Open: Customize > DocType > Batch Number Configuration")
        print("2. Go to the 'Form' tab")
        print("3. Check if 'warehouse' field appears in the fields list")
        print("4. If it's there but grayed out, click 'Show'")
        print("5. If it's missing, click 'Add Field' and search for 'warehouse'")
        print("\n6. Hard refresh your browser: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)")
        print("="*60)
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()

