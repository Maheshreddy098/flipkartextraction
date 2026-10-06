import json

import frappe
from frappe import _
from frappe.utils import now_datetime, today, getdate, flt, add_days, cint
from frappe.utils.pdf import get_pdf

from khanal_tech_integrations.consumables.services.role_guard import (
    assert_plant_access,
    get_accessible_plants,
    require_consumables_role,
)

# SAP B1 document numbering — internal series key for Purchase Orders (Series setup in B1).
CONSUMABLES_SAP_PO_SERIES = 521

# SAP mandates Distribution Rule 4 on PO/GRN lines — OcrCode4 is the DB column
# name (confirmed against real posted PDN1/POR1 history: each warehouse has one
# dominant/exclusive code, matching OOCR's ATP=Akshay Tech Park, DF=Mahadevpura,
# HNF=Malur Factory, KNJ=Krishnagiri, NH=Nandi Hills) but Service Layer's JSON
# property for it is CostingCode4 — sending "OcrCode4" in the payload is a
# silently-ignored unknown key, not an error, which is why it had zero effect.
WAREHOUSE_DISTRIBUTION_RULE = {
    "DC-STR": "DF",
    "HN-STR": "HNF",
    "KG-STR": "KNJ",
    "NH-STR": "NH",
    "ATP-HO": "ATP",
}


def _enabled_users_with_role(role):
    rows = frappe.db.sql(
        """
        SELECT DISTINCT u.name
        FROM `tabUser` u
        JOIN `tabHas Role` r ON r.parent = u.name AND r.parenttype = 'User'
        WHERE u.enabled = 1 AND r.role = %s
        """,
        role,
        as_dict=True,
    )
    return [(row.name or "").strip() for row in rows if (row.name or "").strip()]


def _require_procurement_or_admin():
    require_consumables_role()
    roles = frappe.get_roles()
    if not any(r in roles for r in ("Consumables Procurement User", "Consumables Super Admin")):
        frappe.throw(
            _("Only a Procurement User or Super Admin can perform this action."),
            frappe.PermissionError,
        )


def _require_grn_roles():
    """Allow Procurement, Store Manager, Inventory Manager, and Super Admin to submit GRN."""
    require_consumables_role()
    roles = frappe.get_roles()
    allowed = (
        "Consumables Procurement User",
        "Consumables Store Manager",
        "Consumables Inventory Manager",
        "Consumables Super Admin",
    )
    if not any(r in roles for r in allowed):
        frappe.throw(
            _("Only Store Manager, Inventory Manager, Procurement User, or Super Admin can submit GRN."),
            frappe.PermissionError,
        )




def _require_cpr_read_access(doc):
    require_consumables_role()
    roles = frappe.get_roles()
    if not any(r in roles for r in ("Consumables Procurement User", "Consumables Super Admin")):
        assert_plant_access(doc.requesting_plant)


def _fmt_amount(value):
    return "{:,.2f}".format(flt(value or 0))


def _fmt_qty(value):
    qty = flt(value or 0)
    return "{:,.0f}".format(qty) if qty == int(qty) else "{:,.2f}".format(qty)


def _safe_po_pdf_filename(doc):
    import re
    base = doc.sap_po_doc_num or doc.name
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", str(base)).strip("-") or doc.name
    return f"Consumables-PO-{base}.pdf"


def _purchase_order_pdf_html(doc):
    rows = []
    total_qty = 0
    total_amount = 0
    for idx, li in enumerate(doc.line_items or [], start=1):
        qty = flt(getattr(li, "sap_order_qty", None) or li.quantity or 0)
        rate = flt(getattr(li, "po_unit_price", None) or 0)
        amount = qty * rate
        total_qty += qty
        total_amount += amount
        rows.append({
            "idx": idx,
            "item_code": li.item_code or "",
            "item_name": li.item_name or "",
            "qty": _fmt_qty(qty),
            "uom": li.uom or "",
            "warehouse_code": getattr(li, "warehouse_code", None) or "",
            "tax_code": getattr(li, "tax_code", None) or "",
            "rate": _fmt_amount(rate),
            "amount": _fmt_amount(amount),
            "is_extra_item": cint(getattr(li, "is_extra_item", 0)),
        })

    return frappe.render_template(
        """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body { font-family: Arial, sans-serif; color: #111827; font-size: 12px; }
    .header { display: table; width: 100%; border-bottom: 2px solid #111827; padding-bottom: 14px; margin-bottom: 18px; }
    .header-left { display: table-cell; vertical-align: top; }
    .header-right { display: table-cell; text-align: right; vertical-align: top; }
    .title { font-size: 22px; font-weight: 700; margin: 0 0 6px; }
    .muted { color: #6b7280; }
    .badge { display: inline-block; padding: 4px 8px; border-radius: 4px; background: #ccfbf1; color: #115e59; font-weight: 700; }
    .grid { display: table; width: 100%; margin-bottom: 18px; }
    .grid-row { display: table-row; }
    .grid-cell { display: table-cell; width: 25%; padding: 6px 12px 6px 0; vertical-align: top; }
    .label { display: block; color: #6b7280; font-size: 10px; text-transform: uppercase; letter-spacing: .04em; margin-bottom: 3px; }
    table { width: 100%; border-collapse: collapse; margin-top: 8px; }
    th { background: #f3f4f6; color: #374151; font-size: 10px; text-align: left; padding: 8px 6px; border: 1px solid #d1d5db; text-transform: uppercase; }
    td { padding: 8px 6px; border: 1px solid #d1d5db; vertical-align: top; }
    .num { text-align: right; white-space: nowrap; }
    .total-row td { font-weight: 700; background: #f9fafb; }
    .remarks { margin-top: 18px; padding: 10px; border: 1px solid #d1d5db; background: #f9fafb; }
    .footer { margin-top: 22px; font-size: 10px; color: #6b7280; }
  </style>
</head>
<body>
  <div class="header">
    <div class="header-left">
      <h1 class="title">Consumables Purchase Order</h1>
      <div class="muted">CPR: {{ doc.name }}</div>
    </div>
    <div class="header-right">
      <div class="badge">{{ doc.status }}</div>
      <div style="margin-top: 8px;"><strong>SAP PO #:</strong> {{ doc.sap_po_doc_num or "-" }}</div>
      <div><strong>DocEntry:</strong> {{ doc.sap_po_doc_entry or "-" }}</div>
    </div>
  </div>

  <div class="grid">
    <div class="grid-row">
      <div class="grid-cell"><span class="label">Vendor</span>{{ doc.vendor_code or "-" }}</div>
      <div class="grid-cell"><span class="label">Requesting Plant</span>{{ doc.requesting_plant or "-" }}</div>
      <div class="grid-cell"><span class="label">Receiving Plant</span>{{ doc.receiving_plant or doc.requesting_plant or "-" }}</div>
      <div class="grid-cell"><span class="label">Source CMR</span>{{ doc.cmr_reference or "-" }}</div>
    </div>
    <div class="grid-row">
      <div class="grid-cell"><span class="label">Document Date</span>{{ doc.sap_document_date or "-" }}</div>
      <div class="grid-cell"><span class="label">Delivery Date</span>{{ doc.sap_delivery_date or "-" }}</div>
      <div class="grid-cell"><span class="label">Tax Date</span>{{ doc.sap_tax_date or "-" }}</div>
      <div class="grid-cell"><span class="label">Requested By</span>{{ doc.requested_by or "-" }}</div>
    </div>
  </div>

  <table>
    <thead>
      <tr>
        <th style="width: 28px;">#</th>
        <th>Item Code</th>
        <th>Item Name</th>
        <th class="num">Qty</th>
        <th>UOM</th>
        <th>Warehouse</th>
        <th>Tax Code</th>
        <th class="num">Unit Price</th>
        <th class="num">Amount</th>
      </tr>
    </thead>
    <tbody>
      {% for row in rows %}
      <tr>
        <td>{{ row.idx }}</td>
        <td>{{ row.item_code or "-" }}{% if row.is_extra_item %}<br><span class="muted">Added by procurement</span>{% endif %}</td>
        <td>{{ row.item_name or "-" }}</td>
        <td class="num">{{ row.qty }}</td>
        <td>{{ row.uom or "-" }}</td>
        <td>{{ row.warehouse_code or "-" }}</td>
        <td>{{ row.tax_code or "-" }}</td>
        <td class="num">{{ row.rate }}</td>
        <td class="num">{{ row.amount }}</td>
      </tr>
      {% endfor %}
      <tr class="total-row">
        <td colspan="3" class="num">Total</td>
        <td class="num">{{ total_qty }}</td>
        <td colspan="4"></td>
        <td class="num">{{ total_amount }}</td>
      </tr>
    </tbody>
  </table>

  {% if doc.remarks %}
  <div class="remarks">
    <span class="label">Remarks</span>
    {{ doc.remarks }}
  </div>
  {% endif %}

  <div class="footer">Generated from Consumables on {{ generated_on }}</div>
</body>
</html>
        """,
        {
            "doc": doc,
            "rows": rows,
            "total_qty": _fmt_qty(total_qty),
            "total_amount": _fmt_amount(total_amount),
            "generated_on": now_datetime().strftime("%Y-%m-%d %H:%M"),
        },
    )

def _cpr_to_dict(doc):
    return {
        "name": doc.name,
        "status": doc.status,
        "cmr_reference": doc.cmr_reference or "",
        "split_from": getattr(doc, "split_from", None) or "",
        "requesting_plant": doc.requesting_plant or "",
        "requested_by": doc.requested_by or "",
        "requested_on": str(doc.requested_on or ""),
        "vendor_code": doc.vendor_code or "",
        "sap_po_series": getattr(doc, "sap_po_series", None) or 0,
        "sap_document_date": str(doc.sap_document_date or "") if getattr(doc, "sap_document_date", None) else "",
        "sap_delivery_date": str(doc.sap_delivery_date or "") if getattr(doc, "sap_delivery_date", None) else "",
        "sap_tax_date": str(doc.sap_tax_date or "") if getattr(doc, "sap_tax_date", None) else "",
        "sap_ship_to_code": getattr(doc, "sap_ship_to_code", None) or "",
        "sap_bill_to_code": getattr(doc, "sap_bill_to_code", None) or "",
        "receiving_plant": getattr(doc, "receiving_plant", None) or "",
        "sap_draft_doc_entry": getattr(doc, "sap_draft_doc_entry", None) or "",
        "sap_po_doc_entry": doc.sap_po_doc_entry or "",
        "sap_po_doc_num": doc.sap_po_doc_num or "",
        "sap_grpo_doc_entry": doc.sap_grpo_doc_entry or "",
        "sap_grpo_doc_num": doc.sap_grpo_doc_num or "",
        "sap_last_error": doc.sap_last_error or "",
        "remarks": doc.remarks or "",
        "modified": str(doc.modified or ""),
        "line_items": [
            {
                "name": li.name,
                "item_code": li.item_code or "",
                "item_name": li.item_name or "",
                "item_purpose": getattr(li, "item_purpose", None) or "",
                "quantity": li.quantity or 0,
                "uom": li.uom or "",
                "po_unit_price": flt(getattr(li, "po_unit_price", None)),
                "sap_order_qty": flt(getattr(li, "sap_order_qty", None)),
                "tax_code": getattr(li, "tax_code", None) or "",
                "warehouse_code": getattr(li, "warehouse_code", None) or "",
                "quantity_received": li.quantity_received or 0,
                "fulfillment_status": li.fulfillment_status or "Pending",
                "is_extra_item": cint(getattr(li, "is_extra_item", 0)),
            }
            for li in (doc.line_items or [])
        ],
    }


