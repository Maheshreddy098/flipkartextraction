# Ghee Production Order — Persistent Records & Enterprise UI

**Date:** 2026-06-29
**Branch:** GheeProductionOrder_Yogesha_23062026
**Status:** Approved, ready for implementation

---

## Problem

1. Completed production orders are deleted from the database — no permanent record exists after completion.
2. Current UI is prototype-level; production team needs enterprise-grade visibility and state tracking.

---

## Decisions

- **Approach B**: Replace `Ghee Production Draft` with a new `Ghee Production Order` doctype. The draft concept becomes `status = Draft` on the same document. Records are never deleted.
- **States**: `Draft → PO Created → GI Done → GR Done → Completed` with `Failed` as a non-terminal error state that stays at the last successful state.
- **No cancellation**. Failed orders stay retryable.
- **UI**: Dashboard KPI strip + filterable list combined view; order detail shows summary card + expandable audit trail + expandable cost breakdown.

---

## Section 1 — Data Model

### Doctype: `Ghee Production Order`

Series: `GPO-.YYYY.-.#####`

#### Header Fields

| Field | Type | Description |
|---|---|---|
| `status` | Select | `Draft / PO Created / GI Done / GR Done / Completed / Failed` |
| `source_item_code` | Data | FG item being reversed (e.g. FGHN0132) |
| `new_item_code` | Data | Output raw material (e.g. RMHN0094) |
| `doc_date` | Date | SAP posting date |
| `new_item_warehouse` | Data | Default: HN-WIP |
| `remarks` | Small Text | Optional SAP remarks |
| `po_entry` | Data | SAP Production Order AbsEntry |
| `po_doc_num` | Data | SAP Production Order DocNum |
| `goods_issue_doc` | Data | SAP GI DocNum |
| `goods_receipt_doc` | Data | SAP GR DocNum |
| `po_closed` | Check | Whether SAP PO was successfully closed |
| `error_message` | Small Text | Last error text (for Failed state retry display) |
| `selected_batches_json` | Long Text | JSON array of source batches [{batch_no, source_qty, warehouse}] |
| `output_batch_nos_json` | Long Text | JSON map of output batch numbers {item_code: batch_no} |

#### Step Timestamp Fields (Audit Trail)

| Field | Type |
|---|---|
| `po_created_at` | Datetime |
| `gi_done_at` | Datetime |
| `gr_done_at` | Datetime |
| `completed_at` | Datetime |

#### Cost Summary Fields

| Field | Type |
|---|---|
| `total_gi_cost` | Currency |
| `total_gr_cost` | Currency |
| `jar_cost` | Currency |
| `scrap_cost` | Currency |
| `fg_residual` | Currency |

### Child Table: `Ghee Production Order Item`

Parent: `Ghee Production Order`, fieldname: `items`

| Field | Type | Description |
|---|---|---|
| `item_code` | Data | SAP item code |
| `item_name` | Data | SAP item name |
| `quantity` | Float | |
| `unit_price` | Currency | |
| `line_cost` | Currency | unit_price × quantity |
| `warehouse` | Data | Receiving warehouse |
| `batch_no` | Data | Output batch number assigned |
| `cost_source` | Data | `po_ige1 / oitm_avg / minimum_0.01 / remainder` |

### Migration

Old `Ghee Production Draft` records converted via one-time whitelisted API `migrate_ghee_drafts()`:
- Reads all existing Draft records
- Creates corresponding `Ghee Production Order` docs mapping fields 1:1
- Converts `cost_summary_json` → individual Currency fields
- Deletes source Draft after successful creation of new doc
- Run once from browser console after deploy

Old `Ghee Production Draft` doctype deleted after migration is confirmed.

---

## Section 2 — Backend API & State Machine

### State Machine

```
Draft ──► PO Created ──► GI Done ──► GR Done ──► Completed
              │               │           │
              └───────────────┴───────────┴──► Failed
                                                  │
                                                  └──► (retry resumes from this state)
```

**Rules:**
- Transitions are forward-only (no rollback, no cancellation)
- On SAP failure: set `status = Failed`, write `error_message`, preserve all previously-saved SAP doc numbers
- Retry picks up at the last successful state (idempotency via UDF stamps on SAP PO already implemented)

### API Changes (`production_order.py`)

**`save_ghee_draft` → `save_production_order`**
- Creates or updates `Ghee Production Order` doc
- Returns `name` (GPO-YYYY-NNNNN) for frontend to store and reuse
- Never deletes on completion — sets `status = Completed` and `completed_at = now()`

**`delete_ghee_draft` → removed** (no deletion after completion)

**`create_production_order`** — after SAP PO success:
- Sets `status = PO Created`, `po_created_at = now()`
- Saves `po_entry`, `po_doc_num`

**`complete_production_order`** — state transitions added inline:
- After GI posted → `status = GI Done`, `gi_done_at = now()`, saves `goods_issue_doc`
- After GR posted → `status = GR Done`, `gr_done_at = now()`, saves `goods_receipt_doc`
- After PO closed + HANA jugad → `status = Completed`, `completed_at = now()`
- Populates `items` child table from `real_items + scrap_items + fg_items`
- Populates all cost summary Currency fields from `cost_summary` dict

**SAP posting logic unchanged** — only Frappe save/state calls change.

**New: `migrate_ghee_drafts`** (whitelisted, run-once)

---

## Section 3 — Frontend UI/UX

### Dashboard (`/kiosk/ghee-production-order`)

**KPI Strip — 4 cards:**
- Today's Orders | Completed | In Progress | Failed

**Order Table:**

Columns: `GPO#` | `Date` | `Source Item` | `Source Batches` | `Status` | `GI Doc` | `GR Doc` | `Total Cost` | `Action`

**Status badges:**
| Status | Color |
|---|---|
| Draft | Gray |
| PO Created | Blue |
| GI Done | Indigo |
| GR Done | Purple |
| Completed | Green |
| Failed | Red |

**Actions:** `Resume` (Draft/Failed) · `View` (Completed/GR Done)

**Filters:** Date range + status multi-select

---

### New Order Wizard (`/kiosk/ghee-production-order/new`)

Same 5-step flow. Changes:
- Saves to `Ghee Production Order` from Step 1 onwards; stores `name` in frontend state
- On step failure: red banner with exact SAP error + "Retry" button; stays on same step
- Step indicator reflects current `status` from Frappe doc

---

### Order Detail Page (`/kiosk/ghee-production-order/:name`)

**Summary card (always visible):**
- GPO number, date, status badge
- Source item → Output item
- Source batches, output batch numbers
- SAP doc numbers: PO / GI / GR as copyable chips

**Audit trail (expandable):**
- Step timeline with timestamps and `created_by`
- PO Created at · GI Done at · GR Done at · Completed at

**Cost breakdown (expandable table):**
- Item Code | Name | Qty | Unit Price | Line Cost | Warehouse | Batch | Cost Source

**Failed state:**
- Red error card with `error_message`
- "Retry" button → resumes wizard at step matching last successful state

---

### UI Principles

- SAP doc numbers always visible at a glance
- Status always in page header
- Every async action: spinner + disabled button
- Error messages show exact SAP error text
- No modals for important actions — inline confirmations
- Retry is one click from Failed state

---

## Out of Scope

- PDF export
- Email notifications on state change
- Role-based field permissions
- Bulk operations
