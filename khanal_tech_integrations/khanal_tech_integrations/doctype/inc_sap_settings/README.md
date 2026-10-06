# INC SAP Settings

Single doctype used by **WowPets** for INC company SAP B1 Service Layer and SAP HANA.

## Setup

1. Open **INC SAP Settings** from the Frappe desk (search "INC SAP Settings" or go to the WowPets / Khanal Tech module).
2. **SAP Business One (Service Layer):**  
   Fill CompanyDB, User Name, Password, SAP B1 URL. Use **Initiate Session** to log in.
3. **SAP HANA Database (for batch lookup):**  
   Fill HANA Host, HANA Port (default 30015), HANA User, HANA Password, HANA Schema (e.g. `TEST_KF_INC_26022026`).
4. Save.

Batch numbers for Work Order components are read from HANA (OBTQ/OBTN) when these HANA fields are set; otherwise the app falls back to Service Layer APIs.

## When the SAP session expires

WowPets uses **INC SAP Settings** for SAP B1 Service Layer. If the session has expired (e.g. "SAP session expired" in errors, or 401 from SAP), you can initiate a new session in either of these ways:

1. **From Frappe Desk**
   - Go to **INC SAP Settings** (search in the Awesome Bar or open from the module).
   - Click the **Initiate Session** button on the form.
   - This logs in to SAP B1 Service Layer again and saves the new session (B1SESSION, ROUTEID, expires_on) on the document.

2. **From the command line**
   ```bash
   bench --site <your_site> execute khanal_tech_integrations.api.wowpets.sap_master.initiate_inc_sap_session
   ```
   Example: `bench --site dev.localhost execute khanal_tech_integrations.api.wowpets.sap_master.initiate_inc_sap_session`

After initiating, retry the WowPets action (e.g. post PO to SAP, create GRN, sync work order).
