
**Safe Express** is a logistics and supply chain company based in India, known for providing a variety of services including warehousing, transportation, and supply chain solutions. Founded in 1997, Safe Express has grown into one of the leading logistics companies in India, with a network that covers the entire country.

The company's services are geared towards helping businesses manage their supply chains efficiently and include:

1. **Express Distribution**: Fast, reliable transportation of goods across the country.
2. **Warehousing Solutions**: Storage facilities equipped with modern technology to manage inventory efficiently.
3. **3PL Services (Third Party Logistics)**: Outsourced logistics services, which include transportation, warehousing, and fulfillment.
4. **Supply Chain Consulting**: Offering businesses advice and solutions for optimizing their supply chain operations.
5. **Value-Added Services**: These include activities like packaging, labeling, and reverse logistics.

Safe Express serves a wide range of industries such as pharmaceuticals, FMCG (Fast Moving Consumer Goods), e-commerce, apparel, and more. They also place a strong emphasis on safety, ensuring that the goods are handled and transported securely.

<!---
#### 1. **AuthenticateSafexpress Function**
This function is designed to authenticate with the Safexpress API. It checks whether the current token has expired and renews it if necessary.


- **Process**:
  - Fetches the token's expiration date (`expires_on`) from the Safexpress Settings.
  - If no expiration date is found, it tries to renew the session by calling `renew_session()`.
  - If an expiration date is found, it checks whether the current time is past the expiration.
  - If expired, it calls `renew_session()` to refresh the token.
  - If the token is still valid, it returns the Safexpress settings document as-is.
  
#### 2. **renew_session Function**
This function is responsible for renewing the API session with Safexpress by sending a POST request to the authentication endpoint. If successful, it updates the token and the expiration time.

- **Process**:
  - Retrieves login details from the Safexpress Settings document (e.g., `login_url`, `username`, and `password`).
  - Prepares the payload and headers for the POST request, including the basic authorization and content type.
  - Sends the request to Safexpress' authentication API.
  - If successful, stores the new access token and updates the expiration time in the document.
  - In case of errors, it logs appropriate error messages for request timeouts, request failures, and JSON parsing issues.

### Explanation

#### `Get_Waybill_in_ArInvoice` Function

This function retrieves a list of "SAP AR Invoice Detail" documents based on certain filters and processes them to update their waybill information.

#### **Parameters**:
- `Day` (default value = 4): The function will fetch records where the last updated date is within the past `Day` number of days (default 4 days).

#### **Process**:

1. **Get Current Date**: The current date is fetched using `frappe.utils.nowdate()` and stored in the variable `Today`.
  
2. **Iterate and Process Each Record**:
   - The function then iterates over each document entry in the `List_of_INV` (list of `docentry`).
   - For each entry (`Single_Ar`), it calls the `Update_waybill_and_filePath` function, passing the `docentry` of that specific invoice to update its waybill and file path.

3. **Logging the Length of the List**:
   - It prints the length of the `List_of_INV` to the console, indicating how many documents met the filter conditions.

#### **Key Points**:
- The function operates on invoices that are updated within the last `Day` days and where the waybill and file path (POD URL) are missing.
- It ensures that the waybill information is updated by calling an external function `Update_waybill_and_filePath` for each document.



#### `Update_Tracking_by_WayBill` Function

This function is designed to update the delivery status and shipping details of delivery notes in the ERP system by tracking them via Safexpress API. It fetches delivery notes that are not marked as delivered and attempts to update their tracking information using the Safexpress tracking API.

#### **Process**:

1. **Retrieve Delivery Notes**:
   - The function fetches a list of delivery note documents (`SAP Delivery Notes`) from the database.
   - The filter conditions applied are:
     - `delivery_status` is empty (i.e., not yet assigned a delivery status).
     - `delivery_status` is not equal to "DELIVERED".
     - `transporter_name` is set to "Safexpress" (indicating the transporter).
   - It retrieves only the `docentry` field of the matching delivery notes (using `pluck="docentry"`).
   
2. **Loop Through Each Delivery Note**:
   - The function iterates over the list of delivery notes (`delivery_notes`).
   - For each entry (`Docentry`), it fetches the corresponding delivery note document from the database using `frappe.get_doc()`.

3. **Send Tracking Request to Safexpress API**:
   - The function sends a POST request to the Safexpress tracking API to get the tracking status of the shipment.

4. **Process the API Response**:
   - The function checks the API response for the shipment status.
   - If the response message is not `'Invalid Request'`:
     - It updates the `shipping_details` field of the delivery note with the result from the API.
     - If the API result indicates success (`result['shipment']['result'] == 'success'`):
       - The `delivery_status` of the delivery note is updated with the status provided in the API response.
     - If the result is not successful, the delivery status is set to `'Data Not Found'`.

   - The function saves the updated delivery note document back into the database using `doc.save()` and commits the changes with `frappe.db.commit()`.
   - The function logs the number of delivery notes processed, the document entry being updated, and whether it was successfully saved.

