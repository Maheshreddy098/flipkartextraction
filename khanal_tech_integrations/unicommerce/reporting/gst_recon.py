"""
GST Reconciliation orchestrator (Ops Center → Reconciliation tab).

End-to-end flow for a user-supplied date range:
  1. Trigger fresh UC export job per facility (no cached file is reused).
  2. Wait + download merged UC sale-orders Excel and read the Master sheet.
  3. Filter to COMPLETE/DELIVERED orders, compute Taxable Value =
     subtotal - line discount, derive a SeriesN bucket per row from the
     channel (using channel_series_map in Unicommerce Settings).
  4. Run the trimmed GSTR1 HANA query and filter to the configured SAP
     SeriesN list (defaults: KAB2C26, TNB2C26, MHB2C26, HRB2C26).
  5. Build two pivots:
       - UC pivot:  Channel × (Taxable Value, CGST, SGST, IGST, Shipping)
       - SAP pivot: "Customer Name SeriesN" × (Taxable Value, CGST, SGST, IGST)
  6. Build a side-by-side comparison using the existing
     `channel_customer_map` (UC channel → SAP customer code) plus
     `channel_series_map` (UC channel → SeriesN). Multiple UC channels
     that map to the same SAP customer code roll into a single SAP row
     (e.g. all 4 Amazon UC channels in BLR → "Amazon KAB2C26").
  7. Persist a workbook (UC Master Data, UC Pivot, SAP GSTR1 Raw,
     SAP Pivot, Side-by-Side) on the site and stash a snapshot in
     frappe.cache for the Ops Center UI.

The whitelisted entry points live in `unicommerce/api/ops.py`.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone, timedelta

_IST = timezone(timedelta(hours=5, minutes=30))
from typing import Any, Callable, Iterable

import frappe
from frappe.utils import add_to_date, now_datetime


GST_RECON_LAST_RUN_CACHE_KEY = "unicommerce_gst_recon_last_run_v1"
GST_RECON_LAST_FILE_CACHE_KEY = "unicommerce_gst_recon_last_file_v1"

# TTL for the cached snapshot. Terminal states (matched/mismatch/error) live
# for 120 days so the UI keeps showing the last outcome; in-flight states
# (queued/running) expire after 4 hours so a crashed run doesn't block the
# concurrency guard forever.
_TTL_TERMINAL_SEC = 120 * 24 * 60 * 60
_TTL_INFLIGHT_SEC = 4 * 60 * 60

DEFAULT_SAP_SERIES = ["KAB2C26", "TNB2C26", "MHB2C26", "HRB2C26"]

# UC sale-order statuses considered completed for reconciliation.
# Keep this strict to avoid including in-flight/cancelled rows.
COMPLETE_STATUS_VALUES = {"COMPLETE", "COMPLETED"}

# Terminal run statuses — UI polling stops and the concurrency guard lets a
# new run start from here.
_TERMINAL_STATUSES = frozenset({"matched", "mismatch", "error", "not_run"})

_logger = frappe.logger("gst_recon")


# ---------------------------------------------------------------------------
# Generic helpers (used by multiple aggregators / pivots)
# ---------------------------------------------------------------------------

def _emit(progress_hook: Callable[[dict], None] | None, payload: dict) -> None:
    """Forward a progress payload to an optional hook, logging any error.

    Progress hooks are best-effort: a hook failure should never abort the
    reconciliation job, but we want the failure in the logs rather than silently
    swallowed so we can spot UI/progress bugs.
    """
    if not callable(progress_hook):
        return
    try:
        progress_hook(payload)
    except Exception:
        _logger.warning("GST recon progress hook raised; continuing", exc_info=True)


def _clean_strings(values: Iterable[Any]) -> set[str]:
    """Normalise an iterable of values into a set of non-empty, non-NaN strings."""
    clean: set[str] = set()
    for x in values:
        if x is None:
            continue
        t = str(x).strip()
        if not t or t.lower() == "nan":
            continue
        clean.add(t)
    return clean


def _join_unique(values: Iterable[Any]) -> str:
    """Sorted comma-joined unique non-empty string values (for pandas groupby agg)."""
    return ", ".join(sorted(_clean_strings(values)))


def _first_non_empty(values: Iterable[Any]) -> str:
    """First non-empty, non-NaN stringified value (for pandas groupby agg)."""
    for x in values:
        t = str(x).strip() if x is not None else ""
        if t and t.lower() != "nan":
            return t
    return ""


def _safe_json_loads(value: Any) -> dict:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except Exception:
        return {}


def _settings():
    return frappe.get_single("Unicommerce Settings")


def _get_channel_series_map() -> dict[str, str]:
    """UC channel code → SAP SeriesN. Channel codes are upper-cased so lookups
    are case-insensitive. Falls back to the legacy `facility_series_map` key if
    a site still has data under the old fieldname, so sites that were
    configured before the rename keep working without re-pasting.
    """
    settings = _settings()
    raw = settings.get("channel_series_map") or settings.get("facility_series_map") or "{}"
    parsed = _safe_json_loads(raw)
    return {str(k).strip().upper(): str(v).strip().upper() for k, v in parsed.items() if k and v}


def _get_channel_customer_map() -> dict[str, str]:
    raw = _settings().get("channel_customer_map") or "{}"
    parsed = _safe_json_loads(raw)
    return {str(k).strip().upper(): str(v).strip() for k, v in parsed.items() if k and v}


def _get_sap_series_filter() -> list[str]:
    raw = (_settings().get("gst_recon_sap_series") or "").strip()
    if not raw:
        return list(DEFAULT_SAP_SERIES)
    series = [piece.strip().upper() for piece in raw.split(",") if piece.strip()]
    return series or list(DEFAULT_SAP_SERIES)


def _pick_col(df, candidates: list[str]) -> str | None:
    cols = {str(c).strip().lower(): c for c in list(df.columns)}
    for cand in candidates:
        hit = cols.get(cand.lower())
        if hit is not None:
            return hit
    return None


# ---------------------------------------------------------------------------
# UC side
# ---------------------------------------------------------------------------

def _read_uc_master_dataframe(excel_path: str):
    import pandas as pd

    if not excel_path or not os.path.exists(excel_path):
        raise FileNotFoundError(f"UC export Excel not found: {excel_path}")

    xl = pd.ExcelFile(excel_path)
    # Read all facility sheets (skip Master Data / Pivot Table / Validation Summary
    # if they happen to exist) and stitch them so we can derive facility from sheet
    # name when the export columns don't carry facility info per row.
    utility_sheets = {"master data", "pivot table", "validation summary", "missing orders"}
    facility_frames = []
    facility_frames_all = []
    for sheet in xl.sheet_names:
        sheet_norm = str(sheet or "").strip().lower()
        if sheet_norm in utility_sheets:
            continue
        try:
            df = pd.read_excel(excel_path, sheet_name=sheet)
        except Exception as exc:
            frappe.logger().warning(f"GST recon: failed to read UC sheet {sheet}: {exc}")
            continue
        if df is None:
            continue
        df = df.copy()
        df["__uc_facility"] = sheet
        facility_frames_all.append(df)
        if not df.empty:
            facility_frames.append(df)

    if facility_frames:
        return pd.concat(facility_frames, ignore_index=True, sort=False)

    # Fallback: if all facility sheets are header-only, still return a stitched
    # empty dataframe so the caller can report "no data in window" gracefully
    # instead of raising a hard parser error.
    if facility_frames_all:
        return pd.concat(facility_frames_all, ignore_index=True, sort=False)

    # Final fallback: maybe the workbook only had a single Master Data sheet.
    master_name = next((s for s in xl.sheet_names if str(s or "").strip().lower() == "master data"), None)
    if master_name:
        df = pd.read_excel(excel_path, sheet_name=master_name)
        if df is not None and not df.empty:
            df = df.copy()
            df["__uc_facility"] = ""
            return df

    raise ValueError("UC export Excel has no usable facility sheets")


def _build_uc_pivot(uc_master, channel_series_map: dict[str, str], progress_hook=None):
    """Return (uc_pivot_df, uc_clean_df)."""
    import pandas as pd

    if uc_master is None or uc_master.empty:
        empty = pd.DataFrame(columns=["Channel", "Taxable Value", "CGST", "SGST", "IGST", "Shipping Charges"])
        return empty, uc_master

    df = uc_master.copy()

    # Status filter --------------------------------------------------------
    status_col = _pick_col(
        df,
        ["sale order status", "saleorderstatus", "order status", "status", "fulfillmenttatstatus"],
    )
    if status_col:
        normalised = df[status_col].astype(str).str.strip().str.upper()
        df = df[normalised.isin(COMPLETE_STATUS_VALUES)]

    if df.empty:
        empty = pd.DataFrame(columns=["Channel", "Taxable Value", "CGST", "SGST", "IGST", "Shipping Charges"])
        return empty, df

    # Column resolution ----------------------------------------------------
    channel_col = _pick_col(df, ["channel", "channel name", "channelname", "channelcode"])
    subtotal_col = _pick_col(df, ["subtotal", "sub total", "item subtotal", "item_subtotal", "selling price", "total price"])
    discount_col = _pick_col(df, ["discount", "line discount", "linediscount", "item discount", "itemdiscount"])
    cgst_col = _pick_col(df, ["cgst", "cgst amount", "cgst tax", "cgst_value"])
    sgst_col = _pick_col(df, ["sgst", "sgst amount", "sgst tax", "sgst_value"])
    igst_col = _pick_col(df, ["igst", "igst amount", "igst tax", "igst_value"])
    shipping_col = _pick_col(df, ["shipping charges", "shipping_charges", "shipping charge", "shippingmethodcharge", "shipping price", "shippingcharge"])

    if not channel_col:
        raise ValueError("UC export is missing a Channel column; cannot build pivot")
    if not subtotal_col:
        raise ValueError("UC export is missing a Subtotal column; cannot compute Taxable Value")

    df = df.copy()

    def _num(series):
        return pd.to_numeric(series, errors="coerce").fillna(0.0)

    df["__channel"] = df[channel_col].astype(str).str.strip().str.upper()
    subtotal = _num(df[subtotal_col])
    discount = _num(df[discount_col]) if discount_col else 0.0
    df["__taxable_value"] = subtotal - discount
    df["__cgst"] = _num(df[cgst_col]) if cgst_col else 0.0
    df["__sgst"] = _num(df[sgst_col]) if sgst_col else 0.0
    df["__igst"] = _num(df[igst_col]) if igst_col else 0.0
    df["__shipping"] = _num(df[shipping_col]) if shipping_col else 0.0

    # Derive series bucket from the UC channel (not the facility): FLIPKART,
    # MEESHO, CRED, etc. all ship from the same KFL facility but belong to
    # different SAP SeriesN buckets. Falls back to facility code when the
    # channel isn't mapped (e.g. legacy data that only has facility info).
    if "__uc_facility" not in df.columns:
        df["__uc_facility"] = ""
    series_map_upper = dict(channel_series_map or {})
    channels_upper = df["__channel"]
    df["__series"] = channels_upper.map(lambda c: series_map_upper.get(str(c).strip().upper(), ""))
    missing = df["__series"] == ""
    if missing.any():
        fallback = df.loc[missing, "__uc_facility"].astype(str).map(
            lambda f: series_map_upper.get(str(f).strip().upper(), "")
        )
        df.loc[missing, "__series"] = fallback

    _emit(progress_hook, {"stage": "uc_pivot", "label": f"Aggregating UC pivot from {len(df):,} rows"})

    return _build_uc_pivot_from_clean(df), df


def _build_uc_pivot_from_clean(df):
    import pandas as pd

    if df is None or df.empty:
        return pd.DataFrame(columns=["Channel", "Taxable Value", "CGST", "SGST", "IGST", "Shipping Charges", "Total"])

    grouped = (
        df.groupby("__channel", dropna=False, as_index=False)[["__taxable_value", "__cgst", "__sgst", "__igst", "__shipping"]]
        .sum()
        .round(2)
    )
    grouped = grouped.rename(
        columns={
            "__channel": "Channel",
            "__taxable_value": "Taxable Value",
            "__cgst": "CGST",
            "__sgst": "SGST",
            "__igst": "IGST",
            "__shipping": "Shipping Charges",
        }
    )
    grouped["Total"] = (
        grouped["Taxable Value"] + grouped["CGST"] + grouped["SGST"] + grouped["IGST"] + grouped["Shipping Charges"]
    ).round(2)
    return grouped.sort_values(by="Taxable Value", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# SAP side
# ---------------------------------------------------------------------------

def _build_sap_pivot(sap_raw, sap_series_filter: list[str], progress_hook=None):
    """Return (sap_pivot_df, sap_clean_df)."""
    import pandas as pd

    if sap_raw is None or sap_raw.empty:
        empty = pd.DataFrame(columns=["Customer Name SeriesN", "Customer Name", "SeriesN", "Taxable Value", "CGST", "SGST", "IGST"])
        return empty, sap_raw

    df = sap_raw.copy()
    series_set = {s.strip().upper() for s in sap_series_filter if s.strip()}
    df["__series_norm"] = df.get("SeriesN", "").astype(str).str.strip().str.upper()
    df = df[df["__series_norm"].isin(series_set)] if series_set else df

    if df.empty:
        empty = pd.DataFrame(columns=["Customer Name SeriesN", "Customer Name", "SeriesN", "Taxable Value", "CGST", "SGST", "IGST"])
        return empty, df

    def _num(series):
        return pd.to_numeric(series, errors="coerce").fillna(0.0)

    taxable = _num(df.get("Taxable Value", 0)) - _num(df.get("Total_Disc", 0))
    df["__taxable_value"] = taxable
    df["__cgst"] = _num(df.get("CGST Tax Amount", 0))
    df["__sgst"] = _num(df.get("SGST Tax Amount", 0))
    df["__igst"] = _num(df.get("IGST Tax Amount", 0))
    df["__customer_name"] = df.get("Customer Name", "").astype(str).str.strip()
    df["__customer_code"] = df.get("Customer Code", "").astype(str).str.strip()
    df["__row_label"] = df["__customer_name"].fillna("") + " " + df["__series_norm"]

    _emit(progress_hook, {"stage": "sap_pivot", "label": f"Aggregating SAP pivot from {len(df):,} rows"})

    grouped = (
        df.groupby(["__row_label", "__customer_name", "__customer_code", "__series_norm"], dropna=False, as_index=False)[
            ["__taxable_value", "__cgst", "__sgst", "__igst"]
        ]
        .sum()
        .round(2)
    )
    grouped = grouped.rename(
        columns={
            "__row_label": "Customer Name SeriesN",
            "__customer_name": "Customer Name",
            "__customer_code": "Customer Code",
            "__series_norm": "SeriesN",
            "__taxable_value": "Taxable Value",
            "__cgst": "CGST",
            "__sgst": "SGST",
            "__igst": "IGST",
        }
    )
    grouped["Total"] = (grouped["Taxable Value"] + grouped["CGST"] + grouped["SGST"] + grouped["IGST"]).round(2)
    grouped = grouped.sort_values(by=["SeriesN", "Customer Name"]).reset_index(drop=True)
    return grouped, df


# ---------------------------------------------------------------------------
# Side-by-side
# ---------------------------------------------------------------------------

def _posted_uc_buckets_from_frappe(
    start_date: str,
    end_date: str,
    channel_customer_map: dict[str, str],
    channel_series_map: dict[str, str],
    candidate_order_ids: set[str] | None = None,
) -> dict[tuple[str, str], dict]:
    """Build UC buckets from posted Frappe orders using SAP-confirmed amounts.

    In posted-only mode, finance expects exact SAP-aligned numbers. We therefore
    use `ar_invoice_unit_price_actual` + `ar_invoice_tax_actual` as primary
    source (captured from SAP reconciliation), with expected fields as a safety
    fallback for legacy rows.
    """
    filters: dict[str, object] = {
        "pipeline_status": "posted",
        "status": ["in", list(COMPLETE_STATUS_VALUES)],
    }
    scoped_ids = {str(x).strip() for x in (candidate_order_ids or set()) if str(x).strip()}
    if scoped_ids:
        filters["name"] = ["in", list(scoped_ids)]
    else:
        filters["order_date"] = ["between", [start_date, end_date]]
    rows = frappe.get_all(
        "Unicommerce Orders",
        filters=filters,
        fields=[
            "name",
            "channel_name",
            "ar_invoice_unit_price_actual",
            "ar_invoice_tax_actual",
            "ar_invoice_unit_price_expected",
            "ar_invoice_tax_expected",
        ],
        limit_page_length=0,
    )
    buckets: dict[tuple[str, str], dict] = {}
    for row in rows:
        channel = str(row.get("channel_name") or "").strip().upper()
        if not channel:
            continue
        series = str(channel_series_map.get(channel, "") or "").strip().upper()
        cust_code = str(channel_customer_map.get(channel, "") or "").strip()
        key = (cust_code, series)
        bucket = buckets.setdefault(
            key,
            {
                "channels": set(),
                "facilities": set(),
                "taxable_value": 0.0,
                "cgst": 0.0,
                "sgst": 0.0,
                "igst": 0.0,
                "shipping": 0.0,
            },
        )
        bucket["channels"].add(channel)
        taxable_actual = row.get("ar_invoice_unit_price_actual")
        tax_actual = row.get("ar_invoice_tax_actual")
        taxable = float(
            taxable_actual
            if taxable_actual not in (None, "")
            else (row.get("ar_invoice_unit_price_expected") or 0.0)
        )
        tax_total = float(
            tax_actual
            if tax_actual not in (None, "")
            else (row.get("ar_invoice_tax_expected") or 0.0)
        )
        bucket["taxable_value"] += taxable
        # We store aggregate tax in one bucket so total tax comparison remains exact.
        # side-by-side tax total stays correct without inventing split values.
        bucket["igst"] += tax_total
    return buckets


def _build_side_by_side(uc_clean, sap_pivot, channel_customer_map, channel_series_map, uc_buckets_override=None):
    """Roll UC up to (SAP customer code, SeriesN) and join to SAP pivot rows.

    Multiple UC channels can map to the same SAP customer (e.g. AMAZON_IN_API,
    AMAZON_FBA_IN_BLR5/7/8 → "Amazon"). Each (customer_code, series) becomes one
    row. UC channels that have no mapping are listed as "Unmapped" rows so the
    user can fix Unicommerce Settings.
    """
    import pandas as pd

    # SAP keyed by (customer_code, series) -------------------------------
    sap_lookup: dict[tuple[str, str], dict] = {}
    if sap_pivot is not None and not sap_pivot.empty:
        for _, row in sap_pivot.iterrows():
            key = (str(row.get("Customer Code") or "").strip(), str(row.get("SeriesN") or "").strip().upper())
            sap_lookup[key] = {
                "label": row.get("Customer Name SeriesN") or "",
                "customer_name": row.get("Customer Name") or "",
                "customer_code": row.get("Customer Code") or "",
                "series": row.get("SeriesN") or "",
                "taxable_value": float(row.get("Taxable Value") or 0),
                "cgst": float(row.get("CGST") or 0),
                "sgst": float(row.get("SGST") or 0),
                "igst": float(row.get("IGST") or 0),
            }

    # UC bucketed by (customer_code, series) ------------------------------
    uc_buckets: dict[tuple[str, str], dict] = {}
    if uc_buckets_override is not None:
        uc_buckets = dict(uc_buckets_override or {})
    elif uc_clean is not None and not uc_clean.empty:
        for _, row in uc_clean.iterrows():
            channel = str(row.get("__channel") or "").strip().upper()
            series = str(row.get("__series") or "").strip().upper()
            cust_code = channel_customer_map.get(channel, "")
            key = (cust_code, series)
            bucket = uc_buckets.setdefault(
                key,
                {
                    "channels": set(),
                    "facilities": set(),
                    "taxable_value": 0.0,
                    "cgst": 0.0,
                    "sgst": 0.0,
                    "igst": 0.0,
                    "shipping": 0.0,
                },
            )
            bucket["channels"].add(channel)
            facility = str(row.get("__uc_facility") or "").strip()
            if facility:
                bucket["facilities"].add(facility)
            bucket["taxable_value"] += float(row.get("__taxable_value") or 0)
            bucket["cgst"] += float(row.get("__cgst") or 0)
            bucket["sgst"] += float(row.get("__sgst") or 0)
            bucket["igst"] += float(row.get("__igst") or 0)
            bucket["shipping"] += float(row.get("__shipping") or 0)

    rows: list[dict] = []
    matched_keys: set[tuple[str, str]] = set()

    for key, bucket in uc_buckets.items():
        cust_code, series = key
        sap_row = sap_lookup.get(key)
        matched_keys.add(key)
        sap_label = sap_row["label"] if sap_row else ""
        sap_taxable = float(sap_row["taxable_value"]) if sap_row else 0.0
        sap_cgst = float(sap_row["cgst"]) if sap_row else 0.0
        sap_sgst = float(sap_row["sgst"]) if sap_row else 0.0
        sap_igst = float(sap_row["igst"]) if sap_row else 0.0
        if not sap_row and not cust_code:
            status = "uc_unmapped"
        elif not sap_row:
            status = "missing_in_sap"
        else:
            taxable_diff = round(bucket["taxable_value"] - sap_taxable, 2)
            tax_diff = round((bucket["cgst"] + bucket["sgst"] + bucket["igst"]) - (sap_cgst + sap_sgst + sap_igst), 2)
            status = "matched" if abs(taxable_diff) <= 1.0 and abs(tax_diff) <= 1.0 else "amount_mismatch"
        rows.append(
            {
                "status": status,
                "sap_label": sap_label,
                "sap_customer_code": cust_code,
                "sap_series": series,
                "uc_channels": sorted(list(bucket["channels"])),
                "uc_facilities": sorted(list(bucket["facilities"])),
                "uc_taxable_value": round(bucket["taxable_value"], 2),
                "uc_cgst": round(bucket["cgst"], 2),
                "uc_sgst": round(bucket["sgst"], 2),
                "uc_igst": round(bucket["igst"], 2),
                "uc_shipping": round(bucket["shipping"], 2),
                "sap_taxable_value": round(sap_taxable, 2),
                "sap_cgst": round(sap_cgst, 2),
                "sap_sgst": round(sap_sgst, 2),
                "sap_igst": round(sap_igst, 2),
                "taxable_diff": round(bucket["taxable_value"] - sap_taxable, 2),
                "tax_diff": round((bucket["cgst"] + bucket["sgst"] + bucket["igst"]) - (sap_cgst + sap_sgst + sap_igst), 2),
            }
        )

    # SAP rows that had no matching UC bucket (missing in UC)
    for key, sap_row in sap_lookup.items():
        if key in matched_keys:
            continue
        rows.append(
            {
                "status": "missing_in_uc",
                "sap_label": sap_row["label"],
                "sap_customer_code": sap_row["customer_code"],
                "sap_series": sap_row["series"],
                "uc_channels": [],
                "uc_facilities": [],
                "uc_taxable_value": 0.0,
                "uc_cgst": 0.0,
                "uc_sgst": 0.0,
                "uc_igst": 0.0,
                "uc_shipping": 0.0,
                "sap_taxable_value": float(sap_row["taxable_value"]),
                "sap_cgst": float(sap_row["cgst"]),
                "sap_sgst": float(sap_row["sgst"]),
                "sap_igst": float(sap_row["igst"]),
                "taxable_diff": -float(sap_row["taxable_value"]),
                "tax_diff": -float(sap_row["cgst"] + sap_row["sgst"] + sap_row["igst"]),
            }
        )

    priority = {"amount_mismatch": 0, "missing_in_sap": 1, "missing_in_uc": 2, "uc_unmapped": 3, "matched": 4}
    rows.sort(
        key=lambda r: (
            priority.get(str(r.get("status")), 9),
            -abs(float(r.get("taxable_diff") or 0)),
            str(r.get("sap_label") or "") or ",".join(r.get("uc_channels") or []),
        )
    )
    return rows


# ---------------------------------------------------------------------------
# Per-Order Diff (one UC order → one SAP AR invoice)
# ---------------------------------------------------------------------------
#
# Join key: `U_Order` on SAP INV1 (line-level UDF set by our AR Invoice payload
# builder in unicommerce/mappers/sap_payload.py) == `Unicommerce Orders.name`
# (== uniware_id, which is the UC saleOrderCode / displayOrderCode).
#
# Classification (full-invoice total compare, strict SAP date window):
#   matched         - both sides present, |UC total − SAP total| ≤ ₹1
#   amount_mismatch - both present, totals differ beyond tolerance
#   missing_in_sap  - UC order in window, no SAP invoice (Document Date in
#                     window). Pipeline state is attached so the user sees why.
#   missing_in_uc   - SAP invoice has a U_Order that isn't in UC export
#                     (e.g. UC order_date is outside the window but SAP posted
#                     it with a DocDate inside the window).

# UC master-data columns we know how to recognise as "Sale Order Code".
_UC_ORDER_CODE_CANDIDATES = [
    "sale order code",
    "sales order code",
    "saleordercode",
    "salesordercode",
    "display order code",
    "displayordercode",
    "order code",
    "ordercode",
    "channel order code",
    "channelordercode",
    
]

_UC_ORDER_DATE_CANDIDATES = [
    "sale order date",
    "order date",
    "orderdate",
    "sale_order_date",
    "order_date",
    "created",
    "created on",
]

_AMOUNT_TOLERANCE = 1.0  # ₹1 absolute


def _aggregate_uc_by_order(uc_clean):
    """Aggregate the completed-orders UC dataframe down to one row per order.

    Returns a DataFrame with:
        order_id, channel, facility, order_date,
        uc_taxable, uc_shipping, uc_cgst, uc_sgst, uc_igst, uc_total,
        uc_line_count
    """
    import pandas as pd

    if uc_clean is None or uc_clean.empty:
        return pd.DataFrame()

    order_code_col = _pick_col(uc_clean, _UC_ORDER_CODE_CANDIDATES)
    if not order_code_col:
        raise ValueError(
            "UC export is missing a Sale/Display Order Code column; cannot build per-order diff"
        )

    order_date_col = _pick_col(uc_clean, _UC_ORDER_DATE_CANDIDATES)

    df = uc_clean.copy()
    df["__order_id"] = df[order_code_col].astype(str).str.strip()
    df = df[df["__order_id"] != ""]
    df = df[df["__order_id"].str.lower() != "nan"]
    if df.empty:
        return pd.DataFrame()

    if order_date_col:
        df["__order_date"] = df[order_date_col].astype(str).str.strip()
    else:
        df["__order_date"] = ""

    agg = (
        df.groupby("__order_id", dropna=False, as_index=False)
        .agg(
            channel=("__channel", _join_unique),
            facility=("__uc_facility", _join_unique),
            order_date=("__order_date", _first_non_empty),
            uc_taxable=("__taxable_value", "sum"),
            uc_shipping=("__shipping", "sum"),
            uc_cgst=("__cgst", "sum"),
            uc_sgst=("__sgst", "sum"),
            uc_igst=("__igst", "sum"),
            uc_line_count=("__order_id", "size"),
        )
    )
    agg["uc_total"] = (
        agg["uc_taxable"] + agg["uc_shipping"] + agg["uc_cgst"] + agg["uc_sgst"] + agg["uc_igst"]
    ).round(2)
    for col in ("uc_taxable", "uc_shipping", "uc_cgst", "uc_sgst", "uc_igst"):
        agg[col] = agg[col].round(2)
    agg = agg.rename(columns={"__order_id": "order_id"})
    return agg


def _filter_uc_clean_to_order_ids(uc_clean, order_ids: set[str] | None):
    if uc_clean is None or uc_clean.empty:
        return uc_clean
    if order_ids is None:
        return uc_clean

    order_id_set = {str(x).strip() for x in (order_ids or set()) if str(x).strip()}
    if not order_id_set:
        return uc_clean.iloc[0:0].copy()

    order_code_col = _pick_col(uc_clean, _UC_ORDER_CODE_CANDIDATES)
    if not order_code_col:
        return uc_clean.iloc[0:0].copy()

    df = uc_clean.copy()
    df["__order_id_filter"] = df[order_code_col].astype(str).str.strip()
    df = df[df["__order_id_filter"].isin(order_id_set)].copy()
    return df.drop(columns=["__order_id_filter"], errors="ignore")


def _filter_sap_raw_to_order_ids(sap_raw, order_ids: set[str] | None):
    """Restrict SAP raw rows to a specific UC-order-id set."""
    import pandas as pd

    if sap_raw is None:
        return sap_raw
    if order_ids is None:
        return sap_raw
    order_id_set = {str(x).strip() for x in (order_ids or set()) if str(x).strip()}
    if not order_id_set:
        return sap_raw.iloc[0:0].copy() if hasattr(sap_raw, "iloc") else sap_raw
    if not hasattr(sap_raw, "copy"):
        return sap_raw
    df = sap_raw.copy()
    order_col = _pick_col(df, ["UC Order ID", "U_Order", "uc order id", "order_id", "order id"])
    if not order_col:
        frappe.logger().warning("GST recon posted_only: SAP raw has no UC order id column; returning empty compare scope")
        return df.iloc[0:0].copy()
    df["__sap_order_id_filter"] = df[order_col].astype(str).str.strip()
    df = df[df["__sap_order_id_filter"].isin(order_id_set)].copy()
    return df.drop(columns=["__sap_order_id_filter"], errors="ignore")


def _aggregate_sap_by_order(sap_raw, sap_series_filter):
    """Aggregate the SAP GSTR1 raw dataframe down to one row per UC order id.

    Rows without a `UC Order ID` (legacy invoices posted before we started
    setting U_Order) are returned separately so the caller can report them as
    "sap_no_uc_order_id" rather than silently dropping them.
    """
    import pandas as pd

    if sap_raw is None or sap_raw.empty:
        return pd.DataFrame(), pd.DataFrame()

    df = sap_raw.copy()
    series_set = {s.strip().upper() for s in (sap_series_filter or []) if s and s.strip()}
    df["__series_norm"] = df.get("SeriesN", "").astype(str).str.strip().str.upper()
    if series_set:
        df = df[df["__series_norm"].isin(series_set)]
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    def _num(s):
        return pd.to_numeric(s, errors="coerce").fillna(0.0)

    df["__sap_taxable"] = _num(df.get("Taxable Value", 0)) - _num(df.get("Total_Disc", 0))
    df["__sap_cgst"] = _num(df.get("CGST Tax Amount", 0))
    df["__sap_sgst"] = _num(df.get("SGST Tax Amount", 0))
    df["__sap_igst"] = _num(df.get("IGST Tax Amount", 0))
    # SAP posts shipping/freight as a separate INV1 line so it's already
    # included in `Taxable Value`; we don't double-count the Freight Charges
    # column. `Freight Charges` is retained for reporting only.
    # `UC Order Name` (= OINV.U_UCOrderID) is not projected by the HANA query
    # on this install — the UDF lives only in the Service Layer payload, not
    # on the OINV table itself. Keep the fallback code path in case a future
    # tenant adds the column, but default it to empty when absent.
    if "UC Order ID" in df.columns:
        df["__order_id"] = df["UC Order ID"].astype(str).str.strip()
    else:
        df["__order_id"] = ""
    if "UC Order Name" in df.columns:
        df["__order_name"] = df["UC Order Name"].astype(str).str.strip()
    else:
        df["__order_name"] = ""
    df["__join_key"] = df["__order_id"].where(df["__order_id"] != "", df["__order_name"])

    no_key = df[df["__join_key"] == ""].copy()
    with_key = df[df["__join_key"] != ""].copy()

    if with_key.empty:
        return pd.DataFrame(), no_key

    agg = (
        with_key.groupby("__join_key", dropna=False, as_index=False)
        .agg(
            sap_docnums=("DocNum", _join_unique),
            sap_series=("__series_norm", _join_unique),
            sap_customer_code=("Customer Code", _join_unique),
            sap_customer_name=("Customer Name", _join_unique),
            sap_doc_date=("Document Date", _first_non_empty),
            sap_taxable=("__sap_taxable", "sum"),
            sap_cgst=("__sap_cgst", "sum"),
            sap_sgst=("__sap_sgst", "sum"),
            sap_igst=("__sap_igst", "sum"),
            sap_line_count=("__join_key", "size"),
        )
    )
    agg["sap_total"] = (
        agg["sap_taxable"] + agg["sap_cgst"] + agg["sap_sgst"] + agg["sap_igst"]
    ).round(2)
    for col in ("sap_taxable", "sap_cgst", "sap_sgst", "sap_igst"):
        agg[col] = agg[col].round(2)
    agg = agg.rename(columns={"__join_key": "order_id"})
    return agg, no_key


def _enrich_missing_with_pipeline(order_ids):
    """Batched read on Unicommerce Orders for the given UC order ids.

    Returns {order_id: {pipeline_status, last_error, attempt_count,
    sap_ar_invoice_docnum, sap_ar_invoice_docentry, posting_started_at}}.
    Orders that aren't found in the doctype are simply absent from the map
    (caller classifies them as `not_ingested`).
    """
    if not order_ids:
        return {}
    order_ids = list({str(x).strip() for x in order_ids if str(x).strip()})
    if not order_ids:
        return {}
    fields = [
        "name",
        "uniware_id",
        "channel_id",
        "pipeline_status",
        "last_error",
        "attempt_count",
        "sap_ar_invoice_docnum",
        "sap_ar_invoice_docentry",
        "posting_started_at",
        "order_date",
    ]
    # Two passes: lookup by name and by uniware_id, since either can legitimately
    # be the value in U_Order depending on when the invoice was posted.
    out: dict[str, dict] = {}
    CHUNK = 500
    for start in range(0, len(order_ids), CHUNK):
        chunk = order_ids[start : start + CHUNK]
        try:
            rows = frappe.get_all(
                "Unicommerce Orders",
                filters={"name": ["in", chunk]},
                fields=fields,
                limit_page_length=0,
            )
        except Exception as exc:
            frappe.logger().warning(f"GST recon: enrichment lookup by name failed: {exc}")
            rows = []
        for row in rows:
            key = str(row.get("name") or "").strip()
            if key:
                out[key] = row
        # Capture by uniware_id too, in case U_Order used that value.
        try:
            rows = frappe.get_all(
                "Unicommerce Orders",
                filters={"uniware_id": ["in", chunk]},
                fields=fields,
                limit_page_length=0,
            )
        except Exception as exc:
            frappe.logger().warning(f"GST recon: enrichment lookup by uniware_id failed: {exc}")
            rows = []
        for row in rows:
            key = str(row.get("uniware_id") or "").strip()
            if key and key not in out:
                out[key] = row
    return out


def _parse_uc_date_str(value: Any) -> str:
    """Parse UC date-like values to YYYY-MM-DD (best effort)."""
    if value is None:
        return ""
    raw = str(value).strip()
    if not raw or raw.lower() == "nan":
        return ""
    # Epoch timestamps (ms or seconds) from UC exports.
    # Use IST (+05:30) — UC timestamps are Indian local time, so UTC conversion
    # would shift dates near midnight by 5.5 hours into the wrong calendar day.
    if raw.isdigit():
        try:
            epoch = int(raw)
            if epoch > 10_000_000_000:
                epoch = int(epoch / 1000)
            return datetime.fromtimestamp(epoch, tz=_IST).date().isoformat()
        except Exception:
            return ""
    # ISO-like date/datetime strings.
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
    except Exception:
        pass
    # Last-resort slice for values already in YYYY-MM-DD...
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        return raw[:10]
    return ""


def _filter_uc_clean_to_window(uc_clean, start_date: str, end_date: str):
    """Keep UC rows whose created/order date falls in requested compare window."""
    if uc_clean is None or getattr(uc_clean, "empty", True):
        return uc_clean
    start = str(start_date or "").strip()[:10]
    end = str(end_date or "").strip()[:10]
    if not start or not end:
        return uc_clean
    date_col = _pick_col(
        uc_clean,
        [
            "created",
            "created on",
            "order date",
            "sale order date",
            "displayorderdatetime",
            "display order datetime",
            "orderdate",
            "order_date",
        ],
    )
    if not date_col:
        return uc_clean
    df = uc_clean.copy()
    df["__window_date"] = df[date_col].map(_parse_uc_date_str)
    df = df[(df["__window_date"] >= start) & (df["__window_date"] <= end)].copy()
    return df.drop(columns=["__window_date"], errors="ignore")


def _get_posted_order_ids(
    start_date: str,
    end_date: str,
    candidate_order_ids: set[str] | None = None,
) -> set[str]:
    """Return the set of order IDs (name + uniware_id) that were posted from UC to SAP.

    Queries Unicommerce Orders for posted+completed rows. When
    ``candidate_order_ids`` is provided, the lookup is restricted to those UC
    order ids (preferred, keeps it aligned with current UC export scope).
    Otherwise falls back to order_date window filters.
    """
    try:
        filters: dict[str, object] = {
            "pipeline_status": "posted",
            "status": ["in", list(COMPLETE_STATUS_VALUES)],
        }
        scoped_ids = {str(x).strip() for x in (candidate_order_ids or set()) if str(x).strip()}
        if scoped_ids:
            filters["name"] = ["in", list(scoped_ids)]
        else:
            filters["order_date"] = ["between", [start_date, end_date]]
        rows = frappe.get_all(
            "Unicommerce Orders",
            filters=filters,
            fields=["name", "uniware_id"],
            limit_page_length=0,
        )
    except Exception as exc:
        frappe.logger().warning(f"GST recon: posted order ID lookup failed: {exc}")
        return set()
    ids: set[str] = set()
    for row in rows:
        for field in ("name", "uniware_id"):
            val = str(row.get(field) or "").strip()
            if val:
                ids.add(val)
    return ids


def _classify_missing_reason(info: dict | None) -> tuple[str, str]:
    """Return (reason_code, reason_label) for a missing-in-SAP order."""
    if not info:
        return ("not_ingested", "Order never reached Frappe (not in Unicommerce Orders)")
    status = (info.get("pipeline_status") or "").strip().lower()
    # Posted in Frappe but SAP date outside window
    if status == "posted" and info.get("sap_ar_invoice_docnum"):
        return (
            "posted_outside_window",
            "Already posted to SAP, but SAP DocDate falls outside the reconciliation window",
        )
    mapping = {
        "fetched": ("fetched", "Fetched from UC but not promoted to ready (pre-posting)"),
        "batch_hold": ("batch_hold", "Held by batch-check (will auto-retry after cooldown)"),
        "ready": ("ready", "Queued for posting, not yet processed by the worker"),
        "posting": ("posting", "Currently posting to SAP"),
        "verify": ("verify", "SAP POST returned timeout/ack-missing; pending verification"),
        "failed": ("failed", "SAP POST failed — see last_error"),
        "dead": ("dead", "Max retries exhausted — needs manual fix"),
        "posted": ("posted_no_docnum", "Marked posted in Frappe but no SAP DocNum captured"),
    }
    return mapping.get(status, ("unknown", f"Unrecognised pipeline_status: {status or 'empty'}"))


def _classify_post_then_match(row_status: str, info: dict | None = None) -> tuple[str, str, str]:
    """Return (code, label, tone) for the post-then-match indicator."""
    status = (row_status or "").strip().lower()
    pipeline_status = str((info or {}).get("pipeline_status") or "").strip().lower()

    if status == "matched":
        return ("already_matched", "Yes — already matched", "good")
    if status == "amount_mismatch":
        return ("already_mismatched", "No — already mismatched", "bad")
    if status == "missing_in_uc":
        return ("missing_in_uc", "No — SAP invoice has no UC order in scope", "bad")
    if status == "uc_order_outside_export_window":
        return ("cross_period", "Cross-period invoice — review in the correct window", "info")

    if pipeline_status in {"failed", "dead"}:
        return ("blocked_before_posting", "No — fix posting issue first", "bad")
    if pipeline_status == "batch_hold":
        return ("batch_hold", "Wait for batch cooldown, then compare", "warn")
    if pipeline_status in {"ready", "pending", "fetched"}:
        return ("pending_posting", "Post first, then compare", "warn")
    if pipeline_status in {"posting", "verify"}:
        return ("posting_in_progress", "Posting in progress — compare after SAP invoice", "warn")
    if pipeline_status == "posted":
        return ("posted_but_not_visible", "Posted, but SAP invoice is not visible in this window", "warn")
    if not info:
        return ("not_ingested", "Ingest/post first, then compare", "info")
    return ("manual_review", "Needs manual review", "info")


def _date_outside_window(order_date: str, start_date: str, end_date: str) -> bool:
    od = str(order_date or "").strip()[:10]
    s = str(start_date or "").strip()[:10]
    e = str(end_date or "").strip()[:10]
    if not od or not s or not e:
        return False
    # YYYY-MM-DD lexical compare is safe.
    return od < s or od > e


def _build_per_order_diff(
    uc_clean,
    sap_raw,
    sap_series_filter,
    progress_hook=None,
    posted_order_ids: set[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Build the per-order diagnostics view for the latest GST reconciliation.

    In `posted_only` mode the actual UC-vs-SAP comparison is restricted to
    posted orders, while non-posted orders are still included as separate
    diagnostic rows with a dedicated post-then-match indicator.
    """
    uc_agg = _aggregate_uc_by_order(uc_clean)
    sap_agg, sap_without_uc_key = _aggregate_sap_by_order(sap_raw, sap_series_filter)

    _emit(
        progress_hook,
        {
            "stage": "per_order",
            "label": f"Building per-order diff for {len(uc_agg):,} UC orders vs {len(sap_agg):,} SAP orders",
        },
    )

    uc_index_all: dict[str, dict] = {}
    if not uc_agg.empty:
        for _, row in uc_agg.iterrows():
            uc_index_all[str(row["order_id"])] = row.to_dict()

    compare_posted_only = posted_order_ids is not None
    posted_order_id_set = {str(x).strip() for x in (posted_order_ids or set()) if str(x).strip()}
    uc_index = dict(uc_index_all)
    if compare_posted_only:
        uc_index = {k: v for k, v in uc_index_all.items() if k in posted_order_id_set}

    sap_index: dict[str, dict] = {}
    if not sap_agg.empty:
        for _, row in sap_agg.iterrows():
            sap_index[str(row["order_id"])] = row.to_dict()

    enrichment_ids = list(uc_index_all.keys()) if compare_posted_only else [oid for oid in uc_index.keys() if oid not in sap_index]
    enrichment = _enrich_missing_with_pipeline(enrichment_ids)
    rows: list[dict] = []

    for order_id, uc_row in uc_index.items():
        sap_row = sap_index.get(order_id)
        uc_total = float(uc_row.get("uc_total") or 0)
        base = {
            "order_id": order_id,
            "channel": uc_row.get("channel") or "",
            "facility": uc_row.get("facility") or "",
            "uc_order_date": uc_row.get("order_date") or "",
            "uc_taxable": float(uc_row.get("uc_taxable") or 0),
            "uc_shipping": float(uc_row.get("uc_shipping") or 0),
            "uc_cgst": float(uc_row.get("uc_cgst") or 0),
            "uc_sgst": float(uc_row.get("uc_sgst") or 0),
            "uc_igst": float(uc_row.get("uc_igst") or 0),
            "uc_total": uc_total,
            "compare_scope": "posted_compare" if compare_posted_only else "all_completed",
            "comparison_available": True,
        }
        if sap_row:
            sap_total = float(sap_row.get("sap_total") or 0)
            total_diff = round(uc_total - sap_total, 2)
            status = "matched" if abs(total_diff) <= _AMOUNT_TOLERANCE else "amount_mismatch"
            post_then_match_code, post_then_match_label, post_then_match_tone = _classify_post_then_match(status)
            base.update(
                {
                    "sap_docnum": sap_row.get("sap_docnums") or "",
                    "sap_series": sap_row.get("sap_series") or "",
                    "sap_customer_code": sap_row.get("sap_customer_code") or "",
                    "sap_customer_name": sap_row.get("sap_customer_name") or "",
                    "sap_doc_date": sap_row.get("sap_doc_date") or "",
                    "sap_taxable": float(sap_row.get("sap_taxable") or 0),
                    "sap_cgst": float(sap_row.get("sap_cgst") or 0),
                    "sap_sgst": float(sap_row.get("sap_sgst") or 0),
                    "sap_igst": float(sap_row.get("sap_igst") or 0),
                    "sap_total": sap_total,
                    "total_diff": total_diff,
                    "status": status,
                    "reason_code": "",
                    "reason_label": "",
                    "post_then_match_code": post_then_match_code,
                    "post_then_match_label": post_then_match_label,
                    "post_then_match_tone": post_then_match_tone,
                }
            )
        else:
            info = enrichment.get(order_id) or {}
            reason_code, reason_label = _classify_missing_reason(info)
            post_then_match_code, post_then_match_label, post_then_match_tone = _classify_post_then_match("missing_in_sap", info)
            base.update(
                {
                    "sap_docnum": (info.get("sap_ar_invoice_docnum") or "") if info else "",
                    "sap_series": "",
                    "sap_customer_code": "",
                    "sap_customer_name": "",
                    "sap_doc_date": "",
                    "sap_taxable": 0.0,
                    "sap_cgst": 0.0,
                    "sap_sgst": 0.0,
                    "sap_igst": 0.0,
                    "sap_total": 0.0,
                    "total_diff": round(uc_total, 2),
                    "status": "missing_in_sap",
                    "reason_code": reason_code,
                    "reason_label": reason_label,
                    "pipeline_status": info.get("pipeline_status") if info else "",
                    "last_error": (info.get("last_error") or "")[:500] if info else "",
                    "attempt_count": int(info.get("attempt_count") or 0) if info else 0,
                    "posting_started_at": str(info.get("posting_started_at") or "") if info else "",
                    "uc_order_name": info.get("name") if info else "",
                    "post_then_match_code": post_then_match_code,
                    "post_then_match_label": post_then_match_label,
                    "post_then_match_tone": post_then_match_tone,
                }
            )
        rows.append(base)

    if compare_posted_only:
        for order_id, uc_row in uc_index_all.items():
            if order_id in posted_order_id_set:
                continue
            info = enrichment.get(order_id) or {}
            sap_row = sap_index.get(order_id)
            uc_total = float(uc_row.get("uc_total") or 0)
            base = {
                "order_id": order_id,
                "channel": uc_row.get("channel") or "",
                "facility": uc_row.get("facility") or "",
                "uc_order_date": uc_row.get("order_date") or "",
                "uc_taxable": float(uc_row.get("uc_taxable") or 0),
                "uc_shipping": float(uc_row.get("uc_shipping") or 0),
                "uc_cgst": float(uc_row.get("uc_cgst") or 0),
                "uc_sgst": float(uc_row.get("uc_sgst") or 0),
                "uc_igst": float(uc_row.get("uc_igst") or 0),
                "uc_total": uc_total,
                "status": "not_posted",
                "pipeline_status": info.get("pipeline_status") if info else "",
                "last_error": (info.get("last_error") or "")[:500] if info else "",
                "attempt_count": int(info.get("attempt_count") or 0) if info else 0,
                "posting_started_at": str(info.get("posting_started_at") or "") if info else "",
                "uc_order_name": info.get("name") if info else "",
                "comparison_available": False,
            }
            if sap_row:
                sap_total = float(sap_row.get("sap_total") or 0)
                total_diff = round(uc_total - sap_total, 2)
                if abs(total_diff) <= _AMOUNT_TOLERANCE:
                    post_then_match_code = "sap_exists_amount_aligned"
                    post_then_match_label = "Yes — amounts align, but posting state is stale"
                    post_then_match_tone = "warn"
                else:
                    post_then_match_code = "sap_exists_amount_mismatch"
                    post_then_match_label = "No — SAP invoice exists and the amounts differ"
                    post_then_match_tone = "bad"
                rows.append(
                    {
                        **base,
                        "sap_docnum": sap_row.get("sap_docnums") or "",
                        "sap_series": sap_row.get("sap_series") or "",
                        "sap_customer_code": sap_row.get("sap_customer_code") or "",
                        "sap_customer_name": sap_row.get("sap_customer_name") or "",
                        "sap_doc_date": sap_row.get("sap_doc_date") or "",
                        "sap_taxable": float(sap_row.get("sap_taxable") or 0),
                        "sap_cgst": float(sap_row.get("sap_cgst") or 0),
                        "sap_sgst": float(sap_row.get("sap_sgst") or 0),
                        "sap_igst": float(sap_row.get("sap_igst") or 0),
                        "sap_total": sap_total,
                        "total_diff": total_diff,
                        "reason_code": "sap_invoice_exists",
                        "reason_label": "Excluded from posted-only comparison because the order is not marked posted in Frappe, but a SAP invoice already exists.",
                        "compare_scope": "not_posted_state_mismatch",
                        "post_then_match_code": post_then_match_code,
                        "post_then_match_label": post_then_match_label,
                        "post_then_match_tone": post_then_match_tone,
                    }
                )
                continue

            reason_code, _ = _classify_missing_reason(info)
            post_then_match_code, post_then_match_label, post_then_match_tone = _classify_post_then_match("not_posted", info)
            rows.append(
                {
                    **base,
                    "sap_docnum": "",
                    "sap_series": "",
                    "sap_customer_code": "",
                    "sap_customer_name": "",
                    "sap_doc_date": "",
                    "sap_taxable": None,
                    "sap_cgst": None,
                    "sap_sgst": None,
                    "sap_igst": None,
                    "sap_total": None,
                    "total_diff": None,
                    "reason_code": reason_code,
                    "reason_label": "Excluded from posted-only comparison because the order is not posted to SAP yet.",
                    "compare_scope": "not_posted_excluded",
                    "post_then_match_code": post_then_match_code,
                    "post_then_match_label": post_then_match_label,
                    "post_then_match_tone": post_then_match_tone,
                }
            )

    sap_only_ids = [
        oid
        for oid in sap_index.keys()
        if oid not in uc_index and not (compare_posted_only and oid in uc_index_all)
    ]
    sap_only_frappe = _enrich_missing_with_pipeline(sap_only_ids)

    for order_id, sap_row in sap_index.items():
        if order_id in uc_index or (compare_posted_only and order_id in uc_index_all):
            continue
        sap_total = float(sap_row.get("sap_total") or 0)
        frappe_info = sap_only_frappe.get(order_id) or {}

        if frappe_info:
            frappe_order_date = str(frappe_info.get("order_date") or "")
            if _date_outside_window(frappe_order_date, str(start_date or ""), str(end_date or "")):
                row_status = "uc_order_outside_export_window"
                reason_code = "uc_order_outside_export_window"
                reason_label = (
                    "Order exists in Unicommerce (Frappe) but its order date falls "
                    "outside this reconciliation window — SAP invoice was posted cross-period"
                )
            else:
                row_status = "missing_in_uc"
                reason_code = "uc_export_missing_order"
                reason_label = (
                    "Order exists in Frappe within this window, but it is missing "
                    "from the UC export workbook used for this reconciliation run"
                )
        else:
            row_status = "missing_in_uc"
            reason_code = "no_matching_uc_order"
            reason_label = "SAP invoice references a UC order ID that does not exist in Frappe at all"

        post_then_match_code, post_then_match_label, post_then_match_tone = _classify_post_then_match(row_status, frappe_info)
        rows.append(
            {
                "order_id": order_id,
                "channel": "",
                "facility": "",
                "uc_order_date": str(frappe_info.get("order_date") or "") if frappe_info else "",
                "uc_taxable": 0.0,
                "uc_shipping": 0.0,
                "uc_cgst": 0.0,
                "uc_sgst": 0.0,
                "uc_igst": 0.0,
                "uc_total": 0.0,
                "sap_docnum": sap_row.get("sap_docnums") or "",
                "sap_series": sap_row.get("sap_series") or "",
                "sap_customer_code": sap_row.get("sap_customer_code") or "",
                "sap_customer_name": sap_row.get("sap_customer_name") or "",
                "sap_doc_date": sap_row.get("sap_doc_date") or "",
                "sap_taxable": float(sap_row.get("sap_taxable") or 0),
                "sap_cgst": float(sap_row.get("sap_cgst") or 0),
                "sap_sgst": float(sap_row.get("sap_sgst") or 0),
                "sap_igst": float(sap_row.get("sap_igst") or 0),
                "sap_total": sap_total,
                "total_diff": round(-sap_total, 2),
                "status": row_status,
                "reason_code": reason_code,
                "reason_label": reason_label,
                "pipeline_status": frappe_info.get("pipeline_status") if frappe_info else "",
                "uc_order_name": frappe_info.get("name") if frappe_info else "",
                "last_error": "",
                "attempt_count": 0,
                "posting_started_at": "",
                "compare_scope": "posted_compare" if compare_posted_only else "all_completed",
                "comparison_available": True,
                "post_then_match_code": post_then_match_code,
                "post_then_match_label": post_then_match_label,
                "post_then_match_tone": post_then_match_tone,
            }
        )

    priority = {
        "amount_mismatch": 0,
        "missing_in_sap": 1,
        "not_posted": 2,
        "missing_in_uc": 3,
        "uc_order_outside_export_window": 4,
        "matched": 5,
    }
    rows.sort(
        key=lambda r: (
            priority.get(r.get("status", ""), 9),
            -abs(float(r.get("total_diff") or 0)),
            str(r.get("order_id") or ""),
        )
    )

    from collections import Counter

    status_counts = Counter(r["status"] for r in rows)
    missing_reason_counts = Counter(
        r.get("reason_code") or "unknown" for r in rows if r["status"] == "missing_in_sap"
    )
    not_posted_reason_counts = Counter(
        r.get("reason_code") or "unknown" for r in rows if r["status"] == "not_posted"
    )
    compare_rows = [r for r in rows if r.get("comparison_available", True)]
    uc_total_sum = round(sum(float(r.get("uc_total") or 0) for r in compare_rows), 2)
    sap_total_sum = round(sum(float(r.get("sap_total") or 0) for r in compare_rows), 2)

    summary = {
        "uc_order_count": int(len(uc_index)),
        "uc_order_count_all": int(len(uc_index_all)),
        "sap_order_count": int(len(sap_index)),
        "matched": int(status_counts.get("matched", 0)),
        "amount_mismatch": int(status_counts.get("amount_mismatch", 0)),
        "missing_in_sap": int(status_counts.get("missing_in_sap", 0)),
        "not_posted": int(status_counts.get("not_posted", 0)),
        "not_posted_blocked": int(
            sum(1 for r in rows if r.get("status") == "not_posted" and r.get("post_then_match_tone") == "bad")
        ),
        "not_posted_pending": int(
            sum(1 for r in rows if r.get("status") == "not_posted" and r.get("post_then_match_tone") in {"warn", "info"})
        ),
        "missing_in_uc": int(status_counts.get("missing_in_uc", 0)),
        "uc_order_outside_export_window": int(status_counts.get("uc_order_outside_export_window", 0)),
        "missing_in_sap_by_reason": dict(missing_reason_counts),
        "not_posted_by_reason": dict(not_posted_reason_counts),
        "sap_lines_without_uc_order_id": int(len(sap_without_uc_key) if sap_without_uc_key is not None else 0),
        "uc_total": uc_total_sum,
        "sap_total": sap_total_sum,
        "total_diff": round(uc_total_sum - sap_total_sum, 2),
        "posted_only_mode": bool(compare_posted_only),
    }
    return rows, summary