@frappe.whitelist()
def search_vendors(query=""):
    """Search SAP vendors (suppliers) by CardCode or CardName.

    Returns up to 20 matches from HANA OCRD where CardType = 'S'.
    Search is case-insensitive on both code and name.
    """
    _require_procurement_or_admin()
    query = (query or "").strip()
    if len(query) < 2:
        return []

    from khanal_tech_integrations.consumables.hana.client import ConsumablesHANAClient

    like_val = f"%{query.upper()}%"
    try:
        with ConsumablesHANAClient() as client:
            sql = f"""
SELECT TOP 20
    T0."CardCode"  AS card_code,
    T0."CardName"  AS card_name
FROM {client.schema}."OCRD" T0
WHERE T0."CardType" = 'S'
  AND T0."frozenFor" = 'N'
  AND (UPPER(T0."CardCode") LIKE ? OR UPPER(T0."CardName") LIKE ?)
ORDER BY
    CASE WHEN UPPER(T0."CardCode") = ? THEN 0
         WHEN UPPER(T0."CardCode") LIKE ? THEN 1
         ELSE 2
    END,
    T0."CardName" ASC
"""
            rows = client.execute(sql, [like_val, like_val, query.upper(), f"{query.upper()}%"])
        return [{"card_code": r["card_code"], "card_name": r["card_name"]} for r in rows]
    except Exception as e:
        frappe.log_error(str(e), "StoreOps search_vendors error")
        frappe.throw(_("Could not search vendors: {0}").format(str(e)[:200]))


@frappe.whitelist()
def list_vendor_po_addresses(card_code=None, addr_type="S"):
    """Return BP address codes from SAP HANA CRD1 for Ship-To (S) or Bill-To (B)."""
    _require_procurement_or_admin()
    card_code = (card_code or "").strip()
    if not card_code:
        return []
    addr_type = (addr_type or "S").strip().upper()[:1]
    if addr_type not in ("S", "B"):
        frappe.throw(_("addr_type must be S (ship) or B (bill)."), frappe.ValidationError)

    from khanal_tech_integrations.consumables.hana.client import ConsumablesHANAClient

    try:
        with ConsumablesHANAClient() as client:
            sql = f"""
SELECT DISTINCT
    T0."Address" AS address_code,
    T0."Street" AS street,
    T0."City" AS city,
    T0."AdresType" AS adres_type
FROM {client.schema}."CRD1" T0
WHERE T0."CardCode" = ?
ORDER BY T0."Address"
"""
            rows = client.execute(sql, [card_code])
    except Exception as e:
        frappe.log_error(str(e), "list_vendor_po_addresses")
        return []

    want = addr_type.upper()
    filtered = [r for r in rows if (str(r.get("adres_type") or "").strip().upper()[:1] == want)]
    use_rows = filtered if filtered else rows
    out = []
    for r in use_rows:
        code = (r.get("address_code") or "").strip()
        if not code:
            continue
        city = (r.get("city") or "").strip()
        street = (r.get("street") or "").strip()
        label = " — ".join([p for p in (code, street or city) if p])
        out.append({"address_code": code, "label": label})
    return out


@frappe.whitelist()
def list_plant_ship_addresses(plant_code):
    """Return ship-to addresses from SAP OWHS for the plant's warehouses."""
    _require_procurement_or_admin()
    plant_code = (plant_code or "").strip()
    if not plant_code:
        return []
    assert_plant_access(plant_code)

    # Get warehouse codes configured for this plant in Frappe
    wh_rows = frappe.db.get_all(
        "Consumables Plant Warehouse",
        filters={"parent": plant_code, "is_active": 1},
        fields=["warehouse_code"],
    )
    wh_codes = [r.warehouse_code for r in wh_rows if r.warehouse_code]
    if not wh_codes:
        return []

    from khanal_tech_integrations.consumables.hana.client import ConsumablesHANAClient
    placeholders = ", ".join(["?"] * len(wh_codes))
    try:
        with ConsumablesHANAClient() as client:
            sql = f"""
SELECT
    T0."WhsCode"  AS warehouse_code,
    T0."WhsName"  AS warehouse_name,
    T0."Street"   AS street,
    T0."Block"    AS block,
    T0."City"     AS city,
    T0."ZipCode"  AS zip_code,
    T0."State"    AS state
FROM {client.schema}."OWHS" T0
WHERE T0."WhsCode" IN ({placeholders})
ORDER BY T0."WhsCode"
"""
            rows = client.execute(sql, wh_codes)
    except Exception as e:
        frappe.log_error(str(e), "list_plant_ship_addresses")
        return []

    out = []
    for r in rows:
        code = (r.get("warehouse_code") or "").strip()
        if not code:
            continue
        parts = [p for p in [
            r.get("warehouse_name") or "",
            r.get("street") or "",
            r.get("block") or "",
            r.get("city") or "",
            r.get("state") or "",
            r.get("zip_code") or "",
        ] if p.strip()]
        label = f"{code} — " + ", ".join(parts) if parts else code
        out.append({"address_code": code, "label": label})
    return out



@frappe.whitelist()
def get_items_tax_info(item_codes):
    """Return purchase tax code, rate, and last 3 purchase prices from SAP for the given item codes."""
    require_consumables_role()
    if isinstance(item_codes, str):
        try:
            item_codes = json.loads(item_codes)
        except Exception:
            item_codes = [item_codes]
    item_codes = [str(c).strip() for c in (item_codes or []) if str(c).strip()]
    if not item_codes:
        return {}
    from khanal_tech_integrations.consumables.hana.client import ConsumablesHANAClient
    placeholders = ", ".join(["?" for _ in item_codes])

    # Fetch tax code, rate, and last purchase price from item master
    try:
        with ConsumablesHANAClient() as client:
            tax_sql = f"""
SELECT
    T0."ItemCode"   AS item_code,
    T0."TaxCodeAP"  AS tax_code,
    T0."LastPurPrc" AS previous_purchase_price,
    T0."LastPurCur" AS previous_purchase_currency,
    T1."Rate"       AS tax_rate
FROM {client.schema}."OITM" T0
LEFT JOIN {client.schema}."OSTC" T1 ON T1."Code" = T0."TaxCodeAP"
WHERE T0."ItemCode" IN ({placeholders})
"""
            rows = client.execute(tax_sql, item_codes)
    except Exception as e:
        frappe.log_error(str(e), "get_items_tax_info")
        return {}

    # Fetch last 3 purchase prices from AP invoice history (best-effort; won't break tax info if it fails)
    price_history = {}
    try:
        with ConsumablesHANAClient() as client:
            history_sql = f"""
SELECT item_code, price, currency, doc_date
FROM (
    SELECT
        T1."ItemCode"     AS item_code,
        T1."Price"        AS price,
        T0."DocCur"       AS currency,
        T0."DocDate"      AS doc_date,
        ROW_NUMBER() OVER (PARTITION BY T1."ItemCode" ORDER BY T0."DocDate" DESC, T0."DocEntry" DESC) AS rn
    FROM {client.schema}."OPCH" T0
    JOIN {client.schema}."PCH1" T1 ON T1."DocEntry" = T0."DocEntry"
    WHERE T1."ItemCode" IN ({placeholders})
        AND T1."Price" > 0
) ranked
WHERE rn <= 3
ORDER BY item_code, rn
"""
            history_rows = client.execute(history_sql, item_codes)
        for r in history_rows:
            code = (r.get("item_code") or "").strip()
            if not code:
                continue
            price_history.setdefault(code, []).append({
                "price": float(r.get("price") or 0),
                "currency": (r.get("currency") or "").strip(),
                "date": str(r.get("doc_date") or ""),
            })
    except Exception as e:
        frappe.log_error(str(e), "get_items_tax_info_history")

    result = {}
    for r in rows:
        code = (r.get("item_code") or "").strip()
        if code:
            result[code] = {
                "tax_code": (r.get("tax_code") or "").strip(),
                "tax_rate": float(r.get("tax_rate") or 0),
                "previous_purchase_price": float(r.get("previous_purchase_price") or 0),
                "previous_purchase_currency": (r.get("previous_purchase_currency") or "").strip(),
                "previous_purchase_prices": price_history.get(code, []),
            }
    return result


@frappe.whitelist()
def get_cpr_grn_info(cpr_names):
    """Return GRN-relevant info for a list of CPR names — for Store Managers on the CMR page."""
    _require_grn_roles()
    if isinstance(cpr_names, str):
        try:
            cpr_names = json.loads(cpr_names)
        except Exception:
            cpr_names = [cpr_names]
    cpr_names = [str(n).strip() for n in (cpr_names or []) if str(n).strip()]
    if not cpr_names:
        return []
    accessible = get_accessible_plants()
    result = []
    for name in cpr_names:
        if not frappe.db.exists("Consumables Purchase Request", name):
            continue
        doc = frappe.get_doc("Consumables Purchase Request", name)
        if (doc.requesting_plant or "") not in accessible:
            continue
        if doc.status not in ("PO Raised", "GRN Done"):
            continue
        result.append({
            "name": doc.name,
            "status": doc.status,
            "vendor_code": doc.vendor_code or "",
            "sap_po_doc_num": doc.sap_po_doc_num or "",
            "sap_po_doc_entry": doc.sap_po_doc_entry or "",
            "sap_grpo_doc_num": doc.sap_grpo_doc_num or "",
            "sap_last_error": doc.sap_last_error or "",
            "line_items": [
                {
                    "name": li.name,
                    "item_code": li.item_code,
                    "item_name": li.item_name or "",
                    "quantity": float(li.quantity or 0),
                    "quantity_received": float(getattr(li, "quantity_received", 0) or 0),
                    "uom": li.uom or "",
                }
                for li in (doc.line_items or [])
                if li.item_code
            ],
        })
    return result


