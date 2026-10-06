"""
HANA Database Query Engine - Read-Only Version
Uses Python HANA driver (hdbcli) for read-only database access
"""

import pandas as pd
import logging
from typing import Dict, List, Optional, Union
from datetime import datetime, timedelta
import os
import sys
import frappe

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
if project_root not in sys.path:
    sys.path.append(project_root)

from .configuration import HANA_CONFIG, DEFAULT_DATE_RANGE
from .query_templates import get_comprehensive_sales_query, get_query_template, get_comprehensive_sales_query_simplified

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import hdbcli.dbapi as hana_dbapi
    HANA_DRIVER_AVAILABLE = True
except ImportError:
    HANA_DRIVER_AVAILABLE = False
    logger.warning("HANA Python driver (hdbcli) not available. Install with: pip install hdbcli")

class HANAReadOnlyQueryEngine:
    """
    Read-only HANA database query engine using Python HANA driver
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize read-only HANA database connection
        
        Args:
            config: Database configuration dictionary
        """
        self.config = config or HANA_CONFIG
        self.connection = None
        self.cursor = None
        
        if not HANA_DRIVER_AVAILABLE:
            raise ImportError("HANA Python driver not available. Install with: pip install hdbcli")
    
    def connect(self) -> bool:
        """
        Establish read-only connection to HANA database
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # HANA connection parameters (without databaseName for better compatibility)
            connection_params = {
                'address': self.config['host'],
                'port': self.config['port'],
                'user': self.config['user'],
                'password': self.config['password'],
                'autocommit': False,  # Explicit transaction control
                # Note: readOnly parameter may not be supported by all HANA versions
            }
            
            self.connection = hana_dbapi.connect(**connection_params)
            self.cursor = self.connection.cursor()
            
            logger.info(f"Successfully connected to HANA database in read-only mode: {self.config['host']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to HANA database: {str(e)}")
            return False
    
    def disconnect(self):
        """
        Close database connection
        """
        try:
            if self.cursor:
                self.cursor.close()
            if self.connection:
                self.connection.close()
            logger.info("Read-only database connection closed")
        except Exception as e:
            logger.error(f"Error closing database connection: {str(e)}")
    
    def test_connection(self) -> bool:
        """
        Test database connection
        
        Returns:
            bool: True if connection is working, False otherwise
        """
        try:
            if not self.connection:
                return self.connect()
            
            # Simple test query
            self.cursor.execute("SELECT 1 FROM DUMMY")
            result = self.cursor.fetchone()
            return result is not None
            
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False
    
    def execute_query(self, query: str, params: Dict = None) -> pd.DataFrame:
        """
        Execute read-only SQL query and return DataFrame
        
        Args:
            query: SQL query string
            params: Query parameters dictionary
            
        Returns:
            pd.DataFrame: Query results as DataFrame
        """
        try:
            if not self.test_connection():
                raise Exception("Database connection not available")
            
            # Validate query is read-only
            self._validate_readonly_query(query)
            
            # Substitute parameters into query after strict validation.
            # Cursor-level parameterization is not supported for HANA procedural
            # SQL blocks (DECLARE / := syntax), so we sanitise each value before
            # interpolation to prevent injection.
            if params:
                import re as _re
                _DATE_RE = _re.compile(r'^\d{4}-\d{2}-\d{2}$')
                safe_params = {}
                for k, v in params.items():
                    sv = str(v).strip()
                    if not _DATE_RE.match(sv):
                        raise ValueError(
                            f"HANA query param '{k}' must be YYYY-MM-DD, got: {sv!r}"
                        )
                    safe_params[k] = sv
                query = query.format(**safe_params)
            
            logger.info(f"Executing read-only query: {query[:100]}...")
            
            # Execute query
            self.cursor.execute(query)
            
            # Fetch column names
            columns = [desc[0] for desc in self.cursor.description]
            
            # Fetch all rows
            rows = self.cursor.fetchall()
            
            # Create DataFrame
            df = pd.DataFrame(rows, columns=columns)
            
            # Convert data types for better Excel formatting
            df = self._convert_data_types(df)
            
            logger.info(f"Read-only query executed successfully. Retrieved {len(df)} rows")
            return df
            
        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}")
            raise
    
    def _convert_data_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Convert data types for better Excel formatting and analysis
        
        Args:
            df: DataFrame with raw data
            
        Returns:
            pd.DataFrame: DataFrame with converted data types
        """
        try:
            # Define numeric columns
            numeric_columns = [
                'DocNum', 'LineNum', 'Currency Rate', 'Quantity', 'MIS Weight', 
                'MRP', 'Unit Price', 'Discount', 'Difference', 'Diff %', 'INR Price',
                'Taxable Value', 'Total_Disc', 'Net Taxable Value', 'GST_Rate',
                'CGST Tax Amount', 'SGST Tax Amount', 'IGST Tax Amount', 
                'Freight Charges', 'Insurance', 'Total Value', 'COGS per unit', 
                'COGS', 'Gross Margin'
            ]
            
            # Convert numeric columns
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Handle date columns
            date_columns = ['Document Date', 'Order Date']
            for col in date_columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
            
            # Clean string columns - replace None with empty string
            string_columns = df.select_dtypes(include=['object']).columns
            for col in string_columns:
                if col not in numeric_columns + date_columns:
                    df[col] = df[col].fillna('').astype(str)
                    # Remove any 'None' strings
                    df[col] = df[col].replace('None', '')
            
            # Handle percentage columns
            percentage_columns = ['Diff %', 'Gross Margin %']
            for col in percentage_columns:
                if col in df.columns:
                    # Convert percentage strings to numeric
                    df[col] = df[col].astype(str).str.replace('%', '').str.replace(',', '')
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            logger.info(f"Data types converted successfully. Shape: {df.shape}")
            return df
            
        except Exception as e:
            logger.error(f"Error converting data types: {str(e)}")
            return df
    
    def execute_template_query(self, template_name: str, params: Dict = None) -> pd.DataFrame:
        """
        Execute pre-defined query template
        
        Args:
            template_name: Name of the query template
            params: Parameters for the template
            
        Returns:
            pd.DataFrame: Query results as DataFrame
        """
        try:
            query = get_query_template(template_name, **params)
            return self.execute_query(query, params)
        except Exception as e:
            logger.error(f"Template query execution failed: {str(e)}")
            raise
    
    def validate_query(self, query: str) -> bool:
        """
        Validate SQL query syntax and ensure it's read-only
        
        Args:
            query: SQL query string
            
        Returns:
            bool: True if query is valid and read-only, False otherwise
        """
        try:
            # Check for read-only compliance
            return self._validate_readonly_query(query)
            
        except Exception as e:
            logger.error(f"Query validation failed: {str(e)}")
            return False
    
    def _validate_readonly_query(self, query: str) -> bool:
        """
        Validate that query is read-only
        
        Args:
            query: SQL query string
            
        Returns:
            bool: True if query is read-only, False otherwise
            
        Raises:
            ValueError: If query contains write operations
        """
        # Dangerous keywords that modify data
        dangerous_keywords = [
            'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER', 
            'TRUNCATE', 'MERGE', 'UPSERT', 'CALL', 'EXEC', 'EXECUTE'
        ]
        
        query_upper = query.upper()
        
        for keyword in dangerous_keywords:
            if keyword in query_upper:
                raise ValueError(f"Read-only mode: '{keyword}' operations are not allowed")
        
        logger.info("Query validated as read-only")
        return True
    
    def get_table_schema(self, table_name: str) -> Dict:
        """
        Get table schema information
        
        Args:
            table_name: Name of the table
            
        Returns:
            Dict: Table schema information
        """
        try:
            if not self.test_connection():
                raise Exception("Database connection not available")
            
            query = f"""
            SELECT 
                COLUMN_NAME,
                DATA_TYPE_NAME,
                LENGTH,
                IS_NULLABLE,
                COLUMN_DEFAULT
            FROM TABLE_COLUMNS 
            WHERE SCHEMA_NAME = '{self.config['schema']}' 
            AND TABLE_NAME = '{table_name.upper()}'
            ORDER BY POSITION
            """
            
            df = self.execute_query(query)
            return df.to_dict('records')
            
        except Exception as e:
            logger.error(f"Failed to get table schema: {str(e)}")
            raise
    
    def get_available_tables(self) -> List[str]:
        """
        Get list of available tables in the schema
        
        Returns:
            List[str]: List of table names
        """
        try:
            if not self.test_connection():
                raise Exception("Database connection not available")
            
            query = f"""
            SELECT TABLE_NAME 
            FROM TABLES 
            WHERE SCHEMA_NAME = '{self.config['schema']}'
            ORDER BY TABLE_NAME
            """
            
            df = self.execute_query(query)
            return df['TABLE_NAME'].tolist()
            
        except Exception as e:
            logger.error(f"Failed to get available tables: {str(e)}")
            raise
    
    def get_table_count(self, table_name: str) -> int:
        """
        Get record count for a table
        
        Args:
            table_name: Name of the table
            
        Returns:
            int: Number of records in the table
        """
        try:
            if not self.test_connection():
                raise Exception("Database connection not available")
            
            query = f"SELECT COUNT(*) as record_count FROM {self.config['schema']}.{table_name}"
            df = self.execute_query(query)
            return df['record_count'].iloc[0]
            
        except Exception as e:
            logger.error(f"Failed to get table count: {str(e)}")
            raise

