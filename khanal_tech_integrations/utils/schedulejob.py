
import frappe
from frappe.utils import add_to_date


#! bench --site khanaltech.com execute   khanal_tech_integrations.utils.schedulejob.EcomReport_Monthly

#! bench --site dev.localhost execute   khanal_tech_integrations.utils.schedulejob.UpadteJournalentries

#! bench --site dev.localhost execute   khanal_tech_integrations.utils.schedulejob.AgeingReport_Ap_Ar


def EcomReport_Weekly():
    Today = frappe.utils.nowdate()
    YesterDay = add_to_date(Today,days=-1)
    FilterDate = add_to_date(Today,days=-8)
    frappe.enqueue(
			"khanal_tech_integrations.utils.Report.Ecom.reports.ReportGeneration",
            job_name="Ecom.ReportGeneration",
			queue="long",
            StartDate=FilterDate,
            EndDate=YesterDay,
            Type='Weekly',
            timeout=4000,
		)
    return 'Completed'

def ExportReport_Weekly():
    Today = frappe.utils.nowdate()
    YesterDay = add_to_date(Today,days=-1)
    FilterDate = add_to_date(Today,days=-8)
    frappe.enqueue(
			"khanal_tech_integrations.utils.Report.Export.reports.ReportGeneration",
            job_name="Export.ReportGeneration",
			queue="long",
            Type='Weekly',
            StartDate=FilterDate,
            EndDate=YesterDay,
            timeout=4000,
		)
    return 'Completed'

def EcomReport_Monthly():
    frappe.enqueue(
			"khanal_tech_integrations.utils.Report.Ecom.reports.Report_Generation_ForMonthly",
            job_name="Ecom.MonthlyReport",
			queue="long",
            timeout=4000,
		)
    return 'Completed'

def ExportReport_Monthly():
    frappe.enqueue(
			"khanal_tech_integrations.utils.Report.Export.reports.Report_Generation_ForMonthly",
            job_name="Export.MonthlyReport",
			queue="long",
            timeout=4000,
		)
    return 'Completed'


def UnicommerceFill_Order():
    frappe.enqueue(
			"khanal_tech_integrations.unicommerce.workers.fetch.fetch_orders",
            job_name="unicommerce.fill_15days_orders",
			queue="long",
            timeout=4000,
		)
    return 'Completed'


def UpadteJournalentries():
    Today = frappe.utils.nowdate()
    frappe.enqueue(
			"khanal_tech_integrations.utils.React_Api.Ledger.JournalEntries.get_sap_journalentries",
            job_name="JournalEntries.get_sap_journalentries",
			queue="long",
            StartDate='2023-04-01',
            EndDate=Today,
            timeout=4000,
		)
    return 'Completed'


def AgeingReport_Ap_Ar():
    Today = frappe.utils.nowdate()
    # Today = '2024-07-29'
    YesterDay = add_to_date(Today,days=-1)
    FilterDate = add_to_date(Today,days=-8)
    # print(YesterDay,FilterDate)
    frappe.enqueue(
			"khanal_tech_integrations.utils.Finance.AgeingReport.Get_MasterData",
            job_name="AgeingReport.Get_MasterData",
			queue="long",
            CurrentDate=YesterDay,
            PreviousDate=FilterDate,
            timeout=4000,
		)
    return 'Completed'