import os
import frappe
import requests
import json
from collections import defaultdict
from frappe import _
from khanal_tech_integrations.api.real_aquatics import (
	REALAQUATICS_WAREHOUSE,
	PO_WAREHOUSE,
	REALAQUATICS_SAP_AVAILABILITY_WAREHOUSES,
	ORDERS_FROM_WAREHOUSE,
	normalize_warehouse_code,
)
from khanal_tech_integrations.api.real_aquatics.auth import get_user_real_aquatics_roles


# Set SAP_SSL_VERIFY=1 (or "true"/"yes") in the environment to enable SSL certificate
# verification for SAP B1 Service Layer calls. Defaults to False because most SAP B1
# installations use self-signed certificates.
_SAP_VERIFY_SSL = os.environ.get("SAP_SSL_VERIFY", "").lower() in ("1", "true", "yes")

DEFAULT_UOM = "Nos"
SESSION_EXPIRY_BUFFER_MINUTES = 5
_SAP_SESSION_CACHE_KEY = "real_aquatics_sap_b1_session"
_SAP_SESSION_CACHE_TTL = 28 * 60  # 28 minutes (SAP default timeout is 30 min)
# SAP B1 StockTransfer / InventoryTransferRequest Comments field max length (avoids "Value too long" error)
SAP_TRANSFER_COMMENTS_MAX_LEN = 254


def _truncate_sap_comments(comments):
	"""Return comments truncated to SAP transfer Comments field limit."""
	s = (comments or "").strip()
	if not s:
		return ""
	return s[:SAP_TRANSFER_COMMENTS_MAX_LEN]


def _check_real_aquatics_access():
	roles = get_user_real_aquatics_roles()
	if not roles:
		frappe.throw(_("No Real Aquatics access"), frappe.PermissionError)


def _get_sap_session(force_login=False):
	"""Get authenticated SAP B1 Service Layer session using Real Aquatics SAP Settings"""
	try:
		session = _authenticate_real_aquatics_sap(force_login=force_login)
		raw = (frappe.db.get_single_value("Real Aquatics SAP Settings", "sap_b1_url") or "").strip()
		b1_url = (raw.rstrip("/") + "/") if raw else ""
		return session, b1_url
	except Exception as e:
		frappe.log_error(f"SAP B1 auth failed: {str(e)}", "Real Aquatics SAP Error")
		return None, None


def _ensure_real_aquatics_sap_settings_hana_fields():
	"""Add SAP HANA custom fields to Real Aquatics SAP Settings so batch lookup works. Safe to run multiple times. Skips if fields already exist (doctype JSON or Custom Field)."""
	try:
		meta = frappe.get_meta("Real Aquatics SAP Settings")
	except Exception:
		return

	# If doctype already has the HANA section (from JSON or previous custom fields), do nothing
	if meta.get_field("section_break_hana_db"):
		return

	# Insert after last field: find rightmost field from DocField or Custom Field
	insert_after = None
	for _dt, _parent in (("DocField", "parent"), ("Custom Field", "dt")):
		key = _parent
		last = (
			frappe.db.get_all(
				_dt,
				filters={key: "Real Aquatics SAP Settings"},
				fields=["fieldname", "idx"],
				order_by="idx desc",
				limit=1,
			)
			or []
		)
		if last:
			insert_after = last[0].get("fieldname")
			break
	if not insert_after:
		insert_after = "routeid"  # fallback

	fields_to_add = [
		{"fieldname": "section_break_hana_db", "fieldtype": "Section Break", "label": "SAP HANA Database (for batch lookup)", "insert_after": insert_after},
		{"fieldname": "hana_host", "fieldtype": "Data", "label": "HANA Host", "description": "SAP HANA database server hostname or IP address", "insert_after": "section_break_hana_db"},
		{"fieldname": "hana_user", "fieldtype": "Data", "label": "HANA User", "description": "Database username for HANA connection", "insert_after": "hana_host"},
		{"fieldname": "hana_password", "fieldtype": "Password", "label": "HANA Password", "description": "Database password for HANA connection", "insert_after": "hana_user"},
		{"fieldname": "column_break_hana", "fieldtype": "Column Break", "insert_after": "hana_password"},
		{"fieldname": "hana_port", "fieldtype": "Int", "label": "HANA Port", "default": "30015", "description": "SAP HANA database port (default: 30015)", "insert_after": "column_break_hana"},
		{"fieldname": "hana_schema", "fieldtype": "Data", "label": "HANA Schema", "description": "Schema / company database name (e.g. TEST_KF_INC_26022026)", "insert_after": "hana_port"},
	]
	created = 0
	for f in fields_to_add:
		# Skip if field already exists on doctype (from JSON DocField or Custom Field)
		if meta.get_field(f["fieldname"]):
			continue
		name = f"Real Aquatics SAP Settings-{f['fieldname']}"
		if frappe.db.exists("Custom Field", name):
			continue
		cf = frappe.get_doc({"doctype": "Custom Field", "dt": "Real Aquatics SAP Settings", "module": "Khanal Tech Integrations", **f})
		cf.insert(ignore_permissions=True)
		created += 1
		frappe.db.commit()
	if created:
		frappe.clear_cache(doctype="Real Aquatics SAP Settings")
		frappe.reload_doctype("Real Aquatics SAP Settings", force=True)


def _authenticate_real_aquatics_sap(force_login=False):
	"""Authenticate against Real Aquatics SAP Settings (UK CompanyDB).
	Session cookies are stored in Redis (frappe.cache) to avoid mid-transaction DB commits.
	The Real Aquatics SAP Settings doctype is only read for credentials and URL — never written to.
	"""
	import requests as req
	from frappe.utils import add_to_date, now_datetime, get_datetime

	doc = frappe.get_doc("Real Aquatics SAP Settings")
	b1_url = (doc.sap_b1_url or "").rstrip("/") + "/"
	headers = {"Content-Type": "application/json", "Accept": "*/*"}

	cached = None if force_login else frappe.cache().get_value(_SAP_SESSION_CACHE_KEY)

	if cached and cached.get("b1session") and cached.get("expires_on"):
		try:
			expiry_with_buffer = add_to_date(
				get_datetime(cached["expires_on"]),
				minutes=-SESSION_EXPIRY_BUFFER_MINUTES,
			)
			if now_datetime() < expiry_with_buffer:
				session = req.Session()
				session.cookies.set("B1SESSION", cached["b1session"])
				session.cookies.set("ROUTEID", cached["routeid"])
				return session
		except Exception:
			pass  # Treat any parse error as a cache miss — fall through to login

	creds = {
		"CompanyDB": doc.companydb,
		"Password": doc.get_password("password"),
		"UserName": doc.username,
	}
	session = req.Session()
	resp = session.post(b1_url + "Login", json=creds, headers=headers, verify=_SAP_VERIFY_SSL, timeout=15)
	resp.raise_for_status()
	cookies = session.cookies.get_dict()
	session_timeout = int(resp.json().get("SessionTimeout", 30))
	expires_on = add_to_date(now_datetime(), minutes=session_timeout)
	frappe.cache().set_value(
		_SAP_SESSION_CACHE_KEY,
		{"b1session": cookies["B1SESSION"], "routeid": cookies["ROUTEID"], "expires_on": str(expires_on)},
		expires_in_sec=_SAP_SESSION_CACHE_TTL,
	)
	return session


def _sap_get_with_retry(url, session, b1_url, timeout=15):
	"""Make a GET request to SAP, retry with fresh session if response looks stale."""
	resp = session.get(url, verify=_SAP_VERIFY_SSL, timeout=timeout)
	if resp.status_code == 401 or (
		resp.status_code == 200
		and resp.headers.get("Content-Type", "").startswith("text/html")
	):
		new_session, new_b1_url = _get_sap_session(force_login=True)
		if new_session:
			session, b1_url = new_session, new_b1_url
			resp = session.get(url, verify=_SAP_VERIFY_SSL, timeout=timeout)
	return resp, session, b1_url


def _sap_post_with_retry(url, session, b1_url, json_payload, timeout=30):
	"""POST to SAP; retry with fresh session on 401."""
	resp = session.post(url, json=json_payload, verify=_SAP_VERIFY_SSL, timeout=timeout, headers={"Content-Type": "application/json"})
	if resp.status_code == 401:
		session, b1_url = _get_sap_session(force_login=True)
		if session:
			resp = session.post(url, json=json_payload, verify=_SAP_VERIFY_SSL, timeout=timeout, headers={"Content-Type": "application/json"})
	return resp, session, b1_url


def _sap_post_with_retry_transfer(url, session, b1_url, json_payload, max_attempts=3):
	"""POST to SAP for inventory transfers; retry on 401, 5xx, timeouts and connection errors."""
	import time
	last_exc = None
	for attempt in range(max_attempts):
		try:
			resp, session, b1_url = _sap_post_with_retry(url, session, b1_url, json_payload)
			# Retry on server errors (5xx)
			if 500 <= resp.status_code < 600 and attempt < max_attempts - 1:
				time.sleep(2)
				session, b1_url = _get_sap_session(force_login=True)
				if session:
					continue
			return resp, session, b1_url
		except requests.RequestException as e:
			last_exc = e
			if attempt < max_attempts - 1:
				time.sleep(2)
				session, b1_url = _get_sap_session(force_login=True)
				if not session:
					raise
			else:
				raise
	if last_exc:
		raise last_exc
	raise frappe.ValidationError(_("SAP request failed after {0} attempts").format(max_attempts))


def _get_inc_hana_connection():
	"""Get read-only SAP HANA connection using Real Aquatics SAP Settings (UK CompanyDB)."""
	try:
		import hdbcli.dbapi as hana_db
	except ImportError:
		# HANA client not installed – skip HANA path gracefully
		frappe.log_error("SAP HANA driver (hdbcli) not installed; skipping INC HANA batch lookup.", "Real Aquatics SAP Error")
		return None, None, None

	try:
		_ensure_real_aquatics_sap_settings_hana_fields()
		doc = frappe.get_doc("Real Aquatics SAP Settings")

		# Support both hana_* and common alternates (e.g. user_id, schema)
		host = (getattr(doc, "hana_host", None) or "").strip()
		port = int(getattr(doc, "hana_port", None) or 30015)
		user = (getattr(doc, "hana_user", None) or getattr(doc, "user_id", None) or getattr(doc, "username", None) or "").strip()
		schema_raw = (getattr(doc, "hana_schema", None) or getattr(doc, "schema", None) or getattr(doc, "companydb", None) or "").strip()
		password = doc.get_password("hana_password") or doc.get_password("password")

		if not host or not user or not password or not schema_raw:
			frappe.log_error(
				f"Real Aquatics SAP Settings: HANA connection incomplete (host={bool(host)}, user={bool(user)}, password={bool(password)}, schema={bool(schema_raw)}).",
				"Real Aquatics SAP Error",
			)
			return None, None, None

		connection = hana_db.connect(
			address=host,
			port=port,
			user=user,
			password=password,
			autocommit=False,
		)
		cursor = connection.cursor()
		return connection, cursor, schema_raw
	except Exception as e:
		frappe.log_error(f"INC HANA connection failed: {str(e)}", "Real Aquatics SAP Error")
		return None, None, None


def _close_inc_hana_connection(connection, cursor):
	"""Safely close INC HANA connection."""
	try:
		if cursor:
			cursor.close()
		if connection:
			connection.close()
	except Exception as e:
		frappe.log_error(f"Error closing INC HANA connection: {str(e)}", "Real Aquatics SAP Error")


@frappe.whitelist()
def add_real_aquatics_sap_settings_hana_fields():
	"""Add HANA custom fields to Real Aquatics SAP Settings so the form shows HANA Host, Port, User, Password, Schema. Call from Desk or console if the fields are missing."""
	_check_real_aquatics_access()
	try:
		_ensure_real_aquatics_sap_settings_hana_fields()
		return {"ok": True, "message": "HANA fields added or already present. Reload the Real Aquatics SAP Settings page (Ctrl+F5)."}
	except Exception as e:
		frappe.log_error(f"add_real_aquatics_sap_settings_hana_fields: {str(e)}", "Real Aquatics SAP Settings HANA Fields")
		return {"ok": False, "error": str(e)}