@frappe.whitelist()
def get_purchase_requests(status=None, plant=None, page=1, page_size=20):
    require_consumables_role()
    roles = frappe.get_roles()
    is_admin = "Consumables Super Admin" in roles
    is_procurement = "Consumables Procurement User" in roles
    is_manager = "Consumables Store Manager" in roles

    filters = {}
    if status == 'Pending GRN':
        # CPRs where partial GRN was done — SAP PO still open (status = PO Raised + GRPO doc num set)
        filters["status"] = "PO Raised"
        filters["sap_grpo_doc_num"] = ["is", "set"]
    elif status:
        filters["status"] = status
    elif is_procurement:
        # Include Submitted: CPRs from CMR / material requests start as Submitted before PO is raised.
        filters["status"] = ["in", ["Submitted", "Draft", "PO Pending", "PO Posting", "PO Raised", "GRN Done", "Transfer Pending"]]

    if plant:
        if not (is_admin or is_procurement):
            assert_plant_access(plant)
        filters["requesting_plant"] = plant
    elif not (is_admin or is_procurement):
        accessible = get_accessible_plants()
        if not accessible:
            return {"total": 0, "page": page, "page_size": page_size, "items": []}
        filters["requesting_plant"] = ["in", accessible]

    try:
        page = int(page)
        page_size = int(page_size)
    except Exception:
        page, page_size = 1, 20

    total = frappe.db.count("Consumables Purchase Request", filters=filters)
    rows = frappe.get_all(
        "Consumables Purchase Request",
        filters=filters,
        fields=[
            "name", "status", "cmr_reference", "requesting_plant",
            "requested_by", "requested_on", "vendor_code",
            "sap_po_doc_num", "sap_grpo_doc_num",
        ],
        order_by="requested_on desc",
        limit_start=(page - 1) * page_size,
        limit_page_length=page_size,
        ignore_permissions=True,
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "name": r.name,
                "status": r.status,
                "cmr_reference": r.cmr_reference or "",
                "requesting_plant": r.requesting_plant or "",
                "requested_by": r.requested_by or "",
                "requested_on": str(r.requested_on or ""),
                "vendor_code": r.vendor_code or "",
                "sap_po_doc_num": r.sap_po_doc_num or "",
                "sap_grpo_doc_num": r.sap_grpo_doc_num or "",
            }
            for r in rows
        ],
    }


@frappe.whitelist()
def get_purchase_request(name):
    require_consumables_role()
    if not frappe.db.exists("Consumables Purchase Request", name):
        frappe.throw(_("Purchase request {0} not found.").format(name), frappe.DoesNotExistError)
    doc = frappe.get_doc("Consumables Purchase Request", name)
    roles = frappe.get_roles()
    if not any(r in roles for r in ("Consumables Procurement User", "Consumables Super Admin")):
        assert_plant_access(doc.requesting_plant)
    return _cpr_to_dict(doc)


@frappe.whitelist()
def get_split_family(name):
    """Every Purchase Request sharing the same Material Request as `name`, for
    the split-family breadcrumb on the CPR screen — so procurement can see
    what a request was split into (or from) without going back to the MR."""
    require_consumables_role()
    if not frappe.db.exists("Consumables Purchase Request", name):
        frappe.throw(_("Purchase request {0} not found.").format(name), frappe.DoesNotExistError)
    doc = frappe.get_doc("Consumables Purchase Request", name)
    _require_cpr_read_access(doc)

    if not doc.cmr_reference:
        return {"items": []}

    rows = frappe.get_all(
        "Consumables Purchase Request",
        filters={"cmr_reference": doc.cmr_reference},
        fields=["name", "status"],
        order_by="creation asc",
        ignore_permissions=True,
    )
    if len(rows) <= 1:
        return {"items": rows}
    for row in rows:
        row["item_count"] = frappe.db.count("Consumables Purchase Request Item", filters={"parent": row["name"]})
    return {"items": rows}


@frappe.whitelist()
def download_purchase_order_pdf(name):
    require_consumables_role()
    if not frappe.db.exists("Consumables Purchase Request", name):
        frappe.throw(_("Purchase request {0} not found.").format(name), frappe.DoesNotExistError)

    doc = frappe.get_doc("Consumables Purchase Request", name)
    _require_cpr_read_access(doc)

    if not (doc.sap_po_doc_entry or doc.sap_po_doc_num):
        frappe.throw(_("Purchase Order has not been raised for this request yet."), frappe.ValidationError)

    frappe.local.response.filename = _safe_po_pdf_filename(doc)
    frappe.local.response.filecontent = get_pdf(_purchase_order_pdf_html(doc))
    frappe.local.response.type = "download"


@frappe.whitelist()
def approve_warehouse_decision(name, decision, notes=""):
    """Warehouse team approves request with decision: Fulfill or Escalate to Procurement."""
    require_consumables_role()
    roles = frappe.get_roles()
    is_manager = "Consumables Store Manager" in roles
    is_admin = "Consumables Super Admin" in roles

    if not is_manager and not is_admin:
        frappe.throw(
            _("Only a Store Manager or Super Admin can approve warehouse decisions."),
            frappe.PermissionError,
        )

    if not frappe.db.exists("Consumables Purchase Request", name):
        frappe.throw(_("Purchase request {0} not found.").format(name), frappe.DoesNotExistError)

    doc = frappe.get_doc("Consumables Purchase Request", name)
    roles = frappe.get_roles()
    if not any(r in roles for r in ("Consumables Procurement User", "Consumables Super Admin")):
        assert_plant_access(doc.requesting_plant)
    if doc.status != "Awaiting Warehouse Decision":
        frappe.throw(
            _("Warehouse decision can only be approved for requests in 'Awaiting Warehouse Decision' status. Current status: {0}").format(doc.status),
            frappe.ValidationError,
        )

    if decision not in ("Fulfill from Inventory", "Escalate to Procurement"):
        frappe.throw(
            _("Invalid decision. Must be 'Fulfill from Inventory' or 'Escalate to Procurement'."),
            frappe.ValidationError,
        )

    current_user = frappe.session.user
    doc.warehouse_decision = decision
    doc.warehouse_notes = notes or ""
    doc.warehouse_approver = current_user
    doc.warehouse_approver_date = now_datetime()

    if decision == "Fulfill from Inventory":
        doc.status = "Request Fulfilled"
        doc.fulfillment_date = today()
        doc.add_comment(
            "Comment",
            text=f"Request fulfilled from inventory by {current_user}. Notes: {notes or 'N/A'}",
        )
        message = "Request has been fulfilled from available inventory"
        notify_requester(doc, message, "success")
    else:
        doc.status = "PO Pending"
        doc.add_comment(
            "Comment",
            text=f"Request escalated to procurement by {current_user}. Reason: {notes or 'Insufficient inventory'}",
        )
        message = "Request escalated to procurement for PO raising"
        notify_requester(doc, message, "info")
        notify_procurement_team(doc, f"New purchase request {name} awaiting PO")

    doc.save(ignore_permissions=True)
    frappe.publish_realtime(
        "storeops_update",
        {
            "doc_name": name,
            "new_status": doc.status,
            "message": message,
            "level": "success",
        },
        user=current_user,
    )

    return {"name": name, "status": doc.status, "message": f"Warehouse decision recorded: {decision}"}


def _parse_json_dict(val):
    if val is None or val == "":
        return {}
    if isinstance(val, dict):
        return val
    try:
        return json.loads(val)
    except Exception:
        return {}


@frappe.whitelist()
def raise_purchase_order(name, vendor_code, item_prices=None, po_options=None, line_extras=None, extra_items=None):
    _require_procurement_or_admin()

    vendor_code = (vendor_code or "").strip()
    if not vendor_code:
        frappe.throw(_("Vendor code is required to raise a Purchase Order."), frappe.ValidationError)

    item_prices = _parse_json_dict(item_prices)
    po_options = _parse_json_dict(po_options)
    line_extras = _parse_json_dict(line_extras)
    if extra_items and isinstance(extra_items, str):
        try:
            extra_items = json.loads(extra_items)
        except Exception:
            extra_items = []
    extra_items = [ei for ei in (extra_items or []) if isinstance(ei, dict)]

    if not frappe.db.exists("Consumables Purchase Request", name):
        frappe.throw(_("Purchase request {0} not found.").format(name), frappe.DoesNotExistError)

    doc = frappe.get_doc("Consumables Purchase Request", name)
    assert_plant_access(doc.requesting_plant)
    if doc.status not in ("Submitted", "Draft", "PO Pending"):
        frappe.throw(
            _(
                "Purchase Order can only be raised when status is Submitted, Draft, or PO Pending "
                "(after warehouse escalation). Current status: {0}"
            ).format(doc.status),
            frappe.ValidationError,
        )
    if doc.sap_po_doc_entry or doc.sap_po_doc_num:
        frappe.throw(
            _("Purchase Order already raised for this request. PO#: {0}").format(doc.sap_po_doc_num or doc.sap_po_doc_entry),
            frappe.ValidationError,
        )
    if not doc.line_items:
        frappe.throw(_("No items found in purchase request."), frappe.ValidationError)

    series = int(CONSUMABLES_SAP_PO_SERIES)

    requesting_plant = (doc.requesting_plant or "").strip()
    if not requesting_plant:
        frappe.throw(_("Requesting plant is required to raise a Purchase Order."), frappe.ValidationError)

    ship_to = (po_options.get("ship_to_code") or "").strip()
    bill_to = (po_options.get("bill_to_code") or po_options.get("sap_bill_to_code") or "").strip()

    auto_doc = getdate(today())
    auto_tax = getdate(today())
    auto_due = getdate(add_days(today(), 7))

    invalid_prices = []
    for li in doc.line_items:
        code = (li.item_code or "").strip()
        if not code:
            continue
        price_str = item_prices.get(code)
        if price_str is None or price_str == "":
            invalid_prices.append(f"{code} (missing)")
        else:
            try:
                price = float(price_str)
                if price <= 0:
                    invalid_prices.append(f"{code} (must be > 0)")
            except (TypeError, ValueError):
                invalid_prices.append(f"{code} (invalid number)")
    if invalid_prices:
        frappe.throw(
            _("Unit price must be a positive number for all items. Issues: {0}").format(", ".join(invalid_prices)),
            frappe.ValidationError,
        )

    missing_line = []
    for li in doc.line_items:
        code = (li.item_code or "").strip()
        if not code:
            continue
        ex = line_extras.get(code) or line_extras.get(code.upper()) or {}
        raw_sq = ex.get("sap_order_qty")
        try:
            sq = float(raw_sq) if raw_sq is not None and str(raw_sq).strip() != "" else 0.0
        except (TypeError, ValueError):
            sq = 0.0
        ordered = float(li.quantity or 0)
        if sq <= 0:
            sq = ordered
        if sq <= 0:
            missing_line.append(f"{code} (qty)")
            continue
        if sq - ordered > 0.0001:
            frappe.throw(
                _("PO quantity for {0} cannot exceed ordered quantity ({1}).").format(code, ordered),
                frappe.ValidationError,
            )
    if missing_line:
        frappe.throw(
            _("Each line must have a valid quantity. Missing or invalid: {0}").format(
                ", ".join(missing_line)
            ),
            frappe.ValidationError,
        )

    triggered_by = frappe.session.user
    doc.vendor_code = vendor_code
    doc.sap_po_series = series
    doc.sap_document_date = auto_doc
    doc.sap_delivery_date = auto_due
    doc.sap_tax_date = auto_tax
    doc.sap_ship_to_code = ship_to
    doc.sap_bill_to_code = bill_to
    doc.sap_last_error = ""
    receiving_plant = (po_options.get("receiving_plant") or "").strip()
    if receiving_plant and receiving_plant != (doc.requesting_plant or "").strip():
        doc.receiving_plant = receiving_plant
    else:
        doc.receiving_plant = ""

    for li in doc.line_items:
        code = (li.item_code or "").strip()
        if not code:
            continue
        ex = line_extras.get(code) or line_extras.get(code.upper()) or {}
        li.item_purpose = (ex.get("item_purpose") or ex.get("purpose") or "").strip()
        li.tax_code = (ex.get("tax_code") or "").strip()
        li.warehouse_code = (ex.get("warehouse_code") or "").strip()
        raw_sq = ex.get("sap_order_qty")
        try:
            sq = float(raw_sq) if raw_sq is not None and str(raw_sq).strip() != "" else 0.0
        except (TypeError, ValueError):
            sq = 0.0
        ordered = float(li.quantity or 0)
        li.sap_order_qty = sq if sq > 0 else ordered
        try:
            li.po_unit_price = float(item_prices.get(code))
        except (TypeError, ValueError):
            frappe.throw(_("Invalid unit price for item {0}.").format(code), frappe.ValidationError)

    # Validate and append procurement-added extra items
    for idx, ei in enumerate(extra_items, start=1):
        code = str(ei.get("item_code") or "").strip()
        if not code:
            frappe.throw(_("Extra item {0}: item code is required.").format(idx), frappe.ValidationError)
        qty = flt(ei.get("quantity") or 0)
        if qty <= 0:
            frappe.throw(_("Extra item {0} ({1}): quantity must be greater than 0.").format(idx, code), frappe.ValidationError)
        unit_price = flt(ei.get("unit_price") or 0)
        if unit_price <= 0:
            frappe.throw(_("Extra item {0} ({1}): unit price must be greater than 0.").format(idx, code), frappe.ValidationError)
        doc.append("line_items", {
            "item_code": code,
            "item_name": str(ei.get("item_name") or code),
            "quantity": qty,
            "sap_order_qty": qty,
            "uom": str(ei.get("uom") or ""),
            "po_unit_price": unit_price,
            "quantity_received": 0,
            "fulfillment_status": "Pending",
            "is_extra_item": 1,
        })

    doc.status = "Draft"
    doc.add_comment("Comment", text=f"PO details submitted by {triggered_by}. Awaiting Super Admin approval.")
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    frappe.enqueue(
        _post_draft_to_sap, queue="short", doc_name=name,
    )
    _notify_super_admins_po_approval(doc, triggered_by)
    frappe.publish_realtime(
        "storeops_update",
        {"doc_name": name, "new_status": "Draft", "message": "PO details saved. Awaiting Super Admin approval.", "level": "info"},
        user=triggered_by,
    )
    return {"name": name, "message": "PO submitted for Super Admin approval."}


