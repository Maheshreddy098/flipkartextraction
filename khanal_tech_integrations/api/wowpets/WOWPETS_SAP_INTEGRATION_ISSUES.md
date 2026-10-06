# WowPets ↔ SAP B1 Production Flow (Correct Architecture)

The SAP-safe sequence is **always**:

1. Create Production Order  
2. Release Production Order  
3. Issue for Production  
4. Receipt from Production  
5. Close Production Order  

Anything outside this order causes SAP inconsistencies.

---

## 1. Production Order Creation (BOM-driven, like Production Kiosk)

**API:** `POST /b1s/v1/ProductionOrders`

### Flow

1. **Fetch BOM from SAP:** `GET /ProductTrees('{finished_item}')?$expand=ProductTreeLines` (or `$filter=TreeCode eq '...'`). Returns `ProductTreeLines` with `ItemCode`, `Quantity` per component.
2. **Validate:** Work Order `doc.items` must match SAP BOM in **order and item codes** (case-insensitive). Throw if mismatch so WO was created from SAP BOM.
3. **Build ProductionOrderLines:** For each BOM line: `ItemNo`, `PlannedQuantity` = BOM Quantity × PO qty, `Warehouse`, `LocationCode` 2, `ProductionOrderIssueType` `im_Manual`.
4. **POST** Production Order with **header + ProductionOrderLines**. No auto-expand; SAP uses the lines we send. SAP then updates **IssuedQuantity** automatically when Issue is posted.

**Why BOM-driven:** Matches Production Kiosk behaviour. SAP applies Issue to PO when Issue is created (BaseType 202, BaseEntry, BaseLine), so no PATCH of IssuedQuantity and no Close/Post of the Issue document.

SAP PO: Line 0 = FG, Line 1, 2, … = components (in the order we sent).

### Example payload

```json
{
  "ItemNo": "FGDC1018",
  "PlannedQuantity": 10,
  "ProductionOrderType": "bopotStandard",
  "PostingDate": "2026-03-05",
  "DueDate": "2026-03-05",
  "Remarks": "WowPets WO WO-00001",
  "ProductionOrderLines": [
    { "ItemNo": "PMDC1126", "PlannedQuantity": 50, "Warehouse": "WO - STR", "LocationCode": 2, "ProductionOrderIssueType": "im_Manual" },
    { "ItemNo": "PMDC1055", "PlannedQuantity": 20, "Warehouse": "WO - STR", "LocationCode": 2, "ProductionOrderIssueType": "im_Manual" }
  ]
}
```

### After creation

- **Release** immediately: `PATCH /ProductionOrders({DocEntry})` with `{"ProductionOrderStatus": "boposReleased"}`. Without release, SAP blocks Issue.

---

## 2. Issue for Production (Components)

**API:** `POST /InventoryGenExits`

### Payload rules

- **Quantity must be positive.** SAP interprets positive as “consume this many units” and deducts inventory. **Negative** means by-product/output; SAP rejects with “By-products are not allowed in this type of document”. Use `abs(qty)` when building Issue lines.
- **Do not send ItemCode on DocumentLines** when the document is referenced to a production order (BaseType 202). SAP resolves the item from the PO line; sending ItemCode causes “The field should be empty if the document is referenced to a production order”. **Keep ItemCode in BatchNumbers** (batch allocation requires it).
- **Never send BaseLine 0** for Issue. In SAP, Production Order line 0 is the **finished good**; referencing it in InventoryGenExits is treated as by-product → "By-products are not allowed in this type of document". Build the PO line map **excluding LineNum 0** and **skip the finished good** when iterating components so Issue lines only use BaseLine 1, 2, ….
- One document with multiple lines; each line has BaseType 202, BaseEntry, BaseLine, Quantity, WarehouseCode.

### Example payload (BaseLine 1, 2, … only; never 0)

```json
{
  "DocumentLines": [
    { "BaseType": 202, "BaseEntry": 145, "BaseLine": 1, "Quantity": 5, "WarehouseCode": "WO-STR" },
    { "BaseType": 202, "BaseEntry": 145, "BaseLine": 2, "Quantity": 3, "WarehouseCode": "WO-STR" }
  ]
}
```
SAP PO line 0 = finished good. Issue must only reference component lines (1, 2, …). Skip FG in the loop and exclude LineNum 0 from the PO line map.

### Before posting Issue (SAP-driven)

