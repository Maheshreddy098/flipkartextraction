"""
Data Comparison Engine for HANA DB Reporting System
Compares HANA data with Unicommerce reports for reconciliation
"""

import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import numpy as np

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataComparisonEngine:
    """
    Engine for comparing HANA data with Unicommerce reports
    """
    
    def __init__(self):
        """
        Initialize comparison engine
        """
        pass
    
    def compare_with_unicommerce(self, hana_data: pd.DataFrame, 
                                unicommerce_data: pd.DataFrame) -> Dict:
        """
        Compare HANA data with Unicommerce data
        
        Args:
            hana_data: HANA sales DataFrame
            unicommerce_data: Unicommerce sales DataFrame
            
        Returns:
            Dict: Comparison results
        """
        try:
            comparison_result = {
                "hana_total_orders": len(hana_data),
                "unicommerce_total_orders": len(unicommerce_data),
                "matching_orders": 0,
                "discrepancies": [],
                "match_percentage": 0.0,
                "total_sales_hana": 0.0,
                "total_sales_unicommerce": 0.0,
                "sales_variance": 0.0,
                "summary": {}
            }
            
            # Calculate total sales
            if 'Total Value' in hana_data.columns:
                comparison_result['total_sales_hana'] = hana_data['Total Value'].sum()
            
            if 'total_amount' in unicommerce_data.columns:
                comparison_result['total_sales_unicommerce'] = unicommerce_data['total_amount'].sum()
            
            # Calculate sales variance
            if comparison_result['total_sales_unicommerce'] > 0:
                comparison_result['sales_variance'] = (
                    (comparison_result['total_sales_hana'] - comparison_result['total_sales_unicommerce']) / 
                    comparison_result['total_sales_unicommerce'] * 100
                )
            
            # Find matching orders
            matching_data = self._find_matching_orders(hana_data, unicommerce_data)
            comparison_result['matching_orders'] = len(matching_data)
            
            # Calculate match percentage
            if comparison_result['unicommerce_total_orders'] > 0:
                comparison_result['match_percentage'] = (
                    comparison_result['matching_orders'] / comparison_result['unicommerce_total_orders'] * 100
                )
            
            # Identify discrepancies
            discrepancies = self._identify_discrepancies(hana_data, unicommerce_data)
            comparison_result['discrepancies'] = discrepancies
            
            # Generate summary
            comparison_result['summary'] = self._generate_comparison_summary(comparison_result)
            
            logger.info(f"Comparison completed: {comparison_result['match_percentage']:.2f}% match")
            return comparison_result
            
        except Exception as e:
            logger.error(f"Failed to compare data: {str(e)}")
            raise
    
    def identify_discrepancies(self, comparison_result: Dict) -> pd.DataFrame:
        """
        Identify data discrepancies from comparison results
        
        Args:
            comparison_result: Results from compare_with_unicommerce
            
        Returns:
            pd.DataFrame: Discrepancies DataFrame
        """
        try:
            discrepancies = comparison_result.get('discrepancies', [])
            
            if not discrepancies:
                return pd.DataFrame()
            
            # Convert discrepancies to DataFrame
            df = pd.DataFrame(discrepancies)
            
            # Add severity levels
            df['severity'] = df.apply(self._calculate_severity, axis=1)
            
            # Sort by severity and amount
            df = df.sort_values(['severity', 'amount_variance'], ascending=[False, False])
            
            logger.info(f"Identified {len(df)} discrepancies")
            return df
            
        except Exception as e:
            logger.error(f"Failed to identify discrepancies: {str(e)}")
            raise
    
    def generate_reconciliation_report(self, discrepancies: pd.DataFrame) -> str:
        """
        Generate reconciliation report
        
        Args:
            discrepancies: Discrepancies DataFrame
            
        Returns:
            str: Path to reconciliation report file
        """
        try:
            if discrepancies.empty:
                return "No discrepancies found"
            
            # Create reconciliation summary
            summary = {
                'total_discrepancies': len(discrepancies),
                'high_severity': len(discrepancies[discrepancies['severity'] == 'High']),
                'medium_severity': len(discrepancies[discrepancies['severity'] == 'Medium']),
                'low_severity': len(discrepancies[discrepancies['severity'] == 'Low']),
                'total_variance': discrepancies['amount_variance'].sum()
            }
            
            # Save to CSV
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"reconciliation_report_{timestamp}.csv"
            filepath = f"/tmp/{filename}"
            
            discrepancies.to_csv(filepath, index=False)
            
            logger.info(f"Reconciliation report generated: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Failed to generate reconciliation report: {str(e)}")
            raise
    
    def calculate_match_percentage(self, data1: pd.DataFrame, 
                                  data2: pd.DataFrame) -> float:
        """
        Calculate data match percentage
        
        Args:
            data1: First DataFrame
            data2: Second DataFrame
            
        Returns:
            float: Match percentage
        """
        try:
            # Use order ID or document number for matching
            key_columns = ['Document No', 'Order ID', 'DocNum']
            
            for col in key_columns:
                if col in data1.columns and col in data2.columns:
                    matches = set(data1[col].dropna()) & set(data2[col].dropna())
                    total = len(set(data1[col].dropna()) | set(data2[col].dropna()))
                    
                    if total > 0:
                        return len(matches) / total * 100
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Failed to calculate match percentage: {str(e)}")
            return 0.0
    
    def _find_matching_orders(self, hana_data: pd.DataFrame, 
                             unicommerce_data: pd.DataFrame) -> pd.DataFrame:
        """
        Find matching orders between HANA and Unicommerce data
        """
        try:
            # Try different matching strategies
            matching_strategies = [
                self._match_by_order_id,
                self._match_by_document_number,
                self._match_by_customer_and_amount
            ]
            
            for strategy in matching_strategies:
                matches = strategy(hana_data, unicommerce_data)
                if not matches.empty:
                    return matches
            
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"Failed to find matching orders: {str(e)}")
            return pd.DataFrame()
    
    def _match_by_order_id(self, hana_data: pd.DataFrame, 
                          unicommerce_data: pd.DataFrame) -> pd.DataFrame:
        """
        Match orders by order ID
        """
        try:
            if 'ORD ID' in hana_data.columns and 'order_id' in unicommerce_data.columns:
                merged = pd.merge(
                    hana_data, 
                    unicommerce_data, 
                    left_on='ORD ID', 
                    right_on='order_id', 
                    how='inner'
                )
                return merged
            return pd.DataFrame()
        except:
            return pd.DataFrame()
    
    def _match_by_document_number(self, hana_data: pd.DataFrame, 
                                 unicommerce_data: pd.DataFrame) -> pd.DataFrame:
        """
        Match orders by document number
        """
        try:
            if 'Document No' in hana_data.columns and 'invoice_number' in unicommerce_data.columns:
                merged = pd.merge(
                    hana_data, 
                    unicommerce_data, 
                    left_on='Document No', 
                    right_on='invoice_number', 
                    how='inner'
                )
                return merged
            return pd.DataFrame()
        except:
            return pd.DataFrame()
    
    def _match_by_customer_and_amount(self, hana_data: pd.DataFrame, 
                                     unicommerce_data: pd.DataFrame) -> pd.DataFrame:
        """
        Match orders by customer and amount
        """
        try:
            if ('Customer Code' in hana_data.columns and 
                'Total Value' in hana_data.columns and
                'customer_code' in unicommerce_data.columns and
                'total_amount' in unicommerce_data.columns):
                
                # Round amounts for matching
                hana_data_copy = hana_data.copy()
                unicommerce_data_copy = unicommerce_data.copy()
                
                hana_data_copy['amount_rounded'] = hana_data_copy['Total Value'].round(2)
                unicommerce_data_copy['amount_rounded'] = unicommerce_data_copy['total_amount'].round(2)
                
                merged = pd.merge(
                    hana_data_copy, 
                    unicommerce_data_copy, 
                    left_on=['Customer Code', 'amount_rounded'], 
                    right_on=['customer_code', 'amount_rounded'], 
                    how='inner'
                )
                return merged
            return pd.DataFrame()
        except:
            return pd.DataFrame()
    
    def _identify_discrepancies(self, hana_data: pd.DataFrame, 
                               unicommerce_data: pd.DataFrame) -> List[Dict]:
        """
        Identify discrepancies between HANA and Unicommerce data
        """
        try:
            discrepancies = []
            
            # Find orders in HANA but not in Unicommerce
            hana_orders = set(hana_data['Document No'].dropna()) if 'Document No' in hana_data.columns else set()
            unicommerce_orders = set(unicommerce_data['invoice_number'].dropna()) if 'invoice_number' in unicommerce_data.columns else set()
            
            missing_in_unicommerce = hana_orders - unicommerce_orders
            missing_in_hana = unicommerce_orders - hana_orders
            
            # Add missing orders discrepancies
            for order in missing_in_unicommerce:
                discrepancies.append({
                    'type': 'Missing in Unicommerce',
                    'order_id': order,
                    'amount_variance': 0,
                    'description': f'Order {order} exists in HANA but not in Unicommerce'
                })
            
            for order in missing_in_hana:
                discrepancies.append({
                    'type': 'Missing in HANA',
                    'order_id': order,
                    'amount_variance': 0,
                    'description': f'Order {order} exists in Unicommerce but not in HANA'
                })
            
            # Find amount discrepancies for matching orders
            matching_orders = self._find_matching_orders(hana_data, unicommerce_data)
            
            if not matching_orders.empty and 'Total Value' in matching_orders.columns and 'total_amount' in matching_orders.columns:
                for _, row in matching_orders.iterrows():
                    hana_amount = row['Total Value']
                    unicommerce_amount = row['total_amount']
                    
                    if abs(hana_amount - unicommerce_amount) > 0.01:  # Tolerance for rounding
                        discrepancies.append({
                            'type': 'Amount Mismatch',
                            'order_id': row.get('Document No', 'Unknown'),
                            'amount_variance': hana_amount - unicommerce_amount,
                            'hana_amount': hana_amount,
                            'unicommerce_amount': unicommerce_amount,
                            'description': f'Amount mismatch for order {row.get("Document No", "Unknown")}'
                        })
            
            return discrepancies
            
        except Exception as e:
            logger.error(f"Failed to identify discrepancies: {str(e)}")
            return []
    
    def _calculate_severity(self, row) -> str:
        """
        Calculate severity level for discrepancy
        """
        try:
            amount_variance = abs(row.get('amount_variance', 0))
            
            if amount_variance > 10000:
                return 'High'
            elif amount_variance > 1000:
                return 'Medium'
            else:
                return 'Low'
                
        except:
            return 'Low'
    
    def _generate_comparison_summary(self, comparison_result: Dict) -> Dict:
        """
        Generate comparison summary
        """
        try:
            summary = {
                'data_quality': 'Good' if comparison_result['match_percentage'] > 90 else 'Needs Review',
                'reconciliation_status': 'Reconciled' if comparison_result['match_percentage'] > 95 else 'Pending',
                'total_orders_hana': comparison_result['hana_total_orders'],
                'total_orders_unicommerce': comparison_result['unicommerce_total_orders'],
                'matching_orders': comparison_result['matching_orders'],
                'match_percentage': f"{comparison_result['match_percentage']:.2f}%",
                'sales_variance': f"{comparison_result['sales_variance']:.2f}%",
                'discrepancy_count': len(comparison_result['discrepancies'])
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate comparison summary: {str(e)}")
            return {}

def compare_sales_data(hana_sales: pd.DataFrame, unicommerce_sales: pd.DataFrame) -> Dict:
    """
    Compare sales data between HANA and Unicommerce
    
    Args:
        hana_sales: HANA sales DataFrame
        unicommerce_sales: Unicommerce sales DataFrame
        
    Returns:
        Dict: Comparison results
    """
    try:
        engine = DataComparisonEngine()
        return engine.compare_with_unicommerce(hana_sales, unicommerce_sales)
        
    except Exception as e:
        logger.error(f"Failed to compare sales data: {str(e)}")
        raise

def generate_reconciliation_report(hana_data: pd.DataFrame, 
                                 unicommerce_data: pd.DataFrame) -> str:
    """
    Generate reconciliation report between HANA and Unicommerce data
    
    Args:
        hana_data: HANA sales DataFrame
        unicommerce_data: Unicommerce sales DataFrame
        
    Returns:
        str: Path to reconciliation report file
    """
    try:
        engine = DataComparisonEngine()
        
        # Compare data
        comparison_result = engine.compare_with_unicommerce(hana_data, unicommerce_data)
        
        # Identify discrepancies
        discrepancies = engine.identify_discrepancies(comparison_result)
        
        # Generate report
        report_path = engine.generate_reconciliation_report(discrepancies)
        
        logger.info(f"Reconciliation report generated: {report_path}")
        return report_path
        
    except Exception as e:
        logger.error(f"Failed to generate reconciliation report: {str(e)}")
        raise

if __name__ == "__main__":
    # Test the comparison engine
    try:
        # Create sample data
        hana_data = pd.DataFrame({
            'Document No': ['DOC001', 'DOC002', 'DOC003'],
            'Customer Code': ['C001', 'C002', 'C003'],
            'Total Value': [10000, 15000, 20000],
            'ORD ID': ['ORD001', 'ORD002', 'ORD003']
        })
        
        unicommerce_data = pd.DataFrame({
            'invoice_number': ['DOC001', 'DOC002', 'DOC004'],
            'customer_code': ['C001', 'C002', 'C004'],
            'total_amount': [10000, 16000, 25000],
            'order_id': ['ORD001', 'ORD002', 'ORD004']
        })
        
        engine = DataComparisonEngine()
        result = engine.compare_with_unicommerce(hana_data, unicommerce_data)
        
        print(f"✅ Comparison completed:")
        print(f"  - Match percentage: {result['match_percentage']:.2f}%")
        print(f"  - Total discrepancies: {len(result['discrepancies'])}")
        print(f"  - Sales variance: {result['sales_variance']:.2f}%")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
