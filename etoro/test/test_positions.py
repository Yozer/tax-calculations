import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

import calculate_tax as ct
from mapping import CryptoCountry, CfdCountry

# Deterministic mock: amount * 4 PLN
def mock_convert_rate(asOfDate, amount, currency='USD', dec_places=None):
    rate = Decimal('4')
    result = amount * rate
    if dec_places is not None:
        result = round(result, dec_places)
    return result


def make_date(s='15/06/2025 10:30:00'):
    return datetime.strptime(s, ct.excel_date_format)


def make_stock_position_real(pos_id='1', open_amount='100', close_amount='120',
                             open_date='01/03/2025 10:00:00', close_date='15/06/2025 10:00:00'):
    return {
        'id': pos_id,
        'type': ct.StockType,
        'is_cfd': False,
        'open_amount': Decimal(open_amount),
        'close_amount': Decimal(close_amount),
        'open_date': make_date(open_date),
        'close_date': make_date(close_date),
        'equity_change': Decimal(close_amount) - Decimal(open_amount),
    }


def make_stock_position_cfd(pos_id='1', equity_change='20',
                            close_date='15/06/2025 10:00:00'):
    return {
        'id': pos_id,
        'type': ct.StockType,
        'is_cfd': True,
        'equity_change': Decimal(equity_change),
        'close_date': make_date(close_date),
    }


def make_crypto_position(pos_id='1', amount='50', date='15/06/2025 10:00:00', equity_change='10'):
    return {
        'id': pos_id,
        'type': ct.CryptoType,
        'is_cfd': False,
        'amount': Decimal(amount),
        'date': make_date(date),
        'equity_change': Decimal(equity_change),
    }


def make_fee_position(pos_id='1', amount='-5', date='15/06/2025 10:00:00'):
    return {
        'id': pos_id,
        'type': ct.FeeType,
        'is_cfd': True,
        'amount': Decimal(amount),
        'date': make_date(date),
    }


def make_adjustment_position(pos_id='1', amount='3', date='15/06/2025 10:00:00', adj_type=ct.AdjustmentType):
    return {
        'id': pos_id,
        'type': adj_type,
        'is_cfd': True,
        'amount': Decimal(amount),
        'date': make_date(date),
        'equity_change': Decimal(amount),
    }


def make_dividend_position(pos_id='1', amount='-2', date='15/06/2025 10:00:00'):
    return {
        'id': pos_id,
        'type': ct.DividendType,
        'is_cfd': False,
        'amount': Decimal(amount),
        'date': make_date(date),
    }


# Minimal transactions/closed_positions/dividends stubs
def stub_transactions(pos_ids):
    return {pid: [{'Type': 'Position closed', 'Details': 'TEST/USD'}] for pid in pos_ids}

def stub_dividends():
    return []


# ============================================================
# process_positions - Stocks (real)
# ============================================================

