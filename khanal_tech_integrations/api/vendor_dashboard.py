import frappe
from khanal_tech_integrations.utils.cashfree.vrf.bank_verification import Bank_Validation


def _build_docstatus_summary(status_counts):
    summary = {}
    for row in status_counts:
        if row.get("docstatus") is None:
            continue
        summary[int(row["docstatus"])] = row["count"]
    return summary


def _docstatus_label(docstatus):
    mapping = {
        0: "Draft",
        1: "Submitted",
        2: "Cancelled",
    }
    return mapping.get(int(docstatus or 0), "Draft")


@frappe.whitelist()
def get_vendor_master_dashboard():
    registrations = frappe.db.get_list(
        "SAP Vendor Registration",
        fields=[
            "name",
            "company_name",
            "vendor_name",
            "telephone_number",
            "mobile_number",
            "email",
            "vendor_code",
            "docstatus",
            "creation",
            "modified",
        ],
        order_by="modified desc",
    )

    status_counts = frappe.db.get_list(
        "SAP Vendor Registration",
        fields=["docstatus", "count(name) as count"],
        group_by="docstatus",
    )
    status_summary = _build_docstatus_summary(status_counts)

    summary = {
        "total": frappe.db.count("SAP Vendor Registration"),
        "draft": status_summary.get(0, 0),
        "submitted": status_summary.get(1, 0),
        "cancelled": status_summary.get(2, 0),
        "sap_created": frappe.db.count(
            "SAP Vendor Registration", filters={"vendor_code": ["is", "set"]}
        ),
    }
    # Backward-compatible keys for frontend labels
    summary["pending"] = summary["draft"]
    summary["approved"] = summary["submitted"]
    summary["rejected"] = summary["cancelled"]

    for row in registrations:
        row["vendor_number"] = row.get("vendor_code") or row.get("name")
        row["status"] = _docstatus_label(row.get("docstatus", 0))

    sap_vendor_mapping = frappe.db.get_list(
        "SAP Vendor Mapping",
        fields=["vendor_code", "vendor_name", "vendor_short_code"],
        order_by="modified desc",
        limit_page_length=200,
    )

    recent_successful = frappe.db.get_list(
        "SAP Vendor Registration",
        filters={"vendor_code": ["is", "set"]},
        fields=[
            "name",
            "company_name",
            "vendor_name",
            "vendor_code",
            "modified",
        ],
        order_by="modified desc",
        limit_page_length=10,
    )

    return {
        "summary": summary,
        "registrations": registrations,
        "sap_vendor_mapping": sap_vendor_mapping,
        "recent_successful": recent_successful,
    }


@frappe.whitelist()
def validate_penny_drop(vendor_number):
    if not vendor_number:
        return {
            "ok": False,
            "message": "Vendor number is required.",
        }

    docname = frappe.db.get_value(
        "SAP Vendor Registration", {"vendor_code": vendor_number}, "name"
    )
    if not docname:
        docname = frappe.db.get_value(
            "SAP Vendor Registration", {"name": vendor_number}, "name"
        )

    if not docname:
        return {
            "ok": False,
            "message": "Vendor not found.",
        }

    doc = frappe.get_doc("SAP Vendor Registration", docname)
    if not doc.ifsc_code or not doc.account_number:
        return {
            "ok": False,
            "message": "IFSC code or account number is missing for this vendor.",
            "vendor_name": doc.company_name,
            "vendor_code": doc.vendor_code,
            "vendor_number": docname,
        }

    response = Bank_Validation(doc.ifsc_code, doc.account_number)
    return {
        "ok": True,
        "vendor_name": doc.company_name,
        "vendor_code": doc.vendor_code,
        "vendor_number": docname,
        "response": response,
    }
