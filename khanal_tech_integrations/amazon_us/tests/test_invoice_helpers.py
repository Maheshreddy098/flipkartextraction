"""
Unit tests for invoice.py's atomic claim/mark helpers -- the primitives the
8-worker posting pool's race-safety rests on (see test_invoice_pool.py for
the actual concurrency test). Mocks frappe.db.sql, no live DB dependency.
"""
import unittest
from unittest.mock import patch

import frappe

from khanal_tech_integrations.amazon_us.workers import invoice as invoice_mod


class TestClaim(unittest.TestCase):
    def test_claim_succeeds_when_row_count_is_one(self):
        with patch.object(frappe.db, "sql", side_effect=[None, [[1]]]), \
             patch.object(frappe.db, "commit"):
            self.assertTrue(invoice_mod._claim("111-1111111-1111111"))

    def test_claim_fails_when_row_count_is_zero(self):
        # Another worker already claimed it (or it's not stage='ready') --
        # this is the exact mechanism that makes the 8-worker pool race-safe.
        with patch.object(frappe.db, "sql", side_effect=[None, [[0]]]), \
             patch.object(frappe.db, "commit"):
            self.assertFalse(invoice_mod._claim("111-1111111-1111111"))

    def test_claim_only_updates_rows_currently_ready(self):
        with patch.object(frappe.db, "sql", side_effect=[None, [[1]]]) as mock_sql, \
             patch.object(frappe.db, "commit"):
            invoice_mod._claim("111-1111111-1111111")
        update_call = mock_sql.call_args_list[0]
        self.assertIn("stage = 'ready'", update_call.args[0])
        self.assertIn("stage = 'posting'", update_call.args[0])


class TestMarkPosted(unittest.TestCase):
    def test_sets_posted_fields_and_commits(self):
        with patch.object(frappe.db, "set_value") as mock_set, \
             patch.object(frappe.db, "commit") as mock_commit:
            invoice_mod._mark_posted("111-1111111-1111111", {"doc_entry": "123", "doc_num": "456"})
        updates = mock_set.call_args.args[2]
        self.assertEqual(updates["stage"], "posted")
        self.assertEqual(updates["sap_doc_entry"], "123")
        self.assertEqual(updates["sap_doc_num"], "456")
        mock_commit.assert_called_once()


class TestMarkFailed(unittest.TestCase):
    def test_sets_failed_stage_and_truncates_error(self):
        long_error = "x" * 2000
        with patch.object(frappe.db, "set_value") as mock_set, \
             patch.object(frappe.db, "commit"):
            invoice_mod._mark_failed("111-1111111-1111111", long_error)
        updates = mock_set.call_args.args[2]
        self.assertEqual(updates["stage"], "failed")
        self.assertEqual(len(updates["last_error"]), 1000)  # truncated to 1000 chars
