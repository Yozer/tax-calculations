import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

import calculate_tax as ct


def make_transaction(pos_id='100', trans_type='Overnight fee', amount='10.50',
                     date='15/06/2025 10:30:00', details='daily',
                     asset_type='CFD', realized_equity='0'):
    return {
        'Position ID': pos_id,
        'Type': trans_type,
        'Amount': amount,
        'Date': date,
        'Details': details,
        'Asset type': asset_type,
        'Realized Equity Change': realized_equity,
    }


# ============================================================
# process_interest_payment
# ============================================================

class TestProcessInterestPayment:
    def test_basic(self):
        txn = make_transaction(pos_id='42', amount='5.00', date='10/03/2025 12:00:00')
        result = ct.process_interest_payment(txn)
        assert result['id'] == '42'
        assert result['amount'] == Decimal('5.00')
        assert result['type'] == ct.InterestType
        assert result['is_cfd'] is True
        assert result['equity_change'] == Decimal('5.00')
        assert result['date'] == datetime(2025, 3, 10, 12, 0, 0)

    def test_negative_amount(self):
        txn = make_transaction(amount='-3.50')
        result = ct.process_interest_payment(txn)
        assert result['amount'] == Decimal('-3.50')
        assert result['equity_change'] == Decimal('-3.50')


# ============================================================
# process_adjustment
# ============================================================

class TestProcessAdjustment:
    def test_adjustment_type(self):
        txn = make_transaction(trans_type='Adjustment', amount='2.00')
        result = ct.process_adjustment(txn)
        assert result['type'] == ct.AdjustmentType
        assert result['amount'] == Decimal('2.00')
        assert result['is_cfd'] is True

    def test_index_price_adjustment_type(self):
        txn = make_transaction(trans_type='Index price adjustment', amount='-1.50')
        result = ct.process_adjustment(txn)
        assert result['type'] == ct.IndexAdjustmentType
        assert result['amount'] == Decimal('-1.50')


# ============================================================
# process_rollover_fee
# ============================================================

class TestProcessRolloverFee:
    def test_overnight_fee_daily(self):
        txn = make_transaction(trans_type='Overnight fee', details='daily', amount='-2.00', asset_type='CFD')
        result = ct.process_rollover_fee(txn)
        assert result['type'] == ct.FeeType
        assert result['amount'] == Decimal('-2.00')
        assert result['is_cfd'] is True

    def test_overnight_fee_weekend(self):
        txn = make_transaction(trans_type='Overnight fee', details='weekend fee', amount='-3.00', asset_type='CFD')
        result = ct.process_rollover_fee(txn)
        assert result['type'] == ct.FeeType

    def test_sdrt(self):
        txn = make_transaction(trans_type='SDRT', details='whatever', amount='-0.50', asset_type='Stocks')
        result = ct.process_rollover_fee(txn)
        assert result['type'] == ct.FeeType
        assert result['is_cfd'] is False

    def test_dividend(self):
        txn = make_transaction(trans_type='Dividend', details='some dividend', amount='15.00', asset_type='Stocks')
        result = ct.process_rollover_fee(txn)
        assert result['type'] == ct.DividendType
        assert result['amount'] == Decimal('15.00')

    def test_overnight_refund_daily(self):
        txn = make_transaction(trans_type='Overnight refund', details='daily', amount='1.00', asset_type='CFD')
        result = ct.process_rollover_fee(txn)
        assert result['type'] == ct.RefundType
        assert result['amount'] == Decimal('1.00')

    def test_weekend_refund(self):
        txn = make_transaction(trans_type='Weekend refund', details='weekend fee', amount='0.50', asset_type='CFD')
        result = ct.process_rollover_fee(txn)
        assert result['type'] == ct.RefundType

    def test_negative_refund_raises(self):
        txn = make_transaction(trans_type='Overnight refund', details='daily', amount='-1.00', asset_type='CFD')
        with pytest.raises(Exception, match='Negative refund'):
            ct.process_rollover_fee(txn)

    def test_negative_weekend_refund_raises(self):
        txn = make_transaction(trans_type='Weekend refund', details='weekend fee', amount='-0.50', asset_type='CFD')
        with pytest.raises(Exception, match='Negative refund'):
            ct.process_rollover_fee(txn)

    def test_unknown_fee_type_raises(self):
        txn = make_transaction(trans_type='Overnight fee', details='unknown_detail', amount='-1.00', asset_type='CFD')
        with pytest.raises(Exception, match='Unkown fee'):
            ct.process_rollover_fee(txn)

    def test_unknown_refund_type_raises(self):
        txn = make_transaction(trans_type='Overnight refund', details='weekly', amount='1.00', asset_type='CFD')
        with pytest.raises(Exception, match='Unkown fee'):
            ct.process_rollover_fee(txn)

    def test_non_cfd_asset(self):
        txn = make_transaction(trans_type='Overnight fee', details='daily', amount='-1.00', asset_type='Stocks')
        result = ct.process_rollover_fee(txn)
        assert result['is_cfd'] is False

    def test_empty_asset_type_raises(self):
        txn = make_transaction(trans_type='Overnight fee', details='daily', amount='-1.00', asset_type='')
        txn['pos_id'] = txn['Position ID']  # is_asset_cfd accesses r["pos_id"]
        with pytest.raises(Exception, match='Empty asset type'):
            ct.process_rollover_fee(txn)