@frappe.whitelist()
def initiate_real_aquatics_sap_session():
	"""Force a new INC SAP B1 Service Layer login and save session on Real Aquatics SAP Settings. Used by Initiate Session button."""
	_check_real_aquatics_access()
	try:
		session, b1_url = _get_sap_session(force_login=True)
		if session and b1_url:
			return {"ok": True}
		return {"ok": False, "error": "Login failed"}
	except Exception as e:
		frappe.log_error(f"INC SAP session init failed: {str(e)}", "Real Aquatics SAP Error")
		return {"ok": False, "error": str(e)}


@frappe.whitelist()
def get_sap_health():
	"""Lightweight health signal for INC SAP B1 Service Layer connection.

	Returns:
	    {
	        "ok": bool,
	        "status": "connected" | "disconnected" | "error",
	        "message": str (optional)
	    }
	"""
	_check_real_aquatics_access()
	try:
		session, b1_url = _get_sap_session()
		if not session or not b1_url:
			return {
				"ok": False,
				"status": "disconnected",
				"message": "SAP session is not active. Use Renew Session to log in again.",
			}

		return {
			"ok": True,
			"status": "connected",
		}
	except Exception as e:
		frappe.log_error(f"SAP health check failed: {str(e)}", "Real Aquatics SAP Error")
		return {
			"ok": False,
			"status": "error",
			"message": str(e),
		}


def _enrich_item_names(session, b1_url, bom_items, item_codes):
	"""Fetch item names and UOM from SAP for BOM components that have empty names or default UOM."""
	try:
		filter_parts = " or ".join(f"ItemCode eq '{str(code).replace(chr(39), chr(39)+chr(39))}'" for code in item_codes)
		# InventoryUOM / InvntryUom hold the stock UOM on the item master
		url = f"{b1_url}Items?$select=ItemCode,ItemName,InventoryUOM,InvntryUom&$filter={filter_parts}"
		resp = session.get(url, verify=_SAP_VERIFY_SSL, timeout=15)
		if resp.status_code == 200:
			items = resp.json().get("value", [])
			name_map = {it["ItemCode"]: it.get("ItemName", "") for it in items}
			uom_map = {
				it["ItemCode"]: it.get("InventoryUOM") or it.get("InvntryUom") or ""
				for it in items
			}
			for bom_item in bom_items:
				code = bom_item.get("item_code")
				if not code:
					continue
				if not bom_item.get("item_name") and code in name_map:
					bom_item["item_name"] = name_map[code]
				# If UOM is missing or still the generic default, replace with item's InventoryUOM from SAP
				if code in uom_map:
					current_uom = (bom_item.get("uom") or "").strip()
					if not current_uom or current_uom == DEFAULT_UOM:
						u = (uom_map[code] or "").strip()
						if u:
							bom_item["uom"] = u
	except Exception as e:
		frappe.log_error(f"Item name enrichment failed: {e}", "Real Aquatics SAP Error")


@frappe.whitelist()
def _build_sap_item_filter(query):
	"""Return an OData $filter string for SAP Items by ItemCode or ItemName.
	SAP stores ItemCode in uppercase so we match both cases.
	Returns an empty string when query is blank.
	"""
	if not query:
		return ""
	s = str(query).replace("'", "''")[:50]
	s_upper = s.upper()
	return f"startswith(ItemCode,'{s_upper}') or contains(ItemName,'{s}') or contains(ItemName,'{s_upper}')"


def _map_sap_items(value):
	"""Map SAP Items OData response rows to the Real Aquatics item dict format."""
	return [
		{
			"item_code": item["ItemCode"],
			"item_name": item.get("ItemName", ""),
			"uom": item.get("InventoryUOM") or DEFAULT_UOM,
		}
		for item in value
	]


def get_items(search="", page=1, page_size=50):
	"""Fetch items from SAP B1 Service Layer"""
	_check_real_aquatics_access()

	session, b1_url = _get_sap_session()
	if not session:
		return {"data": [], "error": "SAP B1 Service Layer connection failed. Check SAP Settings."}

	try:
		skip = (int(page) - 1) * int(page_size)
		url = (
			f"{b1_url}Items?$select=ItemCode,ItemName,InventoryUOM"
			f"&$top={int(page_size)}&$skip={skip}&$orderby=ItemCode"
		)
		item_filter = _build_sap_item_filter(search)
		if item_filter:
			url += f"&$filter={item_filter}"

		resp, session, b1_url = _sap_get_with_retry(url, session, b1_url)
		if resp.status_code != 200:
			return {"data": [], "error": f"SAP returned status {resp.status_code}"}

		return {"data": _map_sap_items(resp.json().get("value", [])), "source": "sap"}

	except Exception as e:
		frappe.log_error(f"SAP items fetch error: {str(e)}", "Real Aquatics SAP Error")
		return {"data": [], "error": f"Failed to fetch items: {str(e)}"}


@frappe.whitelist()
def search_vendors(query=""):
	"""Search vendors (Business Partners) from SAP B1 Service Layer"""
	_check_real_aquatics_access()

	if not query or len(query) < 2:
		return {"data": []}

	# Escape single quotes for OData filter; case-insensitive for CardCode (SAP often stores in caps)
	q = str(query).replace("'", "''")[:50]
	q_upper = q.upper()

	session, b1_url = _get_sap_session()
	if not session:
		return {"data": [], "error": "SAP B1 Service Layer connection failed. Check SAP Settings."}

	try:
		# BusinessPartners with CardType = 'S' for supplier/vendor
		url = (
			f"{b1_url}BusinessPartners?$select=CardCode,CardName"
			f"&$filter=CardType eq 'S' and (startswith(CardCode,'{q_upper}') or contains(CardName,'{q}') or contains(CardName,'{q_upper}'))"
			f"&$top=20&$orderby=CardCode"
		)
		resp, session, b1_url = _sap_get_with_retry(url, session, b1_url)
		if resp.status_code != 200:
			return {"data": [], "error": f"SAP returned status {resp.status_code}"}

		data = resp.json()
		vendors = [
			{"card_code": item["CardCode"], "card_name": item.get("CardName", "")}
			for item in data.get("value", [])
		]
		return {"data": vendors, "source": "sap"}
	except Exception as e:
		frappe.log_error(f"SAP vendor search error: {str(e)}", "Real Aquatics SAP Error")
		return {"data": [], "error": str(e)}


@frappe.whitelist()
def search_customers(query=""):
	"""Search customers (Business Partners CardType C) from SAP B1 Service Layer. Used for Dispatch Orders."""
	_check_real_aquatics_access()

	if not query or len(query) < 2:
		return {"data": []}

	q = str(query).replace("'", "''")[:50]
	q_upper = q.upper()

	session, b1_url = _get_sap_session()
	if not session:
		return {"data": [], "error": "SAP B1 Service Layer connection failed. Check SAP Settings."}

	try:
		# CardType 'C' = Customer in SAP B1
		url = (
			f"{b1_url}BusinessPartners?$select=CardCode,CardName"
			f"&$filter=CardType eq 'C' and (startswith(CardCode,'{q_upper}') or contains(CardName,'{q}') or contains(CardName,'{q_upper}'))"
			f"&$top=20&$orderby=CardCode"
		)
		resp, session, b1_url = _sap_get_with_retry(url, session, b1_url)
		if resp.status_code != 200:
			return {"data": [], "error": f"SAP returned status {resp.status_code}"}

		data = resp.json()
		customers = [
			{"card_code": item["CardCode"], "card_name": item.get("CardName", "")}
			for item in data.get("value", [])
		]
		return {"data": customers, "source": "sap"}
	except Exception as e:
		frappe.log_error(f"SAP customer search error: {str(e)}", "Real Aquatics SAP Error")
		return {"data": [], "error": str(e)}


@frappe.whitelist()
def get_customer_addresses(card_code):
	"""Fetch all SAP addresses for a customer (CardCode). Used for Dispatch Order Ship-To selection."""
	_check_real_aquatics_access()
	card_code = (card_code or "").strip()
	if not card_code:
		return {"data": [], "error": "Customer code is required"}

	session, b1_url = _get_sap_session()
	if not session:
		return {"data": [], "error": "SAP B1 Service Layer connection failed. Check SAP Settings."}

	try:
		# Escape single quotes in CardCode for OData
		safe_code = card_code.replace("'", "''")
		# Plain GET; SAP B1 SL typically returns BPAddresses without $expand (expand can cause 400 on some versions)
		url = f"{b1_url}BusinessPartners('{safe_code}')"
		resp, session, b1_url = _sap_get_with_retry(url, session, b1_url)
		if resp.status_code == 404:
			return {"data": [], "error": "Customer not found in SAP"}
		if resp.status_code != 200:
			return {"data": [], "error": f"SAP returned status {resp.status_code}"}

		data = resp.json()
		addresses = data.get("BPAddresses") or []
		out = []
		for a in addresses:
			out.append({
				"address_name": a.get("AddressName", ""),
				"street": a.get("Street", ""),
				"city": a.get("City", ""),
				"state": a.get("State", ""),
				"zip_code": a.get("ZipCode", ""),
				"country": a.get("Country", ""),
				"address_type": a.get("AddressType", ""),
			})
		return {"data": out, "source": "sap"}
	except Exception as e:
		frappe.log_error(f"SAP get customer addresses error: {str(e)}", "Real Aquatics SAP Error")
		return {"data": [], "error": str(e)}


def get_vendor_country(card_code):
	"""Fetch a vendor's (BusinessPartner) top-level Country code from SAP B1. Used to decide
	the PO/GRN VAT tax code (UK = standard rate, non-UK = Outside Scope). Raises on failure —
	tax treatment must not silently default."""
	card_code = (card_code or "").strip()
	if not card_code:
		raise frappe.ValidationError(_("Vendor Code is required to determine VAT treatment"))

	session, b1_url = _get_sap_session()
	if not session:
		raise frappe.ValidationError(_("SAP B1 Service Layer connection failed. Check SAP Settings."))

	safe_code = card_code.replace("'", "''")
	url = f"{b1_url}BusinessPartners('{safe_code}')?$select=CardCode,Country"
	resp, session, b1_url = _sap_get_with_retry(url, session, b1_url)
	if resp.status_code == 404:
		raise frappe.ValidationError(_("Vendor {0} not found in SAP").format(card_code))
	if resp.status_code != 200:
		raise frappe.ValidationError(_("Failed to fetch vendor {0} from SAP ({1})").format(card_code, resp.status_code))
	return (resp.json().get("Country") or "").strip()


def get_customer_ship_to_country(card_code, ship_to_code):
	"""Fetch the Country of a specific Ship-To address for a customer. Used to decide the
	Dispatch Order/Sales Order VAT tax code (UK = standard rate, non-UK = Outside Scope).
	Raises if the address can't be resolved — tax treatment must not silently default."""
	card_code = (card_code or "").strip()
	ship_to_code = (ship_to_code or "").strip()
	if not card_code or not ship_to_code:
		raise frappe.ValidationError(_("Customer Code and Ship-To address are required to determine VAT treatment"))

	result = get_customer_addresses(card_code)
	if result.get("error"):
		raise frappe.ValidationError(_("Failed to fetch Ship-To address for {0}: {1}").format(card_code, result["error"]))
	for addr in result.get("data", []):
		if (addr.get("address_name") or "").strip() == ship_to_code:
			return (addr.get("country") or "").strip()
	raise frappe.ValidationError(_("Ship-To address {0} not found for customer {1}").format(ship_to_code, card_code))


