"""
Inventory Report Queries Registry

This module loads all SQL queries for inventory reports and makes them available
via a centralized registry. Queries are organized by report category.

Usage:
    from khanal_tech_integrations.queries.inventory import QUERY_REGISTRY
    
    query = QUERY_REGISTRY['summary'].format(schema=schema)
    cursor.execute(query, params)
"""

from .overview import *
from .warehouse import *
from .slow_moving import *
from .expiry import *
from .abc import *
from .procurement import *
from .product_specs import *
from .warehouse_batch import *
from .batch_availability import *
from .production_trace import *
from .sap_b1_batch_inventory import *

# Central registry - all queries accessible by name
QUERY_REGISTRY = {
    # Overview/Summary
    'summary': SUMMARY_QUERY,
    
    # Warehouse
    'warehouse_breakdown': WAREHOUSE_BREAKDOWN_QUERY,
    'top_items_value': TOP_ITEMS_VALUE_QUERY,
    'top_items_qty': TOP_ITEMS_QTY_QUERY,
    
    # Slow Moving
    'slow_moving': SLOW_MOVING_QUERY,
    'slow_moving_summary': SLOW_MOVING_SUMMARY_QUERY,
    
    # Expiry
    'expiry_summary': EXPIRY_SUMMARY_QUERY,
    'expiring_batches': EXPIRING_BATCHES_QUERY,
    'expiring_by_warehouse': EXPIRING_BY_WAREHOUSE_QUERY,
    
    # ABC Analysis
    'abc_analysis': ABC_ANALYSIS_QUERY,
    
    # Procurement
    'procurement_rows': PROCUREMENT_ROWS_QUERY,
    'procurement_summary_vendor': PROCUREMENT_SUMMARY_VENDOR_QUERY,
    'procurement_summary_warehouse': PROCUREMENT_SUMMARY_WAREHOUSE_QUERY,
    'procurement_summary_material_type': PROCUREMENT_SUMMARY_MATERIAL_TYPE_QUERY,
    'procurement_summary_totals': PROCUREMENT_SUMMARY_TOTALS_QUERY,
    
    # Product Specs
    'product_specs_rows': PRODUCT_SPECS_ROWS_QUERY,
    'product_specs_summary_flavour': PRODUCT_SPECS_SUMMARY_FLAVOUR_QUERY,
    
                # Warehouse Batch
                'warehouse_batch_stock': WAREHOUSE_BATCH_STOCK_QUERY,
                'warehouse_batch_totals': WAREHOUSE_BATCH_TOTALS_QUERY,
                
                # Batch Availability
                'batch_availability_rows': BATCH_AVAILABILITY_ROWS_QUERY,
                'batch_availability_summary': BATCH_AVAILABILITY_SUMMARY_QUERY,
                'batch_availability_summary_warehouse': BATCH_AVAILABILITY_SUMMARY_WAREHOUSE_QUERY,
                
                # Production Trace
                'production_trace_root_batches': PRODUCTION_TRACE_ROOT_BATCHES_QUERY,
                'production_trace_consumption_movements': PRODUCTION_TRACE_CONSUMPTION_MOVEMENTS_QUERY,
                'production_trace_document_info_60': PRODUCTION_TRACE_DOCUMENT_INFO_60_QUERY,
                'production_trace_document_info_67': PRODUCTION_TRACE_DOCUMENT_INFO_67_QUERY,
                'production_trace_output_batches': PRODUCTION_TRACE_OUTPUT_BATCHES_QUERY,

    # SAP B1 Batch Inventory (Raw / Finished)
    'sap_b1_batch_inventory_rows': SAP_B1_BATCH_INVENTORY_ROWS_QUERY,
    'sap_b1_batch_inventory_summary': SAP_B1_BATCH_INVENTORY_SUMMARY_QUERY,
}