# ---------------------------------------------------------------------------
# Returns / Credit Note summary
# ---------------------------------------------------------------------------

def _build_cn_summary_from_frappe(start_date: str, end_date: str):
    """Build a per-channel credit note summary from posted UC Credit Note Staging records.

    Uses the order_date window (same as invoices) so the returns sheet covers the
    same period as the invoice reconciliation. Returns an empty DataFrame if there
    are no posted credit notes for the window.
    """
    import pandas as pd

    try:
        rows = frappe.db.sql(
            """
            SELECT
                o.channel_name                                                      AS channel,
                COUNT(cn.name)                                                      AS return_count,
                SUM(IFNULL(o.ar_creditnote_unit_price_actual, 0))                  AS net_value,
                SUM(IFNULL(o.ar_creditnote_tax_actual, 0))                         AS tax_total,
                SUM(
                    IFNULL(o.ar_creditnote_unit_price_actual, 0)
                    + IFNULL(o.ar_creditnote_tax_actual, 0)
                )                                                                   AS gross_total
            FROM `tabUC Credit Note Staging` cn
            JOIN `tabUnicommerce Orders` o ON cn.uc_order_id = o.name
            WHERE cn.status = 'posted'
              AND o.order_date BETWEEN %(start)s AND %(end)s
            GROUP BY o.channel_name
            ORDER BY gross_total DESC
            """,
            {"start": start_date, "end": end_date},
            as_dict=True,
        )
    except Exception as exc:
        frappe.logger().warning(f"GST recon: CN summary query failed: {exc}")
        return pd.DataFrame(columns=["Channel", "Returns", "Net Value (ex-tax)", "Tax", "Gross Total"])

    if not rows:
        return pd.DataFrame(columns=["Channel", "Returns", "Net Value (ex-tax)", "Tax", "Gross Total"])

    df = pd.DataFrame(rows)
    df = df.rename(columns={
        "channel": "Channel",
        "return_count": "Returns",
        "net_value": "Net Value (ex-tax)",
        "tax_total": "Tax",
        "gross_total": "Gross Total",
    })
    for col in ("Net Value (ex-tax)", "Tax", "Gross Total"):
        df[col] = df[col].round(2)

    total_row = pd.DataFrame([{
        "Channel": "TOTAL",
        "Returns": int(df["Returns"].sum()),
        "Net Value (ex-tax)": round(float(df["Net Value (ex-tax)"].sum()), 2),
        "Tax": round(float(df["Tax"].sum()), 2),
        "Gross Total": round(float(df["Gross Total"].sum()), 2),
    }])
    return pd.concat([df, total_row], ignore_index=True)


