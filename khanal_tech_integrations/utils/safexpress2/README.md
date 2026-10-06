# Safexpress2 - Production-Grade Integration

A clean, modular, and production-ready implementation of Safexpress API integration for SAP B1 invoice and delivery note management.

## Features

✅ **Clean Architecture**: Modular design with clear separation of concerns  
✅ **Production Ready**: Comprehensive error handling, retry logic, and logging  
✅ **Type Hints**: Full type annotations for better IDE support and maintainability  
✅ **Industry Standard**: Follows SOLID principles and Python best practices  
✅ **Break Proof**: Robust error handling with custom exceptions  
✅ **Well Documented**: Comprehensive docstrings and comments  

## Architecture

```
safexpress2/
├── __init__.py          # Public API exports
├── config.py            # Configuration constants
├── exceptions.py        # Custom exception classes
├── utils.py             # Utility functions
├── auth.py              # Authentication management
├── api_client.py        # Safexpress API client
├── sap_integration.py   # SAP B1 integration
├── pod_service.py       # POD processing service
└── tracking_service.py  # Tracking update service
```

## Module Overview

### `config.py`
Centralized configuration constants including:
- API endpoints
- Invoice series prefixes
- Default values and limits
- Date formats
- SAP field names

### `exceptions.py`
Custom exception hierarchy:
- `SafexpressError` - Base exception
- `SafexpressAuthenticationError` - Auth failures
- `SafexpressAPIError` - API errors
- `SafexpressPODNotFoundError` - POD not found
- `SafexpressDateParsingError` - Date parsing errors
- `SafexpressSAPIntegrationError` - SAP integration errors
- `SafexpressFileUploadError` - File upload errors

### `utils.py`
Utility functions:
- `parse_delivery_date()` - Parse dates with multiple format support
- `retry_with_backoff()` - Retry decorator with exponential backoff
- `format_invoice_number()` - Format invoice numbers for API
- `validate_docentry()` - Validate document entries
- `get_invoice_series_variants()` - Get series name variants

### `auth.py`
Authentication management:
- `SafexpressAuth` class for token management
- Automatic token renewal
- Token expiration checking
- Global instance for convenience

### `api_client.py`
Safexpress API client:
- `get_tracking_by_invoice()` - Get tracking by invoice number
- `get_tracking_by_waybill()` - Get tracking by waybill
- `get_pod_document()` - Download POD document
- Built-in retry logic
- Comprehensive error handling

### `sap_integration.py`
SAP B1 integration:
- `update_invoice_with_pod()` - Update invoice with POD info
- `update_delivery_note_with_tracking()` - Update DN with tracking
- Session management
- Error handling

### `pod_service.py`
POD processing:
- `process_invoices_without_pod()` - Process multiple invoices
- `process_pod_for_invoice()` - Process single invoice
- `get_all_pods_from_last_year()` - Retrieve POD statistics
- S3 upload handling

### `tracking_service.py`
Tracking updates:
- `update_tracking_by_invoice()` - Update tracking via invoices
- `update_tracking_by_waybill()` - Refresh tracking by waybill
- Delivery note updates

## Usage Examples

### Process Invoices Without POD

```python
from khanal_tech_integrations.utils.safexpress2 import process_invoices_without_pod

# Process last 4 days (default)
result = process_invoices_without_pod()

# Process last 365 days (one year)
result = process_invoices_without_pod(days=365, batch_size=50)

print(f"Processed: {result['processed']}, Failed: {result['failed']}")
```

### Get All PODs from Last Year

```python
from khanal_tech_integrations.utils.safexpress2 import get_all_pods_from_last_year

# Get all PODs including completed
stats = get_all_pods_from_last_year(days=365, include_completed=True)

print(f"Total invoices: {stats['total_invoices']}")
print(f"With POD: {stats['with_pod']}")
print(f"Without POD: {stats['without_pod']}")
```

### Update Tracking by Invoice

```python
from khanal_tech_integrations.utils.safexpress2 import update_tracking_by_invoice

# Update tracking for last 20 days
result = update_tracking_by_invoice(days=20)

print(f"Processed: {result['processed']}, Failed: {result['failed']}")
```

### Update Tracking by Waybill

