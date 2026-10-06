import frappe

@frappe.whitelist(allow_guest=True)
def get_responsive_partial(view_type = "desktop"):
    if view_type == "mobile":
        template_path = "templates/includes/warehouse_mobile_view.html"
    elif view_type == "desktop":
        template_path = "templates/includes/warehouse_desktop_view.html"
    else:
        return "<div>Error: Unknown view type</div>"
    print("====================================================")
    print("View Type:", view_type)
    print("Template Path:", template_path)
    return frappe.render_template(template_path, {})
