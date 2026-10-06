from . import __version__ as app_version
from khanal_tech_integrations.route import routes

app_name 		= "khanal_tech_integrations"
app_title 		= "Khanal Tech Integrations"
app_publisher 	= "Khanal Tech"
app_description = "Integrations of Khanal Tech for Khanal Foods"
app_email 		= "lian@khanalfoods.com"
app_license 	= "MIT"


# application home page (will override Website Settings)
home_page = "/home"

jinja = {
    "methods": [
        "khanal_tech_integrations.utils.context.get_session_custom_reports",
        "khanal_tech_integrations.utils.jinja_filters.num_to_inr_format"
    ]
}

doc_events = {

	"Material Request" :{
		"on_submit":"khanal_tech_integrations.utils.procure_to_pay.MaterialRequest.post_material_request",
		"on_cancel":"khanal_tech_integrations.utils.procure_to_pay.MaterialRequest.cancel_material_request",
	},
	"File": {
        "after_insert": "khanal_tech_integrations.khanal_tech_integrations.doctype.sap_ar_invoice_detail.sap_ar_invoice_detail.Set_to_Public"
    }
}

# Scheduled Tasks

scheduler_events = {
	"all": [
		"khanal_tech_integrations.tasks.all",
	],
		"daily": [
			"khanal_tech_integrations.tasks.daily",
			"khanal_tech_integrations.utils.safexpress2.pod_service.process_invoices_without_pod",
			"khanal_tech_integrations.utils.React_Api.Production_Kiosk.Error_Correction.consolidate_error_msg_list",
			"khanal_tech_integrations.api.plants.batchnumber_gen.batch_number_generator.generate_batches"
		],
	"hourly": [
		"khanal_tech_integrations.tasks.hourly",
	],
	"hourly_long": [
		"khanal_tech_integrations.utils.logistics.delivery_notes.update",
	],
	"weekly": [
		"khanal_tech_integrations.tasks.weekly"
	],
	"monthly": [
		"khanal_tech_integrations.tasks.monthly"
	],
    "cron": {
        "*/5 * * * *":[ #every /n min
			"khanal_tech_integrations.utils.purchase.purchaseorder.update_purchase_orders",
            "khanal_tech_integrations.utils.B2B.Blink.process_email_attachments",
            "khanal_tech_integrations.utils.B2B.Instamart.process_email_attachments",
            "khanal_tech_integrations.utils.B2B.Bigbasket.process_email_attachments",
            "khanal_tech_integrations.utils.B2B.Zepto.process_email_attachments",
            "khanal_tech_integrations.utils.B2B.More.process_email_attachments",
        ],
		"2,32 * * * *":[ # every 30 min (offset): fetch UC orders
			"khanal_tech_integrations.unicommerce.workers.fetch.fetch_orders",
		],
		"7,37 * * * *":[ # every 30 min (offset): post invoices
			"khanal_tech_integrations.unicommerce.workers.invoice.post_invoices",
		],
		"12,42 * * * *":[ # every 30 min (offset): fetch returns
			"khanal_tech_integrations.unicommerce.workers.fetch.fetch_returns",
		],

		"17,47 * * * *":[ # every 30 min (offset): post credit notes
			"khanal_tech_integrations.unicommerce.workers.credit_note.post_credit_notes",
		],
		"24,54 * * * *":[ # every 30 min (offset): sync GRNs
			"khanal_tech_integrations.unicommerce.workers.grn.sync_grns",
		],
		"27,57 * * * *":[ # every 30 min (offset): sync inventory
			"khanal_tech_integrations.unicommerce.workers.inventory.sync_inventory",
		],
		"29,59 * * * *":[ # every 30 min (offset): refresh reconciliation metrics
			"khanal_tech_integrations.unicommerce.validators.reconcile.run_reconciliation_refresh",
		],
		"22,52 * * * *":[ # every 30 min (offset): Amazon US incremental order sync
			"khanal_tech_integrations.amazon_us.workers.fetch.sync_incremental",
		],
		"0 6 * * *":[ # daily 06:00 UTC: Amazon US FBA shipment dates sync
			"khanal_tech_integrations.amazon_us.workers.fba_shipments.sync_fba_shipments_daily",
		],
		"0 7 * * *":[ # daily 07:00 UTC: Amazon US settlement report sync
			"khanal_tech_integrations.amazon_us.workers.settlement.sync_settlement_daily",
		],
		"0 8 * * *":[ # daily 08:00 UTC: Amazon US health check (after both jobs above)
			"khanal_tech_integrations.amazon_us.workers.health_check.run_daily_health_check",
		],

		 "10 */3 * * *":[ # “At minute 10 past every 3 hours.”
            "khanal_tech_integrations.utils.sap.bulk_process_inventory_transfers",
        ],
		"15 */1 * * *":[ #At 15 min past everyhour # At minute 0 past every 12th hour.
			"khanal_tech_integrations.utils.logistics.sales_order.update",
        ],
		"30 */3 * * *":[ # Every 3 hours
			"khanal_tech_integrations.utils.safexpress.tracking.Update_Tracking_by_WayBill",
        ],
		"0 */4 * * *":[ # Every 4 hours — process DSR POD emails
			"khanal_tech_integrations.utils.DSR_Logisticss.DSR_POD_INTEGRATION.process_dsr_emails",
        ],
		"30 */6 * * *":[ # Every 6 hours — recover DSR Pending_SAP records
			"khanal_tech_integrations.utils.DSR_Logisticss.DSR_POD_INTEGRATION.retry_pending_sap_invoices",
        ],
		"20 */4 * * *":[ # Every 4 hours
			"khanal_tech_integrations.utils.logistics.ar_invoice.update",
			"khanal_tech_integrations.utils.sap.Update_inventory_level",
			"khanal_tech_integrations.unicommerce.api.ops.refresh_inventory_parity",
			"khanal_tech_integrations.utils.logistics.delivery_notes.updating_existingvalues"
        ],
		"45 */3 * * *":[ # At minute 10 past every 12th hour
			"khanal_tech_integrations.utils.purchase.purchaseorder.fetch_purchase_orders",
			"khanal_tech_integrations.utils.React_Api.Production_Kiosk.ApprovalPage.Receipt_productionList_InHooks",
            "khanal_tech_integrations.utils.React_Api.Production_Kiosk.productiongoods.Receipt_productionList_InHooks", # harsha added production kiosk higher level issue handler
			"khanal_tech_integrations.utils.React_Api.Grn_creation.ViewGrn.Fetch_GrnWithProductionKey"
        ],
		"50 */2 * * *":[ # At minute 50 past every 2th hour
			"khanal_tech_integrations.utils.React_Api.Production_Kiosk.ApprovalPage.Issue_productionList_InHooks",
            "khanal_tech_integrations.utils.React_Api.Production_Kiosk.productiongoods.Issue_productionList_InHooks" # harsha added production kiosk higher level issue handler
        ],
		"35 */1 * * *":[ # At minute 35 past every hour
			"khanal_tech_integrations.utils.React_Api.Ledger.ApprovalPage.SentMail_ForApproved",
        ],
		"0 */18 * * *":[ # At minute 0 past every 18th hour
			"khanal_tech_integrations.utils.safexpress.tracking.Update_Tracking_by_INV",
        ],
		"35 06 * * *":[ #At 06:35
			"khanal_tech_integrations.utils.purchase.inventory.Update_daily_inventory_level",
        ],
		"40 03 * * *":[ #At 03:40 AM
			"khanal_tech_integrations.utils.safexpress.automated_invoice_attach.Fetching_from_Sap",
        ],
		"40 */2 * * *":[ #At minute 40 past every 2nd hour
			"khanal_tech_integrations.utils.cashfree.vrf.bank_verification.SELECT_LIST_OF_BP_MASTER_VENDORS_FOR_VERIFICATION",
			"khanal_tech_integrations.utils.cashfree.vrf.gst_verification.Gst_Verification_API"
		],
		"20 04 * * *":[ #At 04:20
			"khanal_tech_integrations.utils.React_Api.Ledger.JournalEntries.Daily_Update_JournalEntries",
        ],
		"0 0 * * 1": [  # This cron expression means "at 00:00 on Monday"
			"khanal_tech_integrations.utils.schedulejob.UpadteJournalentries",
        ],
		"0 9 1 * *": [  # 1st of every month at 09:00 — monthly POD pending report + overdue list
			"khanal_tech_integrations.utils.repatch_pod.monthly_pod_pending_report",
		],
    },
}