# Read-only specific query execution functions
def generate_comprehensive_sales_report_readonly(start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """
    Generate comprehensive sales report using read-only access
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        pd.DataFrame: Comprehensive sales data
    """
    try:
        # Use default date range if not provided
        if not start_date:
            start_date = DEFAULT_DATE_RANGE['start_date']
        if not end_date:
            end_date = DEFAULT_DATE_RANGE['end_date']
        
        # Prefer runtime HANA credentials/schema from SAP Settings
        runtime_config = dict(HANA_CONFIG)
        try:
            sap_settings = frappe.get_single("SAP Settings")
            runtime_config.update(
                {
                    "host": sap_settings.hana_host,
                    "port": int(sap_settings.hana_port),
                    "user": sap_settings.hana_user,
                    "password": sap_settings.get_password("hana_password"),
                    "schema": sap_settings.hana_schema,
                }
            )
        except Exception:
            logger.warning("Using default HANA_CONFIG because SAP Settings could not be read")

        # Initialize read-only query engine
        engine = HANAReadOnlyQueryEngine(config=runtime_config)
        
        # Get the comprehensive sales query (simplified version for Python driver)
        query = get_comprehensive_sales_query_simplified(
            start_date, end_date, schema=runtime_config.get("schema")
        )
        
        # Execute query with parameters
        df = engine.execute_query(query, params={"start_date": start_date, "end_date": end_date})
        
        logger.info(f"Read-only comprehensive sales report generated: {len(df)} records from {start_date} to {end_date}")
        return df
        
    except Exception as e:
        logger.error(f"Failed to generate read-only comprehensive sales report: {str(e)}")
        raise
    finally:
        if 'engine' in locals():
            engine.disconnect()

def generate_gstr1_revenue_report_readonly(start_date: str, end_date: str) -> pd.DataFrame:
    """Run the trimmed GSTR1 revenue query against HANA for the given range.

    Used by the Ops Center GST Reconciliation flow. Reuses the same SAP Settings
    HANA credentials/schema discovery as `generate_comprehensive_sales_report_readonly`.
    """
    from .query_templates import get_gstr1_revenue_query

    if not start_date or not end_date:
        raise ValueError("start_date and end_date are required for GSTR1 revenue report")

    runtime_config = dict(HANA_CONFIG)
    try:
        sap_settings = frappe.get_single("SAP Settings")
        runtime_config.update(
            {
                "host": sap_settings.hana_host,
                "port": int(sap_settings.hana_port),
                "user": sap_settings.hana_user,
                "password": sap_settings.get_password("hana_password"),
                "schema": sap_settings.hana_schema,
            }
        )
    except Exception:
        logger.warning("Using default HANA_CONFIG because SAP Settings could not be read")

    engine = HANAReadOnlyQueryEngine(config=runtime_config)
    try:
        query = get_gstr1_revenue_query(start_date, end_date, schema=runtime_config.get("schema"))
        df = engine.execute_query(query, params={"start_date": start_date, "end_date": end_date})
        logger.info(f"GSTR1 revenue report generated: {len(df)} rows from {start_date} to {end_date}")
        return df
    finally:
        try:
            engine.disconnect()
        except Exception:
            logger.warning("HANA disconnect failed after GSTR1 query", exc_info=True)


def test_readonly_connection() -> bool:
    """
    Test read-only connection to HANA database
    
    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        if not HANA_DRIVER_AVAILABLE:
            logger.error("HANA Python driver not available. Install with: pip install hdbcli")
            return False
        
        engine = HANAReadOnlyQueryEngine()
        
        if engine.connect():
            # Test basic query
            df = engine.execute_query("SELECT COUNT(*) as table_count FROM TABLES WHERE SCHEMA_NAME = 'KFL_LIVE'")
            table_count = df['table_count'].iloc[0]
            
            logger.info(f"✅ Read-only connection successful. Found {table_count} tables in schema.")
            
            # Test your main tables
            main_tables = ['OINV', 'INV1', 'ORIN', 'RIN1', 'OITM', 'OCRD']
            for table in main_tables:
                try:
                    count = engine.get_table_count(table)
                    logger.info(f"  - {table}: {count:,} records")
                except Exception as e:
                    logger.warning(f"  - {table}: Not accessible ({str(e)})")
            
            engine.disconnect()
            return True
        else:
            logger.error("Failed to establish read-only connection")
            return False
            
    except Exception as e:
        logger.error(f"Read-only connection test failed: {str(e)}")
        return False

if __name__ == "__main__":
    # Test the read-only query engine
    try:
        if not HANA_DRIVER_AVAILABLE:
            print("❌ HANA Python driver not available. Install with: pip install hdbcli")
            exit(1)
        
        print("🧪 Testing HANA Read-Only Query Engine...")
        print("=" * 50)
        
        success = test_readonly_connection()
        
        if success:
            print("✅ HANA read-only connection successful")
            
            # Test comprehensive sales query
            try:
                df = generate_comprehensive_sales_report_readonly()
                print(f"✅ Read-only comprehensive sales report: {len(df)} records")
                print(f"Columns: {list(df.columns)}")
            except Exception as e:
                print(f"⚠️ Sales report test failed: {str(e)}")
        else:
            print("❌ HANA read-only connection failed")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
