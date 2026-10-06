"""
Tests for the invoice payload calculation logic in mappers/payload.py --
this is literally "what SAP gets charged," so it gets tested even though
the rest of the module didn't have coverage before today.

Mocks frappe.get_doc/get_all, get_item_mapping, and allocate_batches_fefo
(HANA) -- matches the mocking style already established in
unicommerce/tests/test_ops.py and tests/test_ops_order_detail.py. No live
DB/SAP/HANA dependency.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe

from khanal_tech_integrations.amazon_us.mappers import payload as payload_mod


# SimpleNamespace, not frappe._dict: frappe._dict subclasses dict, so a
# fake order's "items" key would collide with dict.items() the bound
# method -- order_doc.items must resolve to the child-table list, exactly
# like it does on a real (non-dict) Frappe Document.
def _fake_settings(**overrides):
    defaults = dict(
        sap_tax_code="etax0", sap_pay_to_code="Amazon USA-B2C",
        sap_warehouse_code="AMZ-FBA", sap_card_code="C00001", sap_series=120,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _fake_item(**overrides):
    defaults = dict(
        seller_sku="SKU-1", quantity=1, item_price_amount=26.99, item_tax_amount=0,
        shipping_price_amount=0, shipping_tax_amount=0, shipping_discount_amount=0,
        promotion_discount_amount=0,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _fake_order(items, **overrides):
    defaults = dict(
        amazon_order_id="111-1111111-1111111", purchase_date="2026-06-30 12:00:00",
        # Real ship date by default: build_invoice_payload refuses to build a
        # payload without one (2026-07-14 -- production posted a batch of
        # orders dated by purchase_date, silently, before ship-date sync had
        # run, giving them the wrong MTR month). Tests of that guard itself
        # override actual_ship_date=None explicitly.
        actual_ship_date="2026-06-30", buyer_name=None, ship_city=None,
        ship_state_or_region=None, ship_postal_code=None, ship_country=None,
        items=items,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestBuildLineUdfs(unittest.TestCase):
    def test_truncates_and_skips_falsy_fields(self):
        order = _fake_order([], buyer_name="X" * 200, purchase_date="2026-06-30 12:00:00")
        udfs = payload_mod.build_line_udfs(order)
        self.assertEqual(len(udfs["U_BuyerName"]), 120)
        self.assertNotIn("U_City", udfs)  # ship_city is None on the fake order
        self.assertEqual(udfs["U_OrderedOn"], "2026-06-30")


class TestBuildInvoicePayload(unittest.TestCase):
    def _build(self, order, allocate_side_effect=None):
        with patch.object(payload_mod, "get_item_mapping", return_value={"SKU-1": {"sap_item_code": "FGDC0001"}}), \
             patch.object(frappe, "get_doc", return_value=_fake_settings()), \
             patch(
                 "khanal_tech_integrations.amazon_us.client.hana.allocate_batches_fefo",
                 side_effect=allocate_side_effect or (lambda *a, **k: []),
             ):
            return payload_mod.build_invoice_payload(order, hana_cursor=object())

    def test_unit_price_is_gross_promotion_discount_ignored(self):
        # Finance policy (2026-07-14): promo rebates are expenditure, never a
        # price reduction -- revenue posts at gross unit price.
        order = _fake_order([_fake_item(item_price_amount=26.99, promotion_discount_amount=2.88, quantity=1)])
        payload, skipped = self._build(order)
        self.assertEqual(payload["DocumentLines"][0]["UnitPrice"], 26.99)

    def test_tax_line_appended_only_when_positive(self):
        order = _fake_order([_fake_item(item_tax_amount=2.51, shipping_tax_amount=0)])
        payload, _ = self._build(order)
        tax_lines = [l for l in payload["DocumentLines"] if l["ItemCode"] == payload_mod._TAX_ITEM_CODE]
        self.assertEqual(len(tax_lines), 1)
        self.assertEqual(tax_lines[0]["UnitPrice"], 2.51)

        order_no_tax = _fake_order([_fake_item(item_tax_amount=0, shipping_tax_amount=0)])
        payload2, _ = self._build(order_no_tax)
        self.assertFalse([l for l in payload2["DocumentLines"] if l["ItemCode"] == payload_mod._TAX_ITEM_CODE])

    def test_shipping_is_gross_discount_ignored(self):
        # Finance policy (2026-07-14): ship-promotion discount is a promo
        # rebate too -- freight posts at the gross shipping charge.
        order = _fake_order([_fake_item(shipping_price_amount=5.00, shipping_discount_amount=1.00)])
        payload, _ = self._build(order)
        ship_lines = [l for l in payload["DocumentLines"] if l["ItemCode"] == payload_mod._SHIPPING_ITEM_CODE]
        self.assertEqual(len(ship_lines), 1)
        self.assertEqual(ship_lines[0]["UnitPrice"], 5.00)

    def test_shipping_line_omitted_when_zero(self):
        order = _fake_order([_fake_item(shipping_price_amount=0, shipping_discount_amount=0)])
        payload, _ = self._build(order)
        self.assertFalse([l for l in payload["DocumentLines"] if l["ItemCode"] == payload_mod._SHIPPING_ITEM_CODE])

    def test_unmapped_sku_skipped_not_fatal(self):
        order = _fake_order([
            _fake_item(seller_sku="SKU-1"),
            _fake_item(seller_sku="SKU-UNMAPPED"),
        ])
        payload, skipped = self._build(order)
        self.assertEqual(len(payload["DocumentLines"]), 1)  # only SKU-1 posted
        self.assertEqual(skipped, [{"seller_sku": "SKU-UNMAPPED", "reason": "No SAP mapping"}])

    def test_no_postable_lines_returns_none(self):
        order = _fake_order([_fake_item(seller_sku="", quantity=1), _fake_item(seller_sku="SKU-1", quantity=0)])
        payload, skipped = self._build(order)
        self.assertIsNone(payload)

    def test_refuses_to_post_without_ship_date(self):
        # 2026-07-14: production posted a batch of orders dated by
        # purchase_date, silently, before ship-date sync had caught up --
        # gave them the wrong MTR month. Refuse instead of guessing.
        order = _fake_order([_fake_item()], actual_ship_date=None, purchase_date="2026-06-30 23:59:03")
        payload, skipped = self._build(order)
        self.assertIsNone(payload)
        self.assertEqual(skipped, [{"reason": "No actual_ship_date -- run the FBA shipments sync before posting"}])

    def test_doc_date_uses_ship_date_when_present(self):
        order = _fake_order([_fake_item()], actual_ship_date="2026-07-02", purchase_date="2026-06-30 23:59:03")
        payload, _ = self._build(order)
        self.assertEqual(payload["DocDate"], "2026-07-02")

    def test_hana_unavailable_propagates_not_swallowed(self):
        from khanal_tech_integrations.amazon_us.client.hana import HanaUnavailableError
        order = _fake_order([_fake_item()])
        with self.assertRaises(HanaUnavailableError):
            self._build(order, allocate_side_effect=HanaUnavailableError("HANA down"))