# ---------------------------------------------------------------------------
# Workbook output
# ---------------------------------------------------------------------------

def _persist_recon_workbook(
    uc_master,
    uc_pivot,
    sap_raw,
    sap_pivot,
    side_by_side,
    per_order_rows,
    per_order_summary,
    start_date,
    end_date,
    cn_summary=None,
):
    import pandas as pd

    output_dir = frappe.get_site_path("private", "files", "gst_reconciliation")
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"gst_reconciliation_{start_date}_{end_date}_{timestamp}.xlsx"
    abs_path = os.path.join(output_dir, filename)

    side_df = pd.DataFrame(side_by_side or [])
    if not side_df.empty:
        side_df["uc_channels"] = side_df["uc_channels"].apply(lambda v: ", ".join(v) if isinstance(v, list) else v)
        side_df["uc_facilities"] = side_df["uc_facilities"].apply(lambda v: ", ".join(v) if isinstance(v, list) else v)

    per_order_df = pd.DataFrame(per_order_rows or [])
    # Render a compact summary sheet for the per-order reason breakdown.
    per_order_summary_df = pd.DataFrame()
    if per_order_summary:
        rows = [
            {"metric": "UC orders (completed, in window)", "value": per_order_summary.get("uc_order_count", 0)},
            {"metric": "UC orders (all completed, in window)", "value": per_order_summary.get("uc_order_count_all", 0)},
            {"metric": "SAP invoices (with UC Order ID, in window)", "value": per_order_summary.get("sap_order_count", 0)},
            {"metric": "Matched", "value": per_order_summary.get("matched", 0)},
            {"metric": "Amount mismatch", "value": per_order_summary.get("amount_mismatch", 0)},
            {"metric": "Missing in SAP", "value": per_order_summary.get("missing_in_sap", 0)},
            {"metric": "Not posted (excluded from compare)", "value": per_order_summary.get("not_posted", 0)},
            {"metric": "Not posted — blocked", "value": per_order_summary.get("not_posted_blocked", 0)},
            {"metric": "Not posted — pending", "value": per_order_summary.get("not_posted_pending", 0)},
            {"metric": "Missing in UC (SAP-only)", "value": per_order_summary.get("missing_in_uc", 0)},
            {"metric": "SAP lines without UC Order ID", "value": per_order_summary.get("sap_lines_without_uc_order_id", 0)},
            {"metric": "UC total (₹)", "value": per_order_summary.get("uc_total", 0)},
            {"metric": "SAP total (₹)", "value": per_order_summary.get("sap_total", 0)},
            {"metric": "Total Δ (UC − SAP)", "value": per_order_summary.get("total_diff", 0)},
        ]
        reasons = per_order_summary.get("missing_in_sap_by_reason") or {}
        for reason, count in sorted(reasons.items(), key=lambda kv: -kv[1]):
            rows.append({"metric": f"  missing_in_sap ∙ {reason}", "value": count})
        not_posted_reasons = per_order_summary.get("not_posted_by_reason") or {}
        for reason, count in sorted(not_posted_reasons.items(), key=lambda kv: -kv[1]):
            rows.append({"metric": f"  not_posted ∙ {reason}", "value": count})
        per_order_summary_df = pd.DataFrame(rows)

    summary_df = pd.DataFrame(
        [
            {
                "start_date": start_date,
                "end_date": end_date,
                "generated_at": str(now_datetime()),
                "uc_master_rows": int(0 if uc_master is None else len(uc_master)),
                "uc_pivot_rows": int(0 if uc_pivot is None else len(uc_pivot)),
                "sap_raw_rows": int(0 if sap_raw is None else len(sap_raw)),
                "sap_pivot_rows": int(0 if sap_pivot is None else len(sap_pivot)),
                "side_by_side_rows": int(len(side_by_side or [])),
                "per_order_rows": int(len(per_order_rows or [])),
            }
        ]
    )

    with pd.ExcelWriter(abs_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, index=False, sheet_name="Summary")
        if not per_order_summary_df.empty:
            per_order_summary_df.to_excel(writer, index=False, sheet_name="Per-Order Summary")
        if uc_pivot is not None and not uc_pivot.empty:
            uc_pivot.to_excel(writer, index=False, sheet_name="UC Pivot")
        if sap_pivot is not None and not sap_pivot.empty:
            sap_pivot.to_excel(writer, index=False, sheet_name="SAP Pivot")
        if cn_summary is not None and not cn_summary.empty:
            cn_summary.to_excel(writer, index=False, sheet_name="Returns Summary")
        if not side_df.empty:
            side_df.to_excel(writer, index=False, sheet_name="Side By Side")
        if not per_order_df.empty:
            # Put the actionable columns first so the user can scan the sheet easily.
            preferred = [
                "status",
                "reason_code",
                "reason_label",
                "post_then_match_code",
                "post_then_match_label",
                "post_then_match_tone",
                "compare_scope",
                "comparison_available",
                "order_id",
                "channel",
                "facility",
                "uc_order_date",
                "uc_taxable",
                "uc_shipping",
                "uc_cgst",
                "uc_sgst",
                "uc_igst",
                "uc_total",
                "sap_docnum",
                "sap_series",
                "sap_customer_code",
                "sap_customer_name",
                "sap_doc_date",
                "sap_taxable",
                "sap_cgst",
                "sap_sgst",
                "sap_igst",
                "sap_total",
                "total_diff",
                "pipeline_status",
                "attempt_count",
                "last_error",
                "posting_started_at",
                "uc_order_name",
            ]
            ordered = [c for c in preferred if c in per_order_df.columns]
            extra = [c for c in per_order_df.columns if c not in ordered]
            per_order_df = per_order_df[ordered + extra]
            per_order_df.head(1_000_000).to_excel(writer, index=False, sheet_name="Per-Order Diff")
        if uc_master is not None and not uc_master.empty:
            uc_master_out = uc_master.drop(
                columns=[c for c in uc_master.columns if str(c).startswith("__")],
                errors="ignore",
            )
            # Excel sheets cap at ~1M rows; truncate if necessary.
            uc_master_out.head(1_000_000).to_excel(writer, index=False, sheet_name="UC Master Data")
        if sap_raw is not None and not sap_raw.empty:
            sap_raw.head(1_000_000).to_excel(writer, index=False, sheet_name="SAP GSTR1 Raw")

    return {"absolute_path": abs_path, "filename": filename, "directory": output_dir}


