"""
Tests for the inventory reconciliation classification logic -- the 4 flags
(missing/mismatch/inactive/blocked) whose exact definitions were confirmed
with the business before building this (see
docs/superpowers/specs/2026-07-13-amazon-us-inventory-reconciliation-design.md).

Mocks get_item_mapping, _fetch_sap_inventory (HANA), and
get_inventory_summaries (Amazon) -- same style as the rest of this test
suite, no live dependency. The FBA Inventory API pagination bug this
worker depends on (client/fba_inventory.py dropping marketplaceIds on
page 2+) was caught and fixed via live testing, not by these mocks --
mocks can't catch a wrong-shape live API call, only wrong logic once the
data is in hand.
"""
import unittest
from unittest.mock import patch

from khanal_tech_integrations.amazon_us.workers import inventory_reconciliation as ir


def _amazon_row(total_quantity, unfulfillable=0, reserved=0, inbound_working=0, inbound_shipped=0, inbound_receiving=0):
    return {
        "totalQuantity": total_quantity,
        "inventoryDetails": {
            "unfulfillableQuantity": {"totalUnfulfillableQuantity": unfulfillable},
            "reservedQuantity": {"totalReservedQuantity": reserved},
            "inboundWorkingQuantity": inbound_working,
            "inboundShippedQuantity": inbound_shipped,
            "inboundReceivingQuantity": inbound_receiving,
        },
    }


class TestBlockedQty(unittest.TestCase):
    def test_sums_unfulfillable_reserved_and_all_three_inbound_buckets(self):
        row = _amazon_row(100, unfulfillable=5, reserved=3, inbound_working=1, inbound_shipped=2, inbound_receiving=4)
        self.assertEqual(ir._blocked_qty(row), 15.0)

    def test_zero_when_all_buckets_empty(self):
        self.assertEqual(ir._blocked_qty(_amazon_row(50)), 0.0)


