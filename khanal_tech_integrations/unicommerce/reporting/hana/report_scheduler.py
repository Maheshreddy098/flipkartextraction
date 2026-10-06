"""
Report Scheduler for HANA DB Reporting System
Handles scheduled report execution and automation
"""

import schedule
import time
import threading
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import os
import sys

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
if project_root not in sys.path:
    sys.path.append(project_root)

from .hana_query_engine_readonly import (
    generate_comprehensive_sales_report_readonly,
    HANAReadOnlyQueryEngine
)
from .excel_report_generator import create_comprehensive_sales_report
from .data_comparison_engine import compare_sales_data
from .configuration import REPORT_SETTINGS, EMAIL_CONFIG

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HANAReportScheduler:
    """
    Scheduler for automated HANA report generation
    """
    
    def __init__(self):
        """
        Initialize report scheduler
        """
        self.running = False
        self.scheduler_thread = None
        
    def schedule_daily_report(self, report_type: str = "comprehensive_sales", 
                             time: str = "09:00") -> bool:
        """
        Schedule daily report generation
        
        Args:
            report_type: Type of report to generate
            time: Time to generate report (HH:MM format)
            
        Returns:
            bool: True if scheduled successfully
        """
        try:
            if report_type == "comprehensive_sales":
                schedule.every().day.at(time).do(self._execute_comprehensive_sales_report)
            elif report_type == "sales_summary":
                schedule.every().day.at(time).do(self._execute_sales_summary_report)
            elif report_type == "inventory_analysis":
                schedule.every().day.at(time).do(self._execute_inventory_report)
            elif report_type == "batch_analysis":
                schedule.every().day.at(time).do(self._execute_batch_report)
            else:
                logger.error(f"Unknown report type: {report_type}")
                return False
            
            logger.info(f"Scheduled daily {report_type} report at {time}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to schedule daily report: {str(e)}")
            return False
    
    def schedule_weekly_report(self, report_type: str = "comprehensive_sales", 
                              day: str = "Monday") -> bool:
        """
        Schedule weekly report generation
        
        Args:
            report_type: Type of report to generate
            day: Day of the week
            
        Returns:
            bool: True if scheduled successfully
        """
        try:
            if report_type == "comprehensive_sales":
                getattr(schedule.every(), day.lower()).do(self._execute_comprehensive_sales_report)
            elif report_type == "sales_summary":
                getattr(schedule.every(), day.lower()).do(self._execute_sales_summary_report)
            elif report_type == "inventory_analysis":
                getattr(schedule.every(), day.lower()).do(self._execute_inventory_report)
            elif report_type == "batch_analysis":
                getattr(schedule.every(), day.lower()).do(self._execute_batch_report)
            else:
                logger.error(f"Unknown report type: {report_type}")
                return False
            
            logger.info(f"Scheduled weekly {report_type} report on {day}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to schedule weekly report: {str(e)}")
            return False
    
    def schedule_monthly_report(self, report_type: str = "comprehensive_sales", 
                               day: int = 1) -> bool:
        """
        Schedule monthly report generation
        
        Args:
            report_type: Type of report to generate
            day: Day of the month (1-31)
            
        Returns:
            bool: True if scheduled successfully
        """
        try:
            if report_type == "comprehensive_sales":
                schedule.every().month.do(self._execute_comprehensive_sales_report)
            elif report_type == "sales_summary":
                schedule.every().month.do(self._execute_sales_summary_report)
            elif report_type == "inventory_analysis":
                schedule.every().month.do(self._execute_inventory_report)
            elif report_type == "batch_analysis":
                schedule.every().month.do(self._execute_batch_report)
            else:
                logger.error(f"Unknown report type: {report_type}")
                return False
            
            logger.info(f"Scheduled monthly {report_type} report on day {day}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to schedule monthly report: {str(e)}")
            return False
    
    def execute_scheduled_report(self, report_config: Dict) -> str:
        """
        Execute scheduled report
        
        Args:
            report_config: Report configuration
            
        Returns:
            str: Path to generated report file
        """
        try:
            report_type = report_config.get('type', 'comprehensive_sales')
            date_range = report_config.get('date_range', {})
            
            if report_type == "comprehensive_sales":
                return self._execute_comprehensive_sales_report(date_range)
            elif report_type == "sales_summary":
                return self._execute_sales_summary_report(date_range)
            elif report_type == "inventory_analysis":
                return self._execute_inventory_report()
            elif report_type == "batch_analysis":
                return self._execute_batch_report()
            else:
                raise ValueError(f"Unknown report type: {report_type}")
                
        except Exception as e:
            logger.error(f"Failed to execute scheduled report: {str(e)}")
            raise
    
    def start_scheduler(self) -> bool:
        """
        Start the scheduler in a separate thread
        
        Returns:
            bool: True if started successfully
        """
        try:
            if self.running:
                logger.warning("Scheduler is already running")
                return False
            
            self.running = True
            self.scheduler_thread = threading.Thread(target=self._run_scheduler)
            self.scheduler_thread.daemon = True
            self.scheduler_thread.start()
            
            logger.info("Report scheduler started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start scheduler: {str(e)}")
            return False
    
    def stop_scheduler(self) -> bool:
        """
        Stop the scheduler
        
        Returns:
            bool: True if stopped successfully
        """
        try:
            self.running = False
            if self.scheduler_thread:
                self.scheduler_thread.join(timeout=5)
            
            schedule.clear()
            logger.info("Report scheduler stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop scheduler: {str(e)}")
            return False
    
    def _run_scheduler(self):
        """
        Run the scheduler loop
        """
        try:
            while self.running:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
                
        except Exception as e:
            logger.error(f"Scheduler error: {str(e)}")
        finally:
            self.running = False
    
    def _execute_comprehensive_sales_report(self, date_range: Dict = None) -> str:
        """
        Execute comprehensive sales report
        """
        try:
            # Determine date range
            if not date_range:
                end_date = datetime.now().strftime("%Y-%m-%d")
                start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            else:
                start_date = date_range.get('start_date', (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
                end_date = date_range.get('end_date', datetime.now().strftime("%Y-%m-%d"))
            
            logger.info(f"Generating comprehensive sales report for {start_date} to {end_date}")
            
            # Generate data
            data = generate_comprehensive_sales_report(start_date, end_date)
            
            # Create Excel report
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"comprehensive_sales_report_{timestamp}.xlsx"
            report_path = create_comprehensive_sales_report(data, filename)
            
            # Send email if configured
            if REPORT_SETTINGS.get('auto_email', False):
                self._send_report_email(report_path, "Comprehensive Sales Report")
            
            logger.info(f"Comprehensive sales report generated: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"Failed to execute comprehensive sales report: {str(e)}")
            raise
    
    def _execute_sales_summary_report(self, date_range: Dict = None) -> str:
        """
        Execute sales summary report
        """
        try:
            # Determine date range
            if not date_range:
                end_date = datetime.now().strftime("%Y-%m-%d")
                start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            else:
                start_date = date_range.get('start_date', (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"))
                end_date = date_range.get('end_date', datetime.now().strftime("%Y-%m-%d"))
            
            logger.info(f"Generating sales summary report for {start_date} to {end_date}")
            
            # Generate data
            data = generate_sales_summary(start_date, end_date)
            
            # Create Excel report
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"sales_summary_report_{timestamp}.xlsx"
            report_path = create_sales_summary_report(data, filename)
            
            # Send email if configured
            if REPORT_SETTINGS.get('auto_email', False):
                self._send_report_email(report_path, "Sales Summary Report")
            
            logger.info(f"Sales summary report generated: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"Failed to execute sales summary report: {str(e)}")
            raise
    
    def _execute_inventory_report(self) -> str:
        """
        Execute inventory analysis report
        """
        try:
            logger.info("Generating inventory analysis report")
            
            # Generate data
            data = generate_inventory_report()
            
            # Create Excel report
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"inventory_report_{timestamp}.xlsx"
            
            from .excel_report_generator import ExcelReportGenerator, REPORT_CONFIGS
            generator = ExcelReportGenerator()
            config = REPORT_CONFIGS["inventory_analysis"]
            report_path = generator.create_report(data, config, filename)
            
            # Send email if configured
            if REPORT_SETTINGS.get('auto_email', False):
                self._send_report_email(report_path, "Inventory Analysis Report")
            
            logger.info(f"Inventory report generated: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"Failed to execute inventory report: {str(e)}")
            raise
    
    def _execute_batch_report(self) -> str:
        """
        Execute batch analysis report
        """
        try:
            logger.info("Generating batch analysis report")
            
            # Generate data
            data = generate_batch_report()
            
            # Create Excel report
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"batch_report_{timestamp}.xlsx"
            
            from .excel_report_generator import ExcelReportGenerator, REPORT_CONFIGS
            generator = ExcelReportGenerator()
            config = REPORT_CONFIGS["inventory_analysis"]  # Reuse inventory config
            report_path = generator.create_report(data, config, filename)
            
            # Send email if configured
            if REPORT_SETTINGS.get('auto_email', False):
                self._send_report_email(report_path, "Batch Analysis Report")
            
            logger.info(f"Batch report generated: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"Failed to execute batch report: {str(e)}")
            raise
    
    def _send_report_email(self, report_path: str, subject: str) -> bool:
        """
        Send report via email
        
        Args:
            report_path: Path to report file
            subject: Email subject
            
        Returns:
            bool: True if sent successfully
        """
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            from email.mime.base import MIMEBase
            from email import encoders
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = EMAIL_CONFIG['sender_email']
            msg['To'] = ', '.join(REPORT_SETTINGS['email_recipients'])
            msg['Subject'] = f"{subject} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            # Email body
            body = f"""
            Hello,
            
            Please find attached the {subject} generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.
            
            This report contains comprehensive analysis of the HANA database data.
            
            Best regards,
            HANA Reporting System
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Attach file
            with open(report_path, "rb") as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
            
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {os.path.basename(report_path)}'
            )
            msg.attach(part)
            
            # Send email
            server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
            if EMAIL_CONFIG['use_tls']:
                server.starttls()
            server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['sender_password'])
            
            text = msg.as_string()
            server.sendmail(EMAIL_CONFIG['sender_email'], REPORT_SETTINGS['email_recipients'], text)
            server.quit()
            
            logger.info(f"Report email sent successfully: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send report email: {str(e)}")
            return False

# Global scheduler instance
_scheduler_instance = None

def get_scheduler() -> HANAReportScheduler:
    """
    Get global scheduler instance
    
    Returns:
        HANAReportScheduler: Global scheduler instance
    """
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = HANAReportScheduler()
    return _scheduler_instance

def start_daily_reports():
    """
    Start daily report generation
    """
    try:
        scheduler = get_scheduler()
        
        # Schedule daily reports
        scheduler.schedule_daily_report("comprehensive_sales", "09:00")
        scheduler.schedule_daily_report("sales_summary", "18:00")
        scheduler.schedule_daily_report("inventory_analysis", "10:00")
        
        # Start scheduler
        scheduler.start_scheduler()
        
        logger.info("Daily reports scheduled and scheduler started")
        return True
        
    except Exception as e:
        logger.error(f"Failed to start daily reports: {str(e)}")
        return False

def generate_weekly_report():
    """
    Generate weekly comprehensive report
    """
    try:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        scheduler = get_scheduler()
        report_path = scheduler._execute_comprehensive_sales_report({
            'start_date': start_date,
            'end_date': end_date
        })
        
        logger.info(f"Weekly report generated: {report_path}")
        return report_path
        
    except Exception as e:
        logger.error(f"Failed to generate weekly report: {str(e)}")
        raise

def generate_monthly_report():
    """
    Generate monthly comprehensive report
    """
    try:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        scheduler = get_scheduler()
        report_path = scheduler._execute_comprehensive_sales_report({
            'start_date': start_date,
            'end_date': end_date
        })
        
        logger.info(f"Monthly report generated: {report_path}")
        return report_path
        
    except Exception as e:
        logger.error(f"Failed to generate monthly report: {str(e)}")
        raise

if __name__ == "__main__":
    # Test the scheduler
    try:
        scheduler = HANAReportScheduler()
        
        # Schedule a test report
        scheduler.schedule_daily_report("comprehensive_sales", "09:00")
        
        # Start scheduler
        scheduler.start_scheduler()
        
        print("✅ Scheduler started successfully")
        print("Press Ctrl+C to stop...")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            scheduler.stop_scheduler()
            print("✅ Scheduler stopped")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