@frappe.whitelist()
def add_customer_address(card_code, data, address_type="bo_ShipTo"):
	"""Add a new Ship-To or Bill-To address for a customer in SAP. data: JSON with address_name, street, city, state, zip_code, country. address_type: bo_ShipTo or bo_BillTo."""
	_check_real_aquatics_access()
	card_code = (card_code or "").strip()
	if not card_code:
		frappe.throw(_("Customer code is required"), frappe.ValidationError)
	if isinstance(data, str):
		data = json.loads(data) if data else {}
	if not isinstance(data, dict):
		frappe.throw(_("Invalid address data"), frappe.ValidationError)
	# Normalize address_type for SAP
	addr_type = (address_type or "bo_ShipTo").strip()
	if addr_type.lower() in ("bo_billto", "billto", "bill_to", "bill"):
		addr_type = "bo_BillTo"
	else:
		addr_type = "bo_ShipTo"

	address_name = (data.get("address_name") or "").strip()
	if not address_name:
		frappe.throw(_("Address name is required (e.g. Main or Ship-To 1)"), frappe.ValidationError)
	street = (data.get("street") or "").strip()
	if not street:
		frappe.throw(_("Street is required"), frappe.ValidationError)

	session, b1_url = _get_sap_session()
	if not session:
		frappe.throw(_("SAP B1 Service Layer connection failed. Check SAP Settings."), frappe.ValidationError)

	try:
		safe_code = card_code.replace("'", "''")
		# Plain GET (no $expand) so SAP returns BPAddresses by default; expand can cause 400 on some versions
		url_get = f"{b1_url}BusinessPartners('{safe_code}')"
		resp, session, b1_url = _sap_get_with_retry(url_get, session, b1_url)
		if resp.status_code != 200:
			frappe.throw(_("Customer not found in SAP or SAP error: {0}").format(resp.status_code), frappe.ValidationError)

		bp = resp.json()
		existing = list(bp.get("BPAddresses") or [])
		# New address row: RowNum -1 is standard for new in SAP B1 SL.
		# State is a linked field (OCRD.State2) in SAP; only values from the state master are valid.
		# Omit State to avoid "Linked value X does not exist" - user can set it in SAP if needed.
		new_row = {
			"RowNum": -1,
			"AddressName": address_name[:50],
			"Street": (data.get("street") or "").strip()[:100],
			"City": (data.get("city") or "").strip()[:100],
			"ZipCode": (data.get("zip_code") or "").strip()[:20],
			"County": (data.get("country") or "").strip()[:100],
			"AddressType": addr_type,
			"BPCode": card_code,
		}
		# Keep existing addresses as-is (include RowNum so we don't duplicate)
		patched_list = []
		for a in existing:
			patched_list.append({
				"RowNum": a.get("RowNum"),
				"AddressName": a.get("AddressName", ""),
				"Street": a.get("Street", ""),
				"City": a.get("City", ""),
				"State": a.get("State", ""),
				"ZipCode": a.get("ZipCode", ""),
				"County": a.get("County", ""),
				"AddressType": a.get("AddressType", ""),
				"BPCode": a.get("BPCode", card_code),
			})
		patched_list.append(new_row)

		patch_url = f"{b1_url}BusinessPartners('{safe_code}')"
		patch_payload = {"BPAddresses": patched_list}
		# Avoid Expect: 100-continue so SAP does not return 417 Expectation Failed
		headers = {"Content-Type": "application/json", "Expect": ""}
		resp2 = session.patch(patch_url, json=patch_payload, verify=_SAP_VERIFY_SSL, timeout=30, headers=headers)
		if resp2.status_code not in (200, 204):
			err = getattr(resp2, "text", str(resp2))
			try:
				err = resp2.json().get("error", {}).get("message", {}).get("value", err)
			except Exception:
				pass
			frappe.log_error(f"SAP add address failed: {resp2.status_code} {err}", "Real Aquatics SAP Add Address")
			frappe.throw(_("Failed to add address in SAP: {0}").format(err), frappe.ValidationError)

		return {"address_name": address_name, "message": "Address added in SAP. You can now select it as Ship-To."}
	except frappe.ValidationError:
		raise
	except Exception as e:
		frappe.log_error(f"SAP add customer address error: {str(e)}", "Real Aquatics SAP Error")
		frappe.throw(_("Failed to add address in SAP: {0}").format(str(e)), frappe.ValidationError)


def create_sales_order_from_dispatch_order(doc):
	"""Create SAP B1 Sales Order (Orders) from Real Aquatics Dispatch Order. Used when manager approves.
	Mandatory: CardCode, DocumentLines (ItemCode, Quantity, UnitPrice).
	Returns dict with doc_entry and doc_num. Raises on failure."""
	session, b1_url = _get_sap_session()
	if not session:
		raise frappe.ValidationError(_("SAP B1 Service Layer connection failed. Check SAP Settings."))

	card_code = (doc.card_code or "").strip()
	if not card_code:
		raise frappe.ValidationError(_("Customer Code (CardCode) is required for SAP Sales Order"))
	card_name = (doc.card_name or "").strip() or card_code

	doc_date = (doc.doc_date or frappe.utils.today()).strftime("%Y-%m-%d") if hasattr(doc.doc_date, "strftime") else str(doc.doc_date or frappe.utils.today())
	doc_due_date = (doc.doc_due_date or doc.doc_date or frappe.utils.today()).strftime("%Y-%m-%d") if getattr(doc.doc_due_date, "strftime", None) else str(doc.doc_due_date or doc.doc_date or frappe.utils.today())

	ship_to_code = (getattr(doc, "ship_to_code", None) or "") if not isinstance(doc, dict) else (doc.get("ship_to_code") or "")
	ship_to_code = (ship_to_code or "").strip()
	if not ship_to_code:
		raise frappe.ValidationError(_("Ship-To address (SAP) is required. Select an address for the customer or add one in SAP first."))
	bill_to_code = (getattr(doc, "bill_to_code", None) or "") if not isinstance(doc, dict) else (doc.get("bill_to_code") or "")
	bill_to_code = (bill_to_code or "").strip()
	if not bill_to_code:
		raise frappe.ValidationError(_("Bill-To address (SAP) is required. Select an address for the customer or add one in SAP first."))

	# VAT (per finance): UK Ship-To = standard rate, non-UK = Outside Scope. Resolved from the
	# live Ship-To address country, not the Bill-To — same customer can ship both ways.
	ship_to_country = get_customer_ship_to_country(card_code, ship_to_code)
	tax_code = tax_code_for_country(ship_to_country, sales=True)

	# Build payload in B2B order: header fields first, DocumentLines last (SAP can be strict on key order)
	num_at_card = (doc.num_at_card or "").strip()
	comments = _truncate_sap_comments(doc.comments)

	payload = {
		"CardCode": card_code,
		"CardName": card_name,
		"DocDate": doc_date,
		"DocDueDate": doc_due_date,
		"ShipToCode": ship_to_code,
		"PayToCode": bill_to_code,
	}
	if num_at_card:
		payload["NumAtCard"] = num_at_card[:50]
	if comments:
		payload["Comments"] = comments

	# Document lines: minimal like B2B (ItemCode, Quantity, UnitPrice) so SAP accepts;
	# for Real Aquatics Dispatch Orders, all lines should go from finished warehouse RP-FG.
	lines = []
	for row in doc.items:
		item_code = (row.get("item_code") or "").strip() if isinstance(row, dict) else (getattr(row, "item_code", None) or "").strip()
		qty = float(row.get("quantity") or 0) if isinstance(row, dict) else float(getattr(row, "quantity", 0) or 0)
		unit_price = float(row.get("unit_price") or 0) if isinstance(row, dict) else float(getattr(row, "unit_price", 0) or 0)
		if not item_code or qty <= 0:
			continue
		line_item = {
			"ItemCode": item_code,
			"Quantity": qty,
			"UnitPrice": unit_price,
			"WarehouseCode": "RP-FG",
			"VatGroup": tax_code,
		}
		lines.append(line_item)

	if not lines:
		raise frappe.ValidationError(_("At least one line with ItemCode, Quantity and UnitPrice is required for SAP Sales Order"))

	# DocumentLines must be last (replicate B2B Orders payload structure)
	payload["DocumentLines"] = lines

	url = b1_url + "Orders"
	payload_json = json.dumps(payload, indent=2, default=str)
	resp, session, b1_url = _sap_post_with_retry(url, session, b1_url, payload)
	if resp.status_code not in (200, 201):
		err = resp.text
		try:
			err = resp.json().get("error", {}).get("message", {}).get("value", err)
		except Exception:
			pass
		frappe.log_error(
			f"SAP Sales Order create failed (Dispatch Order): CardCode={card_code!r} | {resp.status_code} {err}\n\n--- Payload sent to SAP ---\n{payload_json}",
			"Real Aquatics Dispatch Order SAP",
		)
		# ODBC -2028 = No matching records – usually invalid CardCode (customer) or ItemCode
		if "ODBC -2028" in str(err) or "No matching records" in str(err):
			item_codes = [ln.get("ItemCode") for ln in lines]
			err = _(
				"No matching records in SAP (ODBC -2028). "
				"Check that Customer '{0}' and all item codes ({1}) exist in SAP. "
				"Select customer and items using the SAP search only."
			).format(card_code, ", ".join(item_codes[:5]) + ("..." if len(item_codes) > 5 else ""))
		# Invalid Ship-To address code on the Sales Order (ORDR.ShipToCode)
		elif "ShipToCode" in str(err):
			err = _(
				"Invalid Ship-To address in SAP for customer {0}. "
				"Open the Dispatch Order in KhanalFoods, refresh customer addresses, "
				"select a valid Ship-To address from SAP, save, and submit again."
			).format(card_code)
		raise frappe.ValidationError(err)

	result = resp.json()
	doc_entry = result.get("DocEntry")
	if not doc_entry:
		raise frappe.ValidationError(_("SAP did not return DocEntry for Sales Order"))
	return {"doc_entry": str(doc_entry), "doc_num": str(result.get("DocNum") or "")}


def create_delivery_from_dispatch_order(dispatch_docname):
	"""Create SAP Delivery (DeliveryNotes) for a Real Aquatics Dispatch Order.

	Uses the SAP Sales Order linked to the dispatch order (sap_doc_entry),
	and maps Real Aquatics dispatch lines (item_code, quantity, batch_number) to
	SAP Sales Order DocumentLines via ItemCode and LineNum. Each delivery
	line is linked using BaseType/BaseEntry/BaseLine so that the Delivery
	is properly connected to the Sales Order in SAP."""
	session, b1_url = _get_sap_session()
	if not session:
		raise frappe.ValidationError(_("SAP B1 Service Layer connection failed. Check SAP Settings."))

	# Load the Real Aquatics Dispatch Order and ensure we have a Sales Order DocEntry
	doc = frappe.get_doc("Real Aquatics Dispatch Order", dispatch_docname)
	so_entry_raw = (doc.sap_doc_entry or "").strip()
	if not so_entry_raw:
		raise frappe.ValidationError(_("SAP Sales Order DocEntry is missing on Dispatch Order {0}").format(doc.name))

	# First, assume sap_doc_entry is the true DocEntry
	order_url = f"{b1_url}Orders({int(so_entry_raw)})"
	resp, session, b1_url = _sap_get_with_retry(order_url, session, b1_url)

	# If that fails for any reason, unconditionally fall back to searching by DocNum.
	if resp.status_code != 200:
		try:
			docnum_int = int(so_entry_raw)
		except Exception:
			raise frappe.ValidationError(_("Failed to fetch Sales Order {0} from SAP ({1})").format(so_entry_raw, resp.status_code))

		search_url = f"{b1_url}Orders?$filter=DocNum eq {docnum_int}"
		resp, session, b1_url = _sap_get_with_retry(search_url, session, b1_url)
		if resp.status_code != 200:
			raise frappe.ValidationError(_("Failed to fetch Sales Order by DocNum {0} from SAP ({1})").format(so_entry_raw, resp.status_code))
		data = resp.json() or {}
		values = data.get("value") or []
		if not values:
			raise frappe.ValidationError(_("No Sales Order found in SAP for DocEntry/DocNum {0}").format(so_entry_raw))
		so = values[0]
		# Replace doc_entry with true DocEntry from SAP so BaseEntry is correct
		so_entry = so.get("DocEntry")
	else:
		so = resp.json()
		so_entry = so.get("DocEntry")

	if not so_entry:
		raise frappe.ValidationError(_("SAP did not return DocEntry for Sales Order when building Delivery"))

	# Map dispatch rows to SAP SO lines. Multiple Real Aquatics rows (e.g. different batches for
	# the same item) often resolve to the *same* SO LineNum. SAP allows only ONE Delivery
	# document line per BaseLine; a second row with the same BaseLine fails with
	# "Invalid value [DocumentLines.BaseLine][line: 1]". Merge by BaseLine and send one
	# line with multiple BatchNumbers when needed.
	so_lines = so.get("DocumentLines", []) or []
	# base_line -> list of (qty, batch_no)
	by_soline = defaultdict(list)

	for row in doc.items:
		item_code = (row.item_code or "").strip()
		qty = float(row.quantity or 0)
		if not item_code or qty <= 0:
			continue

		target_line = None
		for line in so_lines:
			if (line.get("ItemCode") or "").strip() != item_code:
				continue
			if line.get("LineStatus") == "bost_Close":
				continue
			open_qty = float(line.get("OpenQuantity") if "OpenQuantity" in line else line.get("Quantity") or 0)
			if open_qty <= 0:
				continue
			target_line = line
			break

		if not target_line:
			continue

		base_line = int(target_line.get("LineNum", 0))
		batch_no = (getattr(row, "batch_number", None) or "").strip()
		by_soline[base_line].append((qty, batch_no))

	lines = []
	for base_line in sorted(by_soline.keys()):
		segments = by_soline[base_line]
		total_qty = sum(q for q, _ in segments)
		line_payload = {
			"BaseType": 17,  # Orders
			"BaseEntry": int(so_entry),
			"BaseLine": base_line,
			"Quantity": total_qty,
		}

		batched_qty = sum(q for q, bn in segments if bn)
		unbatched_qty = sum(q for q, bn in segments if not bn)
		if batched_qty > 0 and unbatched_qty > 0:
			raise frappe.ValidationError(
				_(
					"For SAP delivery, all rows for the same sales order line must use batch numbers, "
					"or none. Split batches are only supported when every split has a batch."
				)
			)
		if batched_qty > 0:
			batch_totals = defaultdict(float)
			for q, bn in segments:
				if bn:
					batch_totals[bn] += q
			line_payload["BatchNumbers"] = [
				{"BatchNumber": bn, "Quantity": qty} for bn, qty in sorted(batch_totals.items())
			]

		lines.append(line_payload)

	if not lines:
		raise frappe.ValidationError(_("No open lines found on Sales Order {0} for delivery").format(so_entry))

	payload = {
		"CardCode": so.get("CardCode"),
		"DocDate": so.get("DocDate"),
		"DocDueDate": so.get("DocDueDate"),
		"Comments": _truncate_sap_comments(so.get("Comments") or ""),
		"DocumentLines": lines,
	}

	url = b1_url + "DeliveryNotes"
	resp, session, b1_url = _sap_post_with_retry(url, session, b1_url, payload)
	if resp.status_code not in (200, 201):
		err = resp.text
		try:
			err = resp.json().get("error", {}).get("message", {}).get("value", err)
		except Exception:
			pass
		frappe.log_error(
			f"SAP Delivery create failed (Dispatch Order): Order={so_entry!r} | {resp.status_code} {err}",
			"Real Aquatics Dispatch Delivery SAP",
		)
		raise frappe.ValidationError(err)

	result = resp.json()
	dn_entry = result.get("DocEntry")
	if not dn_entry:
		raise frappe.ValidationError(_("SAP did not return DocEntry for Delivery"))
	return {"doc_entry": str(dn_entry), "doc_num": str(result.get("DocNum") or "")}


