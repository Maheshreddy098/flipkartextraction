# SAP B1 Production Order – Postman reference

Use your **INC SAP Settings** values: `sap_b1_url`, `companydb`, `username`, `password`.

---

## 1. Login (get session cookie)

**Method:** `POST`  
**URL:** `{{sap_b1_url}}Login`  
Example: `https://103.69.202.108:50000/b1s/Login`

**Headers:**
```
Content-Type: application/json
Accept: */*
```

**Body (raw JSON):**
```json
{
  "CompanyDB": "TEST_KF_INC_26022026",
  "UserName": "FIN_INC",
  "Password": "YOUR_PASSWORD"
}
```

**Note:** Do not send SSL verification in Postman (or turn off “SSL certificate verification” in Settings).  
After this request, Postman will store the cookies `B1SESSION` and `ROUTEID`; use “Send with cookies” for the next requests (or add Cookie header manually).

---

## 2. Create Production Order

**Method:** `POST`  
**URL:** `{{sap_b1_url}}ProductionOrders`  
Example: `https://103.69.202.108:50000/b1s/ProductionOrders`

**Headers:**
```
Content-Type: application/json
Accept: */*
```
(Plus session cookie from step 1.)

**Body (raw JSON) – exact payload shape the app sends (ProductionOrder uses ItemNo, not ItemCode):**
```json
{
  "ItemNo": "FGDC1018",
  "PlannedQuantity": 1,
  "ProductionOrderType": "bopotStandard",
  "PostingDate": "2026-03-04",
  "DueDate": "2026-03-04",
  "Warehouse": "WO -FG",
  "Remarks": "WowPets WO WP-WO-2026-00009",
  "ProductionOrderLines": [
    {
      "ItemNo": "PMDC1126",
      "PlannedQuantity": -1,
      "Warehouse": "WO - STR",
      "LocationCode": 2,
      "ProductionOrderIssueType": "im_Manual"
    },
    {
      "ItemNo": "FGDC0629",
      "PlannedQuantity": -1,
      "Warehouse": "WO - STR",
      "LocationCode": 2,
      "ProductionOrderIssueType": "im_Manual"
    },
    {
      "ItemNo": "COCM0154",
      "PlannedQuantity": -1,
      "Warehouse": "WO - STR",
      "LocationCode": 2,
      "ProductionOrderIssueType": "im_Manual"
    }
  ]
}
```

**Replace:**
- `ItemNo` (header): your **finished item** code (ProductionOrder uses ItemNo).
- `PlannedQuantity`: qty to produce (positive).
- `PostingDate` / `DueDate`: `YYYY-MM-DD`.
- `Remarks`: any text (e.g. WO name).
- `ProductionOrderLines`: one line per **component**; `ItemNo` = component item, `PlannedQuantity` = **negative** required qty.
- **Warehouse** (header): `WO -FG` (finished goods receipt; no space before FG). **ProductionOrderLines[].Warehouse**: `WO - STR` (component consumption). Constants in `work_order.py`: `SAP_PO_FINISHED_WAREHOUSE`, `SAP_PO_COMPONENT_WAREHOUSE`.

**Success:** 200/201; response body contains `DocEntry` (and often `AbsoluteEntry`, `DocumentNumber`). Use `DocEntry` for step 3.

---

## 3. Release Production Order

**Method:** `PATCH`  
**URL:** `{{sap_b1_url}}ProductionOrders(DocEntry)`  
Example: `https://103.69.202.108:50000/b1s/ProductionOrders(123)`  
Replace `123` with the `DocEntry` from step 2.

**Headers:**
```
Content-Type: application/json
Accept: */*
```

**Body (raw JSON):**
```json
{
  "ProductionOrderStatus": "boposReleased"
}
```

**Success:** 200 or 204.

---

## Summary

| Step | Method | URL | Purpose |
|------|--------|-----|--------|
| 1 | POST | `{base}/Login` | Get B1SESSION cookie |
| 2 | POST | `{base}/ProductionOrders` | Create order (payload above) |
| 3 | PATCH | `{base}/ProductionOrders({DocEntry})` | Release order |

**Constants in code:** `SAP_PO_FINISHED_WAREHOUSE = "WO -FG"`, `SAP_PO_COMPONENT_WAREHOUSE = "WO - STR"` in `work_order.py`.
