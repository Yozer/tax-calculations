import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

from unittest.mock import patch
from datetime import datetime
from decimal import Decimal

# Mock convert_rate before importing calculate_tax so we don't hit NBP API
# Returns amount * 4 (simulating ~4 PLN/USD rate) for deterministic tests
def mock_convert_rate(asOfDate, amount, currency='USD', dec_places=None):
    rate = Decimal('4')
    result = amount * rate
    if dec_places is not None:
        result = round(result, dec_places)
    return result

# Mock get_country_code to avoid HTTP calls to eToro API
def mock_get_country_code(stock_name, stock_symbol):
    if stock_symbol is None:
        return 'USA'
    symbol_lower = stock_symbol.lower()
    if 'btc' in symbol_lower or 'eth' in symbol_lower:
        from calculate_tax import CryptoCountry
        return CryptoCountry
    return 'USA'
