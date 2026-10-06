"""Smoke tests for the Unicommerce ops API layer.

These tests validate shape and routing — they do not exercise the live SAP or
Unicommerce backends. They monkey-patch external dependencies so they can run
inside `bench --site <site> run-tests` without network access.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import frappe

from khanal_tech_integrations.unicommerce.api import ops


class TestOpsOverviewShape(unittest.TestCase):
    def test_overview_returns_expected_keys(self):
        with patch.object(ops, "_health_snapshot", return_value={"sap_login": {"ok": True}, "uc_login": {"ok": True}}), \
             patch.object(ops, "_stage_counts", return_value={"orders": {"_total": 0}, "credit_notes": {"_total": 0}, "inventory": {"_total": 0}}), \
             patch.object(ops, "_last_scheduled_runs", return_value={}), \
             patch.object(ops, "_recent_errors", return_value=[]), \
             patch.object(ops, "_recon_summary", return_value={"gap_count": 0, "ok": True}):
            data = ops.ops_overview()

        for key in ("health", "counts", "last_runs", "recent_errors", "recon_summary", "generated_at"):
            self.assertIn(key, data)
        self.assertIn("orders", data["counts"])
        self.assertIn("credit_notes", data["counts"])
        self.assertIn("inventory", data["counts"])


class TestRetryRouter(unittest.TestCase):
    def test_invalid_mode_raises(self):
        with self.assertRaises(Exception):
            ops.ops_retry(ops.ORDER_DOCTYPE, "FAKE-001", mode="bogus")

    def test_unknown_doctype_raises(self):
        with self.assertRaises(Exception):
            ops.ops_retry("Some Doctype", "X", mode="queue")

    def test_order_queue_mode_resets_status(self):
        with patch.object(frappe.db, "set_value") as mock_set, \
             patch.object(frappe.db, "commit"):
            result = ops.ops_retry(ops.ORDER_DOCTYPE, "ORD-1", mode="queue")
        self.assertTrue(result["queued"])
        mock_set.assert_called_with(ops.ORDER_DOCTYPE, "ORD-1", {"pipeline_status": "ready", "last_error": ""})

    def test_credit_note_queue_mode_resets_status(self):
        with patch.object(frappe.db, "set_value") as mock_set, \
             patch.object(frappe.db, "commit"):
            result = ops.ops_retry(ops.CREDIT_NOTE_DOCTYPE, "CN-1", mode="queue")
        self.assertTrue(result["queued"])
        mock_set.assert_called_with(ops.CREDIT_NOTE_DOCTYPE, "CN-1", {"status": "pending", "last_error": ""})

    def test_inventory_queue_mode_resets_status(self):
        with patch.object(frappe.db, "set_value") as mock_set, \
             patch.object(frappe.db, "commit"):
            result = ops.ops_retry(ops.INVENTORY_DOCTYPE, "INV-1", mode="queue")
        self.assertTrue(result["queued"])
        mock_set.assert_called_with(ops.INVENTORY_DOCTYPE, "INV-1", {"unicommerce_sync_status": "Pending"})


class TestAlertDebounce(unittest.TestCase):
    def test_debounce_blocks_repeat_within_window(self):
        cache = {}

        class FakeCache:
            def get_value(self, k):
                return cache.get(k)

            def set_value(self, k, v, expires_in_sec=None):
                cache[k] = v

        with patch.object(frappe, "cache", return_value=FakeCache()), \
             patch.object(frappe.db, "get_single_value", return_value=15):
            self.assertTrue(ops._should_send("order_failed", "X", "Y"))
            ops._mark_sent("order_failed", "X", "Y")
            self.assertFalse(ops._should_send("order_failed", "X", "Y"))

    def test_send_failure_alert_returns_false_when_disabled(self):
        with patch.object(ops, "_alerts_enabled", return_value=False):
            self.assertFalse(ops.send_failure_alert("order_failed", "X", "Y", "boom"))

    def test_send_failure_alert_returns_false_with_no_recipients(self):
        with patch.object(ops, "_alerts_enabled", return_value=True), \
             patch.object(ops, "_should_send", return_value=True), \
             patch.object(ops, "_resolve_recipients", return_value=[]):
            self.assertFalse(ops.send_failure_alert("order_failed", "X", "Y", "boom"))


class TestFailuresPagination(unittest.TestCase):
    def test_pagination_clamps_page_size(self):
        with patch.object(ops, "_failed_orders", return_value=[]), \
             patch.object(ops, "_failed_credit_notes", return_value=[]), \
             patch.object(ops, "_failed_inventory", return_value=[]):
            data = ops.ops_failures(stage="all", page=1, page_size=9999)
        self.assertEqual(data["page_size"], 100)

    def test_pagination_minimum_page(self):
        with patch.object(ops, "_failed_orders", return_value=[]), \
             patch.object(ops, "_failed_credit_notes", return_value=[]), \
             patch.object(ops, "_failed_inventory", return_value=[]):
            data = ops.ops_failures(stage="all", page=0, page_size=10)
        self.assertEqual(data["page"], 1)


if __name__ == "__main__":
    unittest.main()
