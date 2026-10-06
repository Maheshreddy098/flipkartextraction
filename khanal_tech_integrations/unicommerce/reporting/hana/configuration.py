"""
Configuration settings for HANA DB Reporting System
"""

import os
from datetime import datetime
import frappe

# HANA Database Configuration
HANA_CONFIG = {
    "host": "103.69.202.108",
    "port": 30015,
    "user": "KHANALFOODS",
    "password": "7c1l1L3k7k#O",
    "schema": "KFL_LIVE",
    "connection_timeout": 30,
    "query_timeout": 300,
    "max_retries": 3
}

# Report Configuration
REPORT_SETTINGS = {
    "output_directory": os.path.join(frappe.get_site_path(), 'private', 'files', 'hana_reports'),
    "email_recipients": [
        "yogesha@khanalfoods.com",
        "harsha@khanalfoods.com"
    ],
    "default_format": "xlsx",
    "include_charts": True,
    "auto_email": True,
    "max_rows_per_sheet": 100000,
    "date_format": "%d-%b-%Y",
    "month_format": "%b-%y"
}

# Email Configuration
EMAIL_CONFIG = {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "reports@khanalfoods.com",
    "sender_password": os.getenv("EMAIL_PASSWORD", ""),
    "use_tls": True
}

# Company Mapping Configuration
COMPANY_MAPPING = {
    'C03579': 'KFPL-HR',
    'C03564': 'KFPL-MH', 
    'C03596': 'KFPL-TN',
    'default': 'KFPL-KA'
}

# Revenue Recognition Configuration
REVENUE_RECOGNITION_CUSTOMERS = [
    'C03603', 'C03604', 'C03327', 'C01186', 'C01072', 
    'C03497', 'C03326', 'C03324', 'C03447', 'C03589', 
    'C03529', 'C03595', 'C03597'
]

# White Labelling Customers
WHITE_LABELLING_CUSTOMERS = [
    'C00231', 'C03500', 'C00394', 'C00629', 'C00778', 
    'C00878', 'C01049', 'C03384', 'C03507', 'C03558',
    'C01177', 'C03516', 'C03239', 'C03562', 'C01765', 
    'C03587', 'C03560', 'C03491', 'C02175', 'C02253', 
    'C03554', 'C02567', 'C03573', 'C03458', 'C02776', 
    'C03547', 'C03034', 'C03496'
]

# Inter Transfer Customers
INTER_TRANSFER_CUSTOMERS = ['C01186', 'C03326', 'C03324']

# Channel Mapping
CHANNEL_MAPPING = {
    'E-com': 'E-com',
    'Domestic HN': 'Offline HN',
    'Domestic Dogsee': 'Offline Dogsee',
    'Others': 'Others',
    'Export': 'Export'
}

# Brand Name Mapping
BRAND_MAPPING = {
    'DOGSEE': ['%DC%', 'FGDV%'],
    'HN': 'default'
}

# Default Date Range (if not provided)
DEFAULT_DATE_RANGE = {
    "start_date": datetime.now().replace(day=1).strftime("%Y-%m-%d"),
    "end_date": datetime.now().strftime("%Y-%m-%d")
}