@frappe.whitelist()
def split_purchase_request(name, row_names):
    """Split selected line items off a Purchase Request into a new sibling CPR.

    Used when procurement can't source every item from one vendor — the split-off
    items become an independent CPR (same cmr_reference) that goes through the
    normal single-vendor raise_purchase_order/GRN/transfer flow on its own, so SAP
    (which only allows one CardCode per PO document) still gets one PO per vendor.
    """
    _require_procurement_or_admin()

    if isinstance(row_names, str):
        row_names = json.loads(row_names)
    row_names = [str(r).strip() for r in (row_names or []) if str(r or "").strip()]
    if not row_names:
        frappe.throw(_("Select at least one item to split out."), frappe.ValidationError)

    if not frappe.db.exists("Consumables Purchase Request", name):
        frappe.throw(_("Purchase request {0} not found.").format(name), frappe.DoesNotExistError)

    doc = frappe.get_doc("Consumables Purchase Request", name)
    assert_plant_access(doc.requesting_plant)
    if doc.status not in ("Submitted", "Draft", "PO Pending"):
        frappe.throw(
            _(
                "Items can only be split out before a PO is raised (status Submitted, Draft, "
                "or PO Pending). Current status: {0}"
            ).format(doc.status),
            frappe.ValidationError,
        )
    if not doc.line_items:
        frappe.throw(_("No items found in purchase request."), frappe.ValidationError)

    row_set = set(row_names)
    move_rows = [li for li in doc.line_items if li.name in row_set]
    keep_rows = [li for li in doc.line_items if li.name not in row_set]

    if not move_rows:
        frappe.throw(_("None of the selected items were found on this purchase request."), frappe.ValidationError)
    if not keep_rows:
        frappe.throw(
            _("Cannot split out every item — at least one item must remain on the original request."),
            frappe.ValidationError,
        )

    triggered_by = frappe.session.user

    new_cpr = frappe.new_doc("Consumables Purchase Request")
    new_cpr.naming_series = "CPR-.YYYY.-.#####"
    new_cpr.cmr_reference = doc.cmr_reference
    new_cpr.split_from = doc.name
    new_cpr.requesting_plant = doc.requesting_plant
    new_cpr.receiving_plant = doc.receiving_plant
    new_cpr.status = doc.status
    new_cpr.requested_by = doc.requested_by
    new_cpr.requested_on = doc.requested_on or now_datetime()
    new_cpr.remarks = doc.remarks
    for li in move_rows:
        new_cpr.append("line_items", {
            "item_code": li.item_code,
            "item_name": li.item_name,
            "item_purpose": li.item_purpose,
            "quantity": li.quantity,
            "uom": li.uom,
            "warehouse_code": li.warehouse_code,
            "is_extra_item": li.is_extra_item,
        })
    new_cpr.insert(ignore_permissions=True)
    new_cpr.add_comment("Comment", text=f"Split from {doc.name} by {triggered_by} ({len(move_rows)} item(s)).")

    for li in list(move_rows):
        doc.remove(li)
    doc.add_comment(
        "Comment",
        text=f"{len(move_rows)} item(s) split into {new_cpr.name} by {triggered_by}.",
    )
    doc.save(ignore_permissions=True)

    # Keep the CMR's purchase_links in sync so fulfillment rollup counts the new CPR too.
    if doc.cmr_reference and frappe.db.exists("Consumables Material Request", doc.cmr_reference):
        cmr = frappe.get_doc("Consumables Material Request", doc.cmr_reference)
        if hasattr(cmr, "purchase_links"):
            cmr.append("purchase_links", {
                "purchase_request": new_cpr.name,
                "quantity": sum(float(li.quantity or 0) for li in move_rows),
                "status": new_cpr.status,
            })
            cmr.save(ignore_permissions=True)

    frappe.db.commit()

    notify_procurement_team(new_cpr, f"{new_cpr.name} split from {doc.name} ({len(move_rows)} item(s)).")
    notify_requester(doc, f"{len(move_rows)} item(s) moved to new request {new_cpr.name}.", level="info")

    return {"original": _cpr_to_dict(doc), "new": _cpr_to_dict(new_cpr)}


_PRE_RAISE_STATUSES = ("Submitted", "Draft", "PO Pending")


@frappe.whitelist()
def remove_split_item(name, row_names):
    """Send mistakenly-split items back to the Purchase Request they were split
    from. Fixed direction, no picker — always the immediate parent recorded in
    split_from at the time this CPR was created. If that leaves this (split)
    request with no items, it's deleted outright: Consumables Purchase Request
    .line_items is a mandatory table, so a doc can never be saved with zero
    rows regardless of status.
    """
    _require_procurement_or_admin()

    if isinstance(row_names, str):
        row_names = json.loads(row_names)
    row_names = [str(r).strip() for r in (row_names or []) if str(r or "").strip()]
    if not row_names:
        frappe.throw(_("Select at least one item to remove."), frappe.ValidationError)

    if not frappe.db.exists("Consumables Purchase Request", name):
        frappe.throw(_("Purchase request {0} not found.").format(name), frappe.DoesNotExistError)

    source = frappe.get_doc("Consumables Purchase Request", name)
    source_name = source.name
    assert_plant_access(source.requesting_plant)

    target_name = (source.split_from or "").strip()
    if not target_name:
        frappe.throw(
            _("{0} wasn't created by a split — there's no original request to send items back to.").format(name),
            frappe.ValidationError,
        )
    if not frappe.db.exists("Consumables Purchase Request", target_name):
        frappe.throw(
            _("The original request {0} this was split from no longer exists.").format(target_name),
            frappe.ValidationError,
        )

    target = frappe.get_doc("Consumables Purchase Request", target_name)
    assert_plant_access(target.requesting_plant)

    for doc in (source, target):
        if doc.status not in _PRE_RAISE_STATUSES:
            frappe.throw(
                _(
                    "{0} can only be changed before a PO is raised (status Submitted, Draft, "
                    "or PO Pending). Current status: {1}"
                ).format(doc.name, doc.status),
                frappe.ValidationError,
            )

    row_set = set(row_names)
    move_rows = [li for li in source.line_items if li.name in row_set]
    if not move_rows:
        frappe.throw(_("None of the selected items were found on {0}.").format(source_name), frappe.ValidationError)

    triggered_by = frappe.session.user
    moved_qty = sum(float(li.quantity or 0) for li in move_rows)
    cmr_reference = source.cmr_reference

    for li in move_rows:
        target.append("line_items", {
            "item_code": li.item_code,
            "item_name": li.item_name,
            "item_purpose": li.item_purpose,
            "quantity": li.quantity,
            "uom": li.uom,
            "warehouse_code": li.warehouse_code,
            "is_extra_item": li.is_extra_item,
        })
    target.add_comment("Comment", text=f"{len(move_rows)} item(s) moved in from {source.name} by {triggered_by}.")
    target.save(ignore_permissions=True)

    for li in list(move_rows):
        source.remove(li)

    source_deleted = not source.line_items
    if source_deleted:
        source_name_for_notify = source.name
        source_requested_by = source.requested_by
        source.add_comment(
            "Comment",
            text=f"All items moved to {target.name} by {triggered_by} — request deleted (mistaken split).",
        )
        frappe.delete_doc("Consumables Purchase Request", source.name, ignore_permissions=True)
    else:
        source.add_comment(
            "Comment",
            text=f"{len(move_rows)} item(s) moved out to {target.name} by {triggered_by}.",
        )
        source.save(ignore_permissions=True)

    # Keep the CMR's purchase_links in sync with the move — remove the source's
    # link entirely if it was deleted, otherwise just adjust its quantity.
    if cmr_reference and frappe.db.exists("Consumables Material Request", cmr_reference):
        cmr = frappe.get_doc("Consumables Material Request", cmr_reference)
        if hasattr(cmr, "purchase_links"):
            if source_deleted:
                cmr.purchase_links = [
                    row for row in cmr.purchase_links if row.purchase_request != source_name_for_notify
                ]
            for row in cmr.purchase_links:
                if not source_deleted and row.purchase_request == source.name:
                    row.quantity = max(0.0, float(row.quantity or 0) - moved_qty)
                    row.status = source.status
                elif row.purchase_request == target.name:
                    row.quantity = float(row.quantity or 0) + moved_qty
                    row.status = target.status
            cmr.save(ignore_permissions=True)

    frappe.db.commit()

    notify_procurement_team(
        target,
        f"{len(move_rows)} item(s) moved into {target.name} from {source_name if source_deleted else source.name}.",
    )
    if source_deleted:
        if source_requested_by:
            frappe.publish_realtime(
                "storeops_update",
                {
                    "doc_type": "Consumables Purchase Request",
                    "doc_name": source_name_for_notify,
                    "new_status": "Deleted",
                    "message": f"{source_name_for_notify} was deleted — all items moved to {target.name}.",
                    "level": "info",
                },
                user=source_requested_by,
            )
    else:
        notify_requester(source, f"{len(move_rows)} item(s) moved to {target.name}.", level="info")

    return {
        "source": None if source_deleted else _cpr_to_dict(source),
        "source_deleted": source_deleted,
        "target": _cpr_to_dict(target),
    }


