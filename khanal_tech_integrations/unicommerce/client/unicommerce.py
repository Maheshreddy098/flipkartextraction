"""
Unicommerce REST API client for UC-SAP integration.
"""

from __future__ import annotations

from typing import Any

import frappe
import requests
from frappe.utils import add_to_date, get_datetime, now_datetime
from pytz import timezone

# Seconds before expiry to treat a token as effectively expired (safety buffer).
_TOKEN_EXPIRY_BUFFER_SECS = 300  # 5 minutes


class UCClient:
    def __init__(self):
        self.unicommerce_settings = frappe.get_single("Unicommerce Settings")
        self.base_url = self._resolve_base_url()
        self.username = self._resolve_username()
        self.password = self._resolve_password()
        self.facility_code = self._resolve_facility()
        self.token: str | None = None
        self.token_source: str = ""

    @staticmethod
    def _safe_get(doc: Any, fieldname: str) -> Any:
        return getattr(doc, fieldname, None)

    def _resolve_base_url(self) -> str:
        base_url = (self._safe_get(self.unicommerce_settings, "tenant_url") or "").strip()
        if not base_url:
            frappe.throw("Unicommerce base URL is not configured.")
        if not base_url.startswith(("http://", "https://")):
            base_url = f"https://{base_url}"
        return base_url.rstrip("/")

    def _resolve_username(self) -> str:
        username = (self._safe_get(self.unicommerce_settings, "username") or "").strip()
        if not username:
            frappe.throw("Unicommerce username is not configured.")
        return username

    def _resolve_password(self) -> str:
        password = self.unicommerce_settings.get_password("password")
        if not password:
            frappe.throw("Unicommerce password is not configured.")
        return password

    def _resolve_facility(self) -> str | None:
        return self._safe_get(self.unicommerce_settings, "facility") or None

    def _resolve_facility_codes(self) -> list[str]:
        if not self.facility_code:
            return []
        return [f.strip() for f in str(self.facility_code).split(",") if f.strip()]

    def login(self):
        """Full password grant — always fetches a fresh token from UC."""
        resp = requests.post(
            f"{self.base_url}/oauth/token",
            data={
                "grant_type": "password",
                "username": self.username,
                "password": self.password,
                "client_id": "my-trusted-client",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        self.token = data["access_token"]
        self.token_source = "password_grant"
        self._persist_token(data)

    def _persist_token(self, data: dict):
        """Save access_token, refresh_token, expires_on to Unicommerce Settings (best-effort)."""
        try:
            expires_in = int(data.get("expires_in") or 3600)
            expires_on = add_to_date(now_datetime(), seconds=expires_in, as_string=True)
            frappe.db.set_single_value("Unicommerce Settings", "access_token", data.get("access_token") or "")
            frappe.db.set_single_value("Unicommerce Settings", "refresh_token", data.get("refresh_token") or "")
            frappe.db.set_single_value("Unicommerce Settings", "expires_on", expires_on)
            frappe.db.commit()
        except Exception:
            pass  # Token persistence is best-effort; auth already succeeded

    def _try_stored_token(self) -> bool:
        """Return True and set self.token if the persisted access_token is still valid."""
        token = self._safe_get(self.unicommerce_settings, "access_token") or ""
        expires_on_raw = self._safe_get(self.unicommerce_settings, "expires_on") or ""
        if not token or not expires_on_raw:
            return False
        try:
            expires_on = get_datetime(expires_on_raw)
            cutoff = add_to_date(now_datetime(), seconds=_TOKEN_EXPIRY_BUFFER_SECS, as_datetime=True)
            if expires_on > cutoff:
                self.token = token
                self.token_source = "stored_token"
                return True
        except Exception:
            pass
        return False

    def _try_token_refresh(self) -> bool:
        """Use the refresh_token grant to get a new access_token without the password.
        Returns True if successful; False if the refresh token is missing or rejected."""
        refresh_token = self._safe_get(self.unicommerce_settings, "refresh_token") or ""
        if not refresh_token:
            return False
        try:
            resp = requests.post(
                f"{self.base_url}/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": "my-trusted-client",
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            self.token = data["access_token"]
            self.token_source = "refresh_token"
            self._persist_token(data)
            return True
        except Exception:
            return False

    def _ensure_token(self):
        """Get a valid token, preferring the stored token then refresh, then full login."""
        if self.token:
            return
        # 1. Use stored token if still valid.
        if self._try_stored_token():
            return
        # 2. Use refresh_token grant if available.
        if self._try_token_refresh():
            return
        # 3. Full password grant as last resort.
        self.login()

    def _headers(self) -> dict[str, str]:
        self._ensure_token()
        return {"Authorization": f"Bearer {self.token}"}

    def _get_with_reauth(self, endpoint: str, params: dict) -> dict:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        resp = requests.get(url, headers=self._headers(), params=params, timeout=30)
        if resp.status_code == 401:
            self.login()
            resp = requests.get(url, headers=self._headers(), params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _post_with_reauth(self, endpoint: str, body: dict, extra_headers: dict | None = None) -> dict:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self._headers()
        if extra_headers:
            headers.update(extra_headers)
        resp = requests.post(url, headers=headers, json=body, timeout=30)
        if resp.status_code == 401:
            self.login()
            headers = self._headers()
            if extra_headers:
                headers.update(extra_headers)
            resp = requests.post(url, headers=headers, json=body, timeout=30)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _to_utc_iso(dt_value: str) -> str:
        return get_datetime(dt_value).astimezone(timezone("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _to_uc_date(dt_value: str) -> str:
        """Format datetime as UC return API expects: 'yyyy-MM-dd'T'HH:mm:ss.SSS'Z''"""
        return get_datetime(dt_value).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    def get_orders(self, updated_since: str, channel: str | None = None) -> list[dict]:
        """
        Fetch sale orders using tenant-compatible search API.
        updated_since example: "2024-01-01 00:00:00"
        """
        return self.get_orders_between(
            from_date=updated_since,
            to_date=str(now_datetime()),
            channel=channel,
        )

    def get_orders_between(
        self,
        from_date: str,
        to_date: str,
        channel: str | None = None,
    ) -> list[dict]:
        """
        Fetch sale orders between explicit datetime bounds.
        Both dates can be in Frappe datetime format.
        """
        all_orders: list[dict] = []
        page_size = 1000
        display_start = 0
        total_records = None
        max_pages = 200
        prev_page_first_code = None

        for _page in range(max_pages):
            body = {
                "fromDate": self._to_utc_iso(from_date),
                "toDate": self._to_utc_iso(to_date),
                "searchOptions": {
                    "displayLength": page_size,
                    "displayStart": display_start,
                    "getCount": True,
                },
            }
            facility_codes = self._resolve_facility_codes()
            if facility_codes:
                body["facilityCodes"] = facility_codes
            if channel:
                body["channel"] = channel

            data = self._post_with_reauth("services/rest/v1/oms/saleOrder/search", body=body)
            elements = data.get("elements", []) if isinstance(data, dict) else []
            current_first_code = (elements[0] or {}).get("code") if elements else None
            # Some tenants can repeat same page indefinitely; stop on repetition.
            if prev_page_first_code and current_first_code and current_first_code == prev_page_first_code:
                break
            prev_page_first_code = current_first_code
            all_orders.extend(elements)

            if total_records is None and isinstance(data, dict):
                total_records = data.get("totalRecords") or data.get("totalElements")

            if len(elements) < page_size:
                break
            if total_records and len(all_orders) >= int(total_records):
                break
            display_start += page_size

        return all_orders

    def get_returns(self, from_date: str) -> list[dict]:
        """Fetch returns from Unicommerce since from_date."""
        return self.get_returns_between(from_date=from_date, to_date=str(now_datetime()))

    def _search_returns_single(
        self,
        return_type: str,
        from_uc: str,
        to_uc: str,
        use_updated: bool,
        facility: str,
    ) -> list[dict]:
        """One return/search call for a single facility + return type.
        Each result is tagged with _facility so get_return_detail can pass it."""
        import requests as _requests

        body: dict = {"returnType": return_type}
        if use_updated:
            body["updatedFrom"] = from_uc
            body["updatedTo"] = to_uc
        else:
            body["createdFrom"] = from_uc
            body["createdTo"] = to_uc

        url = f"{self.base_url}/services/rest/v1/oms/return/search"
        headers = {**self._headers(), "Facility": facility}

        raw = _requests.post(url, headers=headers, json=body, timeout=30)
        if raw.status_code == 401:
            self.login()
            headers = {**self._headers(), "Facility": facility}
            raw = _requests.post(url, headers=headers, json=body, timeout=30)

        frappe.logger().info(
            "UC return/search facility=%s type=%s status=%s count=%s",
            facility, return_type, raw.status_code,
            len(raw.json().get("returnOrders") or []) if raw.ok else "err",
        )

        if not raw.ok:
            return []
        try:
            resp = raw.json()
        except Exception:
            return []
        rows = resp.get("returnOrders") or []
        # Tag each row with its facility so detail fetch can use it.
        for row in rows:
            row["_facility"] = facility
        return rows

    def _search_returns_by_type(
        self,
        return_type: str,
        from_uc: str,
        to_uc: str,
        use_updated: bool,
        facility_codes: list[str],
    ) -> list[dict]:
        """Search CIR or RTO returns across all configured facilities."""
        all_rows: list[dict] = []
        for fac in (facility_codes or [""]):
            rows = self._search_returns_single(return_type, from_uc, to_uc, use_updated, fac)
            all_rows.extend(rows)
        return all_rows

    def get_returns_between(self, from_date: str, to_date: str, use_updated: bool = False) -> list[dict]:
        """
        Fetch full return details between datetime bounds.
        Calls return/search for CIR and RTO types (both required per UC API).
        Splits into 30-day chunks (UC enforces a max 30-day window).
        Then fetches full detail for each summary code.
        """
        from_dt = get_datetime(from_date)
        to_dt = get_datetime(to_date)
        facility_codes = self._resolve_facility_codes()

        # Split into 30-day chunks to respect the UC max window.
        chunks: list[tuple] = []
        chunk_start = from_dt
        while chunk_start < to_dt:
            chunk_end = add_to_date(chunk_start, days=29, as_datetime=True)
            if chunk_end > to_dt:
                chunk_end = to_dt
            chunks.append((chunk_start, chunk_end))
            chunk_start = add_to_date(chunk_end, seconds=1, as_datetime=True)

        # code → facility mapping (first-seen wins, deduplicates across chunks/types)
        code_to_facility: dict[str, str] = {}
        for chunk_from, chunk_to in chunks:
            from_uc = self._to_uc_date(str(chunk_from))
            to_uc = self._to_uc_date(str(chunk_to))
            for rtype in ("CIR", "RTO"):
                summaries = self._search_returns_by_type(
                    rtype, from_uc, to_uc, use_updated, facility_codes
                )
                for row in summaries:
                    code = row.get("code") or row.get("reversePickupCode")
                    if code and code not in code_to_facility:
                        code_to_facility[str(code)] = row.get("_facility") or ""

        frappe.logger().info("UC returns total unique codes=%s", len(code_to_facility))

        full_returns: list[dict] = []
        for code, fac in code_to_facility.items():
            try:
                detail = self.get_return_detail(code, facility=fac or None)
                if detail:
                    full_returns.append(detail)
            except Exception as e:
                frappe.logger().warning("UC return/get failed code=%s error=%s", code, str(e))
        return full_returns

    def get_order_detail(self, order_code: str) -> dict:
        """
        Fetch full order detail for a given order code.
        """
        body = {"code": order_code}
        facility_codes = self._resolve_facility_codes()
        if facility_codes:
            body["facilityCodes"] = facility_codes
        data = self._post_with_reauth("services/rest/v1/oms/saleorder/get", body=body)
        if isinstance(data, dict) and data.get("saleOrderDTO"):
            return data["saleOrderDTO"]
        return data if isinstance(data, dict) else {}

    def get_return_detail(self, code: str, facility: str | None = None) -> dict:
        """
        Fetch full return detail.
        RP-prefixed codes → reversePickupCode field.
        Other codes (KFLE shipment codes from RTO search) → shipmentCode field.
        """
        extra_headers = {"Facility": facility} if facility else None
        # CIR returns use RP-prefixed codes as reversePickupCode.
        # RTO returns from search come back with shipment codes (KFLE-prefix).
        if str(code).upper().startswith("RP"):
            body = {"reversePickupCode": code}
        else:
            body = {"shipmentCode": code}

        data = self._post_with_reauth(
            "services/rest/v1/oms/return/get",
            body=body,
            extra_headers=extra_headers,
        )
        if not isinstance(data, dict):
            return {}
        # Successful responses have returnSaleOrderValue; unsuccessful ones have errors.
        if not data.get("successful", True) and not data.get("returnSaleOrderValue"):
            frappe.logger().info("UC return/get code=%s not successful: %s", code, str(data)[:300])
            return {}
        return data

    def get_item_type_inventory(self, sku_code: str, facility: str | None = None) -> list[dict]:
        extra_headers = {}
        target_facility = facility or (self._resolve_facility_codes() or [None])[0]
        if target_facility:
            extra_headers["facility"] = target_facility

        resp = self._post_with_reauth(
            "services/rest/v1/product/itemTypeInventory/get",
            body={"skuCode": sku_code},
            extra_headers=extra_headers,
        )
        return resp.get("inventoryDTOs") or []

    @staticmethod
    def summarize_inventory_rows(rows: list[dict]) -> dict:
        total_qty = 0.0
        good_qty = 0.0
        by_batch: dict[str, float] = {}
        by_type: dict[str, float] = {}

        for row in rows or []:
            qty_raw = (
                row.get("quantity")
                or row.get("inventory")
                or row.get("availableQuantity")
                or row.get("available")
                or 0
            )
            try:
                qty = float(qty_raw or 0)
            except Exception:
                qty = 0.0

            inv_type = str(row.get("type") or "UNKNOWN").strip() or "UNKNOWN"
            batch = str(row.get("vendorBatchNumber") or row.get("batchCode") or "").strip()
            total_qty += qty
            by_type[inv_type] = round(float(by_type.get(inv_type, 0) + qty), 3)
            if inv_type.upper() == "GOOD_INVENTORY":
                good_qty += qty
                if batch:
                    by_batch[batch] = round(float(by_batch.get(batch, 0) + qty), 3)

        return {
            "uc_total_qty": round(total_qty, 3),
            "uc_good_qty": round(good_qty, 3),
            "uc_batches": dict(sorted(by_batch.items())),
            "uc_inventory_types": dict(sorted(by_type.items())),
        }
