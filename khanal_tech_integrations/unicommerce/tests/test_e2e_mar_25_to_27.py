import json
import os
import unittest
from unittest import skipUnless

import frappe

from khanal_tech_integrations.unicommerce.mappers import ar_invoice_payload
from khanal_tech_integrations.unicommerce.client import SAPClient
from khanal_tech_integrations.unicommerce.workers.credit_note import (
	_post_credit_note,
)
from khanal_tech_integrations.unicommerce.workers.invoice import (
	_post_order,
	_update_reconciliation_diffs,
)
from khanal_tech_integrations.unicommerce.workers.fetch import (
	fetch_orders,
	fetch_returns,
)


LIVE_E2E_ENV = "RUN_UC_SAP_LIVE_E2E"
LIVE_E2E_ALLOW_POSTS_ENV = "UC_SAP_E2E_ALLOW_POSTS"

E2E_ALREADY_RUN = False


def _live_e2e_enabled() -> bool:
	# Double opt-in to prevent accidental real posting.
	return (
		os.environ.get(LIVE_E2E_ENV, "").strip() == "1"
		and os.environ.get(LIVE_E2E_ALLOW_POSTS_ENV, "").strip() == "1"
	)


@skipUnless(
	_live_e2e_enabled(),
	f"Set {LIVE_E2E_ENV}=1 and {LIVE_E2E_ALLOW_POSTS_ENV}=1 to run live UC<->SAP E2E",
)
class TestUCToSAPMar25To27E2E(unittest.TestCase):
	start_date = "2026-03-25"
	end_date = "2026-03-27"

	min_tax_diff = float(os.environ.get("UC_SAP_E2E_MIN_TAX_DIFF", "1.0"))
	min_unit_price_diff = float(os.environ.get("UC_SAP_E2E_MIN_UNIT_PRICE_DIFF", "1.0"))

	max_orders = int(os.environ.get("UC_SAP_E2E_MAX_ORDERS", "200"))
	max_returns = int(os.environ.get("UC_SAP_E2E_MAX_RETURNS", "200"))

	def _order_rows_in_date_range(self):
		return frappe.get_all(
			"Unicommerce Orders",
			fields=["name", "order_date", "pipeline_status as status"],
			filters={
				"order_date": ["between", [self.start_date, self.end_date]],
				"pipeline_status": ["in", ["fetched", "ready", "failed", "dead"]],
			},
		)

	def _credit_note_rows_in_date_range(self):
		return frappe.get_all(
			"UC Credit Note Staging",
			fields=["name", "uc_return_id", "return_date", "status"],
			filters={
				"return_date": ["between", [self.start_date, self.end_date]],
				"status": ["in", ["pending", "failed"]],
			},
		)

	def _sap_invoice_count_by_uc_order_id(self, sap: SAPClient, uc_order_id: str) -> int:
		result = sap.get(
			"Invoices",
			params={
				"$filter": f"U_UCOrderID eq '{uc_order_id}'",
				"$select": "DocEntry",
				"$top": 50,
			},
		)
		return len(result.get("value") or [])

	def _sap_credit_note_exists_by_return_id(self, sap: SAPClient, uc_return_id: str) -> bool:
		result = sap.get(
			"CreditNotes",
			params={
				"$filter": f"U_UCReturnID eq '{uc_return_id}'",
				"$select": "DocEntry",
				"$top": 1,
			},
		)
		return bool((result.get("value") or []))

	def test_end_to_end_mar_25_to_27_fetch_post_invoices_creditnotes_reconcile(self):
		global E2E_ALREADY_RUN
		if E2E_ALREADY_RUN:
			self.skipTest("E2E already executed in this test module run.")
		E2E_ALREADY_RUN = True

		# If decorator is ignored by some runner, still guard.
		if not _live_e2e_enabled():
			self.skipTest(
				f"Set {LIVE_E2E_ENV}=1 and {LIVE_E2E_ALLOW_POSTS_ENV}=1 to run live UC<->SAP E2E"
			)

		sap = SAPClient()

		# 1) Bias UC poller to the target window by moving the cursor near start_date.
		cursors = frappe.db.get_single_value("Unicommerce Settings", "last_fetched_at_json") or "{}"
		try:
			cursors_obj = json.loads(cursors)
		except Exception:
			cursors_obj = {}
		cursors_obj["orders"] = f"{self.start_date} 00:00:00"
		cursors_obj["returns"] = f"{self.start_date} 00:00:00"
		settings = frappe.get_single("Unicommerce Settings")
		settings.last_fetched_at_json = json.dumps(cursors_obj)
		settings.save(ignore_permissions=True)
		frappe.db.commit()

		# 2) Fetch orders from UC.
		fetch_orders(max_orders=self.max_orders)

		target_orders = self._order_rows_in_date_range()
		if not target_orders:
			self.skipTest("No Unicommerce Orders rows found in Mar 25–Mar 27 range.")

		target_order_ids = [r.name for r in target_orders if r.name]

		# Promote selected orders only.
		for row in target_orders:
			frappe.db.set_value(
				"Unicommerce Orders", row.name, {"pipeline_status": "ready", "last_error": ""}
			)
		frappe.db.commit()

		# 3) Post AR invoices (one invoice per order).
		for row in target_orders:
			staging = frappe.get_doc("Unicommerce Orders", row.name)

			# Avoid duplicates if invoice already exists in SAP.
			existing = sap.find_invoice_by_uc_order_id(staging.name)
			if existing and existing.get("DocEntry") is not None:
				# Build payload for reconciliation even when skipping posting.
				payload = ar_invoice_payload(staging)
				staging.payload_json = json.dumps(payload, separators=(",", ":"), default=str)
				staging.save(ignore_permissions=True)

				frappe.db.set_value(
					"Unicommerce Orders",
					row.name,
					{
						"pipeline_status": "posted",
						"sap_ar_invoice_docentry": str(existing.get("DocEntry") or ""),
						"sap_ar_invoice_docnum": str(existing.get("DocNum") or ""),
						"ar_invoice_tax_actual": float(existing.get("DocTaxAmount") or 0),
					},
				)
			else:
				_post_order(sap, staging)

			frappe.db.commit()

		for uc_order_id in target_order_ids:
			self.assertEqual(
				self._sap_invoice_count_by_uc_order_id(sap, uc_order_id),
				1,
				f"Expected exactly one SAP invoice for UC order {uc_order_id}",
			)

		# 4) Pull returns -> create credit note staging.
		fetch_returns(max_returns=self.max_returns)

		target_credit_rows = self._credit_note_rows_in_date_range()

		for row in target_credit_rows:
			cn_doc = frappe.get_doc("UC Credit Note Staging", row.name)

			# Avoid duplicates.
			if self._sap_credit_note_exists_by_return_id(sap, cn_doc.uc_return_id):
				frappe.db.set_value(
					"UC Credit Note Staging",
					row.name,
					{"status": "posted", "last_error": ""},
				)
			else:
				_post_credit_note(sap, row.name)

			frappe.db.commit()

		# 5) Reconciliation: tax + unit price diffs should be within thresholds.
		for row in target_orders:
			staging = frappe.get_doc("Unicommerce Orders", row.name)
			if staging.pipeline_status != "posted":
				continue
			_update_reconciliation_diffs(staging.name)
			frappe.db.commit()

			self.assertLessEqual(float(staging.ar_invoice_tax_diff or 0), self.min_tax_diff)
			self.assertLessEqual(float(staging.ar_invoice_unit_price_diff or 0), self.min_unit_price_diff)