@frappe.whitelist()
def approve_purchase_order(name):
    if "Consumables Super Admin" not in frappe.get_roles():
        frappe.throw(_("Only a Super Admin can approve Purchase Orders."), frappe.PermissionError)
    if not frappe.db.exists("Consumables Purchase Request", name):
        frappe.throw(_("Purchase request {0} not found.").format(name), frappe.DoesNotExistError)
    doc = frappe.get_doc("Consumables Purchase Request", name)
    if doc.status != "Draft":
        frappe.throw(
            _("PO can only be approved when status is 'Draft'. Current: {0}").format(doc.status),
            frappe.ValidationError,
        )
    doc.status = "PO Posting"
    doc.add_comment("Comment", text=f"PO approved by {frappe.session.user}")
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    _post_purchase_order_to_sap(name, triggered_by=frappe.session.user, original_status="Draft")
    return {"name": name, "message": "PO approved and posting to SAP."}


@frappe.whitelist()
def reject_purchase_order(name):
    if "Consumables Super Admin" not in frappe.get_roles():
        frappe.throw(_("Only a Super Admin can reject Purchase Orders."), frappe.PermissionError)
    if not frappe.db.exists("Consumables Purchase Request", name):
        frappe.throw(_("Purchase request {0} not found.").format(name), frappe.DoesNotExistError)
    doc = frappe.get_doc("Consumables Purchase Request", name)
    if doc.status != "Draft":
        frappe.throw(
            _("PO can only be rejected when status is 'Draft'. Current: {0}").format(doc.status),
            frappe.ValidationError,
        )
    doc.status = "PO Pending"
    doc.add_comment("Comment", text=f"PO rejected by {frappe.session.user}. Returned to procurement for revision.")
    doc.save(ignore_permissions=True)
    # Clear the SAP draft (best-effort)
    draft_entry = (frappe.db.get_value("Consumables Purchase Request", name, "sap_draft_doc_entry") or "").strip()
    if draft_entry:
        try:
            from khanal_tech_integrations.unicommerce.client.sap import SAPClient
            SAPClient(settings_doctype="Consumables SAP Settings").delete(f"Drafts({draft_entry})")
        except Exception:
            pass
        frappe.db.set_value("Consumables Purchase Request", name, "sap_draft_doc_entry", "")
    frappe.db.commit()
    for user in _enabled_users_with_role("Consumables Procurement User"):
        frappe.publish_realtime(
            "storeops_update",
            {
                "doc_type": "Consumables Purchase Request",
                "doc_name": name,
                "new_status": "PO Pending",
                "message": f"PO for CPR {name} was rejected by Super Admin. Please revise and resubmit.",
                "level": "error",
                "notify_user": True,
            },
            user=user,
        )
    return {"name": name, "message": "PO rejected and returned to procurement."}


def _notify_super_admins_po_approval(doc, triggered_by):
    for user in _enabled_users_with_role("Consumables Super Admin"):
        frappe.publish_realtime(
            "storeops_update",
            {
                "doc_type": "Consumables Purchase Request",
                "doc_name": doc.name,
                "new_status": "Draft",
                "message": f"CPR {doc.name} is awaiting PO approval. Submitted by {triggered_by}.",
                "level": "info",
                "notify_user": True,
            },
            user=user,
        )


def _post_draft_to_sap(doc_name):
    """Create a Purchase Order Draft in SAP B1. Best-effort — logged but non-blocking."""
    from khanal_tech_integrations.unicommerce.client.sap import SAPClient
    from khanal_tech_integrations.consumables.hana.client import ConsumablesHANAClient
    from khanal_tech_integrations.consumables.hana.inventory_queries import get_item_uom_entries, get_item_distribution_rules
    doc = frappe.get_doc("Consumables Purchase Request", doc_name)
    try:
        client = SAPClient(settings_doctype="Consumables SAP Settings")
        item_codes = list({li.item_code for li in doc.line_items if getattr(li, "item_code", None)})
        with ConsumablesHANAClient() as hana:
            uom_entries = get_item_uom_entries(hana, item_codes)
            dist_rules = get_item_distribution_rules(hana, item_codes)
        # Delete stale draft from a previous submission before creating a fresh one
        old_draft = (frappe.db.get_value("Consumables Purchase Request", doc_name, "sap_draft_doc_entry") or "").strip()
        if old_draft:
            try:
                client.delete(f"Drafts({old_draft})")
            except Exception:
                pass
            frappe.db.set_value("Consumables Purchase Request", doc_name, "sap_draft_doc_entry", "")
            frappe.db.commit()
        lines = []
        for li in doc.line_items:
            code = (li.item_code or "").strip()
            if not code:
                continue
            wh = (getattr(li, "warehouse_code", None) or "").strip()
            if not wh:
                plant_for_wh = (getattr(doc, "receiving_plant", None) or doc.requesting_plant or "").strip()
                if plant_for_wh:
                    wh_rows = frappe.db.get_all(
                        "Consumables Plant Warehouse",
                        filters={"parent": plant_for_wh, "is_active": 1},
                        fields=["warehouse_code"],
                        order_by="idx asc",
                        limit=1,
                    )
                    if wh_rows:
                        wh = (wh_rows[0].warehouse_code or "").strip()
            line_qty = float(getattr(li, "sap_order_qty", None) or 0) or float(li.quantity or 0)
            line = {
                "ItemCode": code,
                "Quantity": line_qty,
                "WarehouseCode": wh,
                "UnitPrice": float(li.po_unit_price or 0),
                "TaxCode": (getattr(li, "tax_code", None) or ""),
            }
            uom_entry = uom_entries.get(code)
            if uom_entry is not None:
                line["UoMEntry"] = uom_entry
            ocr4 = WAREHOUSE_DISTRIBUTION_RULE.get(wh)
            if ocr4:
                line["CostingCode4"] = ocr4
            rule = dist_rules.get(code) or {}
            if rule.get("brand_category"):
                line["CostingCode"] = rule["brand_category"]
            if rule.get("brand_name"):
                line["CostingCode2"] = rule["brand_name"]
            if rule.get("product_type"):
                line["CostingCode3"] = rule["product_type"]
            purpose = (getattr(li, "item_purpose", None) or "").strip()
            if purpose:
                line["FreeText"] = purpose[:254]
            lines.append(line)
        payload = {
            "DocObjectCode": "22",
            "Series": int(doc.sap_po_series or 0),
            "CardCode": (doc.vendor_code or "").strip(),
            "DocDate": str(doc.sap_document_date),
            "DocDueDate": str(doc.sap_delivery_date),
            "TaxDate": str(doc.sap_tax_date),
            "Comments": f"StoreOps DRAFT: {doc_name} (CMR: {doc.cmr_reference or ''})",
            "DocumentLines": lines,
        }
        bill_to = (getattr(doc, "sap_bill_to_code", None) or "").strip()
        if bill_to:
            payload["PayToCode"] = bill_to
        result = client.post("Drafts", payload)
        draft_entry = str(result.get("DocEntry", "")).strip()
        if draft_entry:
            frappe.db.set_value("Consumables Purchase Request", doc_name, "sap_draft_doc_entry", draft_entry)
            frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"StoreOps CPR SAP Draft creation failed: {doc_name}")