def create_ar_invoice_from_delivery(doc_entry):
	"""Create SAP AR Invoice (Invoices) from an existing Delivery DocEntry.
	Links invoice lines to the delivery using BaseEntry/BaseLine."""
	session, b1_url = _get_sap_session()
	if not session:
		raise frappe.ValidationError(_("SAP B1 Service Layer connection failed. Check SAP Settings."))

	dn_url = f"{b1_url}DeliveryNotes({int(doc_entry)})"
	resp, session, b1_url = _sap_get_with_retry(dn_url, session, b1_url)
	if resp.status_code != 200:
		raise frappe.ValidationError(_("Failed to fetch Delivery {0} from SAP ({1})").format(doc_entry, resp.status_code))
	dn = resp.json()

	lines = []
	for line in dn.get("DocumentLines", []) or []:
		# For freshly created Delivery Notes, SAP may already mark lines as "closed",
		# but they are still valid as a base for AR Invoice. Only skip lines with
		# non-positive quantity; do NOT filter by LineStatus here.
		qty = float(line.get("Quantity") or 0)
		if qty <= 0:
			continue
		line_payload = {
			"BaseType": 15,  # DeliveryNotes
			"BaseEntry": int(doc_entry),
			"BaseLine": int(line.get("LineNum", 0)),
			"Quantity": qty,
		}
		# Tax code is carried over from the Delivery line, which inherited it from the Sales
		# Order line (set explicitly in create_sales_order_from_dispatch_order based on the
		# Ship-To country). If it's ever missing, don't guess — surface it instead of silently
		# posting an invoice with the wrong VAT treatment.
		vat_group = (line.get("VatGroup") or line.get("TaxCode") or "").strip()
		if not vat_group:
			raise frappe.ValidationError(
				_("Delivery {0} line {1} has no tax code — cannot determine VAT treatment for the AR Invoice.").format(doc_entry, line.get("LineNum", 0))
			)
		line_payload["TaxCode"] = vat_group
		lines.append(line_payload)
	if not lines:
		raise frappe.ValidationError(_("No open lines found on Delivery {0} for invoicing").format(doc_entry))

	payload = {
		"CardCode": dn.get("CardCode"),
		"DocDate": dn.get("DocDate"),
		"DocDueDate": dn.get("DocDueDate"),
		"Comments": _truncate_sap_comments(dn.get("Comments") or ""),
		"DocumentLines": lines,
	}

	url = b1_url + "Invoices"
	resp, session, b1_url = _sap_post_with_retry(url, session, b1_url, payload)
	if resp.status_code not in (200, 201):
		err = resp.text
		try:
			err = resp.json().get("error", {}).get("message", {}).get("value", err)
		except Exception:
			pass
		frappe.log_error(
			f"SAP AR Invoice create failed (Dispatch Order): Delivery={doc_entry!r} | {resp.status_code} {err}",
			"Real Aquatics Dispatch AR Invoice SAP",
		)
		raise frappe.ValidationError(err)

	result = resp.json()
	inv_entry = result.get("DocEntry")
	if not inv_entry:
		raise frappe.ValidationError(_("SAP did not return DocEntry for AR Invoice"))
	return {"doc_entry": str(inv_entry), "doc_num": str(result.get("DocNum") or "")}


@frappe.whitelist()
def search_items(query=""):
	"""Quick item search from SAP B1 Service Layer"""
	_check_real_aquatics_access()

	if not query or len(query) < 2:
		return {"data": []}

	session, b1_url = _get_sap_session()
	if not session:
		return {"data": [], "error": "SAP B1 Service Layer connection failed. Check SAP Settings."}

	try:
		q = str(query).replace("'", "''")[:50]
		q_upper = q.upper()
		url = (
			f"{b1_url}Items?$select=ItemCode,ItemName,InventoryUOM"
			f"&$filter=startswith(ItemCode,'{q_upper}') or contains(ItemName,'{q}') or contains(ItemName,'{q_upper}')"
			f"&$top=20&$orderby=ItemCode"
		)

		resp, session, b1_url = _sap_get_with_retry(url, session, b1_url)
		if resp.status_code != 200:
			return {"data": [], "error": f"SAP returned status {resp.status_code}"}

		data = resp.json()
		items = [
			{
				"item_code": item["ItemCode"],
				"item_name": item.get("ItemName", ""),
				"uom": item.get("InventoryUOM") or DEFAULT_UOM,
			}
			for item in data.get("value", [])
		]
		return {"data": items, "source": "sap"}

	except Exception as e:
		frappe.log_error(f"SAP search error: {str(e)}", "Real Aquatics SAP Error")
		return {"data": [], "error": f"Search failed: {str(e)}"}


@frappe.whitelist()
def get_bom(item_code):
	"""Get BOM (Bill of Materials) from SAP B1 Service Layer"""
	_check_real_aquatics_access()

	if not item_code:
		frappe.throw(_("Item Code is required"))

	session, b1_url = _get_sap_session()
	if not session:
		return {"bom_no": "", "items": [], "error": "SAP B1 connection failed."}

	try:
		item_esc = (item_code or "").strip().replace("'", "''")

		# Strategy 1: filter + $expand (most versions)
		url_filter_expand = f"{b1_url}ProductTrees?$filter=TreeCode eq '{item_esc}'&$expand=ProductTreeLines"
		resp, session, b1_url = _sap_get_with_retry(url_filter_expand, session, b1_url)

		# Strategy 2: direct key access + $expand (some SAP versions reject $expand with $filter)
		if resp.status_code != 200:
			url_key_expand = f"{b1_url}ProductTrees('{item_esc}')?$expand=ProductTreeLines"
			resp, session, b1_url = _sap_get_with_retry(url_key_expand, session, b1_url)

		# Strategy 3: direct key access without $expand (lines fetched separately below)
		if resp.status_code != 200:
			url_key_plain = f"{b1_url}ProductTrees('{item_esc}')"
			resp, session, b1_url = _sap_get_with_retry(url_key_plain, session, b1_url)

		if resp.status_code != 200:
			return {"bom_no": "", "items": [], "error": f"SAP returned {resp.status_code} for BOM of {item_code}"}

		data = resp.json()
		# Normalise: filter response wraps in {value: [...]}, key-access returns the doc directly
		if "value" in data:
			trees = data.get("value", [])
			tree = trees[0] if trees else None
		else:
			tree = data if data.get("TreeCode") else None

		if not tree:
			# Re-login once and retry the first strategy
			session, b1_url = _get_sap_session(force_login=True)
			if session:
				resp2 = session.get(url_filter_expand, verify=_SAP_VERIFY_SSL, timeout=15)
				if resp2.status_code == 200:
					d2 = resp2.json()
					trees2 = d2.get("value", [])
					tree = trees2[0] if trees2 else None

		if not tree:
			return {"bom_no": "", "items": [], "error": f"No BOM found for {item_code}"}

		# If ProductTreeLines is absent (plain GET without $expand), fetch lines separately
		if not tree.get("ProductTreeLines"):
			url_lines = f"{b1_url}ProductTrees('{item_esc}')/ProductTreeLines"
			resp_lines, session, b1_url = _sap_get_with_retry(url_lines, session, b1_url)
			if resp_lines.status_code == 200:
				lines_data = resp_lines.json()
				tree["ProductTreeLines"] = lines_data.get("value", lines_data if isinstance(lines_data, list) else [])

		bom_items = []
		item_codes_needing_enrichment = []
		for line in tree.get("ProductTreeLines", []):
			if line.get("ItemCode"):
				name = line.get("ItemName") or line.get("ItemDescription") or ""
				uom = line.get("InventoryUOM") or DEFAULT_UOM
				row = {
					"item_code": line["ItemCode"],
					"item_name": name,
					"required_qty": float(line.get("Quantity", 0)),
					"uom": uom,
					"warehouse": REALAQUATICS_WAREHOUSE,
				}
				bom_items.append(row)
				# Enrich whenever name is missing OR UOM is still the generic default ("Nos")
				if (not name) or (not (uom or "").strip()) or (uom == DEFAULT_UOM):
					item_codes_needing_enrichment.append(line["ItemCode"])

		if item_codes_needing_enrichment:
			_enrich_item_names(session, b1_url, bom_items, item_codes_needing_enrichment)

		return {
			"bom_no": tree.get("TreeCode", item_code),
			"finished_item_name": tree.get("ProductDescription") or tree.get("ItemName") or "",
			"warehouse": REALAQUATICS_WAREHOUSE,
			"items": bom_items,
			"source": "sap",
		}

	except Exception as e:
		frappe.log_error(f"SAP BOM fetch error: {str(e)}", "Real Aquatics SAP Error")
		return {"bom_no": "", "items": [], "error": f"BOM fetch failed: {str(e)}"}