import json
import os
import unittest
from unittest import skipUnless

import frappe

from khanal_tech_integrations.unicommerce.mappers import ar_invoice_payload
from khanal_tech_integrations.unicommerce.client import SAPClient
from khanal_tech_integrations.unicommerce.workers.credit_note import (
	_post_credit_note,
)
from khanal_tech_integrations.unicommerce.workers.invoice import (
	_post_order,
	_update_reconciliation_diffs,
)
from khanal_tech_integrations.unicommerce.workers.fetch import (
	fetch_orders,
	fetch_returns,
)


LIVE_E2E_ENV = "RUN_UC_SAP_LIVE_E2E"
LIVE_E2E_ALLOW_POSTS_ENV = "UC_SAP_E2E_ALLOW_POSTS"


def _live_e2e_enabled() -> bool:
	# Double opt-in to prevent accidental real posting.
	return (
		os.environ.get(LIVE_E2E_ENV, "").strip() == "1"
		and os.environ.get(LIVE_E2E_ALLOW_POSTS_ENV, "").strip() == "1"
	)


@skipUnless(
	_live_e2e_enabled(),
	f"Set {LIVE_E2E_ENV}=1 and {LIVE_E2E_ALLOW_POSTS_ENV}=1 to run live UC<->SAP E2E",
)
class TestUCToSAPMar25To27E2E(unittest.TestCase):
	start_date = "2026-03-25"
	end_date = "2026-03-27"

	min_tax_diff = float(os.environ.get("UC_SAP_E2E_MIN_TAX_DIFF", "1.0"))
	min_unit_price_diff = float(os.environ.get("UC_SAP_E2E_MIN_UNIT_PRICE_DIFF", "1.0"))

	max_orders = int(os.environ.get("UC_SAP_E2E_MAX_ORDERS", "200"))
	max_returns = int(os.environ.get("UC_SAP_E2E_MAX_RETURNS", "200"))

	def _order_rows_in_date_range(self):
		return frappe.get_all(
			"Unicommerce Orders",
			fields=["name", "order_date", "pipeline_status as status"],
			filters={
				"order_date": ["between", [self.start_date, self.end_date]],
				"pipeline_status": ["in", ["fetched", "ready", "failed", "dead"]],
			},
		)

	def _credit_note_rows_in_date_range(self):
		return frappe.get_all(
			"UC Credit Note Staging",
			fields=["name", "uc_return_id", "return_date", "status"],
			filters={
				"return_date": ["between", [self.start_date, self.end_date]],
				"status": ["in", ["pending", "failed"]],
			},
		)

	def _sap_invoice_count_by_uc_order_id(self, sap: SAPClient, uc_order_id: str) -> int:
		result = sap.get(
			"Invoices",
			params={
				"$filter": f"U_UCOrderID eq '{uc_order_id}'",
				"$select": "DocEntry",
				"$top": 50,
			},
		)
		return len(result.get("value") or [])

	def _sap_credit_note_exists_by_return_id(self, sap: SAPClient, uc_return_id: str) -> bool:
		result = sap.get(
			"CreditNotes",
			params={
				"$filter": f"U_UCReturnID eq '{uc_return_id}'",
				"$select": "DocEntry",
				"$top": 1,
			},
		)
		return bool((result.get("value") or []))

	def test_end_to_end_mar_25_to_27_fetch_post_invoices_creditnotes_reconcile(self):
		global E2E_ALREADY_RUN
		if E2E_ALREADY_RUN:
			self.skipTest("E2E already executed in this test module run.")
		E2E_ALREADY_RUN = True

		# If decorator is ignored by some runner, still guard.
		if not _live_e2e_enabled():
			self.skipTest(
				f"Set {LIVE_E2E_ENV}=1 and {LIVE_E2E_ALLOW_POSTS_ENV}=1 to run live UC<->SAP E2E"
			)

		sap = SAPClient()

		# 1) Bias UC poller to the target window by moving the cursor near start_date.
		cursors = frappe.db.get_single_value("Unicommerce Settings", "last_fetched_at_json") or "{}"
		try:
			cursors_obj = json.loads(cursors)
		except Exception:
			cursors_obj = {}
		cursors_obj["orders"] = f"{self.start_date} 00:00:00"
		cursors_obj["returns"] = f"{self.start_date} 00:00:00"
		settings = frappe.get_single("Unicommerce Settings")
		settings.last_fetched_at_json = json.dumps(cursors_obj)
		settings.save(ignore_permissions=True)
		frappe.db.commit()

		# 2) Fetch orders from UC.
		fetch_orders(max_orders=self.max_orders)

		target_orders = self._order_rows_in_date_range()
		if not target_orders:
			self.skipTest("No Unicommerce Orders rows found in Mar 25–Mar 27 range.")

		target_order_ids = [r.name for r in target_orders if r.name]

		# Promote selected orders only.
		for row in target_orders:
			frappe.db.set_value(
				"Unicommerce Orders", row.name, {"pipeline_status": "ready", "last_error": ""}
			)
		frappe.db.commit()

		# 3) Post AR invoices (one invoice per order).
		for row in target_orders:
			staging = frappe.get_doc("Unicommerce Orders", row.name)

			# Avoid duplicates if invoice already exists in SAP.
			existing = sap.find_invoice_by_uc_order_id(staging.name)
			if existing and existing.get("DocEntry") is not None:
				# Build payload for reconciliation even when skipping posting.
				payload = ar_invoice_payload(staging)
				staging.payload_json = json.dumps(payload, separators=(",", ":"), default=str)
				staging.save(ignore_permissions=True)

				frappe.db.set_value(
					"Unicommerce Orders",
					row.name,
					{
						"pipeline_status": "posted",
						"sap_ar_invoice_docentry": str(existing.get("DocEntry") or ""),
						"sap_ar_invoice_docnum": str(existing.get("DocNum") or ""),
						"ar_invoice_tax_actual": float(existing.get("DocTaxAmount") or 0),
					},
				)
			else:
				_post_order(sap, staging)

			frappe.db.commit()

		for uc_order_id in target_order_ids:
			self.assertEqual(
				self._sap_invoice_count_by_uc_order_id(sap, uc_order_id),
				1,
				f"Expected exactly one SAP invoice for UC order {uc_order_id}",
			)

		# 4) Pull returns -> create credit note staging.
		fetch_returns(max_returns=self.max_returns)

		target_credit_rows = self._credit_note_rows_in_date_range()
		# It's possible your tenant has no returns in that window.

		for row in target_credit_rows:
			cn_doc = frappe.get_doc("UC Credit Note Staging", row.name)

			# Avoid duplicates.
			if self._sap_credit_note_exists_by_return_id(sap, cn_doc.uc_return_id):
				frappe.db.set_value(
					"UC Credit Note Staging",
					row.name,
					{"status": "posted", "last_error": ""},
				)
			else:
				_post_credit_note(sap, row.name)

			frappe.db.commit()

		# 5) Reconciliation: tax + unit price diffs should be within thresholds.
		for row in target_orders:
			staging = frappe.get_doc("Unicommerce Orders", row.name)
			if staging.pipeline_status != "posted":
				continue
			_update_reconciliation_diffs(staging.name)
			frappe.db.commit()

			self.assertLessEqual(float(staging.ar_invoice_tax_diff or 0), self.min_tax_diff)
			self.assertLessEqual(float(staging.ar_invoice_unit_price_diff or 0), self.min_unit_price_diff)

