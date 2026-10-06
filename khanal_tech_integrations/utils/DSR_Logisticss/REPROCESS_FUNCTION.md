# DSR POD Reprocess Function - Simple Guide

## 📋 Function Overview

The `reprocess_dsr_emails_with_sap_check()` function is a simple, clean function that:

1. ✅ Processes **ALL emails** (not just unread)
2. ✅ Checks **SAP B1** to see if POD fields (`pod_url`, `pod_date`) are already filled
3. ✅ **Only uploads and updates** if POD fields are empty
4. ✅ **Skips** invoices that already have POD data
5. ✅ Uses **clear print statements** for easy monitoring

---

## 🚀 How to Use

### Command Line Execution

```bash
bench --site <your_site_name> execute khanal_tech_integrations.utils.DSR_Logistics.Dsr_Pod.reprocess_dsr_emails_with_sap_check
```

### Example

```bash
bench --site khanaltech.com execute khanal_tech_integrations.utils.DSR_Logistics.Dsr_Pod.reprocess_dsr_emails_with_sap_check
```

---

## 📊 What It Does

### Step-by-Step Process

1. **Connects to Email**
   - Reads DSR Settings for email credentials
   - Connects to Gmail IMAP

2. **Fetches ALL Emails**
   - Searches for ALL emails in inbox (not just unread)
   - Processes each email sequentially

3. **Parses Attachments**
   - Extracts POD attachments from emails
   - Validates filename format: `{waybill}_{series}_{invoice}_{date}.ext`

4. **Checks SAP B1 Status**
   - For each invoice, checks if `pod_url` and `pod_date` are already filled
   - Checks if `pod_status` is "Completed"

5. **Decision Logic**
   ```
   IF (pod_url exists AND pod_date exists AND pod_status == "Completed"):
       → SKIP (already processed)
   ELSE:
       → UPLOAD POD and UPDATE invoice
   ```

6. **Uploads to S3** (if needed)
   - Uploads POD file to S3
   - Gets S3 URL

7. **Updates Database** (if needed)
   - Updates SAP AR Invoice Detail with:
     - way_bill_number
     - pod_url
     - pod_date
     - pod_status = "Completed"
     - shipping_status = "Completed"
     - transporter_type = "DSR Logistics"

8. **Updates SAP B1** (if needed)
   - PATCH request to SAP B1 with POD information

---

## 📝 Output Example

```
================================================================================
DSR POD REPROCESSING - Checking SAP B1 before updating
================================================================================
✓ Connected to email: dsr@example.com
✓ S3 bucket configured: my-bucket-name
✓ Successfully logged into email

📧 Found 10 total email(s) to process
--------------------------------------------------------------------------------

[1/10] Processing Email ID: 12345
  ✓ Found 1 valid attachment(s)

  📄 Attachment: 123456_ABC_789012_15012025.pdf
     Invoice: 789012, Waybill: 123456
     ✓ POD fields are empty/incomplete - Proceeding with upload
     📤 Uploading to S3...
     ✓ Uploaded successfully: https://bucket.s3.amazonaws.com/...
     💾 Updating SAP AR Invoice Detail...
     ✓ Database updated successfully
     🔄 Updating SAP B1...
     ✓ SAP B1 updated successfully
     ✅ COMPLETED: Invoice 789012 processed successfully

[2/10] Processing Email ID: 12346
  ✓ Found 1 valid attachment(s)

  📄 Attachment: 123457_XYZ_789013_16012025.pdf
     Invoice: 789013, Waybill: 123457
     ⏭️  SKIPPED: Invoice already has POD
        POD URL: https://bucket.s3.amazonaws.com/...
        POD Date: 2025-01-16
        POD Status: Completed

[3/10] Processing Email ID: 12347
  ⚠️  No valid POD attachments found

================================================================================
PROCESSING COMPLETE - Final Statistics
================================================================================
Total Emails Processed: 10
✅ Successfully Updated: 5
⏭️  Skipped (Already Filled): 3
⚠️  Skipped (No Attachments): 1
❌ Errors: 1
================================================================================

✓ Email connection closed
```

---

## 🔍 Key Features

### ✅ Smart Skipping
- Automatically skips invoices that already have POD data
- Prevents duplicate processing
- Saves time and resources

### ✅ Clear Visibility
- Print statements show exactly what's happening
- Easy to monitor progress
- Clear error messages

### ✅ Safe Processing
- Only updates if POD is missing
- Won't overwrite existing POD data
- Continues processing even if one email fails

### ✅ Complete Updates
- Updates both Frappe database AND SAP B1
- Ensures data consistency
- Handles errors gracefully

---

## ⚙️ Configuration Required

Make sure these are configured in Frappe:

1. **DSR Settings** doctype:
   - `email` - Email address
   - `password` or `app_password` - Email password/app password

2. **AWS Settings** doctype:
   - `access_key_id` - AWS access key
   - `secret_access_key` - AWS secret key
   - `region` - AWS region
   - `bucket_name_dsr` - S3 bucket name
   - `folder_prefix` (optional) - S3 folder prefix

---

## 🆚 Comparison with Main Function

| Feature | `process_dsr_emails()` | `reprocess_dsr_emails_with_sap_check()` |
|---------|----------------------|------------------------------------------|
| **Emails Processed** | Only UNREAD | ALL emails |
| **SAP Check** | Basic check | Detailed check before processing |
| **Logging** | Structured logging | Print statements |
| **Use Case** | Daily automated processing | Manual reprocessing/recovery |
| **Complexity** | Production-ready with retries | Simple and straightforward |

---

## 💡 When to Use

### Use `reprocess_dsr_emails_with_sap_check()` when:
- ✅ You want to reprocess old emails
- ✅ You need to see clear print output
- ✅ You want to ensure no duplicate processing
- ✅ You're doing manual recovery/backfill
- ✅ You want simple, easy-to-understand output

### Use `process_dsr_emails()` when:
- ✅ Daily automated processing (scheduled job)
- ✅ You need production-grade error handling
- ✅ You want structured logging
- ✅ You need retry logic and metrics

---

## 🐛 Troubleshooting

### "ERROR: DSR email credentials not configured"
- Check DSR Settings doctype
- Ensure email and password/app_password are set

### "ERROR: Failed to load S3 Settings"
- Check AWS Settings doctype
- Ensure all required fields are filled

### "ERROR: Email login failed"
- Check email credentials
- For Gmail, use App Password instead of regular password
- Enable "Less secure app access" or use App Password

### "Invoice not found in SAP AR Invoice Detail"
- Invoice number from email doesn't match any record
- Check if invoice exists in Frappe
- Verify invoice number format in email attachment filename

---

## 📞 Support

For issues or questions, check:
1. Frappe error logs: `bench --site <site> console` → Check Error Log
2. Email connection: Verify IMAP settings
3. S3 access: Verify AWS credentials and bucket permissions

---

## 🔄 Next Steps

After running this function, you can:
1. Check the statistics output
2. Review any errors in the output
3. Manually check invoices that were skipped
4. Run again if needed (it's safe to run multiple times)