@frappe.whitelist()
def get_warehouses():
	"""Return list of warehouses from SAP B1 Service Layer for dropdowns (code + name)."""
	_check_real_aquatics_access()

	session, b1_url = _get_sap_session()
	if not session:
		return {"data": [], "error": "SAP B1 Service Layer connection failed. Check SAP Settings."}

	try:
		def _is_active(row):
			"""SAP B1: Inactive = 'tYES' means inactive; Active = 'tNO' means inactive. Keep only active."""
			inactive = row.get("Inactive") or row.get("inactive")
			if inactive is not None:
				if isinstance(inactive, str) and inactive.upper() in ("TYES", "Y", "YES", "1", "TRUE"):
					return False
				if isinstance(inactive, bool) and inactive:
					return False
			active = row.get("Active") or row.get("active")
			if active is not None:
				if isinstance(active, str) and active.upper() in ("TNO", "N", "NO", "0", "FALSE"):
					return False
				if isinstance(active, bool) and not active:
					return False
			return True

		# Service Layer: try common entity names; return only active warehouses
		for entity in ("Warehouses", "Warehouse", "OWHS"):
			url = f"{b1_url}{entity}?$top=100"
			resp, session, b1_url = _sap_get_with_retry(url, session, b1_url)
			if resp.status_code != 200:
				continue
			try:
				data = resp.json()
			except Exception:
				continue
			rows = data.get("value") or data.get("d", {}).get("results") or []
			if isinstance(rows, dict):
				rows = [rows]
			if not rows:
				continue
			out = []
			for row in rows:
				if not _is_active(row):
					continue
				code = (
					row.get("WarehouseCode") or row.get("WhsCode") or row.get("Code") or ""
				).strip()
				name = (
					row.get("WarehouseName") or row.get("WhsName") or row.get("Name") or ""
				).strip()
				if not code and isinstance(row, dict):
					for k, v in row.items():
						if k and v and isinstance(v, str) and len(v) <= 20 and " " not in v:
							code = (v or "").strip()
							break
				if code:
					out.append({"warehouse_code": code, "warehouse_name": name or code})
			if out:
				return {"data": out, "source": "sap"}
		return {"data": [], "error": "No warehouse list found in SAP"}
	except Exception as e:
		frappe.log_error(f"SAP warehouses fetch error: {str(e)}", "Real Aquatics SAP Error")
		return {"data": [], "error": str(e)}


@frappe.whitelist()
def get_batches_for_item(item_code, warehouse_code=None, all_warehouses=False):
	"""Return available batches for an item (and optionally warehouse) from SAP B1 Service Layer.

	Returns list of { "batch_number": str, "quantity": float } for use in WO component batch dropdown.
	Pass all_warehouses=True to skip warehouse filtering (used for Special production orders where
	components can be finished goods items stored in any warehouse).
	"""
	_check_real_aquatics_access()

	if not item_code or not str(item_code).strip():
		return {"data": [], "error": "Item code is required"}

	# all_warehouses=True skips warehouse filter entirely (Special WO components span all warehouses).
	if all_warehouses in (True, "true", "1", 1):
		whs = ""
	else:
		# Normalize warehouse: decode + as space, strip and collapse spaces; SAP may use "RP-STR" or "RP-STR".
		whs = (warehouse_code or REALAQUATICS_WAREHOUSE or "").replace("+", " ").strip().replace("  ", " ")
	whs_variants = list({whs, whs.replace(" ", "")} if whs else [""])

	try:
		# Case-insensitive: normalize to uppercase so SAP/HANA match (SAP often stores ItemCode in caps)
		item_code_norm = str(item_code).strip().upper()
		item_esc = item_code_norm.replace("'", "''")

		def _only_positive_qty(batch_list):
			"""Exclude batches with quantity 0 so the dropdown only shows usable options."""
			return [b for b in (batch_list or []) if (b.get("quantity") or 0) > 0]

		# First, try INC HANA (OBTQ/OBTN) using the same logic used elsewhere for batch + quantity.
		connection, cursor, schema = _get_inc_hana_connection()
		if connection and cursor and schema:
			try:
				# Basic HANA query: OBTQ (quantity by ItemCode+WhsCode+SysNumber) + OBTN (DistNumber, dates)
				# We prefer warehouse-filtered results when a warehouse is provided.
				base_query = f'''
					SELECT
						T1."DistNumber" AS "BatchNumber",
						T0."Quantity"   AS "Quantity"
					FROM {schema}."OBTQ" T0
					JOIN {schema}."OBTN" T1
						ON T0."ItemCode" = T1."ItemCode"
						AND T0."SysNumber" = T1."SysNumber"
					WHERE
						T0."ItemCode" = ?
						AND T0."Quantity" > 0
				'''

				params_base = [item_code_norm]

				# If we have a warehouse, filter on WhsCode; try primary then variant (e.g. "RP-STR" then "RP-STR").
				warehouses_to_try = [None] if not whs else list({whs, whs.replace(" ", "")})
				rows = []
				for wh in warehouses_to_try:
					q = base_query + (' AND T0."WhsCode" = ?' if wh else "") + ' ORDER BY T1."InDate" DESC'
					p = params_base + ([wh] if wh else [])
					cursor.execute(q, p)
					rows = cursor.fetchall() or []
					if rows:
						break

				if rows:
					batches = [
						{"batch_number": str(r[0]).strip(), "quantity": float(r[1] or 0)}
						for r in rows
					]
					batches = _only_positive_qty(batches)
					if batches:
						_close_inc_hana_connection(connection, cursor)
						return {"data": batches, "source": "sap_hana_inc"}
			except Exception as e:
				# Log and fall back to Service Layer implementation
				frappe.log_error(f"INC HANA batch fetch failed for item {item_code}: {str(e)}", "Real Aquatics SAP Error")
			finally:
				_close_inc_hana_connection(connection, cursor)

		def _get_any_key(row, *keys):
			"""Get first matching key from row (case-insensitive)."""
			lower_map = {k.lower(): v for k, v in (row or {}).items() if isinstance(k, str)}
			for k in keys:
				for lk, v in lower_map.items():
					if k.lower() in lk or lk in k.lower():
						if v is not None and v != "":
							return v
			return None

		def _get_quantity(row):
			"""Try all known SAP quantity field names; prefer non-zero when available."""
			# Order: prefer stock/on-hand style fields first (often the "available" qty), then Quantity
			candidate_keys = (
				"QuantityOnStock", "QuantityOnHand", "AvailableQuantity", "OnHand", "InStock",
				"QtyOnHand", "Balance", "StockQuantity", "QuantityAvailable", "AvailQty", "OnOrder",
				"Quantity", "quantity", "InQty", "Qty",
			)
			for k in candidate_keys:
				v = row.get(k)
				if v is not None and v != "":
					try:
						f = float(v)
						if f >= 0:
							return f
					except (TypeError, ValueError):
						pass
			# Case-insensitive fallback: any key suggesting quantity
			q = _get_any_key(row, "QuantityOnStock", "OnHand", "Quantity", "Available", "Stock", "Balance", "Qty", "Avail")
			if q is not None:
				try:
					return float(q)
				except (TypeError, ValueError):
					pass
			return 0.0

		def parse_batches(rows):
			out = []
			for row in rows:
				if not isinstance(row, dict):
					continue
				bn = (
					row.get("BatchNumber") or row.get("batch_number") or row.get("DistNumber")
					or row.get("BatchNum") or row.get("Number") or row.get("DocEntry")
					or _get_any_key(row, "Batch", "Dist", "Number", "batch", "dist")
				)
				bn = str(bn).strip() if bn is not None else ""
				qty = _get_quantity(row)
				if bn:
					out.append({"batch_number": bn, "quantity": qty})
			return out

		# Service Layer fallback: get session only when HANA did not return data.
		session, b1_url = _get_sap_session()
		if not session:
			return {"data": [], "error": "SAP B1 Service Layer connection failed. Check Real Aquatics SAP Settings."}

		# Try both ItemBatchNumbers and BatchNumberDetails (SL API doc entity); warehouse may be WarehouseCode or WhsCode.
		select = "BatchNumber,Quantity,QuantityOnStock,QuantityOnHand,OnHand,DistNumber,ItemCode,WarehouseCode,WhsCode,DocEntry,ItemDescription"
		for entity in ("ItemBatchNumbers", "BatchNumberDetails"):
			for whs_field in ("WarehouseCode", "WhsCode"):
				for w in whs_variants:
					if not w:
						continue
					w_esc = w.replace("'", "''")
					url = f"{b1_url}{entity}?$filter=ItemCode eq '{item_esc}' and {whs_field} eq '{w_esc}'&$select={select}"
					resp, session, b1_url = _sap_get_with_retry(url, session, b1_url)
					if resp.status_code == 404:
						break
					if resp.status_code != 200:
						continue
					payload = resp.json() or {}
					rows = payload.get("value") or payload.get("d") or payload.get("results") or []
					if rows:
						return {"data": _only_positive_qty(parse_batches(rows)), "source": "sap"}
			if resp.status_code == 404:
				break

		# Fallback: query without warehouse filter, then filter by warehouse in Python (same parse_batches for qty).
		for entity in ("ItemBatchNumbers", "BatchNumberDetails"):
			url = f"{b1_url}{entity}?$filter=ItemCode eq '{item_esc}'&$select={select}"
			resp, session, b1_url = _sap_get_with_retry(url, session, b1_url)
			if resp.status_code != 200:
				continue
			payload = resp.json() or {}
			rows = payload.get("value") or payload.get("d") or payload.get("results") or []
			if rows:
				batches = []
				for row in rows:
					row_whs = (row.get("WarehouseCode") or row.get("WhsCode") or "").strip()
					if row_whs and whs_variants:
						row_whs_ns = row_whs.replace(" ", "")
						if not any(
							row_whs.upper() == v.upper() or (v and row_whs_ns.upper() == v.replace(" ", "").upper())
							for v in whs_variants if v
						):
							continue
					batches.extend(parse_batches([row]))
				batches = _only_positive_qty(batches)
				if batches:
					return {"data": batches, "source": "sap"}

		# Last resort: try multiple possible entity names and return all batches for item.
		# Some SL versions use different names; try without $select to get any batch-related fields.
		for entity in ("ItemBatchNumbers", "BatchNumberDetails", "BatchNumbers", "OIBT", "ItemBatches"):
			for use_select in (True, False):
				select_part = "&$select=BatchNumber,Quantity,QuantityOnStock,QuantityOnHand,OnHand,ItemCode,WarehouseCode,WhsCode,DistNumber" if use_select else ""
				url = f"{b1_url}{entity}?$filter=ItemCode eq '{item_esc}'{select_part}"
				resp, session, b1_url = _sap_get_with_retry(url, session, b1_url)
				if resp.status_code == 200:
					payload = resp.json() or {}
					rows = payload.get("value") or payload.get("d") or payload.get("results") or []
					if rows:
						batches = _only_positive_qty(parse_batches(rows))
						if batches:
							return {"data": batches, "source": "sap"}
						# Response has rows but parse_batches got nothing – try to extract from first row keys
						first = rows[0] if rows else {}
						# Log for debugging what SAP actually returned
						frappe.log_error(
							message=f"get_batches_for_item: entity={entity} item={item_code} keys={list(first.keys())} sample={json.dumps(first)[:500]}",
							title="SAP Batch Response Shape",
						)
				if resp.status_code == 404:
					break

		return {"data": [], "source": "sap"}

	except Exception as e:
		frappe.log_error(f"SAP batches fetch error: {str(e)}", "Real Aquatics SAP Error")
		return {"data": [], "error": str(e)}


@frappe.whitelist()
def get_batches_for_dispatch_item(item_code):
	"""Return available batches for an item from RP-FG only (for Dispatch Orders).
	Returns list of { batch_number, quantity, warehouse_code }."""
	from khanal_tech_integrations.api.real_aquatics import SAP_PO_FINISHED_WAREHOUSE

	_check_real_aquatics_access()
	if not item_code or not str(item_code).strip():
		return {"data": [], "error": "Item code is required"}

	combined = []
	# Only fetch from finished-goods warehouse for dispatch orders
	wh = SAP_PO_FINISHED_WAREHOUSE
	res = get_batches_for_item(item_code, warehouse_code=wh)
	for b in (res.get("data") or []):
		combined.append({
			"batch_number": b.get("batch_number", "").strip(),
			"quantity": float(b.get("quantity") or 0),
			# Always expose exact warehouse code as required by Real Aquatics dispatch: RP-FG
			"warehouse_code": "RP-FG",
		})
	return {"data": combined, "source": "sap"}


@frappe.whitelist()
def get_batches_for_item_debug(item_code, warehouse_code=None):
	"""Call SAP with ItemBatchNumbers (no filter) and return raw response for debugging batch field names."""
	_check_real_aquatics_access()
	if not item_code or not str(item_code).strip():
		return {"error": "item_code required"}
	item_esc = str(item_code).strip().replace("'", "''")
	session, b1_url = _get_sap_session()
	if not session:
		return {"error": "No SAP session"}
	url = f"{b1_url}ItemBatchNumbers?$filter=ItemCode eq '{item_esc}'&$top=5"
	resp, _, _ = _sap_get_with_retry(url, session, b1_url)
	try:
		body = resp.json() if resp.headers.get("Content-Type", "").find("json") >= 0 else resp.text
	except Exception:
		body = resp.text[:2000] if resp.text else None
	return {
		"url": url,
		"status_code": resp.status_code,
		"response": body,
	}


