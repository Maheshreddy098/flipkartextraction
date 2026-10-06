# Real Aquatics 3PL Portal — Production Deployment Guide

**Branch:** `RealAquatics_Yogesha_10062026`
**Partner:** Real Aquatics (UK)
**Companion doc:** `docs/realaquatics_blueprint.md` (build spec, Phases 1–7)

---

## 1. Current State (code)

All application code is complete and verified against WowPets parity:

- 16 DocTypes (order, PO, work order, dispatch, inventory, return, ticket, SAP log, SAP settings + child tables)
- 13 backend API modules (`khanal_tech_integrations/api/real_aquatics/`)
- Frontend SPA (`realaquatics-frontend/`) — 1:1 page parity with WowPets (khanalfoods + warehouse teams; no procurement team, no ShipHero — both intentionally out of scope for this partner)
- Routes (`/realaquatics/*`), roles, `after_migrate` hook — all registered in `hooks.py` / `route.py`
- SAP B1 Service Layer + HANA connectivity code — tested and working end-to-end against a UK sandbox (`TEST_UK` companyDB)

**Nothing left to build.** Everything below is production *configuration*, not code.

---

## 2. Mandatory Fields to Fill in Production

None of these can be set in advance — they only exist in the production Frappe site's database, not in git. Fill them via Frappe Desk (`/app/real-aquatics-sap-settings`) or `bench console` after the branch is deployed.

### 2.1 `Real Aquatics SAP Settings` (Single DocType)

| Field | Required | Notes |
|---|---|---|
| `companydb` | **Yes** | Production UK SAP B1 CompanyDB name (sandbox used `TEST_UK` — production value will differ) |
| `username` | **Yes** | SAP B1 Service Layer login for production |
| `password` | **Yes** | SAP B1 Service Layer password — enter via Desk, never commit to git |
| `sap_b1_url` | **Yes** | Confirm whether production UK SAP B1 is on the same server as WowPets (`https://103.69.202.108:50000/b1s/v1/`) or a different one |
| `routeid` | Only if load-balanced | Same caveat as above — confirm with SAP hosting team |
| `hana_host` | **Yes** (for batch/inventory lookups) | Production HANA host — confirm same server or different |
| `hana_port` | **Yes** | Default `30015` unless told otherwise |
| `hana_user` | **Yes** | Production HANA read user |
| `hana_password` | **Yes** | Production HANA password |
| `hana_schema` | **Yes** | Must match the production CompanyDB's HANA schema name (not necessarily the same string as `companydb`) |

### 2.2 Code constants — `khanal_tech_integrations/api/real_aquatics/__init__.py`

| Constant | Current value | Status |
|---|---|---|
| `SAP_COMPONENT_WAREHOUSE` | `"RP-STR"` (Real Pets-Stores) | ✅ Set — **confirm this warehouse code exists in the production CompanyDB**, not just the sandbox, before go-live |
| `SAP_FINISHED_WAREHOUSE` | `"RP-FG"` (Real Pets-FG) | ✅ Set — same caveat as above |
| `SAP_ISSUE_ACCOUNT_CODE` | `"TBD"` | ❌ **Blocking** — GL account code for Work Order issue lines. Get from UK finance before any production Work Order is posted |

### 2.3 `AWS` (Single DocType) — S3 attachments

| Field | Required | Notes |
|---|---|---|
| `wowpets_access_key_id` | Already set (shared with WowPets) | No action needed unless rotating keys |
| `wowpets_secret_access_key` | **Yes — currently missing on dev.localhost, verify on production** | Shared IAM credential; without it, no attachment uploads work for WowPets *or* Real Aquatics |
| `wowpets_region` | Already set (`us-west-1`) | No action needed |
| `real_aquatics_khanalfoods_bucket` | **Yes** | Default `realaquatics-khanalfoods` if left blank — **bucket must be created in AWS console first**, this field doesn't create it |
| `real_aquatics_tickets_bucket` | **Yes** | Default `realaquatics-tickets` — same caveat, create bucket first |

### 2.4 AWS console (outside Frappe)

- [ ] Create S3 bucket `realaquatics-khanalfoods` (private, no public access)
- [ ] Create S3 bucket `realaquatics-tickets` (private, no public access)
- [ ] Grant the existing WowPets IAM user `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` on both new buckets
- [ ] Confirm presigned-URL access works end-to-end (upload + download) before go-live

### 2.5 Roles (Frappe Desk → User)

Assign the relevant role to each production UK user:

- `RealAquatics KhanalFoods User` / `RealAquatics KhanalFoods Manager`
- `RealAquatics Warehouse User` / `RealAquatics Warehouse Manager`

(No procurement role exists for this partner — by design.)

---

## 3. Deployment Steps

1. Merge `RealAquatics_Yogesha_10062026` into `main` (or deploy the branch directly, per your release process).
2. On the production bench: `bench --site <production-site> migrate`
   - Watch for "Orphaned DocType(s) found" — if the production app checkout doesn't yet include some *other* unmerged branch's doctypes, migrate will drop those doctypes' metadata (not their data — Single doctype values survive in `tabSingles`). Check what's orphaned before confirming, same as we hit on dev.localhost with `Unicommerce Ops Settings`.
3. Build the frontend on the production box:
   ```
   cd realaquatics-frontend
   npm install
   npm run build
   ```
   This writes `public/realaquatics/` and regenerates `www/realaquatics.html`.
4. `bench --site <production-site> clear-website-cache`
5. Fill in all fields from Section 2 above via Desk.
6. Assign roles to production users (Section 2.5).
7. Test SAP B1 connectivity: log in as a KhanalFoods Manager, use "Initiate Session" on `Real Aquatics SAP Settings`, confirm success.
8. End-to-end test: create a Purchase Order → accept → sync to SAP → confirm it lands correctly in the production CompanyDB.
9. Test one file upload (PO attachment or ticket attachment) to confirm S3 is wired correctly.

---

## 4. Known Risk to Check Before Go-Live

Error Log entries from 2026-06-23 (sandbox testing) show:
```
Real Aquatics SAP sync failed: SAP Purchase Order creation failed: The logged-on user does not have permission to use this object.
```
This was a SAP B1 object-level authorization issue for the sandbox test user. **Before production go-live, confirm the production SAP B1 service-layer user has the correct object permissions for Purchase Orders, Inventory Transfers, and Issues for Production** — this is a SAP-side authorization group setting, not something fixable from the Frappe side.

---

## 5. What Is Never Touched

- `api/wowpets/` — zero changes
- `INC SAP Settings` doctype — zero changes
- All `wowpets_*` DocTypes and `wowpets-frontend/` — zero changes
- WowPets roles — zero changes (only additions for Real Aquatics)
