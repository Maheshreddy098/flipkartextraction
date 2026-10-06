"""
SAP B1 Service Layer client for UC-SAP integration.

Uses session-based authentication against SAP Service Layer.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

import frappe
import requests
from frappe.utils import add_to_date, now_datetime

# Transient-error retry policy for the primary warehouse-scoped batch-qty lookup.
# Total worst-case wall time per call = 0 + 1 + 5 + 10 = 16 seconds, after which
# we fall through to HANA + local snapshot (still warehouse-scoped) before
# finally returning 0 ("fail closed" → caller will batch_hold the order).
_BATCH_QTY_ODATA_BACKOFFS_SEC: tuple[int, ...] = (0, 1, 5, 10)


def _extract_sap_error_message(resp) -> str:
    """Pull the human-readable text out of a SAP Service Layer error body:
    {"error": {"code": -5002, "message": {"value": "..."}}}

    Falls back to raw response text (no internal URL) if the body isn't in
    that shape, so callers never see a bare "400 Client Error" with nothing
    to act on.
    """
    try:
        body = resp.json()
        message = body.get("error", {}).get("message", {}).get("value")
        if message:
            return str(message)
    except Exception:
        pass
    return (resp.text or "").strip()[:500]


class SAPClient:
    def __init__(self, settings_doctype: str = "SAP Settings"):
        # settings_doctype lets a caller point this client at an isolated
        # settings Single (e.g. "Consumables SAP Settings") instead of the
        # shared "SAP Settings" every other vertical (unicommerce, amazon_us,
        # B2B, safexpress, ...) reads — so one vertical can point at a test
        # company DB without touching what everyone else has live.
        self.settings_doctype = settings_doctype
        self.uc_settings = frappe.get_single("Unicommerce Settings")
        self.sap_settings = frappe.get_single(settings_doctype)
        self.session = requests.Session()
        self._logged_in = False
        self.base_url = self._resolve_base_url()
        # TLS cert verification — defaults to secure (True). Only disable via
        # site_config.json ("sap_sl_verify_ssl": false) for a self-signed SAP
        # Service Layer cert in dev; never hardcode this off.
        self._verify_ssl = bool(frappe.conf.get("sap_sl_verify_ssl", True))

    def _resolve_base_url(self) -> str:
        uc_url = self._safe_get(self.uc_settings, "sap_sl_base_url")
        base_url = (uc_url or self._safe_get(self.sap_settings, "sap_b1_url") or "").strip()
        if not base_url:
            frappe.throw("SAP Service Layer URL is not configured.")
        return base_url.rstrip("/")

    @staticmethod
    def _safe_get(doc: Any, fieldname: str) -> Any:
        # Handles cases where the field is not part of the current DocType schema.
        return getattr(doc, fieldname, None)

    def _credentials(self) -> dict[str, str]:
        company_db = self._safe_get(self.uc_settings, "sap_company_db") or self._safe_get(self.sap_settings, "companydb")
        username = self._safe_get(self.uc_settings, "sap_username") or self._safe_get(self.sap_settings, "username")

        password = None
        if self._safe_get(self.uc_settings, "sap_password"):
            password = self.uc_settings.get_password("sap_password")
        else:
            password = self.sap_settings.get_password("password")

        missing = []
        if not company_db:
            missing.append("CompanyDB")
        if not username:
            missing.append("UserName")
        if not password:
            missing.append("Password")
        if missing:
            frappe.throw(f"SAP credentials missing: {', '.join(missing)}")

        return {
            "CompanyDB": company_db,
            "UserName": username,
            "Password": password,
        }

    def login(self):
        resp = self.session.post(
            f"{self.base_url}/Login",
            json=self._credentials(),
            timeout=30,
            verify=self._verify_ssl,
        )
        resp.raise_for_status()
        try:
            data = resp.json() if resp.text else {}
        except Exception:
            data = {}
        self._persist_login_session(resp, data)
        self._logged_in = True

    def _persist_login_session(self, response: requests.Response, data: dict):
        """Best-effort persistence of SAP session info into SAP Settings."""
        try:
            b1session = str(data.get("SessionId") or response.cookies.get("B1SESSION") or "").strip()
            route_id = str(response.cookies.get("ROUTEID") or "").strip()
            timeout_mins = int(data.get("SessionTimeout") or 30)
            expires_on = add_to_date(now_datetime(), minutes=timeout_mins, as_string=True)
            updates = {
                "b1session": b1session,
                "routeid": route_id,
                "expires_on": expires_on,
            }
            frappe.db.set_value(self.settings_doctype, self.settings_doctype, updates, update_modified=False)
            frappe.db.commit()
        except Exception:
            # Auth must not fail if settings write fails.
            pass

    def _try_restore_session(self) -> bool:
        """Restore a previously saved SAP B1 session from SAP Settings.

        Always reads directly from DB so background jobs see sessions saved
        by previous jobs, not the stale object cached at __init__ time.
        Returns True if a valid, non-expired session was loaded (login skipped).
        """
        try:
            from frappe.utils import get_datetime, add_to_date
            # Direct DB read — bypasses the in-memory sap_settings object so
            # sessions written by a previous background job are always visible.
            vals = frappe.db.get_value(
                self.settings_doctype, self.settings_doctype,
                ["b1session", "routeid", "expires_on"],
                as_dict=True,
            ) or {}
            b1session  = (vals.get("b1session") or "").strip()
            routeid    = (vals.get("routeid")   or "").strip()
            expires_on = vals.get("expires_on")
            if not b1session or not expires_on:
                return False
            # Require at least 3 minutes left so we don't hand a session that
            # will expire mid-request.
            if get_datetime(expires_on) <= get_datetime(add_to_date(now_datetime(), minutes=3)):
                return False
            from requests.cookies import RequestsCookieJar
            jar = RequestsCookieJar()
            jar.set("B1SESSION", b1session)
            if routeid:
                jar.set("ROUTEID", routeid)
            self.session.cookies.update(jar)
            self._logged_in = True
            return True
        except Exception:
            return False

    def _ensure_logged_in(self):
        if not self._logged_in:
            if not self._try_restore_session():
                self.login()

    def post(self, endpoint: str, payload: dict) -> dict:
        self._ensure_logged_in()
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        resp = self.session.post(url, json=payload, timeout=60, verify=self._verify_ssl)
        if resp.status_code == 401:
            # Restored session was rejected — force a fresh login and retry once.
            self._logged_in = False
            self.login()
            resp = self.session.post(url, json=payload, timeout=60, verify=self._verify_ssl)
        if resp.status_code >= 400:
            detail = _extract_sap_error_message(resp)
            raise requests.HTTPError(
                f"SAP error ({resp.status_code}): {detail}",
                response=resp,
            )
        return resp.json() if resp.text else {}

    def get(self, endpoint: str, params: dict | None = None) -> dict:
        self._ensure_logged_in()
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        resp = self.session.get(url, params=params, timeout=30, verify=self._verify_ssl)
        if resp.status_code == 401:
            self._logged_in = False
            self.login()
            resp = self.session.get(url, params=params, timeout=30, verify=self._verify_ssl)
        resp.raise_for_status()
        return resp.json() if resp.text else {}

    @staticmethod
    def _hana_batch_quantity(item_code: str, batch_num: str, whs_code: str) -> float | None:
        """Exact batch quantity from HANA (warehouse + item + batch).
        Returns None when HANA is unavailable or query fails.
        Matches the Amazon_FBA_AL SQL query pattern used in SAP Service Layer.
        """
        try:
            from khanal_tech_integrations.api.common.sap_connector import SAPConnector
            connector = SAPConnector()
            connection, cursor, schema = connector.get_hana_connection()
            try:
                query = f"""
                    SELECT COALESCE(SUM(q."Quantity"), 0)
                    FROM {schema}."OBTQ" q
                    LEFT JOIN {schema}."OBTN" b
                      ON b."ItemCode" = q."ItemCode"
                     AND b."SysNumber" = q."SysNumber"
                    WHERE q."WhsCode" = ?
                      AND q."ItemCode" = ?
                      AND b."DistNumber" = ?
                      AND q."Quantity" > 0
                      AND b."DistNumber" IS NOT NULL
                """
                cursor.execute(query, [whs_code, item_code, batch_num])
                row = cursor.fetchone()
                return float((row[0] if row else 0) or 0)
            finally:
                connector.close_hana_connection(connection, cursor)
        except Exception:
            return None

    def _hana_warehouse_all_batches(self, whs_code: str) -> list[dict]:
        """Return all positive-stock batch rows for an entire warehouse from HANA.
        Uses LEFT JOIN + DistNumber IS NOT NULL (Amazon_FBA_AL pattern).
        FEFO order: ExpDate first, MnfDate as fallback when ExpDate is null.
        """
        try:
            from khanal_tech_integrations.api.common.sap_connector import SAPConnector
            connector = SAPConnector()
            connection, cursor, schema = connector.get_hana_connection()
            try:
                query = f"""
                    SELECT q."ItemCode", b."DistNumber",
                           COALESCE(SUM(q."Quantity"), 0) AS qty,
                           MIN(b."ExpDate") AS exp_date,
                           MIN(b."MnfDate") AS mnf_date
                    FROM {schema}."OBTQ" q
                    LEFT JOIN {schema}."OBTN" b
                      ON b."ItemCode" = q."ItemCode"
                     AND b."SysNumber" = q."SysNumber"
                    WHERE q."WhsCode" = ?
                      AND q."Quantity" > 0
                      AND b."DistNumber" IS NOT NULL
                    GROUP BY q."ItemCode", b."DistNumber"
                    ORDER BY COALESCE(MIN(b."ExpDate"), MIN(b."MnfDate")) ASC NULLS LAST,
                             b."DistNumber" ASC
                """
                cursor.execute(query, [whs_code])
                rows = []
                for row in cursor.fetchall():
                    item_code, batch_num, qty, exp_date, mnf_date = row
                    rows.append({
                        "item_code": str(item_code),
                        "batch_number": str(batch_num),
                        "warehouse_code": whs_code,
                        "quantity": float(qty or 0),
                        "expiry": (exp_date.isoformat() if hasattr(exp_date, "isoformat") else exp_date),
                        "mnf_date": (mnf_date.isoformat() if hasattr(mnf_date, "isoformat") else mnf_date),
                    })
                return rows
            finally:
                connector.close_hana_connection(connection, cursor)
        except Exception as exc:
            frappe.logger().warning("_hana_warehouse_all_batches wh=%s: %s", whs_code, exc)
            return []

    def check_batch_quantity(
        self,
        item_code: str,
        batch_num: str,
        whs_code: str,
        fast_mode: bool = False,
    ) -> float:
        """Return available quantity for a batch in a specific warehouse via HANA.

        STRICT WAREHOUSE SCOPE — never returns a cross-warehouse total.

        ``fast_mode`` is retained for call-site compatibility but has no effect:
        HANA is always used (OData BatchNumberDetails was removed because it
        rejects non-exact filters with HTTP 400 and has up to 16 s retry overhead).
        """
        qty = self._hana_batch_quantity(item_code, batch_num, whs_code)
        if qty is not None:
            return float(qty)
        frappe.logger().warning(
            "check_batch_quantity: HANA unavailable for item=%s batch=%s wh=%s — returning 0",
            item_code, batch_num, whs_code,
        )
        return 0.0

    def bulk_batch_inventory_by_warehouse(
        self,
        whs_code: str,
        item_codes: "list[str] | set[str] | tuple[str, ...]",
        chunk_size: int = 500,
    ) -> "list[dict]":
        """Return batch-level inventory rows for the given items in a single
        warehouse, ordered FEFO (earliest expiry first).

        Uses HANA ``OBTQ`` + ``OBTN`` joined directly so ``IN (...)`` and
        ``ORDER BY`` are fully supported. Shape of each row::

            {
                "item_code":   "FGHN0059",
                "batch_number":"H203406L07A",
                "warehouse_code": "EC-FG",
                "quantity":    40.0,
                "expiry":      "2026-10-31",  # ISO string or None
            }

        Why HANA and not OData: SAP B1 Service Layer's ``BatchNumberDetails``
        endpoint in many installations (including this one) requires
        ``ItemCode eq X and BatchNumber eq Y and WhsCode eq Z`` as three
        equality predicates — it rejects ``IN (...)`` and even
        ``WhsCode``-only filters with HTTP 400, and every 400 triggers the
        full ~16 s retry backoff. HANA has no such restriction and answers
        a 20-item query in ~90 ms, so the pre-validate pre-warm collapses
        from tens of minutes to under a second.

        Failure policy: if HANA is unreachable in the current environment,
        returns an empty list and the caller falls back to the legacy
        per-line ``check_batch_quantity`` path (which uses OData with the
        full three-predicate filter and still works).
        """
        safe_whs = str(whs_code or "").strip()
        cleaned = sorted({str(c or "").strip() for c in (item_codes or []) if str(c or "").strip()})
        if not safe_whs or not cleaned:
            return []

        try:
            from khanal_tech_integrations.api.common.sap_connector import SAPConnector

            connector = SAPConnector()
            connection, cursor, schema = connector.get_hana_connection()
        except Exception as exc:
            frappe.logger().warning(
                "bulk_batch_inventory_by_warehouse: HANA unavailable (%s) — "
                "caller will use per-line OData fallbacks (slow)",
                exc,
            )
            return []

        rows_out: list[dict] = []
        try:
            step = max(1, int(chunk_size))
            for start in range(0, len(cleaned), step):
                chunk = cleaned[start : start + step]
                placeholders = ",".join(["?"] * len(chunk))
                # LEFT JOIN + DistNumber IS NOT NULL matches Amazon_FBA_AL SAP query pattern.
                # FEFO: ExpDate primary, MnfDate fallback (for batches without expiry).
                query = f"""
                    SELECT q."ItemCode",
                           b."DistNumber",
                           COALESCE(SUM(q."Quantity"), 0) AS qty,
                           MIN(b."ExpDate") AS exp_date,
                           MIN(b."MnfDate") AS mnf_date
                    FROM {schema}."OBTQ" q
                    LEFT JOIN {schema}."OBTN" b
                      ON b."ItemCode" = q."ItemCode"
                     AND b."SysNumber" = q."SysNumber"
                    WHERE q."WhsCode" = ?
                      AND q."Quantity" > 0
                      AND q."ItemCode" IN ({placeholders})
                      AND b."DistNumber" IS NOT NULL
                    GROUP BY q."ItemCode", b."DistNumber"
                    ORDER BY COALESCE(MIN(b."ExpDate"), MIN(b."MnfDate")) ASC NULLS LAST,
                             b."DistNumber" ASC
                """
                try:
                    cursor.execute(query, [safe_whs, *chunk])
                    for row in cursor.fetchall():
                        item_code, batch_num, qty, exp_date, mnf_date = row[0], row[1], row[2], row[3], row[4]
                        if not item_code or not batch_num:
                            continue
                        try:
                            qty_f = float(qty or 0)
                        except (TypeError, ValueError):
                            qty_f = 0.0
                        rows_out.append({
                            "item_code": str(item_code),
                            "batch_number": str(batch_num),
                            "warehouse_code": safe_whs,
                            "quantity": qty_f,
                            "expiry": (exp_date.isoformat() if hasattr(exp_date, "isoformat") else exp_date),
                            "mnf_date": (mnf_date.isoformat() if hasattr(mnf_date, "isoformat") else mnf_date),
                        })
                except Exception as exc:
                    frappe.logger().warning(
                        "bulk_batch_inventory_by_warehouse HANA chunk failed "
                        "wh=%s size=%s: %s",
                        safe_whs,
                        len(chunk),
                        exc,
                    )
        finally:
            try:
                connector.close_hana_connection(connection, cursor)
            except Exception:
                pass
        return rows_out

    def bulk_batch_quantities_by_warehouse(
        self,
        whs_code: str,
        item_codes: "list[str] | set[str] | tuple[str, ...]",
        chunk_size: int = 500,
    ) -> dict[tuple[str, str], float]:
        """Return ``{(item_code, batch_number): quantity}`` for all batches of
        the given items in a single warehouse.

        Thin wrapper around ``bulk_batch_inventory_by_warehouse`` — kept for
        callers that only care about quantities, not FEFO metadata.
        """
        rows = self.bulk_batch_inventory_by_warehouse(
            whs_code=whs_code,
            item_codes=item_codes,
            chunk_size=chunk_size,
        )
        out: dict[tuple[str, str], float] = {}
        for r in rows:
            key = (r["item_code"], r["batch_number"])
            out[key] = out.get(key, 0.0) + float(r.get("quantity") or 0)
        return out

    def bulk_manage_batch_numbers(
        self,
        item_codes: "list[str] | set[str] | tuple[str, ...]",
        chunk_size: int = 500,
    ) -> "dict[str, bool | None]":
        """Return ``{item_code: ManageBatchNumbers?}`` for the given items.

        Tri-state value matches ``_resolve_batch_managed``:

        * ``True``  — item is batch-managed
        * ``False`` — item is NOT batch-managed
        * ``None``  — lookup failed (caller MUST skip batch allocation for
          this item to stay consistent with payload builders)

        Strategy:

        1. HANA direct query on ``OITM."ManageBatchNumbers"`` with ``IN
           (...)`` — one round-trip per 500 items, ~0.1 s total.
        2. On HANA failure, fall back to OData ``Items`` with an ``OR``
           chain (``ItemCode eq 'A' or ItemCode eq 'B' ...``). We use OR
           rather than ``IN (...)`` because this installation's Service
           Layer returns HTTP 400 on the ``IN`` operator. Each OR-chain
           call is ~0.5 s.

        Used by ``ops_prevalidate_batches_*`` to collapse what would be
        dozens of per-item Service Layer calls into one or two.
        """
        cleaned = sorted({str(c or "").strip() for c in (item_codes or []) if str(c or "").strip()})
        if not cleaned:
            return {}

        out: "dict[str, bool | None]" = {}

        # Preferred path: HANA (fast, supports IN).
        hana_ok = False
        try:
            from khanal_tech_integrations.api.common.sap_connector import SAPConnector

            connector = SAPConnector()
            connection, cursor, schema = connector.get_hana_connection()
            try:
                step = max(1, int(chunk_size))
                for start in range(0, len(cleaned), step):
                    chunk = cleaned[start : start + step]
                    placeholders = ",".join(["?"] * len(chunk))
                    query = (
                        f'SELECT "ItemCode", "ManageBatchNumbers" '
                        f'FROM {schema}."OITM" '
                        f'WHERE "ItemCode" IN ({placeholders})'
                    )
                    cursor.execute(query, list(chunk))
                    for row in cursor.fetchall():
                        code = str(row[0] or "").strip()
                        if not code:
                            continue
                        raw = str(row[1] or "").strip().upper()
                        out[code] = raw in ("Y", "YES", "TRUE", "1", "TYES")
                hana_ok = True
            finally:
                try:
                    connector.close_hana_connection(connection, cursor)
                except Exception:
                    pass
        except Exception as exc:
            frappe.logger().warning(
                "bulk_manage_batch_numbers: HANA path failed (%s) — "
                "falling back to OData OR-chain",
                exc,
            )

        if hana_ok:
            for code in cleaned:
                out.setdefault(code, False)
            return out

        # Fallback: OData with OR-chain (NOT `in (...)`; this SL rejects it
        # with HTTP 400). Chunk smaller because each OR term adds URL bytes.
        step = max(1, min(40, int(chunk_size)))
        for start in range(0, len(cleaned), step):
            chunk = cleaned[start : start + step]
            or_clause = " or ".join(
                f"ItemCode eq '{c.replace(chr(39), chr(39) * 2)}'" for c in chunk
            )

            last_exc: Exception | None = None
            for attempt_idx, delay in enumerate(_BATCH_QTY_ODATA_BACKOFFS_SEC):
                if delay:
                    time.sleep(delay)
                try:
                    result = self.get(
                        "Items",
                        params={
                            "$filter": or_clause,
                            "$select": "ItemCode,ManageBatchNumbers",
                        },
                    )
                    for row in result.get("value", []) or []:
                        code = str(row.get("ItemCode") or "").strip()
                        if not code:
                            continue
                        raw = str(row.get("ManageBatchNumbers") or "").strip().upper()
                        out[code] = raw in ("TYES", "Y", "YES", "TRUE", "1")
                    last_exc = None
                    break
                except Exception as exc:
                    last_exc = exc
                    frappe.logger().warning(
                        "bulk_manage_batch_numbers OR-chain attempt %s/%s "
                        "failed for items=%s: %s",
                        attempt_idx + 1,
                        len(_BATCH_QTY_ODATA_BACKOFFS_SEC),
                        len(chunk),
                        exc,
                    )
            if last_exc is not None:
                # Leave this chunk's items as "unknown" so the caller skips
                # batch allocation rather than making a wrong decision.
                for code in chunk:
                    out.setdefault(code, None)

        # Items that neither HANA nor OData found: treat as not-batch-managed.
        # ``OITM.ManageBatchNumbers=N`` is the common reality, and a missing
        # row usually means the SKU is a bundle master with no physical stock.
        for code in cleaned:
            out.setdefault(code, False)
        return out

    def warehouse_inventory_snapshot(self, whs_code: str) -> dict[str, Any]:
        """Return item+batch inventory for a warehouse, sourced from SAP HANA."""
        hana_rows = self._hana_warehouse_all_batches(whs_code)
        by_item: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"item_code": "", "sap_qty": 0.0, "batches": defaultdict(float)}
        )
        for row in hana_rows:
            item_code = str(row.get("item_code") or "").strip()
            batch_num = str(row.get("batch_number") or "").strip()
            if not item_code:
                continue
            qty = float(row.get("quantity") or 0)
            item_row = by_item[item_code]
            item_row["item_code"] = item_code
            item_row["sap_qty"] += qty
            if batch_num:
                item_row["batches"][batch_num] += qty
        items = [
            {
                "item_code": v["item_code"],
                "sap_qty": round(float(v["sap_qty"] or 0), 3),
                "sap_batches": {b: round(float(q or 0), 3) for b, q in sorted(v["batches"].items())},
            }
            for v in by_item.values()
        ]
        items.sort(key=lambda r: r["item_code"])
        return {"warehouse_code": whs_code, "item_count": len(items), "items": items}

    def find_invoice_by_uc_order_id(self, uc_order_id: str) -> dict | None:
        """
        Find existing AR Invoice by U_UCOrderID UDF.
        Returns invoice dict with DocEntry/DocNum/tax fields or None.
        """
        order_key = str(uc_order_id or "").strip()
        if not order_key:
            return None

        escaped_key = order_key.replace("'", "''")
        primary_select = "DocEntry,DocNum,DocTaxAmount,DocTotal,U_UCOrderID,Comments,Reference3,DocDate,CreateDate"
        fallback_select = "DocEntry,DocNum,DocTaxAmount,DocTotal,Comments,Reference3,DocDate,CreateDate"

        # 1) Primary lookup by dedicated UDF (fast and exact when server supports it).
        try:
            result = self.get(
                "Invoices",
                params={
                    "$filter": f"U_UCOrderID eq '{escaped_key}'",
                    "$select": primary_select,
                    "$orderby": "DocEntry desc",
                    "$top": 5,
                },
            )
            items = result.get("value", [])
            if items:
                return items[0]
        except Exception:
            pass

        # 2) Fallback server-side lookup by Comments text (for manual/Postman posts).
        try:
            result = self.get(
                "Invoices",
                params={
                    "$filter": f"contains(Comments,'{escaped_key}')",
                    "$select": fallback_select,
                    "$orderby": "DocEntry desc",
                    "$top": 20,
                },
            )
            items = result.get("value", [])
            if items:
                return items[0]
        except Exception:
            pass

        # 3) Last-resort client-side scan on recent invoices (works when $filter is restricted).
        try:
            result = self.get(
                "Invoices",
                params={
                    "$select": fallback_select,
                    "$orderby": "DocEntry desc",
                    "$top": 200,
                },
            )
            items = result.get("value", [])
            for row in items:
                comments = str(row.get("Comments") or "")
                reference3 = str(row.get("Reference3") or "")
                if order_key in comments or order_key in reference3:
                    return row
        except Exception:
            pass

        return None

    def get_invoice_by_doc_entry(self, doc_entry: str | int) -> dict:
        """
        Fetch full invoice JSON by DocEntry.
        """
        return self.get(f"Invoices({int(doc_entry)})")

    def cancel_ar_invoice(self, doc_entry: str | int) -> dict:
        """Cancel an AR invoice in SAP B1 via Service Layer.

        Uses the standard entity action::

            POST {base}/Invoices({DocEntry})/Cancel

        Document must not be cancelled already, and must not have dependent
        postings that B1 rejects (e.g. closed periods, linked payments —
        Service Layer returns HTTP 4xx with a message body).

        Returns the JSON body from SAP when present, otherwise ``{}``.
        """
        self._ensure_logged_in()
        url = f"{self.base_url}/Invoices({int(doc_entry)})/Cancel"
        resp = self.session.post(url, json={}, timeout=120, verify=self._verify_ssl)
        if resp.status_code == 401:
            self.login()
            resp = self.session.post(url, json={}, timeout=120, verify=self._verify_ssl)
        if resp.status_code >= 400:
            detail = (resp.text or "")[:2000]
            raise requests.HTTPError(
                f"{resp.status_code} Error cancelling Invoices({int(doc_entry)}). Response: {detail}",
                response=resp,
            )
        try:
            return resp.json() if resp.text else {}
        except Exception:
            return {}

    def cancel_delivery_note(self, doc_entry: str | int) -> dict:
        """Cancel a Delivery Note in SAP B1 via Service Layer.

        Uses the standard entity action::

            POST {base}/DeliveryNotes({DocEntry})/Cancel

        Document must not be cancelled already, and must not have dependent
        postings that B1 rejects (e.g. closed periods, a linked AR Invoice —
        Service Layer returns HTTP 4xx with a message body).

        Returns the JSON body from SAP when present, otherwise ``{}``.
        """
        self._ensure_logged_in()
        url = f"{self.base_url}/DeliveryNotes({int(doc_entry)})/Cancel"
        resp = self.session.post(url, json={}, timeout=120, verify=self._verify_ssl)
        if resp.status_code == 401:
            self.login()
            resp = self.session.post(url, json={}, timeout=120, verify=self._verify_ssl)
        if resp.status_code >= 400:
            detail = _extract_sap_error_message(resp)
            raise requests.HTTPError(
                f"SAP error ({resp.status_code}) cancelling DeliveryNotes({int(doc_entry)}): {detail}",
                response=resp,
            )
        try:
            return resp.json() if resp.text else {}
        except Exception:
            return {}

    def get_credit_note_by_doc_entry(self, doc_entry: str | int) -> dict:
        """
        Fetch full credit note JSON by DocEntry.
        """
        return self.get(f"CreditNotes({int(doc_entry)})")

    def find_credit_note_by_return_id(self, uc_return_id: str) -> dict | None:
        """
        Find existing SAP Credit Note by U_UCReturnID UDF.
        Returns credit note dict with DocEntry/DocNum or None.
        Used as an idempotency guard before posting a new credit note.
        """
        return_key = str(uc_return_id or "").strip()
        if not return_key:
            return None

        escaped_key = return_key.replace("'", "''")
        primary_select = "DocEntry,DocNum,DocTaxAmount,DocTotal,U_UCReturnID,Comments,DocDate,CreateDate"
        fallback_select = "DocEntry,DocNum,DocTaxAmount,DocTotal,Comments,DocDate,CreateDate"

        # 1) Primary lookup by dedicated UDF (fast and exact when server supports it).
        try:
            result = self.get(
                "CreditNotes",
                params={
                    "$filter": f"U_UCReturnID eq '{escaped_key}'",
                    "$select": primary_select,
                    "$orderby": "DocEntry desc",
                    "$top": 5,
                },
            )
            items = result.get("value", [])
            if items:
                return items[0]
        except Exception:
            pass

        # 2) Fallback server-side lookup by Comments text.
        try:
            result = self.get(
                "CreditNotes",
                params={
                    "$filter": f"contains(Comments,'{escaped_key}')",
                    "$select": fallback_select,
                    "$orderby": "DocEntry desc",
                    "$top": 20,
                },
            )
            items = result.get("value", [])
            if items:
                return items[0]
        except Exception:
            pass

        # 3) Last-resort client-side scan on recent credit notes.
        try:
            result = self.get(
                "CreditNotes",
                params={
                    "$select": fallback_select,
                    "$orderby": "DocEntry desc",
                    "$top": 200,
                },
            )
            items = result.get("value", [])
            for row in items:
                comments = str(row.get("Comments") or "")
                if return_key in comments:
                    return row
        except Exception:
            pass

        return None

    def delete(self, endpoint: str) -> dict:
        self._ensure_logged_in()
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        resp = self.session.delete(url, timeout=30, verify=self._verify_ssl)
        if resp.status_code == 401:
            self._logged_in = False
            self.login()
            resp = self.session.delete(url, timeout=30, verify=self._verify_ssl)
        if resp.status_code >= 400:
            raise requests.HTTPError(
                f"{resp.status_code} Error deleting {url}. Response: {(resp.text or '')[:1200]}",
                response=resp,
            )
        return resp.json() if resp.text else {}

    def logout(self):
        try:
            self.session.post(f"{self.base_url}/Logout", timeout=10, verify=self._verify_ssl)
        except Exception:
            pass
        self._logged_in = False
