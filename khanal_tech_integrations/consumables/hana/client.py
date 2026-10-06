import time
import frappe
from frappe import _


class ConsumablesHANAClient:
    def __init__(self, schema=None):
        # Consumables SAP Settings is consumables' own isolated settings Single —
        # separate from the shared "SAP Settings" every other vertical
        # (unicommerce, amazon_us, B2B, safexpress, ...) reads, so consumables
        # can point at a test company DB without affecting what's live
        # everywhere else. hana_schema also lives only here now — it used to
        # be duplicated on Consumables Settings too, which could silently
        # drift out of sync with SAP Settings' own copy.
        self.schema = schema or frappe.db.get_single_value("Consumables SAP Settings", "hana_schema")
        if not self.schema:
            frappe.throw(_("Consumables SAP Settings: HANA Schema is not configured. Please set it in Consumables SAP Settings before proceeding."))
        self._conn = None
        self._cursor = None

    def _connect(self):
        try:
            import hdbcli.dbapi as hana_db
        except ImportError:
            frappe.throw(_("SAP HANA driver (hdbcli) is not installed."))

        try:
            sap = frappe.get_single("Consumables SAP Settings")
            self._conn = hana_db.connect(
                address=sap.hana_host,
                port=int(sap.hana_port),
                user=sap.hana_user,
                password=sap.get_password("hana_password"),
                autocommit=False,
            )
            self._cursor = self._conn.cursor()
        except Exception as e:
            frappe.log_error(str(e), "ConsumablesHANAClient connection error")
            frappe.throw(_("Could not connect to SAP HANA. Check Consumables SAP Settings."))

    def execute(self, query: str, params: list = None) -> list:
        if not self._conn:
            self._connect()

        start = time.monotonic()
        try:
            self._cursor.execute(query, params or [])
        except Exception as e:
            frappe.log_error(str(e), "ConsumablesHANAClient query error")
            frappe.throw(_("HANA query failed: {0}").format(str(e)))

        elapsed = time.monotonic() - start
        if elapsed > 2:
            frappe.log_error(
                f"Slow HANA query ({elapsed:.1f}s): {query[:300]}",
                "ConsumablesHANAClient slow query",
            )

        cols = [d[0].lower() for d in self._cursor.description]
        return [dict(zip(cols, row)) for row in self._cursor.fetchall()]

    def __enter__(self):
        self._connect()
        return self

    def __exit__(self, *args):
        try:
            if self._cursor:
                self._cursor.close()
            if self._conn:
                self._conn.close()
        except Exception:
            pass