def _cache_snapshot(snapshot: dict) -> None:
    """Persist the recon snapshot with a status-dependent TTL.

    Terminal states live for `_TTL_TERMINAL_SEC` so the UI can keep showing
    the last outcome across restarts. In-flight states use the much shorter
    `_TTL_INFLIGHT_SEC` so a crashed worker doesn't permanently block the
    concurrency guard.
    """
    status = (snapshot.get("status") or "").lower()
    ttl = _TTL_TERMINAL_SEC if status in _TERMINAL_STATUSES else _TTL_INFLIGHT_SEC
    frappe.cache().set_value(
        GST_RECON_LAST_RUN_CACHE_KEY,
        json.dumps(snapshot, default=str),
        expires_in_sec=ttl,
    )


def _cache_file(file_info: dict) -> None:
    frappe.cache().set_value(
        GST_RECON_LAST_FILE_CACHE_KEY,
        json.dumps(file_info, default=str),
        expires_in_sec=_TTL_TERMINAL_SEC,
    )


def _load_snapshot() -> dict:
    raw = frappe.cache().get_value(GST_RECON_LAST_RUN_CACHE_KEY)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _load_file_info() -> dict:
    raw = frappe.cache().get_value(GST_RECON_LAST_FILE_CACHE_KEY)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _update_progress(running_snapshot: dict, payload: dict) -> None:
    """Merge a progress payload onto whatever snapshot is currently cached.

    This reads the *current* cached snapshot (not the stale base snapshot) so
    that once `run_gst_reconciliation` has cached its final results we don't
    overwrite `status=matched/mismatch` + `side_by_side` etc. with a bare
    running snapshot when the last "complete" progress event fires.
    """
    current = _load_snapshot() or dict(running_snapshot)
    snap = dict(current)
    snap.setdefault("job", running_snapshot.get("job"))
    snap.setdefault("window", running_snapshot.get("window"))
    if not snap.get("status"):
        snap["status"] = "running"
    snap["generated_at"] = str(now_datetime())
    snap["progress"] = payload or {}
    log_lines = list((snap.get("progress_log") or [])[-99:])
    label = (payload or {}).get("label") or ""
    if label:
        stamp = f"{now_datetime().strftime('%H:%M:%S')}  {label}"
        if not log_lines or log_lines[-1] != stamp:
            log_lines.append(stamp)
    snap["progress_log"] = log_lines[-100:]
    _cache_snapshot(snap)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_iso_date(value: str, label: str) -> str:
    """Validate ``YYYY-MM-DD`` and reject any other format.

    Used as a defence-in-depth check before the date is interpolated into the
    HANA SQL template. `gst_reconciliation_run_async` already normalises
    dates, but direct callers (scripts, background jobs) could bypass that.
    """
    text = (value or "").strip()
    if not _DATE_RE.match(text):
        raise ValueError(f"{label} must be YYYY-MM-DD, got: {value!r}")
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{label} is not a valid calendar date: {value!r}") from exc
    return text


