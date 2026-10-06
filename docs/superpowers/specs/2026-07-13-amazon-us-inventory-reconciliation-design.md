# Amazon US Inventory Reconciliation — Design

Date: 2026-07-13 · Extends `2026-07-09-amazon-us-dashboard-design.md`

## Goal

Compare Amazon FBA inventory against SAP B1 inventory for every mapped SKU
and surface four specific problems: a SKU SAP knows about but Amazon
doesn't report, a quantity mismatch between the two systems, a SKU that's
inactive in SAP while Amazon still shows it with stock, and a SKU carrying
more than a threshold of non-sellable ("blocked") quantity. Confirmed via
code audit before designing this: zero Amazon Inventory API or SAP-inventory
infrastructure exists anywhere in the `amazon_us` module today — this is a
new capability, not an extension of the existing MTR-vs-SAP `$`
reconciliation (`workers/reconciliation.py`), which only compares invoice/
credit-note amounts, never stock quantities.

## Scope decisions (confirmed with the user before designing)

- **Amazon data source**: FBA Inventory API (`GET /fba/inventory/v1/summaries`,
  real-time) — the Seller Central app registration has this permission.
  Not the daily flat-file inventory report.
- **SAP data source**: `OITW.OnHand` for the `AMZ-FBA` warehouse only (same
  warehouse code used everywhere else in this pipeline,
  `Amazon US Settings.sap_warehouse_code`), queried via the existing HANA
  connection (`client/hana.py`).
- **Missing SKU** = a SKU present in the SAP↔Amazon mapping
  (`mappers/payload.py::get_item_mapping()`, the same hybrid SAP U_Amz_SKU +
  `Amazon US Item Mapping` doctype source already used for invoice posting)
  but **absent from the Amazon Inventory API response** — a stale/dead
  mapping or a delisted item SAP still thinks is live. (Not the reverse
  direction — a SKU Amazon sells that SAP has never heard of is a *staging*
  problem already surfaced by the existing "unmapped SKUs" panel on
  Overview, not an inventory-reconciliation concern.)
- **Quantity mismatch** = exact match required: `SAP OnHand != Amazon
  totalQuantity`. No tolerance band.
- **Inactive SKU** = SAP item is inactive/frozen (`OITM` validity flag) AND
  Amazon still returns nonzero quantity for that SKU — the overselling-risk
  direction, not the orphaned-stock direction.
- **Blocked inventory** = `unfulfillableQuantity + reservedQuantity.total +
  inboundWorkingQuantity + inboundShippedQuantity + inboundReceivingQuantity
  > 20 units`. Reserved/inbound quantity alone is normal ongoing FBA
  activity and would be pure noise as a threshold-free flag; 20 is a
  starting constant, tunable the same way the health check's own
  thresholds are.
- **Cadence**: on-demand only, no scheduler entry. Stateless — no
  persistence doctype, always a live comparison. (Easy to add a history
  doctype and a daily cron later if wanted; out of scope now.)
- **Architecture**: enqueue + poll, matching every other external-API
  action in this app (fetch, post, settlements, `$` reconciliation) rather
  than a plain synchronous endpoint — even though the current catalog
  (65 mapped SKUs, 93 SKUs ever seen in an order) would comfortably finish
  synchronously in a few seconds. Consistency with the established pattern
  and headroom for catalog growth won out over the smaller amount of code
  a sync endpoint would have needed.

## Architecture

**`client/fba_inventory.py`** (new — mirrors the existing one-file-per-
Amazon-API-family pattern in `client/reports.py`/`client/finances.py`):
- `get_inventory_summaries(marketplace_id)` — calls `GET
  /fba/inventory/v1/summaries` with `granularityType=Marketplace`,
  `details=true`, paginating via `nextToken` (same retry/backoff/token-
  refresh machinery every other client file already gets for free from
  `client/sp_api.py::_get`). Returns `{seller_sku: summary_dict}`, where
  each summary carries `totalQuantity` and the `inventoryDetails` breakdown
  (`fulfillableQuantity`, `unfulfillableQuantity`,
  `reservedQuantity.totalReservedQuantity`, `inboundWorkingQuantity`,
  `inboundShippedQuantity`, `inboundReceivingQuantity`).

**`workers/inventory_reconciliation.py`** (new):
- `build_inventory_reconciliation(progress_id=None)`:
  1. `get_item_mapping()` for the full SAP↔Amazon SKU set.
  2. One batched HANA query: `OITW.OnHand` + `OITM` active-flag for every
     mapped `sap_item_code` on `AMZ-FBA`, `WHERE ItemCode IN (...)` — not
     one query per SKU.
  3. One `get_inventory_summaries()` call (paginated internally).
  4. Join and classify each mapped SKU into zero or more of the four flags
     above; build a row per SKU (`seller_sku`, `sap_item_code`, `sap_qty`,
     `sap_active`, `amazon_qty`, `diff`, `blocked_qty`, `status_flags`,
     `remarks`) plus summary counts.
  5. Same `HanaUnavailableError` contract as the rest of the pipeline:
     propagates rather than being swallowed, so the job reports a clear
     `hana_down`-shaped failure instead of a wrong "0 issues found".

**`api/ops.py`** (two new endpoints, same enqueue/poll naming convention as
every other action):
- `enqueue_inventory_reconciliation()` — `_require_poster()`-gated (it
  spends live Amazon API quota, same rationale as every other `enqueue_*`
  in this file).
- `get_inventory_reconciliation_result(job_id)` — poll.

**Frontend**: new `InventoryView.vue`, new `/inventory` route
(`router.ts`) and "Inventory" nav entry (`App.vue`'s `nav` array),
following the exact existing pattern for both. Summary tiles (count per
flag type) at the top, a table (SKU, SAP Qty, Amazon Qty, Diff, Blocked
Qty, status badges, remarks) below, a "Run reconciliation" button wired
through the same `useJobPolling` composable every other action tab
already uses, and a CSV export button matching the Orders tab's pattern
(`export_orders_csv`'s stdlib-csv shape, reused for this report).

## Data flow

Click "Run reconciliation" → `enqueue_inventory_reconciliation()` → job_id
→ poll `get_inventory_reconciliation_result` (same 2.5s interval as every
other job in this app) → on `done`, render summary tiles + table; on
`error`/`hana_down`, surface via the log panel exactly like every other
action tab.

## Error handling

- HANA unavailable → job returns `{"status": "hana_down", ...}`, no
  partial/misleading result.
- Amazon API auth/rate-limit failure → caught, `{"status": "error",
  "message": ...}`, surfaced in the log panel, not a crash.
- A mapped SKU with no `OITW` row at all (never received into that
  warehouse) → `sap_qty = 0`, treated the same as any other quantity
  mismatch rather than a special case.

## Testing

Mock-based unit tests for the join/classification logic in
`build_inventory_reconciliation` — fixed fake SAP rows + fake Amazon
summaries, asserting each of the four flags fires and doesn't fire in the
right cases (including the blocked-quantity threshold boundary). Same
style as `test_payload.py`/`test_credit_note.py`: no live API/HANA
dependency. No new frontend test planned for `InventoryView.vue`, matching
the existing pattern (only `useJobPolling` has frontend coverage).