def _parse_warehouse_info_qty(collection, wh_variants):
	"""Sum OnHand/quantity from ItemWarehouseInfo rows for given warehouse variants."""
	total = 0.0
	if not isinstance(collection, list):
		collection = list(collection) if collection else []
	wh_norm_set = {normalize_warehouse_code(v) for v in (wh_variants or []) if v}
	for row in collection:
		if not isinstance(row, dict):
			continue
		wh = (
			row.get("WarehouseCode") or row.get("WhsCode") or row.get("warehouse_code")
			or row.get("Warehouse") or row.get("Code") or ""
		)
		wh = str(wh).strip() if wh is not None else ""
		if wh_norm_set:
			if normalize_warehouse_code(wh) not in wh_norm_set:
				continue
		q = None
		for _qkey in ("OnHand", "QuantityOnStock", "QuantityOnHand", "AvailableQuantity",
					   "InStock", "Quantity", "StockQuantity", "Balance"):
			_qval = row.get(_qkey)
			if _qval is not None:
				q = _qval
				break
		if q is None:
			continue
		try:
			total += float(q)
		except (TypeError, ValueError):
			pass
	return total


def get_item_stock_from_sap(item_code, warehouse_codes=None):
	"""Get available quantity for an item from SAP B1 (Real Aquatics FG/STR warehouses). Used for Work Order component availability.
	Uses HANA OITW first (same DB as batch lookup), then Service Layer. Returns dict with available_qty (float) and source ('sap' or None on failure)."""
	if not item_code or not str(item_code).strip():
		return {"available_qty": 0, "source": None}
	warehouse_codes = warehouse_codes or REALAQUATICS_SAP_AVAILABILITY_WAREHOUSES
	wh_variants = [str(w).strip() for w in warehouse_codes if w]

	# 0) Try INC HANA first (OITW = item-warehouse stock; same DB used for get_batches_for_item)
	connection, cursor, schema = _get_inc_hana_connection()
	if connection and cursor and schema:
		try:
			item = str(item_code).strip()
			# OITW: ItemCode, WhsCode, OnHand (in-stock qty per warehouse). Try quoted schema for case-sensitive HANA.
			for schema_ref in (f'"{schema}"', schema):
				try:
					if wh_variants:
						placeholders = ",".join("?" for _ in wh_variants)
						query = f'''
							SELECT COALESCE(SUM(T0."OnHand"), 0)
							FROM {schema_ref}."OITW" T0
							WHERE T0."ItemCode" = ? AND T0."WhsCode" IN ({placeholders})
						'''
						params = [item] + list(wh_variants)
						cursor.execute(query, params)
						row = cursor.fetchone()
						if row is not None:
							qty = float(row[0] or 0)
							if qty > 0:
								_close_inc_hana_connection(connection, cursor)
								return {"available_qty": qty, "source": "sap"}
					# Fallback: sum OnHand for this item across ALL warehouses (in case WhsCode differs, e.g. spacing)
					query_all = f'''
						SELECT COALESCE(SUM(T0."OnHand"), 0)
						FROM {schema_ref}."OITW" T0
						WHERE T0."ItemCode" = ?
					'''
					cursor.execute(query_all, [item])
					row_all = cursor.fetchone()
					if row_all is not None:
						qty_all = float(row_all[0] or 0)
						if qty_all > 0:
							_close_inc_hana_connection(connection, cursor)
							return {"available_qty": qty_all, "source": "sap"}
					break
				except Exception as inner_e:
					if schema_ref == schema:
						raise
					continue
		except Exception as e:
			frappe.log_error(f"HANA OITW stock failed for {item_code}: {str(e)}", "Real Aquatics SAP Error")
		finally:
			_close_inc_hana_connection(connection, cursor)

	session, b1_url = _get_sap_session()
	if not session:
		frappe.log_error("SAP session failed for item stock", "Real Aquatics SAP Error")
		return {"available_qty": 0, "source": None}
	item_esc = str(item_code).strip().replace("'", "''")

	# 1) Try direct ItemWarehouseInfo entity (avoids 400 on $expand in some SL versions)
	for entity in ("ItemWarehouseInfo", "ItemWarehouseInfoCollection"):
		url = f"{b1_url}{entity}?$filter=ItemCode eq '{item_esc}'"
		try:
			resp, session, b1_url = _sap_get_with_retry(url, session, b1_url)
			if resp.status_code != 200:
				continue
			data = resp.json() or {}
			collection = data.get("value") or data.get("d") or data.get("results") or []
			if isinstance(collection, dict):
				collection = [collection]
			total = _parse_warehouse_info_qty(collection, wh_variants)
			return {"available_qty": total, "source": "sap"}
		except Exception:
			pass

	# 2) Try Items('X')/ItemWarehouseInfo (child path, no $expand)
	url = f"{b1_url}Items('{item_esc}')/ItemWarehouseInfo"
	try:
		resp, session, b1_url = _sap_get_with_retry(url, session, b1_url)
		if resp.status_code == 200:
			data = resp.json() or {}
			collection = data.get("value") or data.get("d") or data.get("results") or []
			if isinstance(collection, dict):
				collection = collection.get("results") or collection.get("value") or [collection]
			if not isinstance(collection, list):
				collection = [collection] if collection else []
			total = _parse_warehouse_info_qty(collection, wh_variants)
			return {"available_qty": total, "source": "sap"}
	except Exception:
		pass

	# 3) Original: Items('X')?$expand=ItemWarehouseInfoCollection (some SL versions support this)
	url = f"{b1_url}Items('{item_esc}')?$expand=ItemWarehouseInfoCollection"
	try:
		resp, session, b1_url = _sap_get_with_retry(url, session, b1_url)
		if resp.status_code == 200:
			data = resp.json() or {}
			collection = data.get("ItemWarehouseInfoCollection") or data.get("item_warehouse_info_collection") or []
			if isinstance(collection, dict):
				collection = [collection]
			if not isinstance(collection, list):
				collection = list(collection) if collection else []
			total = _parse_warehouse_info_qty(collection, wh_variants)
			return {"available_qty": total, "source": "sap"}
	except Exception:
		pass

	return {"available_qty": 0, "source": None}


def get_items_stock_from_sap_batch(item_codes, warehouse_codes=None):
	"""Fetch available stock for multiple item codes in a single HANA query.

	Returns a dict mapping item_code -> available_qty (float).
	Falls back to calling get_item_stock_from_sap() individually if HANA is unavailable.
	"""
	if not item_codes:
		return {}

	unique_codes = list({str(c).strip() for c in item_codes if c and str(c).strip()})
	warehouse_codes = warehouse_codes or REALAQUATICS_SAP_AVAILABILITY_WAREHOUSES
	wh_variants = [str(w).strip() for w in warehouse_codes if w]
	result = {code: 0.0 for code in unique_codes}

	connection, cursor, schema = _get_inc_hana_connection()
	if connection and cursor and schema:
		try:
			item_placeholders = ",".join("?" for _ in unique_codes)
			for schema_ref in (f'"{schema}"', schema):
				try:
					if wh_variants:
						wh_placeholders = ",".join("?" for _ in wh_variants)
						query = f'''
							SELECT T0."ItemCode", COALESCE(SUM(T0."OnHand"), 0)
							FROM {schema_ref}."OITW" T0
							WHERE T0."ItemCode" IN ({item_placeholders})
							  AND T0."WhsCode" IN ({wh_placeholders})
							GROUP BY T0."ItemCode"
						'''
						params = unique_codes + list(wh_variants)
					else:
						query = f'''
							SELECT T0."ItemCode", COALESCE(SUM(T0."OnHand"), 0)
							FROM {schema_ref}."OITW" T0
							WHERE T0."ItemCode" IN ({item_placeholders})
							GROUP BY T0."ItemCode"
						'''
						params = unique_codes
					cursor.execute(query, params)
					rows = cursor.fetchall()
					for row in rows:
						code = (row[0] or "").strip()
						qty = float(row[1] or 0)
						if code in result:
							result[code] = max(result[code], qty)
					break
				except Exception as inner_e:
					if schema_ref == schema:
						raise
					continue
		except Exception as e:
			import frappe as _frappe
			_frappe.log_error(f"HANA batch stock failed: {str(e)}", "Real Aquatics SAP Error")
			# Fall through to per-item fallback
		finally:
			_close_inc_hana_connection(connection, cursor)
		return result

	# HANA unavailable — fall back to per-item SAP Service Layer calls
	for code in unique_codes:
		sap_result = get_item_stock_from_sap(code, warehouse_codes)
		result[code] = float(sap_result.get("available_qty") or 0)
	return result


@frappe.whitelist()
def get_item_stock_from_sap_debug(item_code="COCM0154"):
	"""Run from bench console or API to see why get_item_stock_from_sap returns 0. Returns HANA status and raw OITW rows for the item."""
	_check_real_aquatics_access()
	item = (item_code or "COCM0154").strip()
	out = {"item_code": item, "hana_connected": False, "hana_error": None, "schema": None, "oitw_rows": [], "stock_result": None}
	connection, cursor, schema = _get_inc_hana_connection()
	if not connection or not cursor:
		out["hana_error"] = "HANA connection failed or not configured (check Real Aquatics SAP Settings: HANA Host, User, Password, Schema; and hdbcli installed)."
		out["stock_result"] = get_item_stock_from_sap(item)
		return out
	out["hana_connected"] = True
	out["schema"] = schema
	try:
		# Get raw OITW rows for this item (all warehouses) to see exact WhsCode and OnHand
		for schema_ref in (f'"{schema}"', schema):
			try:
				query = f'SELECT T0."WhsCode", T0."OnHand" FROM {schema_ref}."OITW" T0 WHERE T0."ItemCode" = ?'
				cursor.execute(query, [item])
				rows = cursor.fetchall() or []
				out["oitw_rows"] = [{"WhsCode": str(r[0]) if r[0] is not None else "", "OnHand": float(r[1]) if r[1] is not None else 0} for r in rows]
				break
			except Exception as e:
				out["hana_error"] = str(e)
				if schema_ref == schema:
					raise
	except Exception as e:
		out["hana_error"] = str(e)
	finally:
		_close_inc_hana_connection(connection, cursor)
	out["stock_result"] = get_item_stock_from_sap(item)
	return out


# SAP B1 Production Order object code in NNM1 (Documents Numbering - Series). Service Layer uses 202 for Production Orders.
_NNM1_OBJECT_CODE_PRODUCTION_ORDER = "202"


@frappe.whitelist()
def get_production_order_series_from_hana():
	"""Return list of Production Order numbering series from SAP HANA (NNM1). Uses Real Aquatics SAP Settings HANA connection.
	Returns list of {series: int, series_name: str} for use in UI (e.g. series dropdown when creating PO)."""
	_check_real_aquatics_access()
	out = {"data": [], "hana_error": None}
	connection, cursor, schema = _get_inc_hana_connection()
	if not connection or not cursor or not schema:
		out["hana_error"] = "HANA connection failed or not configured (Real Aquatics SAP Settings: HANA Host, User, Password, Schema)."
		return out
	try:
		for schema_ref in (f'"{schema}"', schema):
			try:
				# NNM1: ObjectCode = document type (202 = Production Order), Series = int, SeriesName = name
				query = (
					f'SELECT T0."Series", T0."SeriesName" FROM {schema_ref}."NNM1" T0 '
					f'WHERE T0."ObjectCode" = ? ORDER BY T0."Series"'
				)
				cursor.execute(query, [_NNM1_OBJECT_CODE_PRODUCTION_ORDER])
				rows = cursor.fetchall() or []
				out["data"] = [
					{"series": int(r[0]) if r[0] is not None else 0, "series_name": (str(r[1]).strip() if r[1] is not None else "")}
					for r in rows
				]
				# If no rows, try numeric ObjectCode (some DBs store 202 as integer)
				if not out["data"]:
					cursor.execute(query, [202])
					rows = cursor.fetchall() or []
					out["data"] = [
						{"series": int(r[0]) if r[0] is not None else 0, "series_name": (str(r[1]).strip() if r[1] is not None else "")}
						for r in rows
					]
				break
			except Exception as e:
				out["hana_error"] = str(e)
				if schema_ref == schema:
					raise
	except Exception as e:
		out["hana_error"] = out["hana_error"] or str(e)
		frappe.log_error(f"Real Aquatics get_production_order_series_from_hana: {e}", "Real Aquatics SAP Error")
	finally:
		_close_inc_hana_connection(connection, cursor)
	return out


