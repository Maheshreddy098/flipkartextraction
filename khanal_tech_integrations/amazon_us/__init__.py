SP_API_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
SP_API_BASE = "https://sellingpartnerapi-na.amazon.com"
SP_API_ORDERS_PATH = "/orders/v0/orders"

SAP_VERIFY_SSL = False

_LWA_CACHE_KEY = "amazon_us_lwa_token"
_SAP_SESSION_CACHE_KEY = "amazon_us_sap_session"
_SAP_SESSION_CACHE_TTL = 28 * 60  # 28 min in seconds

ORDER_DOCTYPE = "Amazon US Order"
ORDER_ITEM_DOCTYPE = "Amazon US Order Item"

# Lookback applied to both manual CreatedAfter window and incremental LastUpdatedAfter watermark.
# 7 days covers FBA peak-period fulfillment SLAs and SP-API eventual-consistency lag.
INCREMENTAL_LOOKBACK_DAYS = 7


# Fallback used only if Amazon US Settings.posting_cutoff_date has never been saved.
# The doctype's JSON "default" does NOT backfill an existing Single record (Frappe only
# applies field defaults on first explicit save), so a fresh site with the field never
# touched in the UI would otherwise leave this guard silently inert. Keep in sync with
# amazon_us_settings.json's posting_cutoff_date default.
_DEFAULT_POSTING_CUTOFF = "2026-06-01"


def posting_cutoff_violation(check_date):
    """
    Return an error message if check_date is before the posting cutoff, else None.
    Finance booked everything before that date manually in SAP straight from the MTR
    report -- our dedup only catches orders THIS pipeline posted (NumAtCard =
    AmazonOrderId), so a manually-booked order is invisible to it. Without this guard, one
    accidental early from_date (or a stray old order) would double-book real money.
    check_date accepts None (no violation -- caller has nothing to compare yet).
    """
    if not check_date:
        return None
    import frappe

    cutoff = frappe.db.get_single_value("Amazon US Settings", "posting_cutoff_date")
    # An unset Date field reads back as Frappe's null-date sentinel ("0001-01-01"),
    # not None -- that string is truthy and would otherwise defeat the `or` fallback
    # below and silently disable the guard.
    if not cutoff or str(cutoff) == "0001-01-01":
        cutoff = _DEFAULT_POSTING_CUTOFF
    if cutoff and str(check_date) < str(cutoff):
        return (
            f"Posting blocked: {check_date} is before the posting cutoff ({cutoff}). "
            f"Orders before this date were booked manually in SAP by Finance from the MTR "
            f"report -- posting them again would double-book, since SAP's dedup can't see "
            f"manual entries. Change Amazon US Settings > Posting Cutoff Date if this is wrong."
        )
    return None


def enforce_posting_cutoff(check_date):
    """Raises frappe.ValidationError via frappe.throw if posting_cutoff_violation() fires."""
    import frappe

    msg = posting_cutoff_violation(check_date)
    if msg:
        frappe.throw(msg)


def notify_job_failure(job_name, message):
    """
    Best-effort email alert to Amazon US Settings.alert_email when a
    scheduled job fails or a health-check canary trips (e.g. a sync gone
    stale, posted orders piling up without a ship date). Never raises --
    a broken alert must not break the job it's reporting on. No-op if
    alert_email is unset.
    """
    import frappe

    try:
        recipient = frappe.db.get_single_value("Amazon US Settings", "alert_email")
        if not recipient:
            return
        frappe.enqueue(
            method=frappe.sendmail,
            queue="short",
            timeout=300,
            recipients=[recipient],
            subject=f"[Amazon US] {job_name}",
            message=f"<pre>{frappe.utils.escape_html(str(message))}</pre>",
        )
    except Exception as e:
        frappe.log_error(f"notify_job_failure failed for {job_name}: {e}\nOriginal message: {message}", "Amazon US Alerts")
