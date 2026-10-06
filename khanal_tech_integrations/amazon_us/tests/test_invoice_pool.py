"""
Integration test for post_ready_orders' 8-worker pool -- the one property
that actually matters here (no double-posting under concurrency) can't be
meaningfully verified with mocks alone, so this creates real 'ready' orders,
mocks only the SAP/HANA boundary, and checks the real DB afterward.

This is the same test performed ad-hoc against a live bench while building
the pool (see PR history) -- committed here so it runs on every future
change instead of only having been checked once by hand.

Requires DB write access (bench run-tests provides this). Cleans up its
own test orders in tearDown regardless of pass/fail.
"""
import threading
import time
import unittest
from unittest.mock import patch

import frappe

from khanal_tech_integrations.amazon_us.workers import invoice as invoice_mod

_N = 16
_NAMES = [f"TEST-INVPOOL-{i:04d}" for i in range(_N)]


class TestPostReadyOrdersPool(unittest.TestCase):
    def setUp(self):
        for n in _NAMES:
            if frappe.db.exists("Amazon US Order", n):
                frappe.delete_doc("Amazon US Order", n, force=True, ignore_permissions=True)
        frappe.db.commit()

        today = frappe.utils.today()
        for n in _NAMES:
            frappe.get_doc({
                "doctype": "Amazon US Order", "amazon_order_id": n, "stage": "ready",
                "actual_ship_date": today, "purchase_date": frappe.utils.now_datetime(),
                "attempt_count": 0,
            }).insert(ignore_permissions=True)
        frappe.db.commit()

    def tearDown(self):
        for n in _NAMES:
            if frappe.db.exists("Amazon US Order", n):
                frappe.delete_doc("Amazon US Order", n, force=True, ignore_permissions=True)
        frappe.db.commit()

    def test_pool_posts_every_order_exactly_once(self):
        seen_order_ids = []
        lock = threading.Lock()

        def fake_build_invoice_payload(doc, hana_cursor):
            return {"DocumentLines": [{"ItemCode": "TEST"}], "NumAtCard": doc.amazon_order_id}, []

        def fake_post_invoice(payload):
            time.sleep(0.05)
            order_id = payload["NumAtCard"]
            with lock:
                seen_order_ids.append(order_id)
            return {"doc_entry": f"DE-{order_id}", "doc_num": f"DN-{order_id}"}

        with patch.object(invoice_mod, "build_invoice_payload", fake_build_invoice_payload), \
             patch.object(invoice_mod, "post_invoice", fake_post_invoice), \
             patch.object(invoice_mod, "find_invoice_by_order_id", return_value=None):
            today = frappe.utils.today()
            result = invoice_mod.post_ready_orders(today, today, limit=100, progress_id=None)

        self.assertEqual(result["total"], _N)
        self.assertEqual(result["posted"], _N)
        self.assertEqual(result["failed"], 0)
        # The property that actually matters: no order posted twice, none lost.
        self.assertEqual(len(set(seen_order_ids)), _N, "duplicate or lost order -- claim race!")

        frappe.db.commit()
        rows = frappe.db.sql(
            "SELECT stage, sap_doc_entry FROM `tabAmazon US Order` WHERE name LIKE 'TEST-INVPOOL-%%'",
            as_dict=True,
        )
        self.assertTrue(all(r.stage == "posted" for r in rows))
        self.assertEqual(len({r.sap_doc_entry for r in rows}), _N, "duplicate doc entries written")