import json
import os
import unittest
from unittest import skipUnless

import frappe

from khanal_tech_integrations.unicommerce.mappers import ar_invoice_payload
from khanal_tech_integrations.unicommerce.validators import (
	get_gaps,
)
from khanal_tech_integrations.unicommerce.client import SAPClient
from khanal_tech_integrations.unicommerce.client import UCClient
from khanal_tech_integrations.unicommerce.workers.credit_note import (
	_post_credit_note,
)
from khanal_tech_integrations.unicommerce.workers.invoice import (
	_post_order,
	_update_reconciliation_diffs,
)
from khanal_tech_integrations.unicommerce.workers.fetch import (
	fetch_orders,
	fetch_returns,
)


LIVE_E2E_ENV = "RUN_UC_SAP_LIVE_E2E"
LIVE_E2E_ALLOW_POSTS_ENV = "UC_SAP_E2E_ALLOW_POSTS"


def _live_e2e_enabled() -> bool:
	# Require explicit opt-in to avoid accidental real UC/SAP posting.
	return (
		os.environ.get(LIVE_E2E_ENV, "").strip() == "1"
		and os.environ.get(LIVE_E2E_ALLOW_POSTS_ENV, "").strip() == "1"
	)


@skipUnless(
	_live_e2e_enabled(),
	f"Set {LIVE_E2E_ENV}=1 and {LIVE_E2E_ALLOW_POSTS_ENV}=1 to run live UC<->SAP E2E",
)
class TestUCToSAPMar25To27E2E(unittest.TestCase):
	def setUp(self):
		super().setUp()

		# Extra safety: class decorators sometimes get ignored by custom runners.
		# If live mode isn't enabled, skip at runtime as well.
		if not _live_e2e_enabled():
			self.skipTest(
				f"Set {LIVE_E2E_ENV}=1 and {LIVE_E2E_ALLOW_POSTS_ENV}=1 to run live UC<->SAP E2E"
			)

		# Debug: show what env flags are seen by the test process.
		# (This will only run when live E2E is enabled, because otherwise we skip.)
		print(
			f"[UC-SAP E2E LIVE] {LIVE_E2E_ENV}={os.environ.get(LIVE_E2E_ENV)!r} "
			f"{LIVE_E2E_ALLOW_POSTS_ENV}={os.environ.get(LIVE_E2E_ALLOW_POSTS_ENV)!r}"
		)

		# Ensure settings exist; the integration code uses these in clients.
		self.settings = frappe.get_single("Unicommerce Settings")
		if not getattr(self.settings, "uc_base_url", None) and not getattr(
			self.settings, "uc_username", None
		):
			# Clients fall back to Unicommerce Settings, so we only hard-fail on obvious missing.
			pass

		# Thresholds should match dashboard behavior (kiosk Vue uses min_tax_diff/min_unit_price_diff=1.0).
		self.min_tax_diff = float(os.environ.get("UC_SAP_E2E_MIN_TAX_DIFF", "1.0"))
		self.min_unit_price_diff = float(os.environ.get("UC_SAP_E2E_MIN_UNIT_PRICE_DIFF", "1.0"))

		# Mar 25–Mar 27 dataset (2026) requested by user.
		self.start_date = "2026-03-25"
		self.end_date = "2026-03-27"

		# Keep this test bounded.
		self.max_orders = int(os.environ.get("UC_SAP_E2E_MAX_ORDERS", "200"))
		self.max_returns = int(os.environ.get("UC_SAP_E2E_MAX_RETURNS", "200"))

	def _order_rows_in_date_range(self):
		return frappe.get_all(
			"Unicommerce Orders",
			fields=["name", "order_date", "pipeline_status as status"],
			filters={
				"order_date": ["between", [self.start_date, self.end_date]],
				"pipeline_status": ["in", ["fetched", "ready", "posting", "verify", "failed", "dead"]],
			},
		)

	def _credit_note_rows_in_date_range(self):
		return frappe.get_all(
			"UC Credit Note Staging",
			fields=["name", "uc_return_id", "return_date", "status"],
			filters={
				"return_date": ["between", [self.start_date, self.end_date]],
				"status": ["in", ["pending", "failed", "posted"]],
			},
		)

	def _sap_invoice_count_by_uc_order_id(self, sap: SAPClient, uc_order_id: str) -> int:
		# Service Layer returns `{"value": [...]}` for OData collections.
		result = sap.get(
			"Invoices",
			params={
				"$filter": f"U_UCOrderID eq '{uc_order_id}'",
				"$select": "DocEntry",
				"$top": 50,
			},
		)
		return len(result.get("value") or [])

	def _sap_credit_note_exists_by_return_id(
		self, sap: SAPClient, uc_return_id: str
	) -> tuple[bool, str]:
		# CreditNotes also supports UDF filtering.
		result = sap.get(
			"CreditNotes",
			params={
				"$filter": f"U_UCReturnID eq '{uc_return_id}'",
				"$select": "DocEntry",
				"$top": 50,
			},
		)
		value = result.get("value") or []
		if not value:
			return False, ""
		return True, str(value[0].get("DocEntry") or "")

	def test_end_to_end_fetch_post_invoices_creditnotes_reconcile(self):
		sap = SAPClient()
		uc = UCClient()

		# 1) Pull orders from UC
		# The poller uses `Unicommerce Settings.last_fetched_at_json` as a cursor.
		# We set it to just before start_date to bias results into the range.
		cursors = frappe.db.get_single_value("Unicommerce Settings", "last_fetched_at_json") or "{}"
		try:
			cursors_obj = json.loads(cursors)
		except Exception:
			cursors_obj = {}
		cursors_obj["orders"] = f"{self.start_date} 00:00:00"
		cursors_obj["returns"] = f"{self.start_date} 00:00:00"
		self.settings.last_fetched_at_json = json.dumps(cursors_obj)
		self.settings.save(ignore_permissions=True)
		frappe.db.commit()

		fetch_orders(max_orders=self.max_orders)

		# 2) Promote orders in date range to ready (only those).
		target_orders = self._order_rows_in_date_range()
		self.assertTrue(len(target_orders) > 0, "No Unicommerce Orders rows found in date range.")

		for row in target_orders:
			frappe.db.set_value(
				"Unicommerce Orders", row.name, {"pipeline_status": "ready", "last_error": ""}
			)
		frappe.db.commit()

		target_order_ids = [r.name for r in target_orders if r.name]

		# 3) Post AR invoices one-by-one (with SAP existence checks to avoid duplicates).
		# We intentionally avoid calling post_invoices(), since it processes all ready rows.
		for row in target_orders:
			staging = frappe.get_doc("Unicommerce Orders", row.name)

			# Pre-check in SAP: if invoice already exists, mark posted without posting again.
			existing = sap.find_invoice_by_uc_order_id(staging.name)
			if existing and existing.get("DocEntry") is not None:
				# Still build payload so reconciliation has ar_invoice_tax_expected/unit totals.
				payload = ar_invoice_payload(staging)
				staging.payload_json = json.dumps(payload, separators=(",", ":"), default=str)
				staging.save(ignore_permissions=True)

				frappe.db.set_value(
					"Unicommerce Orders",
					row.name,
					{
						"pipeline_status": "posted",
						"sap_ar_invoice_docentry": str(existing.get("DocEntry") or ""),
						"sap_ar_invoice_docnum": str(existing.get("DocNum") or ""),
						"ar_invoice_tax_actual": float(existing.get("DocTaxAmount") or 0),
					},
				)
			else:
				_post_order(sap, staging)

			frappe.db.commit()

		# Sanity: one invoice per order
		for uc_order_id in target_order_ids:
			self.assertEqual(
				self._sap_invoice_count_by_uc_order_id(sap, uc_order_id),
				1,
				f"Expected exactly one SAP invoice for UC order {uc_order_id}",
			)

		# 4) Pull returns -> create credit note staging
		fetch_returns(max_returns=self.max_returns)

		target_credit_rows = self._credit_note_rows_in_date_range()
		# Depending on UC returns data, there may be 0 credit notes.
		# If you require at least one, uncomment next line.
		# self.assertTrue(len(target_credit_rows) > 0, "No UC Credit Note Staging rows found in date range.")

		for row in target_credit_rows:
			# Only post pending/failed; if already posted we skip.
			if row.status == "posted":
				continue

			cn_doc = frappe.get_doc("UC Credit Note Staging", row.name)
			exists, doc_entry = self._sap_credit_note_exists_by_return_id(sap, cn_doc.uc_return_id)
			if exists and doc_entry:
				frappe.db.set_value(
					"UC Credit Note Staging",
					row.name,
					{
						"status": "posted",
						"sap_credit_doc_entry": doc_entry,
						"last_error": "",
					},
				)
			else:
				_post_credit_note(sap, row.name)

			frappe.db.commit()

		# 5) Reconciliation refresh (tax/unit diffs) for only our posted orders.
		for row in target_orders:
			staging = frappe.get_doc("Unicommerce Orders", row.name)
			if staging.pipeline_status != "posted":
				continue
			_update_reconciliation_diffs(staging.name)
			frappe.db.commit()

		# 6) Final reconciliation check: diffs below thresholds for targeted orders.
		for row in target_orders:
			staging = frappe.get_doc("Unicommerce Orders", row.name)
			if staging.pipeline_status != "posted":
				continue
			self.assertLessEqual(float(staging.ar_invoice_tax_diff or 0), self.min_tax_diff)
			self.assertLessEqual(float(staging.ar_invoice_unit_price_diff or 0), self.min_unit_price_diff)

		# Optional: also ensure there are no reconciliation gaps using the same thresholds,
		# but note this is global (could include other posted orders outside the test window).
		# If you want strict window-only gaps, we should add a dedicated SQL filter by uc_order_id list.
		gaps = get_gaps(
			min_tax_diff=self.min_tax_diff,
			min_unit_price_diff=self.min_unit_price_diff,
			limit=2000,
		)
		# We don't assert len(gaps)==0 globally because the tenant may have other mismatches.
		# Instead we assert our targeted docs are clean above.