class TestProcessPositionsStockReal:
    @patch('calculate_tax.get_country_code', return_value='USA')
    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_single_real_stock_profit(self, mock_cr, mock_gcc):
        pos = make_stock_position_real(open_amount='100', close_amount='150')
        transactions = stub_transactions(['1'])
        result = ct.process_positions([pos], ct.StockType, None, transactions, {}, stub_dividends())
        income_usd, fees_usd, przychod, koszty, dochod, neg_div, refunds, adjustments, idx_adj, platform_fees = result

        assert income_usd == Decimal('50')  # 150 - 100
        assert fees_usd == Decimal('0')
        # open: 100 * 4 = 400, close: 150 * 4 = 600
        assert przychod['USA'] == Decimal('600')
        assert koszty['USA'] == Decimal('400')
        assert dochod['USA'] == Decimal('200')

    @patch('calculate_tax.get_country_code', return_value='USA')
    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_single_real_stock_loss(self, mock_cr, mock_gcc):
        pos = make_stock_position_real(open_amount='150', close_amount='100')
        transactions = stub_transactions(['1'])
        result = ct.process_positions([pos], ct.StockType, None, transactions, {}, stub_dividends())
        _, _, przychod, koszty, dochod, _, _, _, _, _ = result

        assert przychod['USA'] == Decimal('400')  # 100 * 4
        assert koszty['USA'] == Decimal('600')    # 150 * 4
        assert dochod['USA'] == Decimal('-200')

    @patch('calculate_tax.get_country_code', return_value='USA')
    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_multiple_countries(self, mock_cr, mock_gcc):
        mock_gcc.side_effect = lambda name, sym: 'USA' if sym == 'AAPL/USD' else 'Niemcy'
        pos1 = make_stock_position_real(pos_id='1', open_amount='100', close_amount='120')
        pos2 = make_stock_position_real(pos_id='2', open_amount='200', close_amount='250')
        transactions = {
            '1': [{'Type': 'Position closed', 'Details': 'AAPL/USD'}],
            '2': [{'Type': 'Position closed', 'Details': 'SAP/EUR'}],
        }
        result = ct.process_positions([pos1, pos2], ct.StockType, None, transactions, {}, stub_dividends())
        _, _, przychod, koszty, dochod, _, _, _, _, _ = result

        assert 'USA' in dochod
        assert 'Niemcy' in dochod
        assert dochod['USA'] == Decimal('80')    # (120-100)*4
        assert dochod['Niemcy'] == Decimal('200') # (250-200)*4


# ============================================================
# process_positions - Stocks (CFD)
# ============================================================

class TestProcessPositionsStockCFD:
    @patch('calculate_tax.get_country_code', return_value=CfdCountry)
    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_cfd_profit(self, mock_cr, mock_gcc):
        pos = make_stock_position_cfd(equity_change='25')
        transactions = stub_transactions(['1'])
        result = ct.process_positions([pos], ct.StockType, None, transactions, {}, stub_dividends())
        _, _, przychod, koszty, dochod, _, _, _, _, _ = result

        # 25 * 4 = 100 PLN profit
        assert przychod[CfdCountry] == Decimal('100')
        assert koszty[CfdCountry] == Decimal('0')

    @patch('calculate_tax.get_country_code', return_value=CfdCountry)
    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_cfd_loss(self, mock_cr, mock_gcc):
        pos = make_stock_position_cfd(equity_change='-25')
        transactions = stub_transactions(['1'])
        result = ct.process_positions([pos], ct.StockType, None, transactions, {}, stub_dividends())
        _, _, przychod, koszty, dochod, _, _, _, _, _ = result

        assert przychod[CfdCountry] == Decimal('0')
        assert koszty[CfdCountry] == Decimal('100')  # |-25 * 4|
        assert dochod[CfdCountry] == Decimal('-100')


# ============================================================
# process_positions - Crypto
# ============================================================

class TestProcessPositionsCrypto:
    @patch('calculate_tax.get_country_code', return_value=CryptoCountry)
    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_crypto_sell_positive(self, mock_cr, mock_gcc):
        pos = make_crypto_position(amount='50', equity_change='10')
        transactions = stub_transactions(['1'])
        result = ct.process_positions([pos], ct.CryptoType, None, transactions, {}, stub_dividends())
        income_usd, _, przychod, koszty, dochod, _, _, _, _, _ = result

        assert income_usd == Decimal('10')
        assert przychod[CryptoCountry] == Decimal('200')  # 50 * 4
        assert koszty[CryptoCountry] == Decimal('0')

    @patch('calculate_tax.get_country_code', return_value=CryptoCountry)
    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_crypto_buy_negative(self, mock_cr, mock_gcc):
        pos = make_crypto_position(amount='-50', equity_change='0')
        transactions = stub_transactions(['1'])
        result = ct.process_positions([pos], ct.CryptoType, None, transactions, {}, stub_dividends())
        _, _, przychod, koszty, dochod, _, _, _, _, _ = result

        assert przychod[CryptoCountry] == Decimal('0')
        assert koszty[CryptoCountry] == Decimal('200')  # |-50 * 4|


# ============================================================
# process_positions - Fees
# ============================================================

