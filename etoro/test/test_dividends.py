import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch
from copy import deepcopy

import calculate_tax as ct

# Deterministic mock: amount * 4 PLN
def mock_convert_rate(asOfDate, amount, currency='USD', dec_places=None):
    rate = Decimal('4')
    result = amount * rate
    if dec_places is not None:
        result = round(result, dec_places)
    return result


def make_dividend_entry(pos_id, amount, date_str='15/06/2025 10:30:00', type=ct.DividendType):
    return {
        'id': pos_id,
        'amount': Decimal(str(amount)),
        'date': datetime.strptime(date_str, ct.excel_date_format),
        'type': type,
        'is_cfd': False,
    }

def make_dividend_tax(pos_id, net_amount, withholding_rate, withholding_amount, date_str='15/06/2025'):
    return {
        'Position ID': pos_id,
        'Instrument Name': 'Test Stock',
        'Net Dividend Received (USD)': Decimal(str(net_amount)),
        'Withholding Tax Rate (%)': Decimal(str(withholding_rate)),
        'Withholding Tax Amount (USD)': Decimal(str(withholding_amount)),
        'Date of Payment': datetime.strptime(date_str, '%d/%m/%Y'),
    }


# ============================================================
# process_dividends
# ============================================================

class TestProcessDividends:
    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_single_matched_dividend(self, mock_cr):
        entries = [make_dividend_entry('1', '8.50')]
        dividend_taxes = {
            '1': [make_dividend_tax('1', '8.50', '0.15', '1.50')]
        }
        result = ct.process_dividends(entries, dividend_taxes)
        income_usd, income_usd_brutto, przychod, podstawa, nalezny, zaplacony, unmatched, interest = result

        assert income_usd == Decimal('8.50')
        assert income_usd_brutto == Decimal('10.00')  # 8.50 + 1.50
        # total_pln = 10.00 * 4 = 40.00
        assert przychod == Decimal('40.00')
        assert zaplacony == round(Decimal('0.15') * Decimal('40.00'), 2)  # 6.00
        # tax_rate (0.19) > withholding (0.15), so nalezny = 0.19 * 40 = 7.60
        assert nalezny == round(Decimal('0.19') * Decimal('40.00'))
        assert len(unmatched) == 0

    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_dividend_with_higher_withholding_than_tax_rate(self, mock_cr):
        entries = [make_dividend_entry('1', '7.00')]
        dividend_taxes = {
            '1': [make_dividend_tax('1', '7.00', '0.30', '3.00')]
        }
        result = ct.process_dividends(entries, dividend_taxes)
        income_usd, income_usd_brutto, przychod, podstawa, nalezny, zaplacony, unmatched, interest = result

        total_usd = Decimal('3.00') + Decimal('7.00')
        total_pln = total_usd * Decimal('4')
        # withholding (0.30) > tax_rate (0.19), so nalezny = withholding_rate * total_pln
        assert nalezny == round(round(Decimal('0.30') * total_pln, 2))

    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_unmatched_dividend_goes_to_unmatched_set(self, mock_cr):
        entries = [make_dividend_entry('99', '5.00')]
        dividend_taxes = {}  # no matching tax entry
        result = ct.process_dividends(entries, dividend_taxes)
        _, _, _, _, _, _, unmatched, _ = result
        assert '99' in unmatched

    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_interest_type_processed_separately(self, mock_cr):
        entries = [make_dividend_entry('1', '10.00', type=ct.InterestType)]
        dividend_taxes = {}
        result = ct.process_dividends(entries, dividend_taxes)
        income_usd, income_usd_brutto, przychod, podstawa, nalezny, zaplacony, unmatched, interest = result

        assert interest == Decimal('10.00')
        assert przychod == Decimal('40.00')  # 10 * 4
        assert nalezny == round(round(Decimal('0.19') * Decimal('40.00'), 2))
        assert zaplacony == 0  # no foreign tax on interest

    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_mixed_dividends_and_interest(self, mock_cr):
        entries = [
            make_dividend_entry('1', '8.50', type=ct.DividendType),
            make_dividend_entry('2', '5.00', type=ct.InterestType),
        ]
        dividend_taxes = {
            '1': [make_dividend_tax('1', '8.50', '0.15', '1.50')]
        }
        result = ct.process_dividends(entries, dividend_taxes)
        income_usd, income_usd_brutto, przychod, podstawa, nalezny, zaplacony, unmatched, interest = result

        assert income_usd == Decimal('8.50')
        assert interest == Decimal('5.00')
        assert len(unmatched) == 0

    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_dividend_mismatch_raises(self, mock_cr):
        entries = [make_dividend_entry('1', '8.50')]
        dividend_taxes = {
            '1': [make_dividend_tax('1', '9.00', '0.15', '1.50')]  # 9.00 != 8.50
        }
        with pytest.raises(Exception):
            ct.process_dividends(entries, dividend_taxes)

    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_sum_mismatch_raises(self, mock_cr):
        entries = [make_dividend_entry('1', '8.50')]
        dividend_taxes = {
            '1': [make_dividend_tax('1', '8.50', '0.15', '1.50')],
            '2': [make_dividend_tax('2', '5.00', '0.10', '0.50')],  # extra unmatched tax
        }
        with pytest.raises(Exception, match="Suma dywidend"):
            ct.process_dividends(entries, dividend_taxes)

    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_leftover_dividend_taxes_raises(self, mock_cr):
        entries = [
            make_dividend_entry('1', '8.50'),
            make_dividend_entry('1', '5.00'),
        ]
        dividend_taxes = {
            '1': [
                make_dividend_tax('1', '8.50', '0.15', '1.50'),
                make_dividend_tax('1', '5.00', '0.10', '0.50'),
                make_dividend_tax('1', '3.00', '0.10', '0.30'),  # extra, won't be consumed
            ]
        }
        with pytest.raises(Exception):
            ct.process_dividends(entries, dividend_taxes)

    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_multiple_dividends_same_position(self, mock_cr):
        entries = [
            make_dividend_entry('1', '8.50', date_str='15/06/2025 10:30:00'),
            make_dividend_entry('1', '5.00', date_str='20/06/2025 10:30:00'),
        ]
        dividend_taxes = {
            '1': [
                make_dividend_tax('1', '8.50', '0.15', '1.50', date_str='15/06/2025'),
                make_dividend_tax('1', '5.00', '0.10', '0.50', date_str='20/06/2025'),
            ]
        }
        result = ct.process_dividends(entries, deepcopy(dividend_taxes))
        income_usd, _, _, _, _, _, unmatched, _ = result
        assert income_usd == Decimal('13.50')
        assert len(unmatched) == 0

    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_no_entries_no_taxes(self, mock_cr):
        result = ct.process_dividends([], {})
        income_usd, income_usd_brutto, przychod, podstawa, nalezny, zaplacony, unmatched, interest = result
        assert income_usd == Decimal('0')
        assert przychod == Decimal('0')
        assert len(unmatched) == 0

    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_non_dividend_type_filtered_out(self, mock_cr):
        """StockType entries are filtered out by the type check, not processed"""
        entries = [make_dividend_entry('1', '5.00', type=ct.StockType)]
        result = ct.process_dividends(entries, {})
        income_usd, _, _, _, _, _, unmatched, _ = result
        assert income_usd == Decimal('0')  # StockType filtered out, not processed