def get_inventory_list_from_sap(warehouse_codes=None, search=None, page=1, page_size=50):
	"""List item stock from SAP for Real Aquatics FG/STR warehouses (e.g. RP-STR, RP-FG). Tries HANA OITW first, then Service Layer. Returns {data: [...], total}."""
	_check_real_aquatics_access()
	warehouse_codes = warehouse_codes or REALAQUATICS_SAP_AVAILABILITY_WAREHOUSES
	wh_variants = [str(w).strip() for w in warehouse_codes if w]
	page = max(1, int(page))
	page_size = max(1, min(int(page_size), 200))

	# 0) Try HANA OITW first (same source as get_item_stock_from_sap) so warehouse inventory shows data when SL filter fails
	connection, cursor, schema = _get_inc_hana_connection()
	if connection and cursor and schema and wh_variants:
		try:
			placeholders = ",".join("?" for _ in wh_variants)
			for schema_ref in (f'"{schema}"', schema):
				try:
					query = f'''
						SELECT T0."ItemCode", MAX(T1."ItemName") AS "ItemName", COALESCE(SUM(T0."OnHand"), 0) AS "OnHand"
						FROM {schema_ref}."OITW" T0
						LEFT JOIN {schema_ref}."OITM" T1 ON T0."ItemCode" = T1."ItemCode"
						WHERE T0."WhsCode" IN ({placeholders})
						GROUP BY T0."ItemCode"
						HAVING COALESCE(SUM(T0."OnHand"), 0) > 0
					'''
					cursor.execute(query, list(wh_variants))
					rows = cursor.fetchall() or []
					by_item = {}
					for row in rows:
						item_code = (row[0] or "").strip() if row else ""
						if not item_code:
							continue
						item_name = (row[1] or "").strip() if len(row) > 1 else ""
						try:
							qty = float(row[2] or 0) if len(row) > 2 else 0.0
						except (TypeError, ValueError):
							qty = 0.0
						by_item[item_code] = {"item_code": item_code, "item_name": item_name, "qty": qty}
					# Non-zero inventory first, then by item code
					items_sorted = sorted(by_item.keys(), key=lambda c: (-(by_item[c].get("qty") or 0), c))
					if search and str(search).strip():
						s = str(search).strip().upper()
						items_sorted = [c for c in items_sorted if s in c.upper() or s in (by_item[c].get("item_name") or "").upper()]
					total = len(items_sorted)
					start = (page - 1) * page_size
					page_codes = items_sorted[start : start + page_size]
					out = [
						{
							"item_code": by_item[item_code]["item_code"],
							"item_name": by_item[item_code].get("item_name") or "",
							"warehouse": wh_variants[0] or "",
							"available_qty": by_item[item_code]["qty"],
							"allocated_qty": 0,
							"total_qty": by_item[item_code]["qty"],
						}
						for item_code in page_codes
					]
					_close_inc_hana_connection(connection, cursor)
					return {"data": out, "total": total}
				except Exception as e:
					if schema_ref == schema:
						frappe.log_error(f"Real Aquatics inventory list HANA query failed: {e}", "Real Aquatics SAP Error")
						raise
					continue
		except Exception:
			pass
		finally:
			_close_inc_hana_connection(connection, cursor)

	session, b1_url = _get_sap_session()
	if not session:
		return {"data": [], "total": 0}
	wh_filter = " or ".join(f"WarehouseCode eq '{w.replace(chr(39), chr(39)+chr(39))}'" for w in wh_variants)
	filter_expr = f"({wh_filter})"
	for entity in ("ItemWarehouseInfo", "ItemWarehouseInfoCollection"):
		# Fetch enough rows to aggregate (multiple warehouses = multiple rows per item)
		url = f"{b1_url}{entity}?$filter={filter_expr}&$orderby=ItemCode&$top=5000"
		try:
			resp, session, b1_url = _sap_get_with_retry(url, session, b1_url)
			if resp.status_code != 200:
				continue
			data = resp.json() or {}
			rows = data.get("value") or data.get("d") or data.get("results") or []
			# Aggregate by ItemCode (sum qty across warehouses)
			by_item = {}
			for row in rows:
				if not isinstance(row, dict):
					continue
				item_code = (row.get("ItemCode") or row.get("item_code") or "").strip()
				if not item_code:
					continue
				wh = (row.get("WarehouseCode") or row.get("WhsCode") or "").strip()
				q = None
				for _qk in ("OnHand", "QuantityOnStock", "QuantityOnHand", "AvailableQuantity", "InStock"):
					_qv = row.get(_qk)
					if _qv is not None:
						q = _qv
						break
				try:
					qty = float(q) if q is not None else 0.0
				except (TypeError, ValueError):
					qty = 0.0
				if item_code not in by_item:
					by_item[item_code] = {"item_code": item_code, "qty": 0.0, "warehouse": wh or (wh_variants[0] or "")}
				by_item[item_code]["qty"] += qty
			# Only show items with stock, sorted by qty desc then item code
			items_sorted = sorted(
				(c for c in by_item if (by_item[c].get("qty") or 0) > 0),
				key=lambda c: (-(by_item[c].get("qty") or 0), c),
			)
			if search and str(search).strip():
				s = str(search).strip().upper()
				items_sorted = [c for c in items_sorted if s in c.upper()]
			total = len(items_sorted)
			start = (page - 1) * page_size
			page_codes = items_sorted[start: start + page_size]
			out = []
			for item_code in page_codes:
				rec = by_item[item_code]
				out.append({
					"item_code": item_code,
					"item_name": "",
					"warehouse": rec["warehouse"],
					"available_qty": rec["qty"],
					"allocated_qty": 0,
					"total_qty": rec["qty"],
				})
			if out:
				item_codes = [r["item_code"] for r in out]
				filter_parts = " or ".join(f"ItemCode eq '{c.replace(chr(39), chr(39)+chr(39))}'" for c in item_codes[:100])
				url_items = f"{b1_url}Items?$select=ItemCode,ItemName&$filter={filter_parts}"
				try:
					r2, session, b1_url = _sap_get_with_retry(url_items, session, b1_url)
					if r2.status_code == 200:
						items_data = (r2.json() or {}).get("value") or []
						name_map = {it.get("ItemCode"): (it.get("ItemName") or "") for it in items_data}
						for rec in out:
							rec["item_name"] = name_map.get(rec["item_code"], "")
				except Exception:
					pass
			return {"data": out, "total": total}
		except Exception:
			pass
	return {"data": [], "total": 0}


def create_po_and_grpo_from_real_aquatics(po_doc):
	"""Create SAP B1 Purchase Order from Real Aquatics PO. Returns dict with po_doc_entry or raises.

	Note: GRPO (Goods Receipt) is no longer auto-created here; it should be created later in SAP.
	"""
	session, b1_url = _get_sap_session()
	if not session:
		raise frappe.ValidationError(_("SAP B1 Service Layer connection failed. Check SAP Settings."))

	doc_date = (po_doc.posting_date or frappe.utils.today()).strftime("%Y-%m-%d") if hasattr(po_doc.posting_date, "strftime") else str(po_doc.posting_date or frappe.utils.today())
	card_code = po_doc.vendor_code or po_doc.supplier_name or ""
	if not card_code:
		raise frappe.ValidationError(_("Vendor Code is required for SAP PO"))

	def _warehouse_code(wh):
		# Normalize legacy "RP-STR" to current PO_WAREHOUSE ("RP-STR") for SAP
		v = (wh or PO_WAREHOUSE).strip()
		return PO_WAREHOUSE if v == "RP-STR" else v

	lines = []
	for row in po_doc.items:
		line = {
			"ItemCode": row.item_code,
			"Quantity": float(row.qty or 0),
			"UnitPrice": float(row.rate or 0),
			"TaxCode": (row.tax_code or "").strip() or None,
			"WarehouseCode": _warehouse_code(row.warehouse),
		}
		# User-defined fields in SAP: Units Per Box (U_QPB), Number Of Boxes (U_NOB)
		u_qpb = getattr(row, "number_of_units_per_box", None)
		u_nob = getattr(row, "number_of_boxes", None)
		try:
			if u_qpb is not None:
				line["U_QPB"] = int(float(u_qpb))
		except (ValueError, TypeError):
			pass
		try:
			if u_nob is not None:
				line["U_NOB"] = int(float(u_nob))
		except (ValueError, TypeError):
			pass
		lines.append(line)
	if not lines:
		raise frappe.ValidationError(_("At least one line is required"))

	po_payload = {
		"CardCode": card_code,
		"DocDate": doc_date,
		"DocDueDate": doc_date,
		"TaxDate": doc_date,
		"NumAtCard": (po_doc.vendor_ref_no or "").strip() or None,
		"DocumentLines": lines,
	}
	url = b1_url + "PurchaseOrders"
	resp, session, b1_url = _sap_post_with_retry(url, session, b1_url, po_payload)
	if resp.status_code not in (200, 201):
		err = resp.text
		try:
			err = resp.json().get("error", {}).get("message", {}).get("value", err)
		except Exception:
			pass
		frappe.log_error(f"SAP PO create failed: {resp.status_code} {err}", "Real Aquatics SAP PO")
		raise frappe.ValidationError(_("SAP Purchase Order creation failed: {0}").format(err))

	po_result = resp.json()
	po_doc_entry = po_result.get("DocEntry")
	po_doc_num = po_result.get("DocNum")
	if not po_doc_entry:
		raise frappe.ValidationError(_("SAP did not return DocEntry for Purchase Order"))

	# Only PO is created here; GRPO will be created manually or by a separate process in SAP.
	return {"po_doc_entry": po_doc_entry, "po_doc_num": po_doc_num}


