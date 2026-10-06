# Amazon US Ops Console — Design

Date: 2026-07-09 · Approved by: Yogesha · Replaces Desk page `amazon-us-ops-center`

## Goal

Enterprise-grade, dark ops-console dashboard for the Amazon US B2C → SAP B1
pipeline. All existing functionality plus a month-centric reconciliation view
answering finance's standing questions (what posted, what's pending, what's
blocked and why). Ship-date windows everywhere — ship date = MTR month
(validated 13,019/13,019 against June 2026 MTR).

## Decision: Vue SPA over Frappe Desk page

Vue 3 SPA served at `/amazonus` (approach A). Desk pages can't carry a dark
product-grade look (Desk chrome/CSS bleed), the existing page is 1,155 lines
of hand-rolled jQuery, and the repo already has the exact pattern to copy
(StoreOps: `consumables-frontend/` → `public/` → www route).

## Architecture

- `amazonus-frontend/` — Vue 3 + Vite + TypeScript + Tailwind + Pinia +
  chart.js. Build config copied from `consumables-frontend`.
- Build output → `khanal_tech_integrations/public/amazonus/`.
- Served at `/amazonus` via `www/amazonus.py|html` with login redirect
  (StoreOps pattern). Frappe session cookie + CSRF header auth.
- Backend: existing `amazon_us/api/ops.py` endpoints unchanged, plus:
  - `get_session_info()` → `{user, can_post}` — `can_post` true for roles
    "Amazon US Manager" or "System Manager".
  - `get_recon_summary(from_date, to_date)` → blockers for the window:
    unmapped SKUs with order counts, zero-stock/inactive SAP items parsed
    from failed orders' `last_error`, stage totals.
  - Server-side guard `_require_poster()` on every mutating endpoint
    (enqueue_fetch, enqueue_post, retry, CN runs, settlements sync, …).
    View-only users get 403; buttons also hidden client-side.

## Views

1. **Overview** (default) — month picker → stat tiles from `get_stats`
   (ship-date window), pipeline bar fetched→ready→posted/failed, blockers
   panel (unmapped SKUs, stock items, counts), stage donut. Answers "does SAP
   match MTR this month" at a glance.
2. **Orders** — table: stage filter, order-id search, pagination; detail
   drawer with items, line financials, last_error, payload JSON, SAP DocNum;
   per-row Retry (role-gated).
3. **Actions** — command bar: Bulk Fetch (Report API + lookback), FBA
   Shipments Sync, Post to SAP (confirm shows ready-count preview), Credit
   Notes live run (dry-run toggle default ON), Bulk Retry, Shipping
   Supplements. Each action streams its job log into a live panel via one
   `useJobPolling` composable (replaces all hand-rolled setInterval code).
4. **Settlements** — settlement list + per-settlement reconciliation detail.
5. **Credit Notes** — CN run results, posted CNs with DocNums, skip reasons.

## Data flow

- One axios client (`src/api/client.ts`) with CSRF + 403/session handling.
- Pinia stores: `session`, `stats`, `orders`, `jobs`, `settlements`.
- `useJobPolling(startFn, resultFn)`: enqueue → poll every 2.5s → append log
  lines → resolve on done/error status. All five job types share it.
- Month picker state shared (Pinia) across Overview/Orders/Actions.

## Look

Dark ops-console: near-black layered surfaces, cyan accent for safe actions,
amber for money actions (post/CN), red for destructive/errors, monospace
tabular numerals for counts/amounts, subtle count-up motion on tiles. No
Frappe Desk chrome.

## Errors & edge cases

- Job status `hana_down` / SAP errors → banner + log, never silent.
- Mutating actions: confirm dialog with affected count.
- View-only user: hidden buttons + server 403 → toast "view-only".
- Session expiry → redirect to /login?redirect-to=/amazonus.
- Old Desk page stays until parity confirmed, then retired.

## Testing

- vitest: `useJobPolling` (happy path, error, hana_down), stores (stats
  mapping, orders pagination), recon summary parsing.
- Manual e2e on dev.localhost: each action against test SAP DB.
