"""
Safe test suite for po_grn.py — zero writes to Unicommerce or any external system.

Tests covered:
  1. Payload builders (_build_po_payload, _build_grn_item_list) with mock line items
  2. GRN round-robin algorithm (_push_grn_rounds) with a mock UC that records calls
     but never actually hits the network
  3. Frappe DB read — get_inward_transfer_list (reads SAP Inventory Transfers only)
  4. ops_inward_transfer_list whitelist wrapper (DB read only)

Run:
  bench --site dev.localhost execute \
    khanal_tech_integrations.unicommerce.workers._test_po_grn.run_all
"""

from __future__ import annotations
import traceback


# ---------------------------------------------------------------------------
# Mock objects — simulate Frappe doc rows without DB access
# ---------------------------------------------------------------------------

class _MockLineItem:
    def __init__(self, itemcode, batchnumber, batchquantity, expirydate=None):
        self.itemcode = itemcode
        self.batchnumber = batchnumber
        self.batchquantity = batchquantity
        self.quantity = batchquantity
        self.expirydate = expirydate


class _MockUC:
    """Fake UCClient that records calls without touching UC."""
    def __init__(self):
        self.calls: list[dict] = []
        self._call_counter = 0

    def _post_with_reauth(self, endpoint, body, extra_headers=None):
        self._call_counter += 1
        self.calls.append({"endpoint": endpoint, "body": body})
        # Simulate successful GRN creation
        if "inflowReceipt/create" in endpoint:
            return {"successful": True, "inflowReceiptCode": f"GRN-TEST-{self._call_counter}"}
        # Simulate successful item add
        if "inflowReceipt/addItemSKU" in endpoint:
            return {"successful": True}
        return {"successful": False}

    def _resolve_facility_codes(self):
        return ["kfl_ecom_warehouse"]


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

_PASS = []
_FAIL = []

def _check(name, condition, detail=""):
    if condition:
        _PASS.append(name)
        print(f"  ✓  {name}")
    else:
        _FAIL.append(name)
        print(f"  ✗  {name}" + (f" — {detail}" if detail else ""))


def _section(title):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


# ---------------------------------------------------------------------------
# Test 1: _build_po_payload
# ---------------------------------------------------------------------------

def test_build_po_payload():
    _section("Test 1 · _build_po_payload")
    from khanal_tech_integrations.unicommerce.workers.po_grn import _build_po_payload

    # Basic case: two items, same SKU should be summed
    items = [
        _MockLineItem("FGHN0001", "B001", 10),
        _MockLineItem("FGHN0001", "B002", 5),   # same SKU, different batch
        _MockLineItem("FGHN0002", "B003", 7),
        _MockLineItem("", "B004", 3),            # empty SKU — should be skipped
        _MockLineItem("FGHN0003", "B005", 0),   # zero qty — should be skipped
    ]
    payload = _build_po_payload(items)

    _check("vendorCode is EC-B2C", payload["vendorCode"] == "EC-B2C")
    po_items = {i["itemSKU"]: i["quantity"] for i in payload["purchaseOrderItems"]}
    _check("FGHN0001 quantity summed to 15", po_items.get("FGHN0001") == 15.0,
           f"got {po_items.get('FGHN0001')}")
    _check("FGHN0002 quantity is 7", po_items.get("FGHN0002") == 7.0,
           f"got {po_items.get('FGHN0002')}")
    _check("empty SKU excluded", "" not in po_items)
    _check("zero qty SKU excluded", "FGHN0003" not in po_items)
    _check("unitPrice is 0", all(i["unitPrice"] == 0 for i in payload["purchaseOrderItems"]))

    # Edge: empty line items
    empty_payload = _build_po_payload([])
    _check("empty items returns empty purchaseOrderItems",
           empty_payload["purchaseOrderItems"] == [])


# ---------------------------------------------------------------------------
# Test 2: _build_grn_item_list
# ---------------------------------------------------------------------------

