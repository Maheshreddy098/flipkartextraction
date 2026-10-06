import json

import frappe

from ..geo import normalize_state_code


def get_tax_code(tax_percent: float, ship_to_state: str, origin_state: str) -> str:
    settings = frappe.get_single("Unicommerce Settings")
    tax_map = json.loads(settings.tax_code_map or "{}")

    ship_to_state_code = normalize_state_code(ship_to_state)
    origin_state_code = normalize_state_code(origin_state)
    tx_type = "intra" if ship_to_state_code and ship_to_state_code == origin_state_code else "inter"
    tax_int = int(float(tax_percent))
    if tax_int == 0:
        # Prefer directional zero-rate keys; keep legacy fallback for compatibility.
        code = tax_map.get(f"0_{tx_type}") or tax_map.get("0_exempt")
        if not code:
            frappe.throw(
                f"No tax code mapped for zero-tax key 0_{tx_type}. "
                "Update Unicommerce Settings -> tax_code_map."
            )
        return code

    key = f"{tax_int}_{tx_type}"

    code = tax_map.get(key)
    if not code:
        frappe.throw(f"No tax code mapped for key: {key}. Update Unicommerce Settings -> tax_code_map.")
    return code


def compute_tax_from_line(unit_price: float, qty: float, tax_percent: float, tax_inclusive: bool) -> float:
    """
    Compute expected tax amount for a line item.
    tax_inclusive=True: price already includes tax (extract it)
    tax_inclusive=False: price is ex-tax (add tax on top)
    Returns tax amount rounded to 2 decimal places.
    """
    gross = float(unit_price) * float(qty)
    tax_percent = float(tax_percent)
    if tax_inclusive:
        tax = gross - (gross / (1 + tax_percent / 100))
    else:
        tax = gross * (tax_percent / 100)
    return round(tax, 2)