after_migrate = [
	"khanal_tech_integrations.api.wowpets.sap_master._ensure_inc_sap_settings_hana_fields",
	"khanal_tech_integrations.api.real_aquatics.sap_master._ensure_real_aquatics_sap_settings_hana_fields",
	"khanal_tech_integrations.consumables.install.ensure_consumables_inventory_manager_role",
]

website_redirects = [
    {"source": "/app/intranet", "target": "/intranet"},
]

website_route_rules = routes

#! bench export-fixtures
fixtures = [
	
    {"doctype": "Custom Field", "filters": [["module", "=", "Khanal Tech Integrations"]]},
    {"doctype": "Client Script", "filters": [["module", "=", "Khanal Tech Integrations"]]},
    {"doctype": "Workflow",},
	{"doctype": "Workflow State",},
    {"doctype": "Workflow Action",},
    {"doctype": "Role", "filters": [["name", "in", [
        "WowPets KhanalFoods User",
        "WowPets KhanalFoods Manager",
        "WowPets Warehouse User",
        "WowPets Warehouse Manager",
        "RealAquatics KhanalFoods User",
        "RealAquatics KhanalFoods Manager",
        "RealAquatics Warehouse User",
        "RealAquatics Warehouse Manager",
        "RealAquatics Procurement User",
        "RealAquatics Procurement Manager",
        "Consumables Store User",
        "Consumables Store Manager",
        "Consumables Inventory Manager",
        "Consumables Super Admin",
        "Consumables Procurement User",
        "WowPets Procurement User",
        "WowPets Procurement Manager",
    ]]]},
    ]