class TestBuildInventoryReconciliation(unittest.TestCase):
    def _run(self, item_mapping, sap_inventory, amazon_inventory):
        with patch.object(ir, "get_item_mapping", return_value=item_mapping), \
             patch.object(ir, "_fetch_sap_inventory", return_value=sap_inventory), \
             patch("khanal_tech_integrations.amazon_us.workers.inventory_reconciliation.get_inventory_summaries",
                   return_value=amazon_inventory), \
             patch("frappe.get_doc") as mock_get_doc:
            mock_get_doc.return_value.sap_warehouse_code = "AMZ-FBA"
            mock_get_doc.return_value.marketplace_id = "ATVPDKIKX0DER"
            return ir.build_inventory_reconciliation(progress_id=None)

    def test_missing_flagged_when_sap_has_it_amazon_does_not(self):
        result = self._run(
            item_mapping={"SKU-1": {"sap_item_code": "ITEM-1"}},
            sap_inventory={"ITEM-1": {"on_hand": 10, "active": True}},
            amazon_inventory={},  # Amazon never returns this SKU
        )
        self.assertEqual(result["counts"]["missing"], 1)
        self.assertEqual(result["rows"][0]["flags"], ["MISSING"])

    def test_no_missing_flag_when_amazon_has_it(self):
        result = self._run(
            item_mapping={"SKU-1": {"sap_item_code": "ITEM-1"}},
            sap_inventory={"ITEM-1": {"on_hand": 10, "active": True}},
            amazon_inventory={"SKU-1": _amazon_row(10)},
        )
        self.assertEqual(result["counts"]["missing"], 0)

    def test_mismatch_flagged_on_any_difference_no_tolerance(self):
        result = self._run(
            item_mapping={"SKU-1": {"sap_item_code": "ITEM-1"}},
            sap_inventory={"ITEM-1": {"on_hand": 10, "active": True}},
            amazon_inventory={"SKU-1": _amazon_row(11)},  # off by 1
        )
        self.assertIn("MISMATCH", result["rows"][0]["flags"])
        self.assertEqual(result["rows"][0]["diff"], -1)

    def test_no_mismatch_when_quantities_match_exactly(self):
        result = self._run(
            item_mapping={"SKU-1": {"sap_item_code": "ITEM-1"}},
            sap_inventory={"ITEM-1": {"on_hand": 10, "active": True}},
            amazon_inventory={"SKU-1": _amazon_row(10)},
        )
        self.assertNotIn("MISMATCH", result["rows"][0]["flags"])

    def test_inactive_flagged_when_sap_inactive_and_amazon_still_has_stock(self):
        # Confirmed direction: SAP inactive + Amazon still selling -- the
        # overselling-risk direction, not orphaned-stock.
        result = self._run(
            item_mapping={"SKU-1": {"sap_item_code": "ITEM-1"}},
            sap_inventory={"ITEM-1": {"on_hand": 0, "active": False}},
            amazon_inventory={"SKU-1": _amazon_row(5)},
        )
        self.assertIn("INACTIVE", result["rows"][0]["flags"])

    def test_no_inactive_flag_when_sap_inactive_but_amazon_also_zero(self):
        result = self._run(
            item_mapping={"SKU-1": {"sap_item_code": "ITEM-1"}},
            sap_inventory={"ITEM-1": {"on_hand": 0, "active": False}},
            amazon_inventory={"SKU-1": _amazon_row(0)},
        )
        self.assertNotIn("INACTIVE", result["rows"][0]["flags"])

    def test_no_inactive_flag_when_sap_active(self):
        result = self._run(
            item_mapping={"SKU-1": {"sap_item_code": "ITEM-1"}},
            sap_inventory={"ITEM-1": {"on_hand": 5, "active": True}},
            amazon_inventory={"SKU-1": _amazon_row(5)},
        )
        self.assertNotIn("INACTIVE", result["rows"][0]["flags"])

    def test_blocked_flagged_only_above_threshold(self):
        # threshold is 20 -- confirm the boundary explicitly
        just_under = self._run(
            item_mapping={"SKU-1": {"sap_item_code": "ITEM-1"}},
            sap_inventory={"ITEM-1": {"on_hand": 20, "active": True}},
            amazon_inventory={"SKU-1": _amazon_row(20, reserved=20)},  # exactly at threshold
        )
        self.assertNotIn("BLOCKED", just_under["rows"][0]["flags"], "exactly at threshold should not flag (> not >=)")

        over = self._run(
            item_mapping={"SKU-1": {"sap_item_code": "ITEM-1"}},
            sap_inventory={"ITEM-1": {"on_hand": 21, "active": True}},
            amazon_inventory={"SKU-1": _amazon_row(21, reserved=21)},
        )
        self.assertIn("BLOCKED", over["rows"][0]["flags"])

    def test_hana_unavailable_returns_hana_down_status(self):
        with patch.object(ir, "get_item_mapping", return_value={"SKU-1": {"sap_item_code": "ITEM-1"}}), \
             patch.object(ir, "_fetch_sap_inventory", side_effect=ir.HanaUnavailableError("down")), \
             patch("frappe.get_doc") as mock_get_doc:
            mock_get_doc.return_value.sap_warehouse_code = "AMZ-FBA"
            mock_get_doc.return_value.marketplace_id = "ATVPDKIKX0DER"
            result = ir.build_inventory_reconciliation(progress_id=None)
        self.assertEqual(result["status"], "hana_down")

    def test_amazon_api_failure_returns_error_status_not_crash(self):
        with patch.object(ir, "get_item_mapping", return_value={"SKU-1": {"sap_item_code": "ITEM-1"}}), \
             patch.object(ir, "_fetch_sap_inventory", return_value={"ITEM-1": {"on_hand": 5, "active": True}}), \
             patch("khanal_tech_integrations.amazon_us.workers.inventory_reconciliation.get_inventory_summaries",
                   side_effect=Exception("Amazon API down")), \
             patch("frappe.get_doc") as mock_get_doc, patch("frappe.log_error"):
            mock_get_doc.return_value.sap_warehouse_code = "AMZ-FBA"
            mock_get_doc.return_value.marketplace_id = "ATVPDKIKX0DER"
            result = ir.build_inventory_reconciliation(progress_id=None)
        self.assertEqual(result["status"], "error")
