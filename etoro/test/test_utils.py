import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import calculate_tax as ct


# ============================================================
# t2_date
# ============================================================

class TestT2Date:
    def test_t_plus_2_disabled_returns_same_date(self):
        date = datetime(2025, 3, 10)  # Monday
        with patch.object(ct, 'use_t_plus_2', False):
            assert ct.t2_date(date) == date

    def test_t_plus_2_enabled_monday(self):
        date = datetime(2025, 3, 10)  # Monday
        with patch.object(ct, 'use_t_plus_2', True):
            result = ct.t2_date(date)
            assert result == datetime(2025, 3, 12)  # Wednesday

    def test_t_plus_2_enabled_wednesday(self):
        date = datetime(2025, 3, 12)  # Wednesday
        with patch.object(ct, 'use_t_plus_2', True):
            result = ct.t2_date(date)
            assert result == datetime(2025, 3, 14)  # Friday

    def test_t_plus_2_enabled_thursday_skips_weekend(self):
        date = datetime(2025, 3, 13)  # Thursday
        with patch.object(ct, 'use_t_plus_2', True):
            result = ct.t2_date(date)
            assert result == datetime(2025, 3, 17)  # Monday (skips Sat+Sun)

    def test_t_plus_2_enabled_friday_skips_weekend(self):
        date = datetime(2025, 3, 14)  # Friday
        with patch.object(ct, 'use_t_plus_2', True):
            result = ct.t2_date(date)
            assert result == datetime(2025, 3, 18)  # Tuesday

    def test_t_plus_2_new_years_day_skipped(self):
        # Dec 30 (Tuesday) + 2 business days = Jan 1 (Thu) -> but Jan 1 is skipped -> Jan 2
        date = datetime(2024, 12, 30)
        with patch.object(ct, 'use_t_plus_2', True):
            result = ct.t2_date(date)
            assert result == datetime(2025, 1, 2)

    def test_t_plus_2_saturday_input(self):
        date = datetime(2025, 3, 15)  # Saturday
        with patch.object(ct, 'use_t_plus_2', True):
            result = ct.t2_date(date)
            assert result == datetime(2025, 3, 18)  # Tuesday (Mon + Tue = 2 working days)


# ============================================================
# group_by_pos_id
# ============================================================

class TestGroupByPosId:
    def test_empty_list(self):
        assert ct.group_by_pos_id([]) == {}

    def test_single_transaction(self):
        txns = [{"Position ID": "123", "data": "a"}]
        result = ct.group_by_pos_id(txns)
        assert result == {"123": [{"Position ID": "123", "data": "a"}]}

    def test_multiple_transactions_same_pos(self):
        txns = [
            {"Position ID": "1", "data": "a"},
            {"Position ID": "1", "data": "b"},
        ]
        result = ct.group_by_pos_id(txns)
        assert len(result["1"]) == 2

    def test_multiple_positions(self):
        txns = [
            {"Position ID": "1", "data": "a"},
            {"Position ID": "2", "data": "b"},
            {"Position ID": "1", "data": "c"},
        ]
        result = ct.group_by_pos_id(txns)
        assert len(result) == 2
        assert len(result["1"]) == 2
        assert len(result["2"]) == 1


# ============================================================
# parse_decimal
# ============================================================

class TestParseDecimal:
    def test_integer(self):
        assert ct.parse_decimal(100) == Decimal('100')

    def test_float(self):
        assert ct.parse_decimal(10.5) == Decimal('10.5')

    def test_string(self):
        assert ct.parse_decimal('99.99') == Decimal('99.99')

    def test_negative(self):
        assert ct.parse_decimal(-5.25) == Decimal('-5.25')

    def test_zero(self):
        assert ct.parse_decimal(0) == Decimal('0')


# ============================================================
# parse_date
# ============================================================

class TestParseDate:
    def test_valid_date(self):
        result = ct.parse_date('15/06/2025 10:30:00')
        assert result == datetime(2025, 6, 15, 10, 30, 0)

    def test_midnight(self):
        result = ct.parse_date('01/01/2025 00:00:00')
        assert result == datetime(2025, 1, 1, 0, 0, 0)

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            ct.parse_date('2025-06-15')


# ============================================================
# is_asset_cfd
# ============================================================