def run_gst_reconciliation(
    start_date: str,
    end_date: str,
    progress_hook: Callable[[dict], None] | None = None,
    email_to: str | None = None,
    posted_only: bool = False,
    compare_mode: str = "finance_month",
) -> dict:
    """Full UC vs SAP GST reconciliation for the supplied YYYY-MM-DD range.

    On completion the snapshot is cached at ``GST_RECON_LAST_RUN_CACHE_KEY``
    and the xlsx file metadata at ``GST_RECON_LAST_FILE_CACHE_KEY``.

    If ``email_to`` is provided AND the run finishes with
    ``status in {matched, mismatch}``, a summary email (with the xlsx attached)
    is sent via ``_send_recon_email``. Failures are NOT emailed — they surface
    in the UI via a ``status=error`` snapshot.

    Any unhandled exception is caught, logged to Frappe's Error Log, and
    cached as a terminal ``status=error`` snapshot so the Ops Center polling
    loop can clear the in-flight state.
    """
    from .uc_export import process_monthly_export_with_download
    from .hana.hana_query_engine import generate_gstr1_revenue_report_readonly

    start_date = _validate_iso_date(start_date, "start_date")
    end_date = _validate_iso_date(end_date, "end_date")
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date")
    mode = str(compare_mode or "finance_month").strip().lower()
    if mode not in {"finance_month", "order_id_trace"}:
        raise ValueError(f"compare_mode must be one of finance_month/order_id_trace, got: {compare_mode!r}")
    effective_posted_only = bool(posted_only) or mode == "order_id_trace"

    clean_email = (email_to or "").strip() or None

    base_snapshot = {
        "status": "running",
        "job": "run_gst_reconciliation",
        "window": {"start_date": start_date, "end_date": end_date},
        "email_to": clean_email,
        "posted_only": effective_posted_only,
        "compare_mode": mode,
        "generated_at": str(now_datetime()),
    }
    _cache_snapshot(base_snapshot)

    def _hook(payload: dict) -> None:
        _emit(progress_hook, payload)
        _update_progress(base_snapshot, payload)

    try:
        snapshot = _run_gst_reconciliation_body(
            start_date,
            end_date,
            base_snapshot,
            _hook,
            process_monthly_export_with_download,
            generate_gstr1_revenue_report_readonly,
            posted_only=effective_posted_only,
            compare_mode=mode,
        )
    except Exception as exc:
        frappe.log_error(frappe.get_traceback(), "GST Recon Run Failed")
        error_snapshot = dict(base_snapshot)
        error_snapshot.update({
            "status": "error",
            "error_message": str(exc)[:500],
            "generated_at": str(now_datetime()),
        })
        _cache_snapshot(error_snapshot)
        _hook({"stage": "error", "label": f"Reconciliation failed: {str(exc)[:200]}"})
        raise

    if clean_email and snapshot.get("status") in {"matched", "mismatch"}:
        try:
            _send_recon_email(clean_email, snapshot)
            _hook({"stage": "email_sent", "label": f"Summary email queued to {clean_email}"})
        except Exception:
            frappe.log_error(frappe.get_traceback(), "GST Recon Email")
            _hook({"stage": "email_failed", "label": f"Summary email to {clean_email} failed (see Error Log)"})

    return snapshot