def _post_purchase_order_to_sap(doc_name, triggered_by=None, original_status=None):
    from khanal_tech_integrations.unicommerce.client.sap import SAPClient
    from khanal_tech_integrations.consumables.hana.client import ConsumablesHANAClient
    from khanal_tech_integrations.consumables.hana.inventory_queries import get_item_uom_entries, get_item_distribution_rules

    notify_user = triggered_by or frappe.session.user

    doc = frappe.get_doc("Consumables Purchase Request", doc_name)
    try:
        client = SAPClient(settings_doctype="Consumables SAP Settings")
        item_codes = list({li.item_code for li in doc.line_items if getattr(li, "item_code", None)})
        with ConsumablesHANAClient() as hana:
            uom_entries = get_item_uom_entries(hana, item_codes)
            dist_rules = get_item_distribution_rules(hana, item_codes)
        vendor_code = (doc.vendor_code or "").strip()
        if not vendor_code:
            raise ValueError("Vendor code is missing on purchase request.")

        if not getattr(doc, "sap_po_series", None) or int(doc.sap_po_series) <= 0:
            raise ValueError("SAP PO Series No. is missing or invalid on purchase request.")
        if not doc.sap_document_date or not doc.sap_delivery_date or not doc.sap_tax_date:
            raise ValueError("SAP document, delivery, or tax date is missing on purchase request.")
        # ShipToCode must reference CRD1 (BP addresses for the purchasing company), NOT OWHS warehouse codes.
        # Until the company's SAP CardCode is configured for CRD1 lookup, we omit ShipToCode from the
        # payload and let SAP use its default ship-to address, avoiding -2028 "No matching record" errors.
        bill_to = (getattr(doc, "sap_bill_to_code", None) or "").strip()

        lines = []
        for li in doc.line_items:
            code = (li.item_code or "").strip()
            if not code:
                continue
            wh = (getattr(li, "warehouse_code", None) or "").strip()
            if not wh:
                plant_for_wh = (getattr(doc, "receiving_plant", None) or doc.requesting_plant or "").strip()
                if plant_for_wh:
                    wh_rows = frappe.db.get_all(
                        "Consumables Plant Warehouse",
                        filters={"parent": plant_for_wh, "is_active": 1},
                        fields=["warehouse_code"],
                        order_by="idx asc",
                        limit=1,
                    )
                    if wh_rows:
                        wh = (wh_rows[0].warehouse_code or "").strip()
            if not wh:
                raise ValueError(f"Warehouse code is missing for line item {code}.")
            unit_price = float(li.po_unit_price or 0)
            if unit_price <= 0:
                raise ValueError(f"Unit price is missing or invalid for line item {code}.")
            tax_c = (getattr(li, "tax_code", None) or "").strip()
            if not tax_c:
                raise ValueError(f"Tax code is missing for line item {code}.")

            line_qty = float(getattr(li, "sap_order_qty", None) or 0)
            if line_qty <= 0:
                line_qty = float(li.quantity or 0)
            if line_qty <= 0:
                raise ValueError(f"Quantity is missing for line item {code}.")

            line = {
                "ItemCode": code,
                "Quantity": line_qty,
                "WarehouseCode": wh,
                "UnitPrice": unit_price,
                "TaxCode": tax_c,
            }
            uom_entry = uom_entries.get(code)
            if uom_entry is not None:
                line["UoMEntry"] = uom_entry
            ocr4 = WAREHOUSE_DISTRIBUTION_RULE.get(wh)
            if ocr4:
                line["CostingCode4"] = ocr4
            rule = dist_rules.get(code) or {}
            if rule.get("brand_category"):
                line["CostingCode"] = rule["brand_category"]
            if rule.get("brand_name"):
                line["CostingCode2"] = rule["brand_name"]
            if rule.get("product_type"):
                line["CostingCode3"] = rule["product_type"]
            purpose = (getattr(li, "item_purpose", None) or "").strip()
            if purpose:
                line["FreeText"] = purpose[:254]
            lines.append(line)

        if not lines:
            raise ValueError("No valid line items for SAP Purchase Order.")

        payload = {
            "Series": int(doc.sap_po_series),
            "CardCode": vendor_code,
            "DocDate": str(doc.sap_document_date),
            "DocDueDate": str(doc.sap_delivery_date),
            "TaxDate": str(doc.sap_tax_date),
            "Comments": f"StoreOps: {doc_name} (CMR: {doc.cmr_reference or ''})",
            "DocumentLines": lines,
        }
        # PayToCode comes from the vendor's CRD1 address — include only if present.
        # ShipToCode is intentionally omitted: the UI shows warehouse codes (OWHS) which are not
        # valid CRD1 BP address codes; sending them causes SAP -2028 "No matching record" errors.
        if bill_to:
            payload["PayToCode"] = bill_to
        result = client.post("PurchaseOrders", payload)
        doc.db_set("sap_po_doc_entry", str(result.get("DocEntry", "")))
        doc.db_set("sap_po_doc_num", str(result.get("DocNum", "")))
        doc.db_set("status", "PO Raised")
        doc.db_set("sap_last_error", "")
        # Delete the SAP draft now that the real PO exists (best-effort)
        draft_entry = (frappe.db.get_value("Consumables Purchase Request", doc_name, "sap_draft_doc_entry") or "").strip()
        if draft_entry:
            try:
                client.delete(f"Drafts({draft_entry})")
                doc.db_set("sap_draft_doc_entry", "")
            except Exception:
                pass
        doc.add_comment(
            "Comment",
            text=f"PO posted to SAP. DocNum: {result.get('DocNum')} DocEntry: {result.get('DocEntry')}",
        )
        frappe.db.commit()  # commit before notify so frontend reads the updated status
        frappe.publish_realtime(
            "storeops_update",
            {
                "doc_name": doc_name,
                "new_status": "PO Raised",
                "message": f"Purchase Order posted to SAP. PO#{result.get('DocNum')}",
                "level": "success",
            },
            user=notify_user,
        )
        _notify_plant_users_po_raised(doc)
        notify_procurement_team(
            doc,
            f"Purchase Order raised in SAP for CPR {doc.name}. PO#: {doc.sap_po_doc_num}",
        )
    except Exception as e:
        restore_status = original_status or "Submitted"
        doc.db_set("status", restore_status)
        doc.db_set("sap_last_error", str(e)[:1000])
        doc.add_comment("Comment", text=f"SAP PO posting failed: {e}")
        frappe.log_error(frappe.get_traceback(), f"StoreOps CPR SAP PO Error: {doc_name}")
        frappe.db.commit()  # commit before notify so frontend reads the restored status + error
        frappe.publish_realtime(
            "storeops_update",
            {
                "doc_name": doc_name,
                "new_status": restore_status,
                "message": f"SAP PO posting failed: {str(e)[:200]}",
                "level": "error",
            },
            user=notify_user,
        )


@frappe.whitelist()
def submit_grn(name, grn_items):
    require_consumables_role()
    if isinstance(grn_items, str):
        try:
            grn_items = json.loads(grn_items)
        except (json.JSONDecodeError, ValueError):
            frappe.throw(_("Invalid GRN items format — expected a JSON array."), frappe.ValidationError)

    if not frappe.db.exists("Consumables Purchase Request", name):
        frappe.throw(_("Purchase request {0} not found.").format(name), frappe.DoesNotExistError)

    doc = frappe.get_doc("Consumables Purchase Request", name)

    # Only the Store Manager of the GRN plant (or Super Admin) can submit GRN.
    # Procurement Users are explicitly blocked even if they also hold the Store Manager role.
    # For inter-plant CPRs the GRN plant is receiving_plant; otherwise requesting_plant.
    roles = frappe.get_roles()
    if "Consumables Super Admin" not in roles:
        if "Consumables Procurement User" in roles:
            frappe.throw(
                _("Procurement Users cannot submit a GRN. Only the plant Store Manager can."),
                frappe.PermissionError,
            )
        if "Consumables Store Manager" not in roles and "Consumables Inventory Manager" not in roles:
            frappe.throw(
                _("Only the Store Manager, Inventory Manager, or Super Admin can submit a GRN."),
                frappe.PermissionError,
            )
        grn_plant = (getattr(doc, "receiving_plant", None) or doc.requesting_plant or "").strip()
        if grn_plant and not frappe.db.exists(
            "Consumables User Plant",
            {"user": frappe.session.user, "plant": grn_plant, "is_active": 1},
        ):
            frappe.throw(
                _("You are not assigned to plant {0}. Only that plant's Store Manager can submit this GRN.").format(grn_plant),
                frappe.PermissionError,
            )
    # Allow GRN for PO Raised and Partial GRN (second receipt for remaining items)
    if doc.status not in ("PO Raised", "GRN Done"):
        frappe.throw(
            _("GRN can only be submitted after PO is raised. Current status: {0}").format(doc.status),
            frappe.ValidationError,
        )
    if not doc.sap_po_doc_entry:
        frappe.throw(_("SAP PO Doc Entry not found. Cannot submit GRN."), frappe.ValidationError)
    if not grn_items:
        frappe.throw(_("No items provided for GRN."), frappe.ValidationError)
    for item in grn_items:
        qty = float(item.get("quantity_received") or 0)
        if qty <= 0:
            continue
        if not str(item.get("batch_number") or "").strip():
            frappe.throw(
                _("Batch number is mandatory for item {0}.").format(item.get("item_code") or "?"),
                frappe.ValidationError,
            )

    lock_key = f"grn_in_progress_{name}"
    if frappe.cache().get_value(lock_key):
        frappe.throw(
            _("A GRN is already being processed for this request. Please wait until it completes."),
            frappe.ValidationError,
        )
    frappe.cache().set_value(lock_key, 1, expires_in_sec=300)

    triggered_by = frappe.session.user
    doc.add_comment("Comment", text=f"GRN submitted by {triggered_by}")
    frappe.db.commit()

    _post_grpo_to_sap(name, grn_items=grn_items, triggered_by=triggered_by)
    return {"name": name, "message": "GRN posted."}



def _get_sap_po_status(po_doc_entry):
    """Query SAP HANA for PO document status. Returns 'O' (Open) or 'C' (Closed)."""
    from khanal_tech_integrations.consumables.hana.client import ConsumablesHANAClient
    try:
        with ConsumablesHANAClient() as client:
            rows = client.execute(
                f'SELECT "DocStatus" FROM {client.schema}."OPOR" WHERE "DocEntry" = ?',
                [int(po_doc_entry)]
            )
        if rows:
            return (rows[0].get("DocStatus") or "O").strip().upper()
    except Exception as e:
        frappe.log_error(str(e), "StoreOps _get_sap_po_status")
    return "O"