class TestIsAssetCfd:
    def test_cfd_returns_true(self):
        assert ct.is_asset_cfd({'Asset type': 'CFD', 'pos_id': '1'}) is True

    def test_stocks_returns_false(self):
        assert ct.is_asset_cfd({'Asset type': 'Stocks', 'pos_id': '1'}) is False

    def test_etf_returns_false(self):
        assert ct.is_asset_cfd({'Asset type': 'ETF', 'pos_id': '1'}) is False

    def test_crypto_returns_false(self):
        assert ct.is_asset_cfd({'Asset type': 'Crypto', 'pos_id': '1'}) is False

    def test_empty_string_raises(self):
        with pytest.raises(Exception, match='Empty asset type'):
            ct.is_asset_cfd({'Asset type': '', 'pos_id': '1'})

    def test_none_raises(self):
        with pytest.raises(Exception, match='Empty asset type'):
            ct.is_asset_cfd({'Asset type': None, 'pos_id': '1'})


# ============================================================
# get_asset_type
# ============================================================

class TestGetAssetType:
    def test_stocks(self):
        assert ct.get_asset_type({'Asset type': 'Stocks'}) == ct.StockType

    def test_etf(self):
        assert ct.get_asset_type({'Asset type': 'ETF'}) == ct.StockType

    def test_cfd(self):
        assert ct.get_asset_type({'Asset type': 'CFD'}) == ct.StockType

    def test_crypto(self):
        assert ct.get_asset_type({'Asset type': 'Crypto'}) == ct.CryptoType

    def test_unknown_raises(self):
        with pytest.raises(Exception, match='Failed to parse'):
            ct.get_asset_type({'Asset type': 'Futures'})


# ============================================================
# get_ticker_country
# ============================================================

class TestGetTickerCountry:
    def test_crypto_position_returns_crypto_country(self):
        position = {'id': '1', 'type': ct.CryptoType, 'is_cfd': False}
        transactions = {'1': [{'Type': 'Open Position', 'Details': 'BTC/USD'}]}
        result = ct.get_ticker_country(position, transactions, {}, {})
        assert result == ct.CryptoCountry

    def test_cfd_position_returns_cfd_country(self):
        position = {'id': '1', 'type': ct.StockType, 'is_cfd': True}
        transactions = {'1': [{'Type': 'Position closed', 'Details': 'AAPL/USD'}]}
        result = ct.get_ticker_country(position, transactions, {}, {})
        assert result == ct.CfdCountry

    def test_position_not_in_transactions_raises(self):
        position = {'id': '999', 'type': ct.StockType, 'is_cfd': False}
        with pytest.raises(Exception, match='Logic error'):
            ct.get_ticker_country(position, {}, {}, {})

    def test_unexpected_type_raises(self):
        position = {'id': '1', 'type': ct.DividendType, 'is_cfd': False}
        transactions = {'1': [{'Type': 'Dividend', 'Details': 'X'}]}
        with pytest.raises(Exception, match='Unexpected position type'):
            ct.get_ticker_country(position, transactions, {}, {})

    @patch('calculate_tax.get_country_code', return_value='USA')
    def test_stock_with_closed_position(self, mock_gcc):
        position = {'id': '1', 'type': ct.StockType, 'is_cfd': False}
        transactions = {'1': [{'Type': 'Position closed', 'Details': 'AAPL/USD'}]}
        closed_positions = {'1': [{'Action': 'Buy AAPL'}]}
        result = ct.get_ticker_country(position, transactions, closed_positions, {})
        assert result == 'USA'
        mock_gcc.assert_called_once_with('Buy AAPL', 'AAPL/USD')

    @patch('calculate_tax.get_country_code', return_value='USA')
    def test_stock_without_closed_position_uses_dividend(self, mock_gcc):
        position = {'id': '1', 'type': ct.StockType, 'is_cfd': False}
        transactions = {'1': [{'Type': 'Dividend', 'Details': 'AAPL/USD'}]}
        dividends = {'1': [{'Instrument Name': 'Apple Inc'}]}
        result = ct.get_ticker_country(position, transactions, {}, dividends)
        assert result == 'USA'
        mock_gcc.assert_called_once_with('Apple Inc', 'AAPL/USD')

    @patch('calculate_tax.get_country_code', return_value='USA')
    def test_fee_type_uses_country_lookup(self, mock_gcc):
        position = {'id': '1', 'type': ct.FeeType, 'is_cfd': False}
        transactions = {'1': [{'Type': 'Position closed', 'Details': 'AAPL/USD'}]}
        closed_positions = {'1': [{'Action': 'Buy AAPL'}]}
        result = ct.get_ticker_country(position, transactions, closed_positions, {})
        assert result == 'USA'