def test_build_grn_item_list():
    _section("Test 2 · _build_grn_item_list")
    from khanal_tech_integrations.unicommerce.workers.po_grn import _build_grn_item_list
    import datetime

    items = [
        _MockLineItem("FGHN0001", "B001", 10, expirydate=datetime.date(2026, 12, 31)),
        _MockLineItem("FGHN0001", "B002", 5, expirydate=None),   # no expiry
        _MockLineItem("FGHN0002", "B003", 7, expirydate=datetime.date(2025, 6, 30)),
        _MockLineItem("", "B004", 3),          # empty SKU — skip
        _MockLineItem("FGHN0003", "B005", 0), # zero qty — skip
    ]
    grn_items = _build_grn_item_list(items)

    _check("3 valid GRN items built", len(grn_items) == 3, f"got {len(grn_items)}")
    skus = [i["skuCode"] for i in grn_items]
    _check("FGHN0001 B001 present", "FGHN0001" in skus)
    _check("empty SKU excluded from GRN", "" not in skus)
    _check("zero qty excluded from GRN", "FGHN0003" not in skus)

    b001 = next(i for i in grn_items if i["skuCode"] == "FGHN0001" and
                i["wsBatchDetail"]["wsBatchGroupFieldValue"]["vendorBatchNumber"] == "B001")
    _check("expiryDate present when set (UTC ISO 8601)",
           b001["wsBatchDetail"]["wsBatchGroupFieldValue"].get("expiryDate") == "2026-12-31T00:00:00.000Z",
           f"got {b001['wsBatchDetail']['wsBatchGroupFieldValue'].get('expiryDate')}")

    b002 = next(i for i in grn_items if i["skuCode"] == "FGHN0001" and
                i["wsBatchDetail"]["wsBatchGroupFieldValue"]["vendorBatchNumber"] == "B002")
    _check("expiryDate is None when not set",
           b002["wsBatchDetail"]["wsBatchGroupFieldValue"].get("expiryDate") is None)

    _check("unitPrice is 1", all(i["unitPrice"] == 1 for i in grn_items))


# ---------------------------------------------------------------------------
# Test 3: _push_grn_rounds (mock UC — zero network calls)
# ---------------------------------------------------------------------------

def test_push_grn_rounds():
    _section("Test 3 · _push_grn_rounds (mock UC, no network)")
    from khanal_tech_integrations.unicommerce.workers.po_grn import _push_grn_rounds

    mock_uc = _MockUC()
    extra_headers = {"facility": "kfl_ecom_warehouse"}

    # Scenario: 2 batches of FGHN0001, 1 batch of FGHN0002 → needs 2 GRN rounds
    # Round 1: FGHN0001/B001 + FGHN0002/B003
    # Round 2: FGHN0001/B002 (duplicate SKU from round 1)
    grn_items = [
        {"skuCode": "FGHN0001", "quantity": 10, "unitPrice": 1,
         "wsBatchDetail": {"wsBatchGroupFieldValue": {"vendorBatchNumber": "B001"}}},
        {"skuCode": "FGHN0001", "quantity": 5, "unitPrice": 1,
         "wsBatchDetail": {"wsBatchGroupFieldValue": {"vendorBatchNumber": "B002"}}},
        {"skuCode": "FGHN0002", "quantity": 7, "unitPrice": 1,
         "wsBatchDetail": {"wsBatchGroupFieldValue": {"vendorBatchNumber": "B003"}}},
    ]

    created_grns, errors = _push_grn_rounds("PO-TEST-001", grn_items, mock_uc, extra_headers)

    _check("2 GRNs created (one per unique-SKU round)", len(created_grns) == 2,
           f"got {len(created_grns)}")
    _check("no errors from mock UC", len(errors) == 0, f"errors: {errors}")

    grn_create_calls = [c for c in mock_uc.calls if "inflowReceipt/create" in c["endpoint"]]
    add_item_calls = [c for c in mock_uc.calls if "inflowReceipt/addItemSKU" in c["endpoint"]]
    _check("2 GRN create calls made", len(grn_create_calls) == 2,
           f"got {len(grn_create_calls)}")
    _check("3 addItemSKU calls made (one per batch)", len(add_item_calls) == 3,
           f"got {len(add_item_calls)}")

    # Verify purchaseOrderCode passed to GRN creation
    for call in grn_create_calls:
        _check("correct PO code in GRN create",
               call["body"].get("purchaseOrderCode") == "PO-TEST-001")

    # Scenario: single SKU, single batch → 1 GRN
    mock_uc2 = _MockUC()
    simple_items = [
        {"skuCode": "FGDC0038", "quantity": 20, "unitPrice": 1,
         "wsBatchDetail": {"wsBatchGroupFieldValue": {"vendorBatchNumber": "B001"}}},
    ]
    grns2, errs2 = _push_grn_rounds("PO-TEST-002", simple_items, mock_uc2, extra_headers)
    _check("single SKU/batch → 1 GRN", len(grns2) == 1, f"got {len(grns2)}")
    _check("no errors for simple case", len(errs2) == 0)

    # Scenario: empty items → no GRNs, no errors
    mock_uc3 = _MockUC()
    grns3, errs3 = _push_grn_rounds("PO-TEST-003", [], mock_uc3, extra_headers)
    _check("empty items → 0 GRNs", len(grns3) == 0)
    _check("empty items → 0 errors", len(errs3) == 0)


