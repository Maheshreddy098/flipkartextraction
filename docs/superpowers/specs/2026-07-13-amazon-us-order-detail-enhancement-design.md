# Amazon US Order Detail Enhancement — Design

Date: 2026-07-13 · Extends `2026-07-09-amazon-us-dashboard-design.md`

## Goal

The dashboard's `Amazon US Order` doctype carries ~40 order fields and 17
line-item fields; the frontend currently surfaces about 12 of them and zero
line-item data anywhere. Ops resolving a stuck order and Finance matching
money both need to drill into a single order and see everything about it —
buyer/shipping, line items with full price/tax/shipping/promo breakdown,
credit-note reversal detail, and which settlement period paid it out. Also
fold in server-side search (the current search box only filters the
already-loaded page, not the full 14K+ order dataset) and CSV export.

## Non-goals

- No CN CSV export in v1 — add later if asked.
- No cross-tab deep-linking from the order drawer into the Settlements tab's
  own recon drawer — just display the settlement id, no state sync.
- No Excel/multi-sheet export — CSV covers this; XLSX stays reserved for the
  MTR reconciliation workbook (`reconciliation.py`), which has a genuine
  multi-sheet need this doesn't.
- Stays within the existing 5 tabs — no new nav-level routes.

## Architecture

New backend endpoints in `amazon_us/api/ops.py`, all read-only (no
`_require_poster()` gate — matches the existing read-endpoint pattern like
`get_orders`/`get_stats`):

- `get_order_detail(order_name)` — full order record + all `Order Item`
  rows + a reverse lookup of which settlement period(s) reference this
  order (`Amazon US Settlement Line.order_id = order.amazon_order_id`,
  joined to the parent `Settlement` for `settlement_id`/`deposit_date`).
  Entirely local DB — no SAP call, fast enough to load on every drawer open.
- `get_credit_note_detail(order_name)` — **on-demand only**, called when a
  user actually opens a CN's detail. Credit-note reversal detail was never
  persisted locally (only the invoice's `payload_json` is stored, never the
  CN's), so this is the only source of truth: a live SAP query via the
  existing `client/sap.py::get_credit_note_lines(doc_entry)`. Wrapped in
  try/except — a SAP failure returns `{"status": "error", "message": ...}`,
  never a raw exception to the frontend. Requires the order to have a
  `cn_doc_entry`; returns a structured error if not.
- `export_orders_csv(from_date, to_date, stage=None, search=None)` — stdlib
  `csv` module, writes to `frappe.response.filecontent` with
  `frappe.response.type = "download"` (standard Frappe file-download
  pattern) — no new dependency, no XLSX formatting need here.

Modified endpoint:

- `get_orders(from_date, to_date, stage, page, page_size, search=None)` —
  add a server-side `search` param matching `amazon_order_id`, `buyer_name`,
  or `Order Item.seller_sku` (bound `LIKE` params, joined for the SKU case).
  This also fixes an existing bug: `OrdersView.vue`'s search box currently
  does `rows.value.filter(...)` client-side, which only searches the 50
  rows already loaded on the current page — silently useless against the
  rest of a 14K+-row dataset.

New frontend component: `amazonus-frontend/src/components/OrderDetailDrawer.vue`
— shared, not duplicated across views. Props: `orderName: string`,
`autoLoadCn?: boolean` (see Data flow). On open, calls `get_order_detail`.
Sections, in order:

1. Header — order id, `StageBadge`, Amazon `order_status`.
2. Buyer & shipping — `buyer_name`, `buyer_email`, `ship_city/state/postal/country`.
3. Order flags & channel — `is_prime`, `is_business_order`,
   `is_replacement_order`, `fulfillment_channel`, `sales_channel`,
   `order_type`, `ship_service_level`, `marketplace_id`.
4. Dates — `purchase_date`, `actual_ship_date`, `last_update_date`,
   `posted_at`, `posting_started_at`.
5. Line items table — `seller_sku`, `sap_item_code` (+ `is_mapped` badge),
   `asin`, `title`, `quantity`, `item_price_amount`, `item_tax_amount`,
   `shipping_price_amount`, `shipping_tax_amount`,
   `shipping_discount_amount`, `promotion_discount_amount`, `cod_fee`,
   `unit_price`.
6. SAP linkage — `sap_doc_entry`/`sap_doc_num`, `order_total_amount`/`currency`.
7. Credit note — shown only if `cn_doc_num` is set. Renders a "Load refund
   detail" button that calls `get_credit_note_detail` on click (or
   immediately if `autoLoadCn` is true); shows the SAP-sourced line-level
   reversal table (SKU, qty, amount) plus the tax/shipping summary lines.