#### **Key Points**:
- The function works only for delivery notes with `Safexpress` as the transporter and updates delivery notes that are not marked as delivered.
- It interacts with the Safexpress tracking API to update delivery statuses and shipping details.
- If no valid tracking information is found, the status is set to `'Data Not Found'`.

### The  `Update_Tracking_by_INV` function

This function is designed to update the tracking information for shipments in an ERP system. It looks at delivery records that don't have tracking numbers and checks the Safexpress system for any available updates using associated invoice numbers.

#### Here's how it works step by step:

1. **Find Relevant Delivery Notes**:
   - First, the function gets today's date and goes back 20 days.
   - It then searches for delivery notes that:
     - Have no tracking number (`tracking_id` is empty).
     - Have no transporter name set.
     - Were updated within the last 20 days.
   - It collects these delivery notes, each identified by a unique ID (`docentry`).

2. **Look for Related Invoices**:
   - For each delivery note found, the function tries to find its related invoice. If no invoice is found, it moves on to the next delivery note.
   - If an invoice is found, it proceeds to check the Safexpress system for tracking information.

3. **Check Safexpress for Tracking Info**:
   - The function uses a list of prefixes (like `"KAIN24"`, `"AR2024"`, etc.) to create possible invoice numbers by combining the prefix with the actual invoice number.
   - It sends a request to the Safexpress API with this combined invoice number to check for tracking updates.

4. **Process Safexpress Response**:
   - If the API returns a valid response with a waybill number (a shipping/tracking number):
     - The function updates the delivery note with the transporter name ("Safexpress"), the waybill number (tracking ID), and other shipping details.
     - If the shipment has a status (e.g., "Delivered"), it also updates the delivery status in the system.
     - The updated information is saved, and the system database is updated.

#### **KeyPoints**:
- This function automatically updates delivery notes that don't have tracking info by using invoice numbers.
- It checks with Safexpress to find shipping details and waybill numbers and saves those details back to the system.
- If tracking info isn't found, it simply moves on to the next delivery note.


###  `Fetching_from_Sap` Function

The `Fetching_from_Sap` function retrieves invoices from a SAP system that haven't been tracked yet. It checks for any invoices updated within a certain number of days and processes them accordingly.

1. **Set Up Dates**:
   - The function starts by getting today’s date and calculating a date from `NoOfDays` ago. For example, if `NoOfDays` is 10, it calculates the date 10 days prior to today.

2. **Prepare to Get Invoice Count**:
     - Do not have a tracking number (`U_TrackingNo` is null).
     - Have a specific transportation code (code `1`).
   - The session for authenticating with SAP is established using the `AuthenticateSAPB1` function.

3. **Get the Count of Invoices**:
   - The function makes a GET request to the SAP API to retrieve the count of invoices that match the criteria.
   - It processes the response to extract the count of distinct invoices.

4. **Calculate Total Batches**:
   - If invoices are found, it calculates how many batches of invoices need to be fetched (20 invoices at a time).
   - The total number of batches is calculated by dividing the count by 20 and rounding up.

   
5. **Process Each Invoice**:
   - For each invoice in the response:
     - If the invoice already exists in the `SAP AR Invoice Detail` table (checked by `DocEntry`), it calls the `Update_waybill_and_filePath` function to update the invoice's waybill and file path.
     - If the invoice does not exist, it calls the `Saved_InvDoc` function to save the new invoice into the system.

### KeyPoints
- The `Fetching_from_Sap` function connects to the SAP system to find and retrieve invoices that were updated within a specified time frame and don't have tracking information.
- It processes these invoices in batches of 20, updating existing records or saving new ones as necessary.
- At the end, it confirms that the operation was successful.

################################################################
-->
<!-- # Control Flow and Data Flow Overview

## 1. Initial Setup and Authentication
- **AuthenticateSafexpress Function**: 
  - This function initiates the process by ensuring that the API session with Safe Express is authenticated. 
  - It checks the token's expiration and renews it if necessary, allowing the system to communicate securely with Safe Express's API.

## 2. Fetching Invoices from SAP
- **Fetching_from_Sap Function**:
  - This function is responsible for retrieving invoices from the SAP system. 
  - It calculates the date from which to start looking for invoices (based on `NoOfDays`).
  - The function makes a request to the SAP API to get the count of invoices that are untracked and that have been updated since the calculated date.
  - If there are invoices to process, it determines how many batches of invoices (20 at a time) need to be fetched and iterates through these batches.

## 3. Processing Each Invoice
- Within each batch retrieved from SAP:
  - The function checks if each invoice (identified by `DocEntry`) already exists in the `SAP AR Invoice Detail` table:
    - **If the invoice exists**:
      - The function calls `Update_waybill_and_filePath` to update the waybill and related file path for that invoice.
    - **If the invoice does not exist**:
      - The function calls `Saved_InvDoc` to save the new invoice details into the system.
  