# ---------------------------------------------------------------------------
# Test 4: Frappe DB read — get_inward_transfer_list
# ---------------------------------------------------------------------------

def test_get_inward_transfer_list():
    _section("Test 4 · get_inward_transfer_list (DB read only)")
    from khanal_tech_integrations.unicommerce.workers.po_grn import get_inward_transfer_list

    rows = get_inward_transfer_list(days=90)

    _check("returns a list", isinstance(rows, list))
    print(f"  ℹ  Found {len(rows)} inward transfer(s) in last 90 days")

    if rows:
        first = rows[0]
        _check("row has 'name' field", "name" in first)
        _check("row has 'docnum' field", "docnum" in first)
        _check("row has 'ui_status' field", "ui_status" in first)
        _check("ui_status is a known value",
               first["ui_status"] in ("PENDING", "PO_CREATED", "GRN_PARTIAL", "GRN_COMPLETED"),
               f"got {first['ui_status']}")
        _check("row has 'docdate' field", "docdate" in first)

        pending = [r for r in rows if r["ui_status"] == "PENDING"]
        po_done = [r for r in rows if r["ui_status"] in ("PO_CREATED", "GRN_COMPLETED", "GRN_PARTIAL")]
        print(f"  ℹ  Pending (no UC PO): {len(pending)}")
        print(f"  ℹ  Has PO/GRN: {len(po_done)}")

        if pending:
            print(f"  ℹ  First pending: {pending[0]['docnum']} ({pending[0]['docdate']})")
    else:
        print("  ℹ  No EC-FG inward transfers found — table may be empty or no transfers in 90 days")


# ---------------------------------------------------------------------------
# Test 5: ops_inward_transfer_list whitelist wrapper
# ---------------------------------------------------------------------------

def test_ops_inward_transfer_list():
    _section("Test 5 · ops_inward_transfer_list (whitelist wrapper)")
    from khanal_tech_integrations.unicommerce.api.ops import ops_inward_transfer_list

    result = ops_inward_transfer_list(days=90)

    _check("returns a dict", isinstance(result, dict))
    _check("has 'rows' key", "rows" in result)
    _check("has 'summary' key", "summary" in result)
    _check("no 'error' key in result", "error" not in result,
           result.get("error", ""))

    summary = result.get("summary") or {}
    _check("summary has 'total'", "total" in summary)
    _check("summary has 'pending'", "pending" in summary)
    _check("summary has 'grn_completed'", "grn_completed" in summary)
    _check("total = sum of status counts",
           summary.get("total", 0) ==
           (summary.get("pending", 0) + summary.get("po_created", 0) +
            summary.get("grn_completed", 0) + summary.get("grn_partial", 0)),
           f"total={summary.get('total')} vs sum={summary.get('pending',0)+summary.get('po_created',0)+summary.get('grn_completed',0)+summary.get('grn_partial',0)}")

    print(f"  ℹ  Summary: {summary}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_all():
    print("\n" + "═"*60)
    print("  po_grn.py — Safe Test Suite (zero UC writes)")
    print("═"*60)

    tests = [
        ("_build_po_payload",            test_build_po_payload),
        ("_build_grn_item_list",          test_build_grn_item_list),
        ("_push_grn_rounds (mock UC)",    test_push_grn_rounds),
        ("get_inward_transfer_list (DB)", test_get_inward_transfer_list),
        ("ops_inward_transfer_list",      test_ops_inward_transfer_list),
    ]

    for name, fn in tests:
        try:
            fn()
        except Exception:
            _FAIL.append(name)
            print(f"\n  ✗ EXCEPTION in {name}:")
            traceback.print_exc()

    print("\n" + "═"*60)
    print(f"  Results: {len(_PASS)} passed · {len(_FAIL)} failed")
    if _FAIL:
        print(f"  Failed: {', '.join(_FAIL)}")
    print("═"*60 + "\n")

    return {"passed": len(_PASS), "failed": len(_FAIL), "failed_tests": _FAIL}