```python
from khanal_tech_integrations.utils.safexpress2 import update_tracking_by_waybill

# Refresh tracking for all delivery notes with waybills
result = update_tracking_by_waybill()

print(f"Processed: {result['processed']}, Failed: {result['failed']}")
```

## Bench Commands

### Process Invoices Without POD

```bash
# Process last 4 days
bench --site <site_name> execute \
  khanal_tech_integrations.utils.safexpress2.pod_service.process_invoices_without_pod

# Process last 365 days
bench --site <site_name> execute \
  khanal_tech_integrations.utils.safexpress2.pod_service.process_invoices_without_pod \
  --kwargs "{'days': 365, 'batch_size': 50}"
```

### Get All PODs from Last Year

```bash
bench --site <site_name> execute \
  khanal_tech_integrations.utils.safexpress2.pod_service.get_all_pods_from_last_year \
  --kwargs "{'days': 365, 'include_completed': True}"
```

### Update Tracking

```bash
# By invoice
bench --site <site_name> execute \
  khanal_tech_integrations.utils.safexpress2.tracking_service.update_tracking_by_invoice \
  --kwargs "{'days': 365}"

# By waybill
bench --site <site_name> execute \
  khanal_tech_integrations.utils.safexpress2.tracking_service.update_tracking_by_waybill
```

## Error Handling

All functions use custom exceptions for better error handling:

```python
from khanal_tech_integrations.utils.safexpress2.exceptions import (
    SafexpressAuthenticationError,
    SafexpressAPIError,
    SafexpressPODNotFoundError,
)

try:
    result = process_pod_for_invoice("12345")
except SafexpressPODNotFoundError:
    print("POD not found for this invoice")
except SafexpressAPIError as e:
    print(f"API error: {e.status_code} - {e.response_text}")
except SafexpressAuthenticationError:
    print("Authentication failed")
```

## Configuration

All configuration is centralized in `config.py`. Key settings:

- `DEFAULT_LOOKBACK_DAYS`: Default days to look back (4)
- `MAX_LOOKBACK_DAYS`: Maximum days (365)
- `DEFAULT_BATCH_SIZE`: Batch size for processing (50)
- `MAX_RETRY_ATTEMPTS`: Maximum retry attempts (3)
- `RETRY_DELAY_SECONDS`: Initial retry delay (2 seconds)

## Logging

The module uses Python's standard logging. Configure logging level:

```python
import logging
logging.getLogger("khanal_tech_integrations.utils.safexpress2").setLevel(logging.DEBUG)
```

## Best Practices

1. **Always handle exceptions**: Use try-except blocks for production code
2. **Use batch processing**: For large datasets, use appropriate batch sizes
3. **Monitor logs**: Check Frappe error logs for detailed error information
4. **Test with small datasets**: Test with small day ranges before processing full year
5. **Check statistics**: Review returned statistics to monitor success rates

## Differences from Legacy Code

1. **Modular Design**: Clear separation of concerns
2. **Type Safety**: Full type hints throughout
3. **Error Handling**: Custom exceptions instead of generic errors
4. **Logging**: Proper logging instead of print statements
5. **Retry Logic**: Built-in retry with exponential backoff
6. **Configuration**: Centralized configuration management
7. **Documentation**: Comprehensive docstrings
8. **Testing Ready**: Dependency injection for easier testing

## Migration Guide

To migrate from legacy `safexpress` to `safexpress2`:

1. Update imports:
   ```python
   # Old
   from khanal_tech_integrations.utils.safexpress.attachpod_to_sap import Get_Waybill_in_ArInvoice
   
   # New
   from khanal_tech_integrations.utils.safexpress2 import process_invoices_without_pod
   ```

2. Update function calls:
   ```python
   # Old
   Get_Waybill_in_ArInvoice(Day=4)
   
   # New
   process_invoices_without_pod(days=4)
   ```

3. Handle exceptions properly:
   ```python
   # Old - generic exception handling
   try:
       # code
   except Exception as e:
       print(str(e))
   
   # New - specific exception handling
   try:
       # code
   except SafexpressPODNotFoundError:
       # handle POD not found
   except SafexpressAPIError as e:
       # handle API error
   ```

## Support

For issues or questions, check:
1. Frappe error logs
2. Python logs (if configured)
3. Function return statistics
4. Exception messages

## License

Part of Khanal Tech Integrations package.