def _post_grpo_to_sap(doc_name, grn_items, triggered_by=None):
    from khanal_tech_integrations.unicommerce.client.sap import SAPClient
    from khanal_tech_integrations.consumables.hana.client import ConsumablesHANAClient
    from khanal_tech_integrations.consumables.hana.inventory_queries import get_item_uom_entries, get_item_distribution_rules

    notify_user = triggered_by or frappe.session.user
    doc = frappe.get_doc("Consumables Purchase Request", doc_name)
    try:
        item_codes = list({li.item_code for li in doc.line_items if getattr(li, "item_code", None)})
        with ConsumablesHANAClient() as hana:
            uom_entries = get_item_uom_entries(hana, item_codes)
            dist_rules = get_item_distribution_rules(hana, item_codes)
        po_doc_entry = int(doc.sap_po_doc_entry)
        po_line_index = {
            li.name: idx
            for idx, li in enumerate(doc.line_items)
            if li.item_code
        }
        code_counts = {}
        po_line_index_by_code = {}
        for idx, li in enumerate(doc.line_items):
            code = (li.item_code or "").strip()
            if not code:
                continue
            code_key = code.upper()
            code_counts[code_key] = code_counts.get(code_key, 0) + 1
            po_line_index_by_code[code_key] = idx
        lines = []
        for idx, item in enumerate(grn_items):
            qty = float(item.get("quantity_received") or 0)
            if qty <= 0:
                continue
            batch_number = str(item.get("batch_number") or "").strip()
            if not batch_number:
                raise ValueError(f"Batch number is mandatory for item {item.get('item_code') or '?'}")
            row_name = item.get("row_name") or ""
            item_code = item.get("item_code") or ""
            base_line = po_line_index.get(row_name)
            if base_line is None and item_code:
                code_key = item_code.strip().upper()
                if code_counts.get(code_key) == 1:
                    base_line = po_line_index_by_code.get(code_key)
            if base_line is None:
                raise ValueError(f"Item {item_code} is not in the Purchase Order and cannot be received.")
            li_for_check = doc.line_items[base_line]
            already_received = float(li_for_check.quantity_received or 0)
            ordered_qty = float(getattr(li_for_check, "sap_order_qty", None) or li_for_check.quantity or 0)
            if (already_received + qty) > ordered_qty:
                raise ValueError(
                    f"Over-receipt for {item_code}: ordered {ordered_qty}, "
                    f"already received {already_received}, trying to receive {qty}."
                )
            # Resolve warehouse explicitly — do NOT rely on SAP inheriting from PO line,
            # because the PO line warehouse may have been wrong or left blank.
            # Priority: line-level warehouse_code → receiving_plant's warehouse → requesting_plant's warehouse.
            grn_wh = (getattr(li_for_check, "warehouse_code", None) or "").strip()
            if not grn_wh:
                grn_plant = (getattr(doc, "receiving_plant", None) or doc.requesting_plant or "").strip()
                if grn_plant:
                    wh_rows = frappe.db.get_all(
                        "Consumables Plant Warehouse",
                        filters={"parent": grn_plant, "is_active": 1},
                        fields=["warehouse_code"],
                        order_by="idx asc",
                        limit=1,
                    )
                    if wh_rows:
                        grn_wh = (wh_rows[0].warehouse_code or "").strip()
            if not grn_wh:
                raise ValueError(f"Could not resolve GRN warehouse for item {item_code}.")
            # Store resolved warehouse back on the line so _create_post_grn_transfer uses it.
            li_for_check.warehouse_code = grn_wh
            grn_line = {
                "ItemCode": item_code,
                "Quantity": qty,
                "BaseEntry": po_doc_entry,
                "BaseType": 22,
                "BaseLine": base_line,
                "WarehouseCode": grn_wh,
                "BatchNumbers": [{"BatchNumber": batch_number, "Quantity": qty}],
            }
            uom_entry = uom_entries.get(item_code)
            if uom_entry is not None:
                grn_line["UoMEntry"] = uom_entry
            ocr4 = WAREHOUSE_DISTRIBUTION_RULE.get(grn_wh)
            if ocr4:
                grn_line["CostingCode4"] = ocr4
            rule = dist_rules.get(item_code) or {}
            if rule.get("brand_category"):
                grn_line["CostingCode"] = rule["brand_category"]
            if rule.get("brand_name"):
                grn_line["CostingCode2"] = rule["brand_name"]
            if rule.get("product_type"):
                grn_line["CostingCode3"] = rule["product_type"]
            lines.append(grn_line)
        if not lines:
            doc.add_comment("Comment", text="GRN skipped — no valid quantities to receive.")
            return

        client = SAPClient(settings_doctype="Consumables SAP Settings")
        payload = {
            "CardCode": doc.vendor_code,
            "DocDate": today(),
            "TaxDate": today(),
            "Comments": f"StoreOps GRN: {doc_name}",
            "DocumentLines": lines,
        }
        # Build a warehouse map keyed by base_line index BEFORE posting,
        # so we can re-apply after doc.reload() wipes in-memory changes.
        grn_wh_by_base_line = {
            grn_line["BaseLine"]: grn_line["WarehouseCode"]
            for grn_line in lines
            if grn_line.get("WarehouseCode")
        }

        try:
            result = client.post("PurchaseDeliveryNotes", payload)
        except Exception as e:
            raise type(e)(f"{e}\n\nGRN Payload sent: {frappe.as_json(payload)}") from e
        doc.reload()
        doc.sap_grpo_doc_entry = str(result.get("DocEntry", ""))
        doc.sap_grpo_doc_num = str(result.get("DocNum", ""))
        doc.sap_last_error = ""

        item_received_map = {i.get("row_name") or i.get("item_code"): float(i.get("quantity_received") or 0) for i in grn_items}
        for idx, li in enumerate(doc.line_items):
            new_qty = item_received_map.get(li.name, item_received_map.get(li.item_code, 0))
            # Accumulate across multiple GRNs; doc was reloaded so quantity_received reflects prior GRNs
            li.quantity_received = float(li.quantity_received or 0) + new_qty
            if li.quantity_received >= float(li.quantity or 0):
                li.fulfillment_status = "Received"
            elif li.quantity_received > 0:
                li.fulfillment_status = "Partial"
            # Re-apply resolved warehouse so _create_post_grn_transfer uses the right source
            resolved_wh = grn_wh_by_base_line.get(idx)
            if resolved_wh:
                li.warehouse_code = resolved_wh

        # Determine if an inter-plant transfer is needed after GRN
        receiving_plant = (getattr(doc, "receiving_plant", None) or "").strip()
        requesting_plant = (doc.requesting_plant or "").strip()
        needs_transfer = bool(receiving_plant and requesting_plant and receiving_plant != requesting_plant)

        # Determine partial vs full GRN by checking whether all lines are fully received.
        is_partial_grn = any(
            float(li.quantity_received or 0) < float(getattr(li, "sap_order_qty", None) or li.quantity or 0)
            for li in doc.line_items if li.item_code
        )

        if is_partial_grn:
            # SAP PO still open — keep CPR as PO Raised so another GRN can be done for remaining items
            doc.status = "PO Raised"
        else:
            doc.status = "Transfer Pending" if needs_transfer else "GRN Done"

        doc.save(ignore_permissions=True)
        doc.add_comment(
            "Comment",
            text=(
                f"GRPO posted to SAP. DocNum: {result.get('DocNum')} DocEntry: {result.get('DocEntry')}"
                + (" (Partial GRN — SAP PO still open)" if is_partial_grn else "")
            ),
        )

        ctr_name = None
        if needs_transfer:
            ctr_name = _create_post_grn_transfer(doc, triggered_by=notify_user, current_grn_map=item_received_map)

        frappe.db.commit()  # commit before notify so frontend reads the updated status

        if is_partial_grn:
            frappe.publish_realtime(
                "storeops_update",
                {
                    "doc_name": doc_name,
                    "new_status": "PO Raised",
                    "message": (
                        f"Partial GRN done (GRPO#{result.get('DocNum')}). "
                        f"SAP PO is still open — remaining items can be received."
                        + (f" Transfer {ctr_name} created for received items." if ctr_name else "")
                    ),
                    "level": "info",
                },
                user=notify_user,
            )
        elif needs_transfer:
            frappe.publish_realtime(
                "storeops_update",
                {
                    "doc_name": doc_name,
                    "new_status": "Transfer Pending",
                    "message": (
                        f"GRN done (GRPO#{result.get('DocNum')}). "
                        f"Inventory transfer {ctr_name or ''} created from {receiving_plant} → {requesting_plant}. "
                        f"Awaiting dispatch from {receiving_plant}."
                    ),
                    "level": "info",
                },
                user=notify_user,
            )
        else:
            frappe.publish_realtime(
                "storeops_update",
                {
                    "doc_name": doc_name,
                    "new_status": "GRN Done",
                    "message": f"GRN posted to SAP. GRPO#{result.get('DocNum')}",
                    "level": "success",
                },
                user=notify_user,
            )

        if not needs_transfer and not is_partial_grn:
            _notify_cmr_grn_done(doc)
            try:
                from khanal_tech_integrations.consumables.api.notifications import notify_cpr_grn_done
                frappe.enqueue(notify_cpr_grn_done, queue="short", cpr_name=doc.name)
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"Email notify: CPR GRN done {doc.name}")
        cmr_ref = (doc.cmr_reference or "").strip()
        if cmr_ref and not needs_transfer and not is_partial_grn:
            try:
                from khanal_tech_integrations.consumables.api.material_requests import _sync_cmr_fulfillment_from_bg
                _sync_cmr_fulfillment_from_bg(cmr_ref)
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"Auto-sync CMR {cmr_ref} after GRN failed")
    except Exception as e:
        doc.db_set("sap_last_error", str(e)[:1000])
        doc.add_comment("Comment", text=f"SAP GRPO posting failed: {e}")
        frappe.log_error(frappe.get_traceback(), f"StoreOps CPR GRPO Error: {doc_name}")
        frappe.db.commit()  # commit before notify so frontend reads the error immediately
        frappe.publish_realtime(
            "storeops_update",
            {
                "doc_name": doc_name,
                "new_status": "Failed",
                "message": f"SAP GRN posting failed: {str(e)[:200]}",
                "level": "error",
            },
            user=notify_user,
        )
        # Email the person who submitted GRN so they know even if they logged out
        try:
            email = frappe.db.get_value("User", notify_user, "email") or notify_user
            subject = f"[StoreOps] GRN Failed — {doc_name}"
            body = (
                f"<p>SAP GRPO posting failed for <strong>{doc_name}</strong>.</p>"
                f"<p><b>Error:</b> {str(e)[:500]}</p>"
                f"<p>Please retry from the Purchase Request page or contact support.</p>"
            )
            frappe.sendmail(recipients=[email], subject=subject, message=body)
        except Exception:
            pass
    finally:
        frappe.cache().delete_value(f"grn_in_progress_{doc_name}")


@frappe.whitelist()
def retry_sap_posting(name):
    _require_procurement_or_admin()
    if not frappe.db.exists("Consumables Purchase Request", name):
        frappe.throw(_("Purchase request {0} not found.").format(name), frappe.DoesNotExistError)
    doc = frappe.get_doc("Consumables Purchase Request", name)
    roles = frappe.get_roles()
    if not any(r in roles for r in ("Consumables Procurement User", "Consumables Super Admin")):
        assert_plant_access(doc.requesting_plant)

    # Allow retry whenever there's a vendor_code and the PO has not yet been raised.
    # Status stays "Submitted" even after a failed SAP attempt (only sap_last_error is set),
    # so we check for vendor_code + no sap_po_doc_entry rather than a specific status.
    can_retry_po = doc.vendor_code and not doc.sap_po_doc_entry
    if can_retry_po:
        original_status = doc.status if doc.status != "PO Posting" else "Submitted"
        doc.db_set("sap_last_error", "")
        doc.db_set("status", "PO Posting")
        frappe.db.commit()
        _post_purchase_order_to_sap(name, triggered_by=frappe.session.user, original_status=original_status)
        return {"name": name, "message": "PO retry posted."}
    frappe.throw(
        _("Nothing to retry. Either the PO is already raised or no vendor is set."),
        frappe.ValidationError,
    )


def _notify_plant_users_po_raised(doc):
    plant = (doc.requesting_plant or "").strip()
    if not plant:
        return
    users = frappe.get_all(
        "Consumables User Plant",
        filters={"plant": plant, "is_active": 1},
        fields=["user"],
    )
    msg = f"Purchase Order raised in SAP for your request. CPR: {doc.name}, PO#: {doc.sap_po_doc_num}"
    cmr_ref = (doc.cmr_reference or "").strip()
    for row in users:
        user = (row.get("user") or "").strip()
        if not user:
            continue
        frappe.publish_realtime(
            "storeops_update",
            {"doc_type": "Consumables Purchase Request", "doc_name": doc.name, "new_status": "PO Raised", "message": msg, "level": "success"},
            user=user,
        )
        # Email fallback so offline users are also notified
        try:
            email = frappe.db.get_value("User", user, "email") or user
            subject = f"[StoreOps] PO Raised — {doc.name} (PO#{doc.sap_po_doc_num})"
            body = (
                f"<p>A Purchase Order has been raised in SAP for <strong>{plant}</strong>.</p>"
                f"<ul>"
                f"<li><b>CPR:</b> {doc.name}</li>"
                f"<li><b>SAP PO#:</b> {doc.sap_po_doc_num}</li>"
                f"{'<li><b>CMR:</b> ' + cmr_ref + '</li>' if cmr_ref else ''}"
                f"</ul>"
                f"<p>Please record the GRN once goods arrive at the warehouse.</p>"
            )
            frappe.sendmail(recipients=[email], subject=subject, message=body)
        except Exception:
            pass