## 4. Updating Delivery Notes with Tracking Information
- **Update_Tracking_by_INV Function**:
  - This function looks for delivery notes in the ERP system that do not have a tracking number and were updated within the last 20 days.
  - For each delivery note, it attempts to find any associated invoices.
  - If an invoice is found, it constructs possible tracking numbers using predefined prefixes and sends requests to Safe Express's API to fetch tracking information.

## 5. Interacting with the Safe Express API
- **Update_Tracking_by_WayBill Function**:
  - This function is specifically focused on delivery notes assigned to Safe Express. 
  - It retrieves delivery notes that are not yet marked as delivered and sends tracking requests to the Safe Express API.
  - Depending on the response from the API:
    - If tracking information is successfully retrieved, it updates the delivery note with the shipping details and delivery status.
    - If tracking information is not found, it sets the delivery status to "Data Not Found."

## 6. Updating Database and Finalization
- Each time information is updated in the ERP system (whether it's invoices or delivery notes):
  - The updated documents are saved back into the database using `doc.save()` and changes are committed to the database with `frappe.db.commit()`.
  - At the end of processing all invoices and delivery notes, success messages are displayed to confirm that the operations were completed successfully.

## Control Flow Summary
1. **Authenticate** with Safe Express to ensure valid sessions.
2. **Fetch Invoices** from the SAP system that need to be processed.
3. For each invoice:
   - Update if it exists, or save it if it doesn’t.
4. **Check Delivery Notes** for tracking information:
   - For each note, find related invoices and request tracking info from Safe Express.
   - Update delivery notes based on the tracking information retrieved.
5. **Save Changes** to the database and confirm successful updates to users.

## Data Flow Summary
- Data flows from the SAP system to the ERP (through fetching invoices) and from the Safe Express API back to the ERP (through tracking updates).
- The interactions between these components ensure that both invoices and delivery notes are properly tracked and updated, facilitating efficient logistics and supply chain management.


This overview provides a structured understanding of how data flows through various components of the system, how the functions interact with each other, and how they work together to maintain and update tracking information effectively.


#############################################################

-->

# Process Flow for Updating SAP AR Invoices with POD Information

## Step 1: Safexpress Authentication
- **Function**: Authentication is handled using the `auth.py` file located in the `safexpress` folder under `utils`.
- **Purpose**: Establishes a secure session with the Safexpress API for subsequent operations.

## Step 2: Fetching Invoices
- **Function**: `get_way_bill_in_ar_invoice`
- **Process**:
  - Retrieves invoices from the SAP system based on specified filters.
  - Filters applied:
    - **Days**: Only invoices updated within a specified number of days.
    - **Fields**: Ensures that both `pod_url` and `way_bill_number` fields are empty.
  - For each invoice fetched, it calls the `update_waybill_and_filePath` function to process them.

## Step 3: Updating Waybill and File Path
- **Function**: `update_waybill_and_filePath`
- **Process**:
  - Retrieves each AR invoice using the document entries fetched from the previous step.
  - **Check**: If the `pod_url` field is not empty, it logs the existing `pod_url` and exits the process.
  - **If Empty**: Prepares the API request using the format: `docseries/docnumber`.
  - **API Response**: Parses the JSON response to check for the presence of the waybill.
    - If the waybill is present:
      - Extracts the waybill number.
      - Updates the AR invoice with the waybill number.
      - Saves the document.
      - Calls `Get_single_pod(ar_invoice)` and `PATCH_POD_AR_invoice(single_ar_invoice)` functions for further processing.

## Step 4: Retrieving the Single POD
- **Function**: `Get_single_pod`
- **Process**:
  - Retrieves the AR invoice.
  - Authenticates with Safexpress using the `AuthenticateSafexpress()` function.
  - Constructs the API request URL by appending the waybill number.
  - **Check**: If the API response data is not null, it treats the data as `base64String`.
    - **Validation**: Checks if the `base64String` is valid.
      - If valid:
        - Decodes the `base64String` to binary data and assigns it to `tiff_data`.
        - Generates a unique filename using the series name, document number, and a timestamp.
        - Uploads the TIFF file to an Amazon S3 bucket using a pre-defined URL.
      - Updates the AR invoice with the new `pod_url` and sets the `pod_status` to 'Completed'.

## Step 5: Patching the AR Invoice
- **Function**: `PATCH_POD_AR_invoice`
- **Process**:
  - Retrieves the AR invoice document.
  - Authenticates with SAP B1 to establish a session.
  - Constructs the API endpoint for updating the invoice.
  - **Check**: Verifies if the `pod_url` field is not empty.
    - If it is not empty:
      - Constructs a JSON payload with the following fields:
        - `U_TN`: Set to "Safexpress".
        - `TransportationCode`: Set to `1`.
        - `U_TrackingNo`: Set to the waybill number.
        - `U_Pod_Link`: Set to the `pod_url` of the invoice.
      - Sends a PATCH request to the SAP API to update the invoice.
####yogesha###
