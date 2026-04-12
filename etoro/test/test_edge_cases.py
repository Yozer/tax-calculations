import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch, call
from io import StringIO

import calculate_tax as ct
from mapping import CryptoCountry, CfdCountry


def mock_convert_rate(asOfDate, amount, currency='USD', dec_places=None):
    rate = Decimal('4')
    result = amount * rate
    if dec_places is not None:
        result = round(result, dec_places)
    return result


# ============================================================
# do_checks - validation against Financial Summary
# ============================================================

class TestDoChecks:
    @patch('calculate_tax.read_summary')
    def test_all_checks_pass(self, mock_rs, capsys):
        mock_rs.return_value = (
            Decimal('100'),  # stock_sum
            Decimal('50'),   # crypto_sum
            Decimal('30'),   # dividends_sum
            Decimal('-15'),  # fees_sum
            Decimal('5'),    # interest_sum
            Decimal('3'),    # refunds_sum
            Decimal('2'),    # index_adjustments_sum
        )
        ct.do_checks('test.xlsx',
                      income_dividends_usd=Decimal('30'),
                      income_stock_usd=Decimal('97'),
                      fees_stock_usd=Decimal('-10'),
                      negative_dividends=Decimal('-5'),
                      income_crypto_usd=Decimal('50'),
                      fees_crypto_usd=Decimal('0'),
                      refunds_sum_usd=Decimal('3'),
                      interest_sum_usd=Decimal('5'),
                      index_adjustments_sum_usd=Decimal('2'))

        captured = capsys.readouterr()
        assert 'Congratulations' in captured.out

    @patch('calculate_tax.read_summary')
    def test_dividend_check_fails(self, mock_rs, capsys):
        mock_rs.return_value = (Decimal('0'), Decimal('0'), Decimal('30'), Decimal('0'),
                                Decimal('0'), Decimal('0'), Decimal('0'))
        ct.do_checks('test.xlsx', Decimal('25'), Decimal('0'), Decimal('0'), Decimal('0'),
                     Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0'))
        captured = capsys.readouterr()
        assert 'Dividends check failed' in captured.out

    @patch('calculate_tax.read_summary')
    def test_stock_check_fails(self, mock_rs, capsys):
        mock_rs.return_value = (Decimal('100'), Decimal('0'), Decimal('0'), Decimal('0'),
                                Decimal('0'), Decimal('0'), Decimal('0'))
        ct.do_checks('test.xlsx', Decimal('0'), Decimal('50'), Decimal('0'), Decimal('0'),
                     Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0'))
        captured = capsys.readouterr()
        assert 'Stock check failed' in captured.out

    @patch('calculate_tax.read_summary')
    def test_fees_check_fails(self, mock_rs, capsys):
        mock_rs.return_value = (Decimal('0'), Decimal('0'), Decimal('0'), Decimal('-20'),
                                Decimal('0'), Decimal('0'), Decimal('0'))
        ct.do_checks('test.xlsx', Decimal('0'), Decimal('0'), Decimal('-15'), Decimal('-3'),
                     Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0'))
        captured = capsys.readouterr()
        assert 'Fees check failed' in captured.out

    @patch('calculate_tax.read_summary')
    def test_crypto_check_fails(self, mock_rs, capsys):
        mock_rs.return_value = (Decimal('0'), Decimal('50'), Decimal('0'), Decimal('0'),
                                Decimal('0'), Decimal('0'), Decimal('0'))
        ct.do_checks('test.xlsx', Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0'),
                     Decimal('40'), Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0'))
        captured = capsys.readouterr()
        assert 'Crypto check failed' in captured.out

    @patch('calculate_tax.read_summary')
    def test_crypto_fees_nonzero_fails(self, mock_rs, capsys):
        mock_rs.return_value = (Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0'),
                                Decimal('0'), Decimal('0'), Decimal('0'))
        ct.do_checks('test.xlsx', Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0'),
                     Decimal('0'), Decimal('5'), Decimal('0'), Decimal('0'), Decimal('0'))
        captured = capsys.readouterr()
        assert 'feed to be 0' in captured.out

    @patch('calculate_tax.read_summary')
    def test_refund_check_fails(self, mock_rs, capsys):
        mock_rs.return_value = (Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0'),
                                Decimal('0'), Decimal('10'), Decimal('0'))
        ct.do_checks('test.xlsx', Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0'),
                     Decimal('0'), Decimal('0'), Decimal('5'), Decimal('0'), Decimal('0'))
        captured = capsys.readouterr()
        assert 'Incorrect refund sum' in captured.out

    @patch('calculate_tax.read_summary')
    def test_interest_check_fails(self, mock_rs, capsys):
        mock_rs.return_value = (Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0'),
                                Decimal('10'), Decimal('0'), Decimal('0'))
        ct.do_checks('test.xlsx', Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0'),
                     Decimal('0'), Decimal('0'), Decimal('0'), Decimal('5'), Decimal('0'))
        captured = capsys.readouterr()
        assert 'Incorrect interest sum' in captured.out

    @patch('calculate_tax.read_summary')
    def test_index_adjustment_check_fails(self, mock_rs, capsys):
        mock_rs.return_value = (Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0'),
                                Decimal('0'), Decimal('0'), Decimal('10'))
        ct.do_checks('test.xlsx', Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0'),
                     Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0'), Decimal('5'))
        captured = capsys.readouterr()
        assert 'Incorrect index adjustment sum' in captured.out


# ============================================================
# Edge cases and integration-like scenarios
# ============================================================

class TestEdgeCases:
    @patch('calculate_tax.get_country_code', return_value='USA')
    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_zero_amount_fee(self, mock_cr, mock_gcc):
        fee = {'id': '1', 'type': ct.FeeType, 'is_cfd': True,
               'amount': Decimal('0'), 'date': datetime(2025, 6, 15)}
        transactions = {'1': [{'Type': 'Position closed', 'Details': 'TEST/USD'}]}
        result = ct.process_positions([fee], ct.StockType, None, transactions, {}, [])
        _, fees_usd, przychod, koszty, dochod, _, _, _ = result

        assert fees_usd == Decimal('0')
        assert przychod.get('USA', Decimal('0')) == Decimal('0')
        assert koszty.get('USA', Decimal('0')) == Decimal('0')

    @patch('calculate_tax.get_country_code', return_value='USA')
    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_large_amounts(self, mock_cr, mock_gcc):
        pos = {
            'id': '1', 'type': ct.StockType, 'is_cfd': False,
            'open_amount': Decimal('1000000'),
            'close_amount': Decimal('1500000'),
            'open_date': datetime(2025, 1, 15),
            'close_date': datetime(2025, 6, 15),
            'equity_change': Decimal('500000'),
        }
        transactions = {'1': [{'Type': 'Position closed', 'Details': 'TEST/USD'}]}
        result = ct.process_positions([pos], ct.StockType, None, transactions, {}, [])
        income_usd, _, przychod, koszty, dochod, _, _, _ = result

        assert income_usd == Decimal('500000')
        assert dochod['USA'] == Decimal('2000000')  # (1.5M - 1M) * 4

    @patch('calculate_tax.get_country_code', return_value=CfdCountry)
    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_many_mixed_positions(self, mock_cr, mock_gcc):
        positions = []
        for i in range(100):
            amt = Decimal(str(i)) - Decimal('50')  # range from -50 to 49
            positions.append({
                'id': str(i),
                'type': ct.FeeType,
                'is_cfd': True,
                'amount': amt,
                'date': datetime(2025, 6, 15),
            })
        transactions = {str(i): [{'Type': 'Position closed', 'Details': 'TEST/USD'}] for i in range(100)}
        result = ct.process_positions(positions, ct.StockType, None, transactions, {}, [])
        _, fees_usd, przychod, koszty, dochod, _, _, _ = result

        # sum of -50 to 49 = -50
        expected_sum = sum(range(-50, 50))
        assert fees_usd == Decimal(str(expected_sum))

    def test_t2_date_consecutive_weekdays(self):
        """Test T+2 across a full work week"""
        with patch.object(ct, 'use_t_plus_2', True):
            mon = datetime(2025, 6, 2)   # Monday
            assert ct.t2_date(mon) == datetime(2025, 6, 4)   # Wednesday
            tue = datetime(2025, 6, 3)
            assert ct.t2_date(tue) == datetime(2025, 6, 5)   # Friday
            wed = datetime(2025, 6, 4)
            assert ct.t2_date(wed) == datetime(2025, 6, 6)   # Friday... wait, June 6 is Friday
            thu = datetime(2025, 6, 5)
            assert ct.t2_date(thu) == datetime(2025, 6, 9)   # Monday
            fri = datetime(2025, 6, 6)
            assert ct.t2_date(fri) == datetime(2025, 6, 10)  # Tuesday

    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_process_dividends_date_matching(self, mock_cr):
        """Dividend matching uses both amount AND date"""
        entries = [
            {'id': '1', 'amount': Decimal('10'), 'date': datetime(2025, 3, 15, 10, 30),
             'type': ct.DividendType, 'is_cfd': False},
            {'id': '1', 'amount': Decimal('10'), 'date': datetime(2025, 6, 15, 10, 30),
             'type': ct.DividendType, 'is_cfd': False},
        ]
        dividend_taxes = {
            '1': [
                {'Position ID': '1', 'Instrument Name': 'Test',
                 'Net Dividend Received (USD)': Decimal('10'),
                 'Withholding Tax Rate (%)': Decimal('0.15'),
                 'Withholding Tax Amount (USD)': Decimal('1.76'),
                 'Date of Payment': datetime(2025, 3, 15)},
                {'Position ID': '1', 'Instrument Name': 'Test',
                 'Net Dividend Received (USD)': Decimal('10'),
                 'Withholding Tax Rate (%)': Decimal('0.15'),
                 'Withholding Tax Amount (USD)': Decimal('1.76'),
                 'Date of Payment': datetime(2025, 6, 15)},
            ]
        }
        result = ct.process_dividends(entries, dividend_taxes)
        income_usd, _, _, _, _, _, unmatched, _ = result
        assert income_usd == Decimal('20')
        assert len(unmatched) == 0

    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_withdrawal_conversion_fee_in_full_pipeline(self, mock_cr):
        """Withdrawal conversion fee should appear as cost in stock position processing"""
        fee = {'id': '1', 'type': ct.FeeType, 'is_cfd': True,
               'amount': Decimal('-10'), 'date': datetime(2025, 6, 15)}
        transactions = {'1': [{'Type': 'Position closed', 'Details': 'TEST/USD'}]}

        result = ct.process_positions([fee], ct.StockType, None, transactions, {}, [])
        _, fees_usd, przychod, koszty, dochod, _, _, _ = result

        assert fees_usd == Decimal('-10')
        # is_cfd=True causes get_ticker_country to return CfdCountry directly
        assert koszty[CfdCountry] == Decimal('40')  # 10 * 4

    @patch('calculate_tax.get_country_code', return_value=CfdCountry)
    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_mixed_stock_cfd_and_real(self, mock_cr, mock_gcc):
        """Mix of CFD and real stock positions"""
        mock_gcc.side_effect = lambda name, sym: CfdCountry if sym == 'OIL/USD' else 'USA'

        cfd_pos = {
            'id': '1', 'type': ct.StockType, 'is_cfd': True,
            'equity_change': Decimal('30'),
            'close_date': datetime(2025, 6, 15),
        }
        real_pos = {
            'id': '2', 'type': ct.StockType, 'is_cfd': False,
            'open_amount': Decimal('100'), 'close_amount': Decimal('140'),
            'open_date': datetime(2025, 3, 1), 'close_date': datetime(2025, 6, 15),
            'equity_change': Decimal('40'),
        }
        transactions = {
            '1': [{'Type': 'Position closed', 'Details': 'OIL/USD'}],
            '2': [{'Type': 'Position closed', 'Details': 'AAPL/USD'}],
        }
        result = ct.process_positions([cfd_pos, real_pos], ct.StockType, None, transactions, {}, [])
        income_usd, _, przychod, koszty, dochod, _, _, _ = result

        assert income_usd == Decimal('70')  # 30 + 40
        assert przychod[CfdCountry] == Decimal('120')  # 30 * 4
        assert dochod['USA'] == Decimal('160')  # (140-100) * 4

    def test_group_by_pos_id_preserves_order(self):
        txns = [
            {"Position ID": "1", "seq": 1},
            {"Position ID": "1", "seq": 2},
            {"Position ID": "1", "seq": 3},
        ]
        result = ct.group_by_pos_id(txns)
        assert [x['seq'] for x in result['1']] == [1, 2, 3]

    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_process_dividends_only_unmatched_returns_zero_income(self, mock_cr):
        """All dividends unmatched -> income_dividends_usd stays 0"""
        entries = [
            {'id': '99', 'amount': Decimal('5'), 'date': datetime(2025, 6, 15),
             'type': ct.DividendType, 'is_cfd': False},
        ]
        result = ct.process_dividends(entries, {})
        income_usd, _, _, _, _, _, unmatched, _ = result
        assert income_usd == Decimal('0')
        assert '99' in unmatched

    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_tax_rate_constant(self, mock_cr):
        assert ct.tax_rate == Decimal('0.19')

    @patch('calculate_tax.get_country_code', return_value='USA')
    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_stock_with_zero_equity_change(self, mock_cr, mock_gcc):
        pos = {
            'id': '1', 'type': ct.StockType, 'is_cfd': False,
            'open_amount': Decimal('100'), 'close_amount': Decimal('100'),
            'open_date': datetime(2025, 3, 1), 'close_date': datetime(2025, 6, 15),
            'equity_change': Decimal('0'),
        }
        transactions = {'1': [{'Type': 'Position closed', 'Details': 'TEST/USD'}]}
        result = ct.process_positions([pos], ct.StockType, None, transactions, {}, [])
        income_usd, _, przychod, koszty, dochod, _, _, _ = result

        assert income_usd == Decimal('0')
        assert dochod['USA'] == Decimal('0')
