"""
Tests for the credit-note payload calculation logic in workers/credit_note.py
-- same "what SAP gets charged" stakes as invoice payloads, plus the
subtlest piece of business logic in the whole module (the SKU-mapping-drift
fallback in _build_credit_note_payload).

Mocks/fixtures only, no live DB/SAP dependency -- matches
tests/test_payload.py's style.
"""
import json
import tempfile
import unittest
from datetime import datetime
from types import SimpleNamespace

from khanal_tech_integrations.amazon_us.workers import credit_note as cn_mod


def _fake_settings(**overrides):
    defaults = dict(sap_warehouse_code="AMZ-FBA", sap_card_code="C00001",
                     sap_credit_note_series=121, sap_pay_to_code="Amazon USA-B2C")
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _fake_item_row(**overrides):
    defaults = dict(seller_sku="SKU-1", unit_price=26.99, sap_item_code="FGDC0001")
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestReceivingBatches(unittest.TestCase):
    def test_no_shipped_batches_returns_none(self):
        self.assertIsNone(cn_mod._receiving_batches({"BatchNumbers": []}, 1))
        self.assertIsNone(cn_mod._receiving_batches({}, 1))

    def test_single_batch_covers_qty_exactly(self):
        line = {"BatchNumbers": [{"BatchNumber": "B1", "Quantity": 5}]}
        result = cn_mod._receiving_batches(line, 3)
        self.assertEqual(result, [{"BatchNumber": "B1", "Quantity": 3}])

    def test_spillover_onto_last_batch_when_refund_exceeds_shipped(self):
        # Real rule from the docstring: refunded qty > what the shipped
        # batches actually recorded -- spill the remainder onto the last
        # batch used rather than erroring.
        line = {"BatchNumbers": [
            {"BatchNumber": "B1", "Quantity": 2},
            {"BatchNumber": "B2", "Quantity": 1},
        ]}
        result = cn_mod._receiving_batches(line, 5)  # only 3 shipped, need 5
        self.assertEqual(result, [
            {"BatchNumber": "B1", "Quantity": 2},
            {"BatchNumber": "B2", "Quantity": 3},  # 1 + spillover of 2
        ])

    def test_spillover_with_zero_shipped_falls_back_to_first_batch(self):
        line = {"BatchNumbers": [{"BatchNumber": "B1", "Quantity": 0}]}
        result = cn_mod._receiving_batches(line, 4)
        self.assertEqual(result, [{"BatchNumber": "B1", "Quantity": 4}])


class TestParseDt(unittest.TestCase):
    def test_strips_trailing_timezone_abbreviation(self):
        dt = cn_mod._parse_dt("Jun 1, 2026 12:21:48 PM PDT")
        self.assertEqual(dt, datetime(2026, 6, 1, 12, 21, 48))


