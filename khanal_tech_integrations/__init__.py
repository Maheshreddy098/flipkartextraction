__version__ = '0.0.1'

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Suppress urllib3 InsecureRequestWarning when using verify=False for SAP/HTTPS (e.g. 103.69.202.108)
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass
