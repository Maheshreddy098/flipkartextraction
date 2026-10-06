"""
Bench Commands for HANA Reporting System
Direct executable functions for bench commands
"""

import frappe
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Optional

# Import all necessary modules
from .hana_query_engine_readonly import generate_comprehensive_sales_report_readonly, HANAReadOnlyQueryEngine
from .excel_report_generator import create_comprehensive_sales_report, ExcelReportGenerator
from .pivot_table_creator import create_comprehensive_pivot_analysis, create_financial_pivot_analysis, create_operational_pivot_analysis
from .data_comparison_engine import compare_sales_data, generate_reconciliation_report
from .report_scheduler import generate_weekly_report, generate_monthly_report, start_daily_reports
from .configuration import HANA_CONFIG, REPORT_SETTINGS

@frappe.whitelist()
def generate_daily_sales_report():
    """
    Generate daily sales report for today
    """
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        frappe.log_error(f"Generating daily sales report for {today}")
        
        # Generate report
        data = generate_comprehensive_sales_report_readonly(today, today)
        
        # Create Excel report
        filename = f"daily_sales_report_{today.replace('-', '')}.xlsx"
        report_path = create_comprehensive_sales_report(data, filename)
        
        frappe.log_error(f"Daily sales report generated: {report_path}")
        return {
            "status": "success",
            "message": f"Daily sales report generated for {today}",
            "file_path": report_path,
            "record_count": len(data)
        }
        
    except Exception as e:
        frappe.log_error(f"Failed to generate daily sales report: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def generate_weekly_sales_report():
    """
    Generate weekly sales report for last 7 days
    """
    try:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        frappe.log_error(f"Generating weekly sales report from {start_date} to {end_date}")
        
        # Generate report
        data = generate_comprehensive_sales_report_readonly(start_date, end_date)
        
        # Create Excel report
        filename = f"weekly_sales_report_{start_date.replace('-', '')}_to_{end_date.replace('-', '')}.xlsx"
        report_path = create_comprehensive_sales_report(data, filename)
        
        frappe.log_error(f"Weekly sales report generated: {report_path}")
        return {
            "status": "success",
            "message": f"Weekly sales report generated from {start_date} to {end_date}",
            "file_path": report_path,
            "record_count": len(data)
        }
        
    except Exception as e:
        frappe.log_error(f"Failed to generate weekly sales report: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def generate_monthly_sales_report():
    """
    Generate monthly sales report for current month
    """
    try:
        today = datetime.now()
        start_date = today.replace(day=1).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
        
        frappe.log_error(f"Generating monthly sales report from {start_date} to {end_date}")
        
        # Generate report
        data = generate_comprehensive_sales_report_readonly(start_date, end_date)
        
        # Create Excel report
        filename = f"monthly_sales_report_{start_date.replace('-', '')}_to_{end_date.replace('-', '')}.xlsx"
        report_path = create_comprehensive_sales_report(data, filename)
        
        frappe.log_error(f"Monthly sales report generated: {report_path}")
        return {
            "status": "success",
            "message": f"Monthly sales report generated from {start_date} to {end_date}",
            "file_path": report_path,
            "record_count": len(data)
        }
        
    except Exception as e:
        frappe.log_error(f"Failed to generate monthly sales report: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def generate_custom_sales_report(start_date: str, end_date: str):
    """
    Generate custom sales report for specified date range
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
    """
    try:
        frappe.log_error(f"Generating custom sales report from {start_date} to {end_date}")
        
        # Generate report
        data = generate_comprehensive_sales_report_readonly(start_date, end_date)
        
        # Create Excel report
        filename = f"custom_sales_report_{start_date.replace('-', '')}_to_{end_date.replace('-', '')}.xlsx"
        report_path = create_comprehensive_sales_report(data, filename)
        
        frappe.log_error(f"Custom sales report generated: {report_path}")
        return {
            "status": "success",
            "message": f"Custom sales report generated from {start_date} to {end_date}",
            "file_path": report_path,
            "record_count": len(data)
        }
        
    except Exception as e:
        frappe.log_error(f"Failed to generate custom sales report: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def generate_pivot_analysis(start_date: str, end_date: str):
    """
    Generate pivot table analysis for specified date range
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
    """
    try:
        frappe.log_error(f"Generating pivot analysis from {start_date} to {end_date}")
        
        # Get sales data
        data = generate_comprehensive_sales_report_readonly(start_date, end_date)
        
        # Create pivot analysis
        pivot_tables = create_comprehensive_pivot_analysis(data)
        
        frappe.log_error(f"Pivot analysis generated with {len(pivot_tables)} tables")
        return {
            "status": "success",
            "message": f"Pivot analysis generated from {start_date} to {end_date}",
            "pivot_tables": list(pivot_tables.keys()),
            "record_count": len(data)
        }
        
    except Exception as e:
        frappe.log_error(f"Failed to generate pivot analysis: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def generate_data_reconciliation(start_date: str, end_date: str):
    """
    Generate data reconciliation report comparing HANA vs Unicommerce
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
    """
    try:
        frappe.log_error(f"Generating data reconciliation from {start_date} to {end_date}")
        
        # Generate reconciliation report
        report_path = generate_reconciliation_report(start_date, end_date)
        
        frappe.log_error(f"Data reconciliation report generated: {report_path}")
        return {
            "status": "success",
            "message": f"Data reconciliation report generated from {start_date} to {end_date}",
            "file_path": report_path
        }
        
    except Exception as e:
        frappe.log_error(f"Failed to generate data reconciliation: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def test_hana_connection():
    """
    Test HANA database connection
    """
    try:
        frappe.log_error("Testing HANA database connection...")
        
        # Initialize query engine
        engine = HANAReadOnlyQueryEngine()
        
        # Test connection
        connection_status = engine.test_connection()
        
        if connection_status:
            frappe.log_error("HANA database connection successful")
            return {
                "status": "success",
                "message": "HANA database connection successful",
                "host": HANA_CONFIG["host"],
                "port": HANA_CONFIG["port"],
                "schema": HANA_CONFIG["schema"]
            }
        else:
            frappe.log_error("HANA database connection failed")
            return {
                "status": "error",
                "message": "HANA database connection failed"
            }
            
    except Exception as e:
        frappe.log_error(f"HANA connection test failed: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def get_report_status():
    """
    Get current report generation status and configuration
    """
    try:
        return {
            "status": "success",
            "hana_config": {
                "host": HANA_CONFIG["host"],
                "port": HANA_CONFIG["port"],
                "schema": HANA_CONFIG["schema"]
            },
            "report_settings": {
                "output_directory": REPORT_SETTINGS["output_directory"],
                "email_recipients": REPORT_SETTINGS["email_recipients"],
                "default_format": REPORT_SETTINGS["default_format"]
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Failed to get report status: {str(e)}")
        return {"status": "error", "message": str(e)}
