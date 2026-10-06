"""
Tests for the order-detail/search/export additions to api/ops.py.

Mocks frappe.db access (SQL query shape, response payload) rather than
depending on real staged data -- matches the pattern in
unicommerce/tests/test_ops.py so these run under `bench run-tests` without
needing fixture orders or a live SAP connection.
"""
import unittest
from unittest.mock import MagicMock, patch

import frappe

from khanal_tech_integrations.amazon_us.api import ops


class TestGetOrdersSearch(unittest.TestCase):
    def test_no_search_omits_join_and_param(self):
        with patch.object(frappe.db, "sql", side_effect=[[], [[0]]]) as mock_sql, \
             patch.object(frappe.db, "count", return_value=0):
            ops.get_orders("2026-01-01", "2026-01-31", stage="all", page=1, page_size=10)

        select_call = mock_sql.call_args_list[0]
        query = select_call.args[0]
        params = select_call.args[1]
        self.assertNotIn("Order Item", query)
        self.assertNotIn("search", params)

    def test_search_adds_join_and_wraps_param(self):
        with patch.object(frappe.db, "sql", side_effect=[[], [[0]]]) as mock_sql, \
             patch.object(frappe.db, "count", return_value=0):
            ops.get_orders("2026-01-01", "2026-01-31", stage="all", page=1, page_size=10, search="ABC123")

        select_call = mock_sql.call_args_list[0]
        query = select_call.args[0]
        params = select_call.args[1]
        self.assertIn("Order Item", query)
        self.assertIn("seller_sku LIKE", query)
        self.assertEqual(params["search"], "%ABC123%")

    def test_blank_search_treated_as_no_search(self):
        with patch.object(frappe.db, "sql", side_effect=[[], [[0]]]) as mock_sql, \
             patch.object(frappe.db, "count", return_value=0):
            ops.get_orders("2026-01-01", "2026-01-31", stage="all", page=1, page_size=10, search="   ")

        query = mock_sql.call_args_list[0].args[0]
        self.assertNotIn("Order Item", query)


class TestGetOrderDetail(unittest.TestCase):
    def test_not_found_returns_error_without_further_queries(self):
        with patch.object(frappe.db, "exists", return_value=False):
            result = ops.get_order_detail("NOT-A-REAL-ORDER")
        self.assertEqual(result["status"], "error")
        self.assertIn("not found", result["message"])

    def test_found_returns_order_items_and_settlement_lines(self):
        fake_order = {"name": "111-1111111-1111111", "amazon_order_id": "111-1111111-1111111"}
        fake_items = [{"seller_sku": "SKU1", "quantity": 1}]
        fake_settlement_lines = [{"settlement_name": "S-1", "settlement_id": "12345", "principal_amount": 26.99}]

        with patch.object(frappe.db, "exists", return_value=True), \
             patch.object(frappe.db, "get_value", return_value=fake_order), \
             patch.object(frappe, "get_all", return_value=fake_items), \
             patch.object(frappe.db, "sql", return_value=fake_settlement_lines):
            result = ops.get_order_detail("111-1111111-1111111")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["order"], fake_order)
        self.assertEqual(result["items"], fake_items)
        self.assertEqual(result["settlement_lines"], fake_settlement_lines)


class TestGetCreditNoteDetail(unittest.TestCase):
    def test_no_cn_doc_entry_short_circuits(self):
        with patch.object(frappe.db, "get_value", return_value=None), \
             patch(
                 "khanal_tech_integrations.amazon_us.client.sap.get_credit_note_lines"
             ) as mock_get_lines:
            result = ops.get_credit_note_detail("111-1111111-1111111")

        self.assertEqual(result["status"], "error")
        mock_get_lines.assert_not_called()

    def test_sap_success_returns_lines(self):
        fake_lines = [{"ItemCode": "EXP000003", "LineTotal": 2.78}]
        with patch.object(frappe.db, "get_value", return_value="12345"), \
             patch(
                 "khanal_tech_integrations.amazon_us.client.sap.get_credit_note_lines",
                 return_value=fake_lines,
             ):
            result = ops.get_credit_note_detail("111-1111111-1111111")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["lines"], fake_lines)

    def test_sap_failure_returns_structured_error(self):
        with patch.object(frappe.db, "get_value", return_value="12345"), \
             patch(
                 "khanal_tech_integrations.amazon_us.client.sap.get_credit_note_lines",
                 side_effect=RuntimeError("SAP down"),
             ):
            result = ops.get_credit_note_detail("111-1111111-1111111")

        self.assertEqual(result["status"], "error")
        self.assertIn("SAP down", result["message"])


class TestExportOrdersCsv(unittest.TestCase):
    def test_csv_header_and_rows_match_columns(self):
        fake_rows = [{
            "amazon_order_id": "111-1111111-1111111", "order_status": "Shipped", "stage": "posted",
            "purchase_date": "2026-06-30 23:59:03", "actual_ship_date": None, "buyer_name": "Jane Doe",
            "order_total_amount": 29.77, "order_total_currency": "USD", "sap_doc_num": "11084",
            "posted_at": "2026-07-08 21:12:49", "cn_doc_num": None, "refunded_at": None, "last_error": "",
        }]
        frappe.local.response = frappe._dict()
        with patch.object(frappe.db, "sql", return_value=fake_rows):
            ops.export_orders_csv("2026-06-01", "2026-07-13", stage="all")

        content = frappe.response.filecontent
        lines = content.splitlines()
        self.assertEqual(
            lines[0],
            "amazon_order_id,order_status,stage,purchase_date,actual_ship_date,buyer_name,"
            "order_total_amount,order_total_currency,sap_doc_num,posted_at,cn_doc_num,refunded_at,last_error",
        )
        self.assertIn("111-1111111-1111111", lines[1])
        self.assertIn("Jane Doe", lines[1])
        self.assertEqual(frappe.response.type, "download")