8. Settlement linkage — list of settlement periods from
   `get_order_detail`'s `settlement_lines` (already fetched, no extra call);
   each row shows `settlement_id`, `deposit_date`, the order's principal
   amount in that settlement. Display-only, no navigation.
9. Errors — `last_error`, `attempt_count`, `posting_started_at` if stuck.
10. Raw JSON — collapsed by default, `payload_json` and `order_json`, for
    ops debugging stuck/failed orders.

Wired into:

- `OrdersView.vue` — swap the inline drawer markup for
  `<OrderDetailDrawer :order-name="detail.name" v-if="detail" @close="detail = null" />`;
  replace the client-side `filtered()` hack with a debounced (300ms) search
  input bound to the new server-side `search` param; add an "Export CSV"
  button.
- `CreditNotesView.vue` — row click opens the same drawer with
  `auto-load-cn` set, since that's why a user clicked through from this tab.
- `SettlementsView.vue` — order rows inside the existing
  `get_settlement_reconciliation` drawer become clickable, opening the same
  `OrderDetailDrawer` for that `order_id`.

## Data flow

- **Order detail**: row click → `get_order_detail(order_name)` → render.
  Local DB only, no SAP round trip, loads on every open.
- **CN detail**: within the open order drawer (button click) or immediately
  when opened from Credit Notes tab (`autoLoadCn`) → `get_credit_note_detail(order_name)`
  → live SAP query → render. Loading state shown inline in that section
  only, not a page-level spinner — errors render inline in the same section,
  not as a toast, since the rest of the drawer is still usable.
- **Settlement linkage**: included in the `get_order_detail` response
  already, no separate call.
- **Search**: debounced input → `get_orders(..., search)` → replaces the
  list, resets to page 1.
- **Export**: click → navigates to
  `/api/method/khanal_tech_integrations.amazon_us.api.ops.export_orders_csv?...`
  with the current filter/search params in the query string; browser
  handles the download via Frappe's response headers. Session cookie auth
  covers this the same way it covers page navigation, no separate CSRF
  wiring needed for a GET.

## Error handling

- `get_order_detail`: order not found → drawer shows a "not found" state,
  no crash.
- `get_credit_note_detail`: missing `cn_doc_entry` → structured error (the
  frontend already only shows the button when `cn_doc_num` is set, so this
  is a defensive backend check, not the primary guard). SAP failure (auth,
  network) → caught, structured error, rendered inline in the CN section.
- `export_orders_csv`: invalid date params surface as Frappe's standard
  validation error page — acceptable for a direct-download endpoint, no
  custom error UI needed.

## Testing

These are read-only queries, not money-moving, so lower stakes than the
posting/credit-note pipeline — but per the existing zero-backend-test-coverage
gap in this module, add one lightweight test file
(`amazon_us/tests/test_ops_order_detail.py` or similar, first test file in
the module) covering:

- `get_orders` search matches on order id, buyer name, and SKU correctly
  (and that an empty search returns the unfiltered set).
- The settlement reverse-lookup join in `get_order_detail` returns the
  right settlement rows for a known order/settlement-line fixture.
- `export_orders_csv` produces the expected header row and one correct data
  row for a known order.

Not full coverage of the whole module — just the new non-trivial logic this
change introduces. Frontend: no new vitest coverage planned for
`OrderDetailDrawer.vue` itself (matches the existing pattern — only
`useJobPolling` has a test today); revisit if the component grows complex
branching logic.
