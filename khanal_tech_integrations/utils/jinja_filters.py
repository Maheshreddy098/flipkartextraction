import frappe
from babel.numbers import format_currency

def num_to_inr_format(value, needsymbol=True):
    """Format number into Indian currency (₹12,34,567.89)"""
    try:
        if needsymbol:
            return format_currency(value or 0, 'INR', locale='en_IN', format="¤#,##,##0", currency_digits=False).strip()
        else:
            return format_currency(value or 0, 'INR', locale='en_IN', format="¤#,##,##0", currency_digits=False).replace('₹', '').strip()
    except Exception:
        return f"₹{value}"