- **Always** fetch PO with **`GET /ProductionOrders({DocEntry})?$expand=ProductionOrderLines`** (SAP returns BOM-expanded lines).
- Build a **PO line map** (e.g. `ItemNo` → `LineNum`) from the expanded lines (exclude LineNum 0 = FG).
- **Issue only WO components that exist in SAP:** for each Work Order component (with batch), if it exists in the PO line map, add an Issue line with that BaseLine and quantity/batch. **Skip** WO items that are not in the SAP PO (no “missing in PO” error — SAP BOM is source of truth). If no WO component matches any SAP line, throw a clear error so the user ensures SAP BOM exists and WO components/batches are selected.

**SAP applies the Issue to the Production Order when the Issue is created** (BaseType 202, BaseEntry, BaseLine). We do not Close/Post the Issue nor PATCH IssuedQty; SAP manages it. Optional 1.5 s delay before Receipt so SAP can apply the issue internally. (Removed obsolete: when the Issue document is posted; SAP then rejects Receipt with “Item Issued Qty in work order should be larger than zero”. **Before posting Receipt**, call **`(removed: do not PATCH; SAP applies Issue automatically)`** to PATCH the PO’s ProductionOrderLines with IssuedQuantity from the Work Order so SAP allows Receipt.

---

## 3. Receipt from Production (Finished Goods)

**API:** `POST /InventoryGenEntries`

### Payload rules

- **ItemCode** must **not** be sent on the receipt line (SAP uses the referenced PO line).
- **BaseLine** must point to the **finished-good line** in the PO (line 0 when FG is first).
- Quantity = finished quantity; WarehouseCode = finished-goods warehouse.

### Example payload

```json
{
  "DocumentLines": [
    { "BaseType": 202, "BaseEntry": 145, "BaseLine": 0, "Quantity": 10, "WarehouseCode": "WO-FG" }
  ]
}
```

### Resolving BaseLine

- Fetch PO with **`$expand=ProductionOrderLines`** (use shared helper **`_get_po_with_lines()`**).
- SAP adds the finished good internally at **line 0**. Find the line where **ItemNo** equals **finished_item_code** (or use BaseLine **0** if FG is always line 0).
- Set **BaseLine** = that line’s **LineNum** (0 for the FG).

---

## 4. Close Production Order

After receipt:

- **PATCH** `/ProductionOrders({DocEntry})` with `{"ProductionOrderStatus": "boposClosed"}`.

This prevents SAP from leaving the order open.

---

## Implementation summary

| Step | What we do |
|------|------------|
| **Create PO** | **BOM-driven:** Fetch BOM from SAP (ProductTrees), validate doc.items match BOM order, build ProductionOrderLines (ItemNo, PlannedQuantity = BOM qty × PO qty, Warehouse, LocationCode 2, ProductionOrderIssueType im_Manual). POST with header + ProductionOrderLines. Store DocEntry. |
| **Release PO** | PATCH ProductionOrderStatus = boposReleased. |
| **Fetch PO** | Always use **`_get_po_with_lines(session, b1_url, po_entry)`** → returns (po_data, po_lines, session, b1_url). |
| **Issue** | BaseLine = index + 1 for each doc.items (skip FG). PO lines are in BOM order; WO items validated at PO creation. Do not send ItemCode on DocumentLines; keep ItemCode in BatchNumbers. AccountCode on each line. |
| **Before Receipt** | Do **not** Close/Post the Issue document; do **not** PATCH IssuedQty on the PO. Validate that `sap_issue_doc_entry` exists; optional short delay (1.5 s) so SAP can apply the Issue to the PO. |
| **Receipt** | Single implementation **`_post_receipt_from_production()`**: validate Issue exists → resolve base_line from po_lines → POST /InventoryGenEntries. Do not send ItemCode on receipt line. |
| **Close PO** | PATCH ProductionOrderStatus = boposClosed after receipt. |

### Removed / avoided

- **Do not Close/Post Issue or PATCH IssuedQty** — SAP applies the Issue when it is created; /Close and /Post are not reliable; manual PATCH can corrupt the PO. (Obsolete: required in many Service Layer setups because SAP may not update the PO when the Issue document is posted; without it, Receipt fails with “Item Issued Qty in work order should be larger than zero”.
- **No manual ProductionOrderLines** — SAP expands BOM from header; no WOWPETS BOM vs SAP BOM mismatch.
- **No “missing in PO” throw** — issue only WO components that match SAP lines; skip others (SAP is source of truth).
- **BaseLine = LineNum** (0-based) for both Issue and Receipt; no +1 offset.

---

## Quantity rules (summary)

| Document | Quantity rule |
|----------|----------------|
| **Production Order** lines | Components: **positive** (e.g. 5, 3). SAP interprets as consumption. |
| **Issue for Production** | **Positive** only. We send AccountCode 12500900 to match Production Kiosk payload; SAP can also derive from item. |
| **Receipt from Production** | **Positive** (finished quantity). Do not send AccountCode; SAP derives from item when linked to Production Order. |

---

## ApprovalPage (Production Kiosk) vs WowPets work_order

The Production Kiosk (`ApprovalPage.py`) uses a flow that works in their environment. Differences:

| Aspect | ApprovalPage (Production Kiosk) | WowPets work_order |
|--------|----------------------------------|---------------------|
| **SAP config** | `SAP Settings` doctype, `sap_b1_url` | `INC SAP Settings`, `sap_b1_url` (can differ; 502 with `bls/v2` suggests URL/path mismatch) |
| **Issue – AccountCode** | Sends **AccountCode: "12500900"** on each DocumentLine | Optional; we now send same code to match working payload |
| **Issue – BaseLine** | First component **BaseLine 0**, then 1, 2, … | **BaseLine ≥ 1** only (we skip FG at line 0; SAP line 0 = FG, 1,2,… = components) |
| **Issue – ItemCode** | Not sent on lines (commented out); only in BatchNumbers | Same: no ItemCode on DocumentLines; only in BatchNumbers |
| **Issue – WarehouseCode** | "DC-WIP" | "WO - STR" (configurable via `SAP_PO_COMPONENT_WAREHOUSE`) |
| **After Issue** | No Post/Close call; only POST and check 201 | We call Post/Close and verify status; only treat success when GET shows CLOSED |
| **Receipt – AccountCode** | Sends **AccountCode: "12500900"**, WarehouseCode "DC-WIP", LocationCode 2 | No AccountCode on receipt (SAP derives); WarehouseCode from PO/FG |
| **Receipt – BaseLine** | From Get_Production_Data (PO lines), LineNumber | Same: from PO lines, FG line’s LineNum (0 when FG at line 0) |
| **After Receipt** | PATCH ProductionOrderStatus to Closed | Same: PATCH PO to boposClosed |

Replicated from ApprovalPage: **AccountCode on Issue lines** (12500900). We do **not** use BaseLine 0 for the first component (see below). After any 200/201/204 from Post/Close we **verify with GET** that the document is CLOSED before treating as success (avoids assuming 204 = closed when proxy returns 204).

### Why we did not replicate BaseLine 0 for the first component

In SAP B1, when you create a Production Order (header only), SAP expands the BOM and creates **Production Order lines** with a fixed meaning:

- **Line 0** = the **finished good** (the item you are producing).
- **Lines 1, 2, 3, …** = the **components** (raw materials) that will be consumed.

**Issue for Production** is the step where you **consume components** (raw materials) from stock. Each line of the Issue document must reference a **component line** of the Production Order (BaseType 202, BaseEntry = PO DocEntry, **BaseLine** = that line’s number). So in a correct Issue:

- Every **BaseLine** must be **1, 2, 3, …** (component lines).
- **BaseLine 0** refers to the **finished good** line. If you use BaseLine 0 on an *Issue* document, SAP interprets it as issuing the **output** (FG) rather than a component. In many setups SAP then treats that as a **by-product** or invalid flow and can respond with errors like *“By-products are not allowed in this type of document”* or similar.

ApprovalPage uses **BaseLine 0 for the first component** (then 1, 2, …). That can work in some SAP configurations or versions, but it is inconsistent with SAP’s usual convention (line 0 = FG). To avoid by-product and “line 0 = FG” mismatches in WowPets, we **do not** replicate that: we only use **BaseLine ≥ 1** for Issue lines, and we map each WO component to the **actual SAP PO component line number** (LineNum from the expanded PO), so we never reference line 0 on Issue.

### Why we did replicate Issue AccountCode

ApprovalPage sends **AccountCode: "12500900"** on each **Issue for Production** DocumentLine. That value is a GL account code (e.g. inventory or WIP) that SAP uses for the consumption posting. We **replicated** this so that:

1. Our Issue payload matches the **working** Production Kiosk payload as closely as possible, which helps when both hit the same SAP company.
2. Some SAP setups expect or default better when the account is explicitly given; sending the same code reduces the chance of posting or validation differences.

So: **BaseLine 0** we did *not* replicate (to stay aligned with SAP’s line 0 = FG and avoid by-product errors). **AccountCode on Issue lines** we *did* replicate (for compatibility with the working Kiosk and correct GL posting).

---

## Constants

- **Warehouses:** `SAP_PO_COMPONENT_WAREHOUSE` (e.g. "WO - STR"), `SAP_PO_FINISHED_WAREHOUSE` (e.g. "WO -FG").
- **Issue AccountCode (optional, matches ApprovalPage):** `SAP_ISSUE_ACCOUNT_CODE` = "12500900".
- **BaseType 202** = Production Order in SAP B1.
- **DocEntry** = unique key for PO/Issue/Receipt; used for all follow-up API calls.
