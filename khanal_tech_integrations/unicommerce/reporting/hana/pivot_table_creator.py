"""
Pivot Table Creator for HANA DB Reporting System
Creates comprehensive pivot table analysis for sales data
"""

import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple
import numpy as np

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HANAPivotTableCreator:
    """
    Creates pivot tables for HANA database analysis
    """
    
    def __init__(self):
        """
        Initialize pivot table creator
        """
        pass
    
    def create_sales_pivot(self, data: pd.DataFrame, pivot_type: str = "comprehensive") -> Dict[str, pd.DataFrame]:
        """
        Create sales analysis pivot tables
        
        Args:
            data: Sales DataFrame
            pivot_type: Type of pivot analysis
            
        Returns:
            Dict: Dictionary of pivot tables
        """
        try:
            pivot_tables = {}
            
            if pivot_type == "comprehensive":
                # Company-wise analysis
                pivot_tables['company_analysis'] = self._create_company_pivot(data)
                
                # Channel-wise analysis
                pivot_tables['channel_analysis'] = self._create_channel_pivot(data)
                
                # Monthly trend analysis
                pivot_tables['monthly_trend'] = self._create_monthly_pivot(data)
                
                # Brand category analysis
                pivot_tables['brand_analysis'] = self._create_brand_pivot(data)
                
                # Customer analysis
                pivot_tables['customer_analysis'] = self._create_customer_pivot(data)
                
                # Product analysis
                pivot_tables['product_analysis'] = self._create_product_pivot(data)
                
                # Geographic analysis
                pivot_tables['geographic_analysis'] = self._create_geographic_pivot(data)
                
                # Tax analysis
                pivot_tables['tax_analysis'] = self._create_tax_pivot(data)
                
            elif pivot_type == "financial":
                # Financial metrics pivot
                pivot_tables['financial_metrics'] = self._create_financial_pivot(data)
                
                # Profitability analysis
                pivot_tables['profitability'] = self._create_profitability_pivot(data)
                
            elif pivot_type == "operational":
                # Order analysis
                pivot_tables['order_analysis'] = self._create_order_pivot(data)
                
                # Inventory turnover
                pivot_tables['inventory_turnover'] = self._create_inventory_pivot(data)
            
            logger.info(f"Created {len(pivot_tables)} pivot tables for {pivot_type} analysis")
            return pivot_tables
            
        except Exception as e:
            logger.error(f"Failed to create sales pivot tables: {str(e)}")
            raise
    
    def create_inventory_pivot(self, data: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """
        Create inventory analysis pivot tables
        
        Args:
            data: Inventory DataFrame
            
        Returns:
            Dict: Dictionary of pivot tables
        """
        try:
            pivot_tables = {}
            
            # Item-wise inventory
            pivot_tables['item_inventory'] = self._create_item_inventory_pivot(data)
            
            # Warehouse-wise inventory
            pivot_tables['warehouse_inventory'] = self._create_warehouse_pivot(data)
            
            # Stock status analysis
            pivot_tables['stock_status'] = self._create_stock_status_pivot(data)
            
            logger.info(f"Created {len(pivot_tables)} inventory pivot tables")
            return pivot_tables
            
        except Exception as e:
            logger.error(f"Failed to create inventory pivot tables: {str(e)}")
            raise
    
    def create_batch_pivot(self, data: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """
        Create batch analysis pivot tables
        
        Args:
            data: Batch DataFrame
            
        Returns:
            Dict: Dictionary of pivot tables
        """
        try:
            pivot_tables = {}
            
            # Item-wise batch distribution
            pivot_tables['item_batch'] = self._create_item_batch_pivot(data)
            
            # Location-wise batch analysis
            pivot_tables['location_batch'] = self._create_location_batch_pivot(data)
            
            # Expiry analysis
            pivot_tables['expiry_analysis'] = self._create_expiry_pivot(data)
            
            logger.info(f"Created {len(pivot_tables)} batch pivot tables")
            return pivot_tables
            
        except Exception as e:
            logger.error(f"Failed to create batch pivot tables: {str(e)}")
            raise
    
    def create_custom_pivot(self, data: pd.DataFrame, config: Dict) -> pd.DataFrame:
        """
        Create custom pivot table based on configuration
        
        Args:
            data: DataFrame to pivot
            config: Pivot configuration
            
        Returns:
            pd.DataFrame: Custom pivot table
        """
        try:
            index_cols = config.get('index', [])
            columns_col = config.get('columns', None)
            values_col = config.get('values', [])
            aggfunc = config.get('aggfunc', 'sum')
            
            if not values_col:
                raise ValueError("Values column must be specified")
            
            pivot_table = pd.pivot_table(
                data,
                index=index_cols,
                columns=columns_col,
                values=values_col,
                aggfunc=aggfunc,
                fill_value=0
            )
            
            logger.info(f"Custom pivot table created with shape: {pivot_table.shape}")
            return pivot_table
            
        except Exception as e:
            logger.error(f"Failed to create custom pivot table: {str(e)}")
            raise
    
    def _create_company_pivot(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create company-wise sales pivot
        """
        try:
            pivot_data = data.groupby('Company').agg({
                'Total Value': ['sum', 'count', 'mean'],
                'Taxable Value': 'sum',
                'COGS': 'sum',
                'Gross Margin': 'sum'
            }).round(2)
            
            # Flatten column names
            pivot_data.columns = ['_'.join(col).strip() for col in pivot_data.columns]
            
            # Add percentage calculations
            pivot_data['Sales_Percentage'] = (pivot_data['Total Value_sum'] / pivot_data['Total Value_sum'].sum() * 100).round(2)
            pivot_data['Margin_Percentage'] = (pivot_data['Gross Margin_sum'] / pivot_data['Taxable Value_sum'] * 100).round(2)
            
            return pivot_data.reset_index()
            
        except Exception as e:
            logger.error(f"Failed to create company pivot: {str(e)}")
            return pd.DataFrame()
    
    def _create_channel_pivot(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create channel-wise sales pivot
        """
        try:
            pivot_data = data.groupby('Channel').agg({
                'Total Value': ['sum', 'count', 'mean'],
                'Taxable Value': 'sum',
                'COGS': 'sum',
                'Gross Margin': 'sum'
            }).round(2)
            
            # Flatten column names
            pivot_data.columns = ['_'.join(col).strip() for col in pivot_data.columns]
            
            # Add percentage calculations
            pivot_data['Sales_Percentage'] = (pivot_data['Total Value_sum'] / pivot_data['Total Value_sum'].sum() * 100).round(2)
            pivot_data['Margin_Percentage'] = (pivot_data['Gross Margin_sum'] / pivot_data['Taxable Value_sum'] * 100).round(2)
            
            return pivot_data.reset_index()
            
        except Exception as e:
            logger.error(f"Failed to create channel pivot: {str(e)}")
            return pd.DataFrame()
    
    def _create_monthly_pivot(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create monthly sales trend pivot
        """
        try:
            # Convert Month to datetime for proper sorting
            data_copy = data.copy()
            data_copy['Month_Date'] = pd.to_datetime(data_copy['Month'], format='%b-%y')
            
            pivot_data = data_copy.groupby('Month').agg({
                'Total Value': ['sum', 'count', 'mean'],
                'Taxable Value': 'sum',
                'COGS': 'sum',
                'Gross Margin': 'sum'
            }).round(2)
            
            # Flatten column names
            pivot_data.columns = ['_'.join(col).strip() for col in pivot_data.columns]
            
            # Add month-over-month growth
            pivot_data['MoM_Growth_%'] = pivot_data['Total Value_sum'].pct_change() * 100
            pivot_data['MoM_Growth_%'] = pivot_data['MoM_Growth_%'].round(2)
            
            return pivot_data.reset_index()
            
        except Exception as e:
            logger.error(f"Failed to create monthly pivot: {str(e)}")
            return pd.DataFrame()
    
    def _create_brand_pivot(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create brand category pivot
        """
        try:
            pivot_data = data.groupby('Brand Category').agg({
                'Total Value': ['sum', 'count', 'mean'],
                'Taxable Value': 'sum',
                'COGS': 'sum',
                'Gross Margin': 'sum'
            }).round(2)
            
            # Flatten column names
            pivot_data.columns = ['_'.join(col).strip() for col in pivot_data.columns]
            
            # Add percentage calculations
            pivot_data['Sales_Percentage'] = (pivot_data['Total Value_sum'] / pivot_data['Total Value_sum'].sum() * 100).round(2)
            pivot_data['Margin_Percentage'] = (pivot_data['Gross Margin_sum'] / pivot_data['Taxable Value_sum'] * 100).round(2)
            
            return pivot_data.reset_index()
            
        except Exception as e:
            logger.error(f"Failed to create brand pivot: {str(e)}")
            return pd.DataFrame()
    
    def _create_customer_pivot(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create customer analysis pivot
        """
        try:
            # Top customers by sales
            customer_sales = data.groupby('Customer Name').agg({
                'Total Value': ['sum', 'count', 'mean'],
                'Taxable Value': 'sum',
                'COGS': 'sum',
                'Gross Margin': 'sum'
            }).round(2)
            
            # Flatten column names
            customer_sales.columns = ['_'.join(col).strip() for col in customer_sales.columns]
            
            # Add customer ranking
            customer_sales['Sales_Rank'] = customer_sales['Total Value_sum'].rank(ascending=False)
            
            # Calculate customer metrics
            customer_sales['Margin_Percentage'] = (customer_sales['Gross Margin_sum'] / customer_sales['Taxable Value_sum'] * 100).round(2)
            
            return customer_sales.reset_index().sort_values('Total Value_sum', ascending=False).head(50)
            
        except Exception as e:
            logger.error(f"Failed to create customer pivot: {str(e)}")
            return pd.DataFrame()
    
    def _create_product_pivot(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create product analysis pivot
        """
        try:
            # Top products by sales
            product_sales = data.groupby('SKU Code').agg({
                'Total Value': ['sum', 'count', 'mean'],
                'Taxable Value': 'sum',
                'COGS': 'sum',
                'Gross Margin': 'sum',
                'Quantity': 'sum'
            }).round(2)
            
            # Flatten column names
            product_sales.columns = ['_'.join(col).strip() for col in product_sales.columns]
            
            # Add product metrics
            product_sales['Margin_Percentage'] = (product_sales['Gross Margin_sum'] / product_sales['Taxable Value_sum'] * 100).round(2)
            product_sales['Avg_Price'] = (product_sales['Total Value_sum'] / product_sales['Quantity_sum']).round(2)
            
            return product_sales.reset_index().sort_values('Total Value_sum', ascending=False).head(50)
            
        except Exception as e:
            logger.error(f"Failed to create product pivot: {str(e)}")
            return pd.DataFrame()
    
    def _create_geographic_pivot(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create geographic analysis pivot
        """
        try:
            pivot_data = data.groupby(['Geography', 'Country']).agg({
                'Total Value': ['sum', 'count', 'mean'],
                'Taxable Value': 'sum',
                'COGS': 'sum',
                'Gross Margin': 'sum'
            }).round(2)
            
            # Flatten column names
            pivot_data.columns = ['_'.join(col).strip() for col in pivot_data.columns]
            
            # Add percentage calculations
            pivot_data['Sales_Percentage'] = (pivot_data['Total Value_sum'] / pivot_data['Total Value_sum'].sum() * 100).round(2)
            pivot_data['Margin_Percentage'] = (pivot_data['Gross Margin_sum'] / pivot_data['Taxable Value_sum'] * 100).round(2)
            
            return pivot_data.reset_index()
            
        except Exception as e:
            logger.error(f"Failed to create geographic pivot: {str(e)}")
            return pd.DataFrame()
    
    def _create_tax_pivot(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create tax analysis pivot
        """
        try:
            # Calculate total tax amounts
            tax_columns = ['CGST Tax Amount', 'SGST Tax Amount', 'IGST Tax Amount']
            available_tax_cols = [col for col in tax_columns if col in data.columns]
            
            if not available_tax_cols:
                return pd.DataFrame()
            
            # Tax summary by state/geography
            pivot_data = data.groupby(['Geography', 'State']).agg({
                'Total Value': 'sum',
                'Taxable Value': 'sum'
            })
            
            # Add tax calculations for available columns
            for tax_col in available_tax_cols:
                pivot_data[f'{tax_col}_sum'] = data.groupby(['Geography', 'State'])[tax_col].sum()
            
            # Calculate total tax
            pivot_data['Total_Tax'] = pivot_data[[f'{col}_sum' for col in available_tax_cols]].sum(axis=1)
            pivot_data['Tax_Percentage'] = (pivot_data['Total_Tax'] / pivot_data['Taxable Value'] * 100).round(2)
            
            return pivot_data.reset_index()
            
        except Exception as e:
            logger.error(f"Failed to create tax pivot: {str(e)}")
            return pd.DataFrame()
    
    def _create_financial_pivot(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create financial metrics pivot
        """
        try:
            financial_metrics = data.groupby('Company').agg({
                'Total Value': 'sum',
                'Taxable Value': 'sum',
                'COGS': 'sum',
                'Gross Margin': 'sum',
                'CGST Tax Amount': 'sum',
                'SGST Tax Amount': 'sum',
                'IGST Tax Amount': 'sum',
                'Freight Charges': 'sum',
                'Insurance': 'sum'
            }).round(2)
            
            # Calculate financial ratios
            financial_metrics['Gross_Margin_%'] = (financial_metrics['Gross Margin'] / financial_metrics['Taxable Value'] * 100).round(2)
            financial_metrics['Total_Tax'] = (financial_metrics['CGST Tax Amount'] + financial_metrics['SGST Tax Amount'] + financial_metrics['IGST Tax Amount'])
            financial_metrics['Tax_Rate_%'] = (financial_metrics['Total_Tax'] / financial_metrics['Taxable Value'] * 100).round(2)
            financial_metrics['Freight_%'] = (financial_metrics['Freight Charges'] / financial_metrics['Total Value'] * 100).round(2)
            
            return financial_metrics.reset_index()
            
        except Exception as e:
            logger.error(f"Failed to create financial pivot: {str(e)}")
            return pd.DataFrame()
    
    def _create_profitability_pivot(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create profitability analysis pivot
        """
        try:
            profitability = data.groupby(['Company', 'Channel']).agg({
                'Total Value': 'sum',
                'Taxable Value': 'sum',
                'COGS': 'sum',
                'Gross Margin': 'sum'
            }).round(2)
            
            # Calculate profitability metrics
            profitability['Gross_Margin_%'] = (profitability['Gross Margin'] / profitability['Taxable Value'] * 100).round(2)
            profitability['COGS_%'] = (profitability['COGS'] / profitability['Total Value'] * 100).round(2)
            
            return profitability.reset_index()
            
        except Exception as e:
            logger.error(f"Failed to create profitability pivot: {str(e)}")
            return pd.DataFrame()
    
    def _create_order_pivot(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create order analysis pivot
        """
        try:
            order_analysis = data.groupby(['Company', 'Channel']).agg({
                'Document No': 'nunique',  # Count unique orders
                'Total Value': 'sum',
                'Taxable Value': 'sum'
            }).round(2)
            
            # Calculate order metrics
            order_analysis['Avg_Order_Value'] = (order_analysis['Total Value'] / order_analysis['Document No']).round(2)
            
            return order_analysis.reset_index()
            
        except Exception as e:
            logger.error(f"Failed to create order pivot: {str(e)}")
            return pd.DataFrame()
    
    def _create_inventory_pivot(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create inventory turnover pivot
        """
        try:
            inventory_turnover = data.groupby('SKU Code').agg({
                'Quantity': 'sum',
                'COGS': 'sum',
                'Total Value': 'sum'
            }).round(2)
            
            # Calculate inventory metrics
            inventory_turnover['Avg_COGS_per_Unit'] = (inventory_turnover['COGS'] / inventory_turnover['Quantity']).round(2)
            inventory_turnover['Avg_Selling_Price'] = (inventory_turnover['Total Value'] / inventory_turnover['Quantity']).round(2)
            inventory_turnover['Margin_per_Unit'] = (inventory_turnover['Avg_Selling_Price'] - inventory_turnover['Avg_COGS_per_Unit']).round(2)
            
            return inventory_turnover.reset_index()
            
        except Exception as e:
            logger.error(f"Failed to create inventory pivot: {str(e)}")
            return pd.DataFrame()
    
    def _create_item_inventory_pivot(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create item-wise inventory pivot
        """
        try:
            item_inventory = data.groupby('ItemCode').agg({
                'OnHand': 'sum',
                'IsCommited': 'sum',
                'OnOrder': 'sum',
                'WhsCode': lambda x: ', '.join(x.unique())
            }).reset_index()
            
            # Calculate available stock
            item_inventory['Available_Stock'] = item_inventory['OnHand'] - item_inventory['IsCommited']
            
            return item_inventory
            
        except Exception as e:
            logger.error(f"Failed to create item inventory pivot: {str(e)}")
            return pd.DataFrame()
    
    def _create_warehouse_pivot(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create warehouse-wise inventory pivot
        """
        try:
            warehouse_inventory = data.groupby('WhsCode').agg({
                'OnHand': 'sum',
                'IsCommited': 'sum',
                'OnOrder': 'sum',
                'ItemCode': 'nunique'
            }).reset_index()
            
            # Calculate warehouse metrics
            warehouse_inventory['Available_Stock'] = warehouse_inventory['OnHand'] - warehouse_inventory['IsCommited']
            warehouse_inventory['Stock_Utilization_%'] = (warehouse_inventory['IsCommited'] / warehouse_inventory['OnHand'] * 100).round(2)
            
            return warehouse_inventory
            
        except Exception as e:
            logger.error(f"Failed to create warehouse pivot: {str(e)}")
            return pd.DataFrame()
    
    def _create_stock_status_pivot(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create stock status analysis pivot
        """
        try:
            data_copy = data.copy()
            data_copy['Available_Stock'] = data_copy['OnHand'] - data_copy['IsCommited']
            
            # Categorize stock status
            def categorize_stock(row):
                if row['Available_Stock'] <= 0:
                    return 'Out of Stock'
                elif row['Available_Stock'] <= 10:
                    return 'Low Stock'
                elif row['Available_Stock'] <= 100:
                    return 'Medium Stock'
                else:
                    return 'High Stock'
            
            data_copy['Stock_Status'] = data_copy.apply(categorize_stock, axis=1)
            
            stock_status = data_copy.groupby('Stock_Status').agg({
                'ItemCode': 'count',
                'OnHand': 'sum',
                'Available_Stock': 'sum'
            }).reset_index()
            
            return stock_status
            
        except Exception as e:
            logger.error(f"Failed to create stock status pivot: {str(e)}")
            return pd.DataFrame()
    
    def _create_item_batch_pivot(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create item-wise batch distribution pivot
        """
        try:
            item_batch = data.groupby('ItemCode').agg({
                'Quantity': 'sum',
                'DistNumber': 'count',
                'Location': lambda x: ', '.join(x.unique())
            }).reset_index()
            
            # Calculate batch metrics
            item_batch['Avg_Batch_Size'] = (item_batch['Quantity'] / item_batch['DistNumber']).round(2)
            
            return item_batch
            
        except Exception as e:
            logger.error(f"Failed to create item batch pivot: {str(e)}")
            return pd.DataFrame()
    
    def _create_location_batch_pivot(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create location-wise batch analysis pivot
        """
        try:
            location_batch = data.groupby('Location').agg({
                'Quantity': 'sum',
                'DistNumber': 'count',
                'ItemCode': 'nunique'
            }).reset_index()
            
            # Calculate location metrics
            location_batch['Avg_Batch_Size'] = (location_batch['Quantity'] / location_batch['DistNumber']).round(2)
            location_batch['Batches_per_Item'] = (location_batch['DistNumber'] / location_batch['ItemCode']).round(2)
            
            return location_batch
            
        except Exception as e:
            logger.error(f"Failed to create location batch pivot: {str(e)}")
            return pd.DataFrame()
    
    def _create_expiry_pivot(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create expiry analysis pivot
        """
        try:
            # Convert expiry date to datetime
            data_copy = data.copy()
            data_copy['ExpDate'] = pd.to_datetime(data_copy['ExpDate'], errors='coerce')
            data_copy['Days_to_Expiry'] = (data_copy['ExpDate'] - pd.Timestamp.now()).dt.days
            
            # Categorize expiry status
            def categorize_expiry(row):
                if pd.isna(row['Days_to_Expiry']):
                    return 'No Expiry Date'
                elif row['Days_to_Expiry'] < 0:
                    return 'Expired'
                elif row['Days_to_Expiry'] <= 30:
                    return 'Expiring Soon (≤30 days)'
                elif row['Days_to_Expiry'] <= 90:
                    return 'Expiring in 3 months'
                else:
                    return 'Good (>3 months)'
            
            data_copy['Expiry_Status'] = data_copy.apply(categorize_expiry, axis=1)
            
            expiry_analysis = data_copy.groupby('Expiry_Status').agg({
                'Quantity': 'sum',
                'DistNumber': 'count',
                'ItemCode': 'nunique'
            }).reset_index()
            
            return expiry_analysis
            
        except Exception as e:
            logger.error(f"Failed to create expiry pivot: {str(e)}")
            return pd.DataFrame()

# Pivot table configurations
PIVOT_CONFIGS = {
    "comprehensive_sales": {
        "index": ["Company", "Channel"],
        "columns": "Month",
        "values": ["Total Value", "Taxable Value", "COGS"],
        "aggfunc": "sum"
    },
    "customer_analysis": {
        "index": ["Customer Name"],
        "columns": "Channel",
        "values": ["Total Value", "Taxable Value"],
        "aggfunc": "sum"
    },
    "product_analysis": {
        "index": ["SKU Code", "Product Category"],
        "columns": "Brand Category",
        "values": ["Total Value", "Quantity"],
        "aggfunc": "sum"
    },
    "financial_summary": {
        "index": ["Company"],
        "columns": "Geography",
        "values": ["Total Value", "Gross Margin", "COGS"],
        "aggfunc": "sum"
    }
}

def create_comprehensive_pivot_analysis(data: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    Create comprehensive pivot analysis for sales data
    
    Args:
        data: Sales DataFrame
        
    Returns:
        Dict: Dictionary of all pivot tables
    """
    try:
        creator = HANAPivotTableCreator()
        return creator.create_sales_pivot(data, "comprehensive")
        
    except Exception as e:
        logger.error(f"Failed to create comprehensive pivot analysis: {str(e)}")
        raise

def create_financial_pivot_analysis(data: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    Create financial pivot analysis
    
    Args:
        data: Sales DataFrame
        
    Returns:
        Dict: Dictionary of financial pivot tables
    """
    try:
        creator = HANAPivotTableCreator()
        return creator.create_sales_pivot(data, "financial")
        
    except Exception as e:
        logger.error(f"Failed to create financial pivot analysis: {str(e)}")
        raise

def create_operational_pivot_analysis(data: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    Create operational pivot analysis
    
    Args:
        data: Sales DataFrame
        
    Returns:
        Dict: Dictionary of operational pivot tables
    """
    try:
        creator = HANAPivotTableCreator()
        return creator.create_sales_pivot(data, "operational")
        
    except Exception as e:
        logger.error(f"Failed to create operational pivot analysis: {str(e)}")
        raise

if __name__ == "__main__":
    # Test the pivot table creator
    try:
        # Create sample data
        sample_data = pd.DataFrame({
            'Company': ['KFPL-KA', 'KFPL-MH', 'KFPL-TN'] * 10,
            'Customer Name': ['Customer A', 'Customer B', 'Customer C'] * 10,
            'Total Value': np.random.randint(10000, 100000, 30),
            'Channel': ['E-com', 'Offline HN', 'Export'] * 10,
            'Month': ['Jan-25', 'Feb-25', 'Mar-25'] * 10,
            'Brand Category': ['Own Brand', 'White Labelling', 'Own Brand'] * 10,
            'SKU Code': ['SKU001', 'SKU002', 'SKU003'] * 10,
            'Taxable Value': np.random.randint(8000, 80000, 30),
            'COGS': np.random.randint(5000, 50000, 30),
            'Gross Margin': np.random.randint(3000, 30000, 30)
        })
        
        creator = HANAPivotTableCreator()
        pivot_tables = creator.create_sales_pivot(sample_data, "comprehensive")
        
        print(f"✅ Created {len(pivot_tables)} pivot tables:")
        for name, table in pivot_tables.items():
            print(f"  - {name}: {table.shape}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