def _notify_cmr_grn_done(doc):
    plant = (doc.requesting_plant or "").strip()
    if not plant:
        return
    users = frappe.get_all(
        "Consumables User Plant",
        filters={"plant": plant, "is_active": 1},
        fields=["user"],
    )
    msg = f"Goods received in SAP for CPR {doc.name}. GRPO#: {doc.sap_grpo_doc_num}"
    notified = set()
    for row in users:
        user = (row.get("user") or "").strip()
        if not user:
            continue
        frappe.publish_realtime(
            "storeops_update",
            {"doc_type": "Consumables Purchase Request", "doc_name": doc.name, "new_status": "GRN Done", "message": msg, "level": "success"},
            user=user,
        )
        notified.add(user)

    # Also notify the original CMR requester if not already notified above
    cmr_ref = (doc.cmr_reference or "").strip()
    if cmr_ref and frappe.db.exists("Consumables Material Request", cmr_ref):
        requester = (frappe.db.get_value("Consumables Material Request", cmr_ref, "requested_by") or "").strip()
        if requester and requester not in notified:
            frappe.publish_realtime(
                "storeops_update",
                {"doc_type": "Consumables Material Request", "doc_name": cmr_ref, "new_status": "GRN Done", "message": msg, "level": "success"},
                user=requester,
            )


def _create_post_grn_transfer(cpr_doc, triggered_by=None, current_grn_map=None):
    """Auto-create a CTR from receiving_plant → requesting_plant after GRN, and link it to the CMR."""
    from khanal_tech_integrations.consumables.api.transfers import _resolve_destination_warehouse

    actor = (triggered_by or frappe.session.user or "").strip()
    receiving_plant = (cpr_doc.receiving_plant or "").strip()
    requesting_plant = (cpr_doc.requesting_plant or "").strip()

    # Resolve source warehouse — use the exact warehouse the GRPO received into
    # (taken from the first CPR line item's warehouse_code, which is what the PO used).
    # Falling back to plant-level lookup only if no warehouse_code is stored on the line.
    source_wh = ""
    try:
        for li in (cpr_doc.line_items or []):
            wh = (getattr(li, "warehouse_code", None) or "").strip()
            if wh:
                source_wh = wh
                break
        if not source_wh:
            src_plant_doc = frappe.get_doc("Consumables Plant", receiving_plant)
            src_rows = [w for w in (src_plant_doc.get("warehouses") or []) if frappe.utils.cint(getattr(w, "is_active", 1)) == 1]
            chosen = src_rows[0] if src_rows else None
            if chosen:
                source_wh = (getattr(chosen, "warehouse_code", "") or "").strip()
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"CTR auto-create: could not resolve source warehouse for {receiving_plant}")

    # Resolve destination warehouse on the requesting plant
    try:
        dest_wh = _resolve_destination_warehouse(requesting_plant, source_wh, None)
    except Exception:
        dest_wh = ""

    ctr = frappe.new_doc("Consumables Transfer Request")
    ctr.from_plant = receiving_plant
    ctr.from_warehouse = source_wh
    ctr.to_plant = requesting_plant
    ctr.to_warehouse = dest_wh
    ctr.requested_by = actor
    ctr.requested_on = frappe.utils.now_datetime()
    ctr.status = "Submitted"
    ctr.submitted_by = actor
    ctr.submitted_on = frappe.utils.now_datetime()
    ctr.cmr_reference = (cpr_doc.cmr_reference or "").strip()
    ctr.remarks = f"Auto-created after GRN for CPR {cpr_doc.name}. GRPO#{cpr_doc.sap_grpo_doc_num}"

    for li in cpr_doc.line_items:
        if current_grn_map is not None:
            qty = float(current_grn_map.get(li.name, current_grn_map.get(li.item_code, 0)))
        else:
            qty = float(li.quantity_received or 0)
        if qty <= 0:
            continue
        ctr.append("line_items", {
            "item_code": li.item_code or "",
            "item_name": li.item_name or "",
            "batch_number": "",
            "quantity": qty,
            "uom": li.uom or "",
            "available_quantity": 0,
        })

    ctr.insert(ignore_permissions=True)
    ctr.add_comment("Comment", text=f"Auto-created from CPR {cpr_doc.name} after GRN. Receiving plant: {receiving_plant} → Requesting plant: {requesting_plant}")

    # Link CTR to the parent CMR's transfer_links table
    cmr_ref = (cpr_doc.cmr_reference or "").strip()
    if cmr_ref and frappe.db.exists("Consumables Material Request", cmr_ref):
        try:
            cmr = frappe.get_doc("Consumables Material Request", cmr_ref)
            cmr.append("transfer_links", {
                "transfer_request": ctr.name,
                "from_plant": receiving_plant,
                "from_warehouse": source_wh,
                "quantity": sum(float(li.quantity_received or li.quantity or 0) for li in cpr_doc.line_items),
                "status": ctr.status,
            })
            cmr.save(ignore_permissions=True)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"CTR auto-create: could not link CTR {ctr.name} to CMR {cmr_ref}")

    # Notify Mahadevpura (receiving plant) store managers to dispatch
    _notify_receiving_plant_for_dispatch(ctr, cpr_doc)

    return ctr.name


def _notify_receiving_plant_for_dispatch(ctr_doc, cpr_doc):
    """Notify the receiving plant's store managers that a dispatch is needed."""
    managers = frappe.get_all(
        "Consumables User Plant",
        filters={"plant": ctr_doc.from_plant, "is_active": 1},
        fields=["user"],
    )
    for row in managers:
        user = (row.get("user") or "").strip()
        if not user:
            continue
        roles = frappe.get_roles(user)
        if not any(r in roles for r in ("Consumables Store Manager", "Consumables Super Admin")):
            continue
        msg = (
            f"New transfer required: dispatch {ctr_doc.name} from {ctr_doc.from_plant} → {ctr_doc.to_plant}. "
            f"Linked CPR: {cpr_doc.name} (GRPO#{cpr_doc.sap_grpo_doc_num}). Please approve and dispatch."
        )
        frappe.publish_realtime(
            "storeops_update",
            {
                "doc_type": "Consumables Transfer Request",
                "doc_name": ctr_doc.name,
                "new_status": "Submitted",
                "message": msg,
                "level": "info",
            },
            user=user,
        )
        try:
            email = frappe.db.get_value("User", user, "email") or user
            subject = f"[StoreOps] Action Required: Dispatch {ctr_doc.name} to {ctr_doc.to_plant}"
            body = (
                f"<p>A Purchase Order has been received at <strong>{ctr_doc.from_plant}</strong> "
                f"and the goods need to be transferred to <strong>{ctr_doc.to_plant}</strong>.</p>"
                f"<ul>"
                f"<li><b>Transfer Request:</b> {ctr_doc.name}</li>"
                f"<li><b>CPR:</b> {cpr_doc.name}</li>"
                f"<li><b>GRPO#:</b> {cpr_doc.sap_grpo_doc_num}</li>"
                f"</ul>"
                f"<p>Please log in to StoreOps, approve and dispatch this transfer.</p>"
            )
            frappe.sendmail(recipients=[email], subject=subject, message=body)
        except Exception:
            pass


@frappe.whitelist()
def on_ctr_completed_for_cpr(ctr_name):
    """Called when a CTR completes — close the linked CPR to GRN Done and sync CMR."""
    require_consumables_role()
    ctr = frappe.get_doc("Consumables Transfer Request", ctr_name)
    cmr_ref = (getattr(ctr, "cmr_reference", None) or "").strip()
    if not cmr_ref:
        return

    # Find CPRs on this CMR that are in Transfer Pending and match the receiving/requesting plants
    linked_cprs = frappe.get_all(
        "Consumables Purchase Request",
        filters={"cmr_reference": cmr_ref, "status": "Transfer Pending"},
        fields=["name", "receiving_plant", "requesting_plant", "requested_by"],
    )

    for cpr_row in linked_cprs:
        if (cpr_row.receiving_plant or "").strip() != (ctr.from_plant or "").strip():
            continue
        if (cpr_row.requesting_plant or "").strip() != (ctr.to_plant or "").strip():
            continue

        frappe.db.set_value("Consumables Purchase Request", cpr_row.name, "status", "GRN Done")
        frappe.db.commit()

        msg = (
            f"Goods from CPR {cpr_row.name} have arrived at {ctr.to_plant}. "
            f"Transfer {ctr_name} completed. Request is fully fulfilled."
        )
        # Notify requesting plant users
        plant_users = frappe.get_all(
            "Consumables User Plant",
            filters={"plant": ctr.to_plant, "is_active": 1},
            fields=["user"],
        )
        notified = set()
        for row in plant_users:
            user = (row.get("user") or "").strip()
            if not user:
                continue
            frappe.publish_realtime(
                "storeops_update",
                {"doc_type": "Consumables Purchase Request", "doc_name": cpr_row.name, "new_status": "GRN Done", "message": msg, "level": "success"},
                user=user,
            )
            notified.add(user)

        # Notify original requester
        requester = (cpr_row.get("requested_by") or "").strip()
        if requester and requester not in notified:
            frappe.publish_realtime(
                "storeops_update",
                {"doc_type": "Consumables Material Request", "doc_name": cmr_ref, "new_status": "Fully Fulfilled", "message": msg, "level": "success"},
                user=requester,
            )

        # Sync CMR fulfillment
        try:
            from khanal_tech_integrations.consumables.api.material_requests import _sync_cmr_fulfillment_from_bg
            _sync_cmr_fulfillment_from_bg(cmr_ref)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Auto-sync CMR {cmr_ref} after CTR completion failed")

        # Update the CMR's transfer_links status for this CTR
        try:
            cmr_doc = frappe.get_doc("Consumables Material Request", cmr_ref)
            for tl in (cmr_doc.transfer_links or []):
                if (tl.transfer_request or "").strip() == ctr_name:
                    tl.status = "Completed"
            cmr_doc.save(ignore_permissions=True)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Could not update CMR transfer_links status for {ctr_name}")


def notify_requester(doc, message, level="info"):
    """Notify the request creator about status changes."""
    if not doc.requested_by:
        return
    try:
        frappe.publish_realtime(
            "storeops_update",
            {
                "doc_type": "Consumables Purchase Request",
                "doc_name": doc.name,
                "new_status": doc.status,
                "message": message,
                "level": level,
            },
            user=doc.requested_by,
        )
    except Exception as e:
        frappe.logger().warning(f"Failed to notify requester {doc.requested_by}: {e}")


def notify_procurement_team(doc, message):
    """Notify procurement and store manager recipients when request is escalated."""
    try:
        recipients = set()
        recipients.update(_enabled_users_with_role("Consumables Procurement User"))
        recipients.update(_enabled_users_with_role("Consumables Store Manager"))
        recipients.update(_enabled_users_with_role("Consumables Super Admin"))

        # Also notify any store managers explicitly assigned to the request plant.
        if doc.requesting_plant:
            plant_links = frappe.get_all(
                "Consumables User Plant",
                filters={"plant": doc.requesting_plant, "is_active": 1},
                fields=["user"],
            )
            recipients.update(
                (row.get("user") or "").strip() for row in plant_links if (row.get("user") or "").strip()
            )

        for user in recipients:
            frappe.publish_realtime(
                "storeops_update",
                {
                    "doc_type": "Consumables Purchase Request",
                    "doc_name": doc.name,
                    "new_status": doc.status,
                    "message": message,
                    "level": "info",
                    "notify_user": True,
                },
                user=user,
            )
    except Exception as e:
        frappe.logger().warning(f"Failed to notify procurement team: {e}")