class TestParseRefundEvents(unittest.TestCase):
    def test_groups_by_order_and_timestamp(self):
        csv_content = (
            '"date/time","type","order id","sku","product sales","product sales tax",'
            '"shipping credits","shipping credits tax"\n'
            '"Jun 1, 2026 12:21:48 PM PDT","Refund","111-1111111-1111111","SKU-1","-10.00","-1.00","0","0"\n'
            '"Jun 1, 2026 12:21:48 PM PDT","Refund","111-1111111-1111111","SKU-2","-5.00","-0.50","0","0"\n'
            '"Jun 1, 2026 12:21:48 PM PDT","Order","111-1111111-1111111","SKU-1","10.00","1.00","0","0"\n'
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            path = f.name

        events = cn_mod._parse_refund_events(path)
        self.assertEqual(len(events), 1)  # one refund event (Order row ignored)
        event = events[0]
        self.assertEqual(event["amazon_order_id"], "111-1111111-1111111")
        self.assertEqual(len(event["item_adjustments"]), 2)  # both SKUs grouped together
        self.assertEqual(event["posted_date"], "2026-06-01")


class TestBuildCreditNotePayload(unittest.TestCase):
    def _order_doc(self, invoice_lines, items, sap_doc_entry="12345"):
        return SimpleNamespace(
            sap_doc_entry=sap_doc_entry,
            payload_json=json.dumps({"DocDate": "2026-06-30", "DocumentLines": invoice_lines}),
            items=items,
            amazon_order_id="111-1111111-1111111",
            buyer_name=None, ship_city=None, ship_state_or_region=None,
            ship_postal_code=None, ship_country=None, purchase_date="2026-06-30 12:00:00",
        )

    def _event(self, **overrides):
        defaults = dict(
            refund_id="111-1111111-1111111-20260701000000",
            amazon_order_id="111-1111111-1111111",
            posted_date="2026-07-01",
            item_adjustments=[{"seller_sku": "SKU-1", "principal_amount": -26.99, "tax_amount": -2.51,
                                "shipping_amount": 0, "shipping_tax_amount": 0}],
        )
        defaults.update(overrides)
        return defaults

    def test_no_posted_invoice_returns_error(self):
        order = self._order_doc([], [], sap_doc_entry=None)
        payload, skipped = cn_mod._build_credit_note_payload(
            self._event(), order, _fake_settings(), {}, "etax0")
        self.assertIsNone(payload)
        self.assertIn("no posted invoice", skipped[0]["reason"].lower())

    def test_qty_derived_from_principal_amount_over_unit_price(self):
        invoice_lines = [{"ItemCode": "FGDC0001", "Quantity": 1, "LineNum": 0}]
        items = [_fake_item_row(seller_sku="SKU-1", unit_price=26.99, sap_item_code="FGDC0001")]
        order = self._order_doc(invoice_lines, items)
        item_mapping = {"SKU-1": {"sap_item_code": "FGDC0001"}}

        payload, skipped = cn_mod._build_credit_note_payload(
            self._event(), order, _fake_settings(), item_mapping, "etax0")
        item_line = payload["DocumentLines"][0]
        self.assertEqual(item_line["Quantity"], round(26.99 / 26.99, 6))  # = 1.0
        self.assertEqual(item_line["BaseEntry"], 12345)
        self.assertEqual(item_line["BaseLine"], 0)

    def test_sku_mapping_drift_falls_back_to_staged_item_code(self):
        # Current SKU mapping now points at a DIFFERENT SAP item than what
        # the invoice was actually posted under (mapping drift) -- must
        # still find the base line via the order's own staged sap_item_code,
        # not the current (drifted) mapping.
        invoice_lines = [{"ItemCode": "FGDC-OLD-CODE", "Quantity": 1, "LineNum": 0}]
        items = [_fake_item_row(seller_sku="SKU-1", unit_price=26.99, sap_item_code="FGDC-OLD-CODE")]
        order = self._order_doc(invoice_lines, items)
        item_mapping = {"SKU-1": {"sap_item_code": "FGDC-NEW-DRIFTED-CODE"}}  # drifted since posting

        payload, skipped = cn_mod._build_credit_note_payload(
            self._event(), order, _fake_settings(), item_mapping, "etax0")
        self.assertIsNotNone(payload, f"should have found the base line via staged code, skipped={skipped}")
        self.assertEqual(payload["DocumentLines"][0]["ItemCode"], "FGDC-OLD-CODE")

    def test_no_matching_invoice_line_is_skipped_not_fatal(self):
        invoice_lines = [{"ItemCode": "SOME-OTHER-CODE", "Quantity": 1, "LineNum": 0}]
        items = [_fake_item_row(seller_sku="SKU-1", unit_price=26.99, sap_item_code="FGDC0001")]
        order = self._order_doc(invoice_lines, items)
        item_mapping = {"SKU-1": {"sap_item_code": "FGDC0001"}}

        payload, skipped = cn_mod._build_credit_note_payload(
            self._event(), order, _fake_settings(), item_mapping, "etax0")
        self.assertIsNone(payload)
        self.assertIn("no matching invoice line", skipped[0]["reason"].lower())

    def test_doc_date_clamped_forward_to_invoice_date_when_earlier(self):
        # Invoice DocDate 2026-06-30, refund posted_date earlier (2026-06-25)
        # -- SAP rejects a CN dated before its base invoice, so must clamp.
        invoice_lines = [{"ItemCode": "FGDC0001", "Quantity": 1, "LineNum": 0}]
        items = [_fake_item_row(seller_sku="SKU-1", unit_price=26.99, sap_item_code="FGDC0001")]
        order = self._order_doc(invoice_lines, items)
        item_mapping = {"SKU-1": {"sap_item_code": "FGDC0001"}}
        event = self._event(posted_date="2026-06-25")

        payload, _ = cn_mod._build_credit_note_payload(event, order, _fake_settings(), item_mapping, "etax0")
        self.assertEqual(payload["DocDate"], "2026-06-30")  # clamped, not 2026-06-25

    def test_doc_date_not_clamped_when_after_invoice_date(self):
        invoice_lines = [{"ItemCode": "FGDC0001", "Quantity": 1, "LineNum": 0}]
        items = [_fake_item_row(seller_sku="SKU-1", unit_price=26.99, sap_item_code="FGDC0001")]
        order = self._order_doc(invoice_lines, items)
        item_mapping = {"SKU-1": {"sap_item_code": "FGDC0001"}}
        event = self._event(posted_date="2026-07-05")

        payload, _ = cn_mod._build_credit_note_payload(event, order, _fake_settings(), item_mapping, "etax0")
        self.assertEqual(payload["DocDate"], "2026-07-05")

    def test_tax_and_shipping_summary_lines_use_absolute_value(self):
        invoice_lines = [{"ItemCode": "FGDC0001", "Quantity": 1, "LineNum": 0}]
        items = [_fake_item_row(seller_sku="SKU-1", unit_price=26.99, sap_item_code="FGDC0001")]
        order = self._order_doc(invoice_lines, items)
        item_mapping = {"SKU-1": {"sap_item_code": "FGDC0001"}}
        event = self._event(item_adjustments=[{
            "seller_sku": "SKU-1", "principal_amount": -26.99, "tax_amount": -2.51,
            "shipping_amount": -5.00, "shipping_tax_amount": -0.50,
        }])

        payload, _ = cn_mod._build_credit_note_payload(event, order, _fake_settings(), item_mapping, "etax0")
        tax_line = next(l for l in payload["DocumentLines"] if l["ItemCode"] == cn_mod._TAX_ITEM_CODE)
        ship_line = next(l for l in payload["DocumentLines"] if l["ItemCode"] == cn_mod._SHIPPING_ITEM_CODE)
        self.assertEqual(tax_line["UnitPrice"], round(2.51 + 0.50, 2))  # tax + shipping_tax, abs
        self.assertEqual(ship_line["UnitPrice"], 5.00)