class TestProcessPositionsFees:
    @patch('calculate_tax.get_country_code', return_value=CfdCountry)
    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_negative_fee_as_cost(self, mock_cr, mock_gcc):
        fee = make_fee_position(amount='-5')
        transactions = stub_transactions(['1'])
        result = ct.process_positions([fee], ct.StockType, None, transactions, {}, stub_dividends())
        _, fees_usd, przychod, koszty, dochod, _, _, _, _, _ = result

        assert fees_usd == Decimal('-5')
        assert koszty[CfdCountry] == Decimal('20')   # |-5 * 4|
        assert przychod[CfdCountry] == Decimal('0')

    @patch('calculate_tax.get_country_code', return_value=CfdCountry)
    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_positive_fee_as_income(self, mock_cr, mock_gcc):
        fee = make_fee_position(amount='3')
        transactions = stub_transactions(['1'])
        result = ct.process_positions([fee], ct.StockType, None, transactions, {}, stub_dividends())
        _, fees_usd, przychod, koszty, _, _, _, _, _, _ = result

        assert fees_usd == Decimal('3')
        assert przychod[CfdCountry] == Decimal('12')  # 3 * 4
        assert koszty[CfdCountry] == Decimal('0')


# ============================================================
# process_positions - Adjustments / Refunds / IndexAdjustments
# ============================================================

class TestProcessPositionsAdjustments:
    @patch('calculate_tax.get_country_code', return_value=CfdCountry)
    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_positive_adjustment_as_income(self, mock_cr, mock_gcc):
        adj = make_adjustment_position(amount='10', adj_type=ct.AdjustmentType)
        transactions = stub_transactions(['1'])
        result = ct.process_positions([adj], ct.StockType, None, transactions, {}, stub_dividends())
        _, _, przychod, _, _, _, _, adjustments, _, _ = result

        assert przychod[CfdCountry] == Decimal('40')
        assert adjustments == Decimal('10')

    @patch('calculate_tax.get_country_code', return_value=CfdCountry)
    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_negative_adjustment_as_cost(self, mock_cr, mock_gcc):
        adj = make_adjustment_position(amount='-5', adj_type=ct.AdjustmentType)
        transactions = stub_transactions(['1'])
        result = ct.process_positions([adj], ct.StockType, None, transactions, {}, stub_dividends())
        _, _, _, koszty, _, _, _, adjustments, _, _ = result

        assert koszty[CfdCountry] == Decimal('20')
        assert adjustments == Decimal('-5')

    @patch('calculate_tax.get_country_code', return_value=CfdCountry)
    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_refund_counted_in_refunds_sum(self, mock_cr, mock_gcc):
        ref = make_adjustment_position(amount='7', adj_type=ct.RefundType)
        transactions = stub_transactions(['1'])
        result = ct.process_positions([ref], ct.StockType, None, transactions, {}, stub_dividends())
        _, _, _, _, _, _, refunds, _, idx, _ = result

        assert refunds == Decimal('7')
        assert idx == Decimal('0')

    @patch('calculate_tax.get_country_code', return_value=CfdCountry)
    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_index_adjustment_counted_separately(self, mock_cr, mock_gcc):
        idx_adj = make_adjustment_position(amount='4', adj_type=ct.IndexAdjustmentType)
        transactions = stub_transactions(['1'])
        result = ct.process_positions([idx_adj], ct.StockType, None, transactions, {}, stub_dividends())
        _, _, _, _, _, _, refunds, _, idx, _ = result

        assert refunds == Decimal('0')
        assert idx == Decimal('4')


# ============================================================
# process_positions - Negative dividends as fees
# ============================================================