def create_grpo_for_real_aquatics_po(po_doc):
	"""Create a SAP B1 GRPO (PurchaseDeliveryNotes) for an existing SAP PO created from RealAquatics.

	Links each GRPO line to the corresponding PO line using BaseType/Entry/Line so procurement
	traceability continues to work as expected.
	"""
	session, b1_url = _get_sap_session()
	if not session:
		raise frappe.ValidationError(_("SAP B1 Service Layer connection failed. Check SAP Settings."))

	if not getattr(po_doc, "sap_po_doc_entry", None):
		raise frappe.ValidationError(_("SAP PO DocEntry is missing; send the PO to SAP before creating GRN."))

	card_code = po_doc.vendor_code or po_doc.supplier_name or ""
	if not card_code:
		raise frappe.ValidationError(_("Vendor Code is required for SAP GRPO"))

	# GRN date = when goods were actually received, not when the PO was placed.
	_grn_raw = getattr(po_doc, "received_date", None) or frappe.utils.today()
	doc_date = _grn_raw.strftime("%Y-%m-%d") if hasattr(_grn_raw, "strftime") else str(_grn_raw)

	document_lines = []
	missing_batches = []
	for idx, row in enumerate(po_doc.items):
		accepted = getattr(row, "accepted_qty", None)
		ordered = float(row.qty or 0)
		try:
			accepted_f = float(accepted) if (accepted is not None and accepted != "") else None
		except (TypeError, ValueError):
			accepted_f = None
		# -1 is the "warehouse explicitly accepted zero" sentinel (see purchase_order.py
		# update_accepted_quantities) and must send 0 to SAP, not fall back to ordered qty.
		if accepted_f is not None and accepted_f < 0:
			qty = 0.0
		elif accepted_f is not None and accepted_f > 0:
			qty = accepted_f
		else:
			qty = ordered
		if qty <= 0:
			continue
		# GRPO: send quantity as integer; do not send units-per-box or number-of-boxes (U_QPB/U_NOB).
		qty_int = int(round(qty))
		line = {
			"ItemCode": row.item_code,
			"Quantity": qty_int,
			"BaseType": 22,  # Purchase Order
			"BaseEntry": int(po_doc.sap_po_doc_entry),
			"BaseLine": idx,  # assumes GRPO lines follow the same order as the PO lines
		}
		wh = (row.warehouse or PO_WAREHOUSE or "").strip()
		if wh:
			# Normalize legacy RP-STR to RP-STR
			line["WarehouseCode"] = PO_WAREHOUSE if wh == "RP-STR" else wh

		# For batch-managed items, SAP expects complete selection of BatchNumbers.
		# Use the batch number already captured on the Real Aquatics PO line.
		bn = (getattr(row, "batch_number", None) or "").strip()
		if bn:
			line["BatchNumbers"] = [
				{
					"BatchNumber": bn,
					"Quantity": qty_int,  # integer; same as line quantity
				}
			]
		else:
			missing_batches.append(row.item_code or f"Line {idx + 1}")

		document_lines.append(line)

	if not document_lines:
		raise frappe.ValidationError(
			_("No lines with positive quantity to post to GRPO. Check that the PO has line items with quantity (or accepted quantity) greater than zero.")
		)

	if missing_batches:
		# Fail fast with a clear message instead of generic SAP error.
		items_str = ", ".join(missing_batches)
		raise frappe.ValidationError(
			_("Cannot create GRN in SAP: batch number is missing for items: {0}. "
			  "Please ensure each PO line has a batch number before posting GRN.").format(items_str)
		)

	payload = {
		"CardCode": card_code,
		"DocObjectCode": 20,  # Goods Receipt PO
		"DocDate": doc_date,
		"TaxDate": doc_date,
		"NumAtCard": (po_doc.vendor_ref_no or "").strip() or None,
		"Comments": f"Posted from Real Aquatics PO {po_doc.name}",
		"DocumentLines": document_lines,
	}

	url = b1_url + "PurchaseDeliveryNotes"
	resp, session, b1_url = _sap_post_with_retry(url, session, b1_url, payload)
	if resp.status_code not in (200, 201):
		err = resp.text
		try:
			err = resp.json().get("error", {}).get("message", {}).get("value", err)
		except Exception:
			pass
		frappe.log_error(
			f"SAP GRPO create failed for PO {po_doc.name} (DocEntry {po_doc.sap_po_doc_entry}): {resp.status_code} {err}",
			"Real Aquatics SAP GRPO",
		)
		raise frappe.ValidationError(_("SAP GRN creation failed: {0}").format(err))

	result = resp.json()
	doc_entry = result.get("DocEntry")
	doc_num = result.get("DocNum")
	if not doc_entry:
		raise frappe.ValidationError(_("SAP did not return DocEntry for GRN"))

	return {"doc_entry": doc_entry, "doc_num": doc_num}


def _target_warehouse_for_item(item_code: str, fallback: str) -> str:
	code = (item_code or "").strip().upper()
	if not code:
		return (fallback or "").strip()
	if code.startswith(("RM", "PM", "CO")):
		return "RP-STR"
	if code.startswith("FG"):
		return "RP-FG"
	return (fallback or "").strip()


# Map UI warehouse codes to exact SAP B1 warehouse codes.
# SAP: SC-STR, SC-FG (no space); RP-STR, RP-FG (no space).
# Support both no-space (new UI) and with-space (legacy) for backward compatibility.
_SAP_WAREHOUSE_MAP = {
	"SC - STR": "SC-STR",
	"SC - FG": "SC-FG",
	"SC-STR": "SC-STR",
	"SC-FG": "SC-FG",
	"RP - STR": "RP-STR",
	"RP - FG": "RP-FG",
	"RP-STR": "RP-STR",
	"RP-FG": "RP-FG",
}


def _normalize_warehouse_for_sap(wh: str) -> str:
	"""Return warehouse code in format SAP B1 expects. Maps SC codes to no-space; others returned as-is."""
	if not wh:
		return (wh or "").strip()
	v = (wh or "").strip()
	return _SAP_WAREHOUSE_MAP.get(v, v)


def _parse_sap_doc_entries(value: str):
	raw = (value or "").strip()
	if not raw:
		return []
	parts = [p.strip() for p in str(raw).split(",") if p and p.strip()]
	out = []
	for p in parts:
		try:
			out.append(int(p))
		except ValueError:
			continue
	return out


def create_stock_transfer_from_real_aquatics_order(doc):
	"""Create SAP B1 Stock Transfer from Real Aquatics Order when warehouse marks order complete.
	From warehouse is always RP-FG (ORDERS_FROM_WAREHOUSE); to warehouse is doc.to_warehouse.
	"""
	session, b1_url = _get_sap_session()
	if not session:
		raise frappe.ValidationError(_("SAP B1 Service Layer connection failed. Check SAP Settings."))

	_raw_date = getattr(doc, "completed_date", None) or doc.doc_date or frappe.utils.today()
	doc_date = _raw_date.strftime("%Y-%m-%d") if hasattr(_raw_date, "strftime") else str(_raw_date)
	from_warehouse_raw = (ORDERS_FROM_WAREHOUSE or doc.get("from_warehouse") or "").strip()
	if not from_warehouse_raw:
		from_warehouse_raw = "RP-FG"
	from_warehouse = _normalize_warehouse_for_sap(from_warehouse_raw)

	to_warehouse_raw = (doc.to_warehouse or "").strip()
	if not to_warehouse_raw:
		raise frappe.ValidationError(_("To Warehouse is required"))
	to_warehouse_sap = _normalize_warehouse_for_sap(to_warehouse_raw)
	if from_warehouse == to_warehouse_sap:
		raise frappe.ValidationError(
			_("To Warehouse cannot be the same as the source warehouse (RP-FG). Please select a different destination warehouse.")
		)

	req_entry_raw = (getattr(doc, "sap_request_doc_entry", None) or "").strip()
	req_entry = int(req_entry_raw) if req_entry_raw else None

	lines = []
	for line_num, row in enumerate(doc.items):
		# Support both dict (from API) and DocType child row
		qty = float(row.get("quantity") or 0) if isinstance(row, dict) else float(getattr(row, "quantity", 0) or 0)
		item_code = row.get("item_code") if isinstance(row, dict) else getattr(row, "item_code", None)
		if not item_code or qty <= 0:
			continue
		bn = (row.get("batch_number") or "").strip() if isinstance(row, dict) else (getattr(row, "batch_number", None) or "").strip()
		line = {
			"ItemCode": item_code,
			"Quantity": qty,
			"WarehouseCode": to_warehouse_sap,
		}
		if bn:
			line["BatchNumbers"] = [{"BatchNumber": bn, "Quantity": qty}]
		# Link IT lines back to the ITR so SAP consumes the existing allocation
		# instead of treating this as a new independent transfer (which causes batch conflict)
		if req_entry is not None:
			line["BaseEntry"] = req_entry
			line["BaseType"] = 1250000001
			line["BaseLine"] = line_num
		# U_QPB/U_NOB deliberately omitted: SAP rejects them on StockTransferLine in this
		# company DB ("Property 'U_NOB' of 'StockTransferLine' is invalid") — same schema
		# gap as the Inventory Transfer Request lines above.
		lines.append(line)

	if not lines:
		raise frappe.ValidationError(_("At least one line with quantity is required"))

	payload = {
		"DocDate": doc_date,
		"FromWarehouse": from_warehouse,
		"ToWarehouse": to_warehouse_sap,
		"StockTransferLines": lines,
	}
	comments = _truncate_sap_comments(doc.comments)
	if comments:
		payload["Comments"] = comments

	url = b1_url + "StockTransfers"
	resp, session, b1_url = _sap_post_with_retry_transfer(url, session, b1_url, payload)
	if resp.status_code not in (200, 201):
		err = resp.text
		try:
			err = resp.json().get("error", {}).get("message", {}).get("value", err)
		except Exception:
			pass
		frappe.log_error(
			f"SAP StockTransfer create failed (Real Aquatics Order): FromWarehouse={from_warehouse!r} ToWarehouse={to_warehouse_sap!r} | {resp.status_code} {err}",
			"Real Aquatics Order SAP",
		)
		raise frappe.ValidationError(_("SAP Inventory Transfer creation failed: {0}").format(err))

	result = resp.json()
	doc_entry = result.get("DocEntry")
	if not doc_entry:
		raise frappe.ValidationError(_("SAP did not return DocEntry for Inventory Transfer"))
	return {"doc_entry": str(doc_entry), "doc_num": str(result.get("DocNum") or "")}


def create_stock_transfer_request_from_real_aquatics_order(doc):
	"""Create a SAP B1 Inventory Transfer Request from Real Aquatics Order.

	This mirrors the Shiphero Inventory Transfer flow: when warehouse accepts the FBA Transfer,
	we raise an Inventory Transfer Request (from RP-FG to the selected To Warehouse) using the
	ordered quantity per line. The final Inventory Transfer is posted separately.
	"""
	session, b1_url = _get_sap_session()
	if not session:
		raise frappe.ValidationError(_("SAP B1 Service Layer connection failed. Check SAP Settings."))

	_raw_date = getattr(doc, "accepted_date", None) or doc.doc_date or frappe.utils.today()
	doc_date = _raw_date.strftime("%Y-%m-%d") if hasattr(_raw_date, "strftime") else str(_raw_date)

	from_warehouse_raw = (ORDERS_FROM_WAREHOUSE or doc.get("from_warehouse") or "").strip()
	if not from_warehouse_raw:
		from_warehouse_raw = "RP-FG"
	from_warehouse = _normalize_warehouse_for_sap(from_warehouse_raw)

	to_warehouse_raw = (doc.to_warehouse or "").strip()
	if not to_warehouse_raw:
		raise frappe.ValidationError(_("To Warehouse is required"))
	to_warehouse_sap = _normalize_warehouse_for_sap(to_warehouse_raw)
	if from_warehouse == to_warehouse_sap:
		raise frappe.ValidationError(
			_("To Warehouse cannot be the same as the source warehouse (RP-FG). Please select a different destination warehouse.")
		)

	lines = []
	for row in doc.items:
		qty = float(row.get("quantity") or 0) if isinstance(row, dict) else float(getattr(row, "quantity", 0) or 0)
		item_code = row.get("item_code") if isinstance(row, dict) else getattr(row, "item_code", None)
		if not item_code or qty <= 0:
			continue
		bn = (row.get("batch_number") or "").strip() if isinstance(row, dict) else (getattr(row, "batch_number", None) or "").strip()
		if not bn:
			raise frappe.ValidationError(_("Batch number is required for every line before creating the Inventory Transfer Request"))
		# U_QPB/U_NOB deliberately omitted here: SAP's Inventory Transfer Request line
		# table (WTQ1) has no such UDFs in this company DB, only the final Stock Transfer
		# line table (WTR1) does — see create_stock_transfer_from_real_aquatics_order.
		line = {
			"ItemCode": item_code,
			"Quantity": qty,
			"WarehouseCode": to_warehouse_sap,
			"BatchNumbers": [{"BatchNumber": bn, "Quantity": qty}],
		}
		lines.append(line)

	if not lines:
		raise frappe.ValidationError(_("At least one line with quantity is required"))

	payload = {
		"DocDate": doc_date,
		"FromWarehouse": from_warehouse,
		"ToWarehouse": to_warehouse_sap,
		"StockTransferLines": lines,
	}
	comments = _truncate_sap_comments(doc.comments)
	if comments:
		payload["Comments"] = comments

	url = b1_url + "InventoryTransferRequests"
	resp, session, b1_url = _sap_post_with_retry_transfer(url, session, b1_url, payload)
	if resp.status_code not in (200, 201):
		err = resp.text
		try:
			err = resp.json().get("error", {}).get("message", {}).get("value", err)
		except Exception:
			pass
		frappe.log_error(
			f"SAP InventoryTransferRequest create failed (Real Aquatics Order): FromWarehouse={from_warehouse!r} ToWarehouse={to_warehouse_sap!r} | {resp.status_code} {err}",
			"Real Aquatics Order SAP Request",
		)
		raise frappe.ValidationError(_("SAP Inventory Transfer Request creation failed: {0}").format(err))

	result = resp.json()
	doc_entry = result.get("DocEntry")
	if not doc_entry:
		raise frappe.ValidationError(_("SAP did not return DocEntry for Inventory Transfer Request"))
	return {"doc_entry": str(doc_entry), "doc_num": str(result.get("DocNum") or "")}