def _run_gst_reconciliation_body(
    start_date: str,
    end_date: str,
    base_snapshot: dict,
    _hook: Callable[[dict], None],
    process_monthly_export_with_download,
    generate_gstr1_revenue_report_readonly,
    posted_only: bool = False,
    compare_mode: str = "finance_month",
) -> dict:
    """Actual reconciliation pipeline (extracted so ``run_gst_reconciliation``
    only deals with error handling + email)."""
    mode_label = " (posted-to-SAP orders only)" if posted_only else ""
    if compare_mode == "order_id_trace":
        mode_label += " [Order-ID Trace]"
    _hook({"stage": "starting", "label": f"Starting GST reconciliation for {start_date} → {end_date}{mode_label}"})

    # 1) UC export ---------------------------------------------------------
    _hook({"stage": "uc_export", "label": "Triggering UC sale-orders export per facility"})
    export_start_date = add_to_date(start_date, days=-1)
    export_end_date = add_to_date(end_date, days=1)

    import pandas as _pd

    uc_export_failed = False
    export_result: dict = {}
    excel_path = ""

    try:
        export_result = process_monthly_export_with_download(
            start_date=export_start_date,
            end_date=export_end_date,
            skip_validation=True,
            include_runtime_updates=1,
            progress_hook=_hook,
            send_email=False,
        )
        merged_excel = (export_result.get("merged_file") or {}).get("excel_file") or {}
        excel_path = merged_excel.get("absolute_path") or merged_excel.get("path") or ""
        if not excel_path or not os.path.exists(excel_path):
            for cand in [
                os.path.join(frappe.utils.get_bench_path(), "sites", excel_path or ""),
                os.path.join(frappe.utils.get_bench_path(), excel_path or ""),
            ]:
                if cand and os.path.exists(cand):
                    excel_path = cand
                    break
        if not excel_path or not os.path.exists(excel_path):
            uc_export_failed = True
            _hook({"stage": "uc_export", "label": "UC export file not found — will use Frappe posted-order data as UC source"})
    except Exception as export_exc:
        uc_export_failed = True
        _hook({"stage": "uc_export", "label": f"UC export failed ({str(export_exc)[:120]}) — falling back to Frappe posted-order data"})
        frappe.logger().warning(f"GST recon: UC export failed, activating Frappe-only fallback: {export_exc}")

    channel_series_map = _get_channel_series_map()

    if uc_export_failed:
        # Frappe-only fallback: UC side of the comparison will be built from
        # posted Unicommerce Orders rows rather than the UC Excel export.
        # Force posted_only=True so _posted_uc_buckets_from_frappe is used
        # for the side-by-side comparison.
        uc_master = _pd.DataFrame()
        uc_clean = _pd.DataFrame()
        uc_pivot = _pd.DataFrame(columns=["Channel", "Taxable Value", "CGST", "SGST", "IGST", "Shipping Charges", "Total"])
        posted_only = True
    else:
        _hook({"stage": "uc_read", "label": "Reading UC export workbook"})
        uc_master = _read_uc_master_dataframe(excel_path)
        uc_pivot, uc_clean = _build_uc_pivot(uc_master, channel_series_map, progress_hook=_hook)
        uc_clean = _filter_uc_clean_to_window(uc_clean, start_date, end_date)
        uc_pivot = _build_uc_pivot_from_clean(uc_clean)

    uc_compare_clean = uc_clean
    uc_compare_pivot = uc_pivot

    # 2) SAP HANA ----------------------------------------------------------
    sap_series_filter = _get_sap_series_filter()
    if compare_mode == "order_id_trace":
        sap_series_filter = []
    sap_query_start = start_date
    sap_query_end = end_date
    if compare_mode == "order_id_trace":
        sap_query_start = add_to_date(start_date, days=-365)
        sap_query_end = add_to_date(end_date, days=365)
    _hook(
        {
            "stage": "sap_query",
            "label": (
                f"Running HANA GSTR1 query for series {', '.join(sap_series_filter)} "
                f"({sap_query_start} → {sap_query_end})"
            ),
        }
    )
    sap_raw = generate_gstr1_revenue_report_readonly(sap_query_start, sap_query_end)
    sap_compare_raw = sap_raw

    posted_order_ids: set[str] | None = None
    uc_candidate_ids: set[str] = set()
    posted_side_buckets = None
    notices: list[str] = []
    if uc_export_failed:
        notices.append(
            "UC Excel export was unavailable — UC-side comparison uses Frappe posted-order data. "
            "Per-order diff and side-by-side are still available via Frappe data source."
        )
    if compare_mode == "order_id_trace":
        notices.append(
            "Order-ID Trace mode active: UC orders are traced by order_id; SAP compare window is widened and series restriction is disabled to include cross-month postings."
        )
    if posted_only:
        _hook({"stage": "per_order_lookup", "label": "Fetching posted order IDs from Unicommerce Orders doctype"})
        try:
            uc_order_agg = _aggregate_uc_by_order(uc_clean)
            if uc_order_agg is not None and not uc_order_agg.empty and "order_id" in uc_order_agg.columns:
                uc_candidate_ids = {
                    str(v).strip()
                    for v in uc_order_agg["order_id"].tolist()
                    if str(v).strip()
                }
        except Exception:
            uc_candidate_ids = set()
        if uc_candidate_ids:
            posted_order_ids = _get_posted_order_ids(
                start_date,
                end_date,
                candidate_order_ids=uc_candidate_ids,
            )
        else:
            posted_order_ids = _get_posted_order_ids(start_date, end_date)
            if posted_order_ids:
                notices.append(
                    "UC export has no usable order rows in the compare window; fallback scope uses posted Frappe orders for SAP comparison."
                )
                _hook({
                    "stage": "per_order_lookup",
                    "label": (
                        "UC scope is empty; using posted-order fallback with "
                        f"{len(posted_order_ids):,} orders"
                    ),
                })
        scope_label = "current UC scope" if uc_candidate_ids else "fallback posted-order scope"
        _hook({
            "stage": "per_order_lookup",
            "label": f"Found {len(posted_order_ids):,} posted order IDs in {scope_label} — restricting pivots + compare",
        })
        try:
            posted_side_buckets = _posted_uc_buckets_from_frappe(
                start_date,
                end_date,
                channel_customer_map=_get_channel_customer_map(),
                channel_series_map=channel_series_map,
                candidate_order_ids=uc_candidate_ids if uc_candidate_ids else None,
            )
        except Exception as exc:
            posted_side_buckets = None
            notices.append(f"Posted-only side totals fallback failed; using UC export buckets ({str(exc)[:120]})")
        uc_compare_clean = _filter_uc_clean_to_order_ids(uc_clean, posted_order_ids)
        uc_compare_pivot = _build_uc_pivot_from_clean(uc_compare_clean)
        sap_compare_raw = _filter_sap_raw_to_order_ids(sap_raw, posted_order_ids)

    sap_pivot, _sap_clean = _build_sap_pivot(sap_compare_raw, sap_series_filter, progress_hook=_hook)

    # 3) Side-by-side ------------------------------------------------------
    _hook({"stage": "compare", "label": "Building side-by-side comparison"})
    channel_customer_map = _get_channel_customer_map()
    side_rows = _build_side_by_side(
        uc_compare_clean,
        sap_pivot,
        channel_customer_map,
        channel_series_map,
        uc_buckets_override=posted_side_buckets if posted_only else None,
    )

    # 3b) Per-order diff ---------------------------------------------------

    _hook({"stage": "per_order", "label": "Joining UC orders to SAP invoices (1-to-1 via U_Order)"})
    try:
        per_order_rows, per_order_summary = _build_per_order_diff(
            uc_clean, sap_compare_raw, sap_series_filter, progress_hook=_hook,
            posted_order_ids=posted_order_ids,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as exc:
        frappe.logger().exception("GST recon: per-order diff failed")
        per_order_rows, per_order_summary = [], {"error": str(exc)[:500]}

    # 4) Workbook ----------------------------------------------------------
    _hook({"stage": "workbook", "label": "Saving reconciliation workbook"})
    _hook({"stage": "workbook", "label": "Building Returns / Credit Note summary sheet"})
    try:
        cn_summary = _build_cn_summary_from_frappe(start_date, end_date)
    except Exception as cn_exc:
        frappe.logger().warning(f"GST recon: CN summary failed, skipping Returns sheet: {cn_exc}")
        cn_summary = None
    file_info = _persist_recon_workbook(
        uc_master,
        uc_pivot,
        sap_compare_raw,
        sap_pivot,
        side_rows,
        per_order_rows,
        per_order_summary,
        start_date,
        end_date,
        cn_summary=cn_summary,
    )

    # 5) Snapshot ----------------------------------------------------------
    matched = sum(1 for r in side_rows if r.get("status") == "matched")
    mismatched = sum(1 for r in side_rows if r.get("status") == "amount_mismatch")
    missing_uc = sum(1 for r in side_rows if r.get("status") == "missing_in_uc")
    missing_sap = sum(1 for r in side_rows if r.get("status") == "missing_in_sap")
    unmapped = sum(1 for r in side_rows if r.get("status") == "uc_unmapped")
    po_actionable = sum(
        1 for r in per_order_rows
        if r.get("status") not in ("matched", "uc_order_outside_export_window", "not_posted")
    )
    is_clean = (
        mismatched == 0
        and missing_uc == 0
        and missing_sap == 0
        and unmapped == 0
        and po_actionable == 0
    )

    snapshot = {
        "job": "run_gst_reconciliation",
        "status": "matched" if is_clean else "mismatch",
        "window": {"start_date": start_date, "end_date": end_date},
        "email_to": base_snapshot.get("email_to"),
        "posted_only": posted_only,
        "compare_mode": compare_mode,
        "notices": notices,
        "generated_at": str(now_datetime()),
        "uc": {
            "master_rows": int(len(uc_master) if uc_master is not None else 0),
            "completed_rows": int(len(uc_compare_clean) if uc_compare_clean is not None else 0),
            "completed_rows_all": int(len(uc_clean) if uc_clean is not None else 0),
            "pivot": uc_compare_pivot.to_dict("records") if uc_compare_pivot is not None and not uc_compare_pivot.empty else [],
            "totals": {
                "taxable_value": round(float(uc_compare_pivot["Taxable Value"].sum()) if not uc_compare_pivot.empty else 0, 2),
                "cgst": round(float(uc_compare_pivot["CGST"].sum()) if not uc_compare_pivot.empty else 0, 2),
                "sgst": round(float(uc_compare_pivot["SGST"].sum()) if not uc_compare_pivot.empty else 0, 2),
                "igst": round(float(uc_compare_pivot["IGST"].sum()) if not uc_compare_pivot.empty else 0, 2),
                "shipping": round(float(uc_compare_pivot["Shipping Charges"].sum()) if not uc_compare_pivot.empty else 0, 2),
            },
        },
        "sap": {
            "raw_rows": int(len(sap_compare_raw) if sap_compare_raw is not None else 0),
            "pivot": sap_pivot.to_dict("records") if sap_pivot is not None and not sap_pivot.empty else [],
            "series_filter": sap_series_filter,
            "totals": {
                "taxable_value": round(float(sap_pivot["Taxable Value"].sum()) if not sap_pivot.empty else 0, 2),
                "cgst": round(float(sap_pivot["CGST"].sum()) if not sap_pivot.empty else 0, 2),
                "sgst": round(float(sap_pivot["SGST"].sum()) if not sap_pivot.empty else 0, 2),
                "igst": round(float(sap_pivot["IGST"].sum()) if not sap_pivot.empty else 0, 2),
            },
        },
        "side_by_side": {
            "rows": side_rows,
            "total_rows": len(side_rows),
            "matched": matched,
            "mismatched": mismatched,
            "missing_in_uc": missing_uc,
            "missing_in_sap": missing_sap,
            "uc_unmapped": unmapped,
        },
        "per_order": {
            # Cache actionable rows (not matched, not informational cross-period rows) plus a
            # hard cap so the Redis payload stays reasonable. The downloadable
            # workbook still has the full list in the "Per-Order Diff" sheet.
            "rows": [r for r in per_order_rows if r.get("status") not in ("matched",)][:500],
            "actionable_count": sum(
                1 for r in per_order_rows
                if r.get("status") not in ("matched", "uc_order_outside_export_window", "not_posted")
            ),
            "total_rows": len(per_order_rows),
            "summary": per_order_summary,
        },
        "uc_export_meta": {
            "excel_path": excel_path,
            "export_failed": uc_export_failed,
            "frappe_only_mode": uc_export_failed,
            "export_window_start": export_start_date,
            "export_window_end": export_end_date,
            "compare_window_start": start_date,
            "compare_window_end": end_date,
            "sap_query_window_start": sap_query_start,
            "sap_query_window_end": sap_query_end,
            "report_period_start": export_result.get("report_period_start"),
            "report_period_end": export_result.get("report_period_end"),
            "last_updated": export_result.get("last_updated"),
        },
        "file": file_info,
    }
    _cache_snapshot(snapshot)
    _cache_file(file_info)
    _hook({"stage": "complete", "label": f"Reconciliation finished — status: {snapshot['status']}"})
    return snapshot


def get_last_run_snapshot() -> dict:
    snap = _load_snapshot()
    if not snap:
        return {"status": "not_run", "generated_at": str(now_datetime())}
    return snap


def get_last_run_file() -> dict:
    return _load_file_info()


# ---------------------------------------------------------------------------
# Email delivery
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _valid_email(addr: str) -> bool:
    return bool(addr and _EMAIL_RE.match(addr.strip()))


def _inr(n: Any) -> str:
    try:
        return f"₹{float(n):,.2f}"
    except (TypeError, ValueError):
        return str(n)


def _build_recon_email_body(snapshot: dict, download_url: str | None) -> str:
    """Render the HTML body for the recon completion email.

    Kept separate from ``_send_recon_email`` so the formatting is trivially
    unit-testable without touching Frappe's outgoing mail queue.
    """
    window = snapshot.get("window") or {}
    uc_totals = (snapshot.get("uc") or {}).get("totals") or {}
    sap_totals = (snapshot.get("sap") or {}).get("totals") or {}
    sbs = snapshot.get("side_by_side") or {}
    per_order = snapshot.get("per_order") or {}
    po_summary = per_order.get("summary") or {}

    uc_total = float(uc_totals.get("taxable_value", 0)) + float(uc_totals.get("cgst", 0)) \
        + float(uc_totals.get("sgst", 0)) + float(uc_totals.get("igst", 0)) \
        + float(uc_totals.get("shipping", 0))
    sap_total = float(sap_totals.get("taxable_value", 0)) + float(sap_totals.get("cgst", 0)) \
        + float(sap_totals.get("sgst", 0)) + float(sap_totals.get("igst", 0))

    reason_rows = ""
    for code, count in sorted((po_summary.get("missing_in_sap_by_reason") or {}).items(), key=lambda kv: -kv[1]):
        reason_rows += f"<tr><td>{frappe.utils.escape_html(code)}</td><td style='text-align:right'>{count}</td></tr>"

    link_html = (
        f"<p><a href='{frappe.utils.escape_html(download_url)}'>Download the full workbook</a> "
        "(Frappe login required).</p>"
        if download_url else ""
    )

    status = snapshot.get("status") or ""
    status_label = {
        "matched": "Matched (clean)",
        "mismatch": "Mismatch — review required",
    }.get(status, status)

    return f"""
        <div style='font-family:Inter,Segoe UI,Arial,sans-serif;font-size:13px;color:#111'>
        <h2 style='margin:0 0 6px'>GST Reconciliation — {frappe.utils.escape_html(status_label)}</h2>
        <p style='color:#555;margin:0 0 14px'>
            Window: <strong>{window.get('start_date','')} → {window.get('end_date','')}</strong>
        </p>

        <h3 style='margin:18px 0 6px'>Totals</h3>
        <table cellpadding='6' style='border-collapse:collapse;border:1px solid #e5e7eb'>
            <tr style='background:#f9fafb'><th align='left'>Side</th><th align='right'>Grand Total</th></tr>
            <tr><td>UC (completed orders)</td><td align='right'>{_inr(uc_total)}</td></tr>
            <tr><td>SAP (GSTR1 filtered series)</td><td align='right'>{_inr(sap_total)}</td></tr>
            <tr style='background:#f9fafb'><td><strong>Delta (UC − SAP)</strong></td>
                <td align='right'><strong>{_inr(uc_total - sap_total)}</strong></td></tr>
        </table>

        <h3 style='margin:18px 0 6px'>Channel comparison</h3>
        <table cellpadding='6' style='border-collapse:collapse;border:1px solid #e5e7eb'>
            <tr style='background:#f9fafb'>
                <th align='left'>Matched</th><th align='left'>Amount mismatch</th>
                <th align='left'>Missing in UC</th><th align='left'>Missing in SAP</th><th align='left'>Unmapped</th>
            </tr>
            <tr>
                <td>{sbs.get('matched', 0)}</td>
                <td>{sbs.get('mismatched', 0)}</td>
                <td>{sbs.get('missing_in_uc', 0)}</td>
                <td>{sbs.get('missing_in_sap', 0)}</td>
                <td>{sbs.get('uc_unmapped', 0)}</td>
            </tr>
        </table>

        <h3 style='margin:18px 0 6px'>Per-order diagnostics</h3>
        <p style='margin:0 0 6px'>
            <strong>{po_summary.get('matched', 0)}</strong> matched,
            <strong>{po_summary.get('amount_mismatch', 0)}</strong> amount mismatches,
            <strong>{po_summary.get('missing_in_sap', 0)}</strong> missing in SAP,
            <strong>{po_summary.get('missing_in_uc', 0)}</strong> missing in UC.
        </p>
        {"<table cellpadding='6' style='border-collapse:collapse;border:1px solid #e5e7eb'>"
         "<tr style='background:#f9fafb'><th align='left'>Reason</th><th align='right'>Orders</th></tr>"
         + reason_rows + "</table>" if reason_rows else ""}

        {link_html}

        <p style='color:#6b7280;font-size:11px;margin-top:18px'>
            The full workbook is attached for offline analysis
            (UC Master, UC Pivot, SAP GSTR1 raw, SAP Pivot, Side-by-Side, Per-Order Diff, Per-Order Summary).
            Failures are NOT emailed — check the Ops Center UI for any <code>status=error</code> snapshot.
        </p>
        </div>
    """


def _send_recon_email(email_to: str, snapshot: dict) -> None:
    """Queue a summary email with the reconciliation workbook attached.

    Uses Frappe's outgoing mail queue (``now=False``) so this is a fast,
    fire-and-forget call that returns immediately. The caller wraps this
    in its own try/except.
    """
    if not _valid_email(email_to):
        raise ValueError(f"Invalid recipient email: {email_to!r}")

    file_info = snapshot.get("file") or _load_file_info() or {}
    abs_path = file_info.get("absolute_path") or ""
    filename = file_info.get("filename") or "gst_reconciliation.xlsx"

    attachments: list[dict] = []
    download_url: str | None = None
    if abs_path and os.path.exists(abs_path):
        try:
            with open(abs_path, "rb") as fh:
                attachments.append({"fname": filename, "fcontent": fh.read()})
        except OSError:
            frappe.log_error(frappe.get_traceback(), "GST Recon Email: attachment read failed")

    window = snapshot.get("window") or {}
    subject = (
        f"GST Reconciliation {window.get('start_date','')} → {window.get('end_date','')} "
        f"— {snapshot.get('status','')}"
    ).strip()

    frappe.sendmail(
        recipients=[email_to.strip()],
        subject=subject,
        message=_build_recon_email_body(snapshot, download_url),
        attachments=attachments or None,
        reference_doctype=None,
        reference_name=None,
        now=False,
    )