class TestProcessPositionsNegativeDividends:
    @patch('calculate_tax.get_ticker_country', return_value='USA')
    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_unmatched_negative_dividend_becomes_fee(self, mock_cr, mock_gtc):
        div = make_dividend_position(pos_id='1', amount='-3')
        transactions = stub_transactions(['1'])
        closed_positions = {'1': [{'Action': 'Buy TEST'}]}
        unmatched = {'1'}

        result = ct.process_positions([div], ct.StockType, unmatched, transactions, closed_positions, stub_dividends())
        _, _, _, koszty, _, neg_div_sum, _, _, _, _ = result

        assert neg_div_sum == Decimal('3')  # -(amount) = -(-3) = 3
        assert koszty['USA'] == Decimal('12')  # 3 * 4

    @patch('calculate_tax.get_ticker_country', return_value='USA')
    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_unmatched_positive_dividend_not_converted(self, mock_cr, mock_gtc):
        div = make_dividend_position(pos_id='1', amount='3')
        transactions = stub_transactions(['1'])
        unmatched = {'1'}

        result = ct.process_positions([div], ct.StockType, unmatched, transactions, {}, stub_dividends())
        _, _, przychod, koszty, _, neg_div_sum, _, _, _, _ = result

        # positive dividends are not converted to fees (only negative ones)
        assert neg_div_sum == Decimal('0')

    @patch('calculate_tax.get_ticker_country', return_value=CryptoCountry)
    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_crypto_negative_dividend_raises(self, mock_cr, mock_gtc):
        div = make_dividend_position(pos_id='1', amount='-3')
        div['is_cfd'] = False
        transactions = stub_transactions(['1'])
        unmatched = {'1'}

        with pytest.raises(Exception, match="Found a rollover fee for crypto"):
            ct.process_positions([div], ct.StockType, unmatched, transactions, {}, stub_dividends())


# ============================================================
# process_positions - Empty / Mixed
# ============================================================

class TestProcessPositionsEdgeCases:
    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_empty_positions(self, mock_cr):
        result = ct.process_positions([], ct.StockType, None, {}, {}, stub_dividends())
        income, fees, przychod, koszty, dochod, neg_div, refunds, adjustments, idx, platform_fees = result
        assert income == Decimal('0')
        assert fees == Decimal('0')
        assert przychod == {}

    @patch('calculate_tax.get_country_code', return_value='USA')
    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_stock_type_filter_includes_fees_adjustments(self, mock_cr, mock_gcc):
        """StockType processing should also include FeeType, AdjustmentType, RefundType, IndexAdjustmentType"""
        stock = make_stock_position_real(pos_id='1')
        fee = make_fee_position(pos_id='2', amount='-2')
        adj = make_adjustment_position(pos_id='3', amount='1', adj_type=ct.AdjustmentType)
        refund = make_adjustment_position(pos_id='4', amount='0.5', adj_type=ct.RefundType)
        idx = make_adjustment_position(pos_id='5', amount='0.3', adj_type=ct.IndexAdjustmentType)

        transactions = stub_transactions(['1', '2', '3', '4', '5'])
        all_positions = [stock, fee, adj, refund, idx]
        result = ct.process_positions(all_positions, ct.StockType, None, transactions, {}, stub_dividends())
        income_usd, fees_usd, przychod, koszty, dochod, _, _, _, _, _ = result

        # All 5 positions should be processed
        assert income_usd == Decimal('20')  # only stock contributes: 120-100
        assert fees_usd == Decimal('-2')

    @patch('calculate_tax.get_country_code', return_value='USA')
    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_crypto_type_filter_excludes_fees(self, mock_cr, mock_gcc):
        """CryptoType processing should NOT include FeeType positions"""
        crypto = make_crypto_position(pos_id='1')
        fee = make_fee_position(pos_id='2')  # should be excluded
        transactions = stub_transactions(['1', '2'])

        result = ct.process_positions([crypto, fee], ct.CryptoType, None, transactions, {}, stub_dividends())
        _, fees_usd, _, _, _, _, _, _, _, _ = result

        # Fee should not be counted in crypto processing
        assert fees_usd == Decimal('0')

    @patch('calculate_tax.get_country_code', return_value=CfdCountry)
    @patch('calculate_tax.convert_rate', side_effect=mock_convert_rate)
    def test_unknown_position_type_raises(self, mock_cr, mock_gcc):
        pos = {'id': '1', 'type': 'unknown_type', 'is_cfd': True, 'amount': Decimal('5'), 'date': make_date()}
        transactions = stub_transactions(['1'])
        with pytest.raises(Exception, match='Unknown'):
            ct.process_positions([pos], 'unknown_type', None, transactions, {}, stub_dividends())
