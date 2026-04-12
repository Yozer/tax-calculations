"""Debug script to find reconciliation discrepancies between Account Activity and Financial Summary."""
import os, sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from openpyxl import load_workbook
from decimal import Decimal
from helpers import convert_sheet

year = 2025
fname = f'statement_{year}.xlsx'

workbook = load_workbook(filename=fname)

# --- Financial Summary ---
print("=" * 60)
print("FINANCIAL SUMMARY")
print("=" * 60)
summary = convert_sheet(workbook['Financial Summary'])
amount_col = 'Amount\n in (USD)'
for row in summary:
    print(f"  {row['Name']}: {row[amount_col]}")

# --- Account Activity breakdown ---
print()
print("=" * 60)
print("ACCOUNT ACTIVITY BREAKDOWN BY TYPE")
print("=" * 60)
transactions = convert_sheet(workbook['Account Activity'])

by_type = {}
for t in transactions:
    tt = t['Type']
    if tt not in by_type:
        by_type[tt] = {'count': 0, 'sum': Decimal('0'), 'items': []}
    amount = Decimal(str(t['Amount']))
    by_type[tt]['count'] += 1
    by_type[tt]['sum'] += amount
    by_type[tt]['items'].append(t)

for tt, data in sorted(by_type.items(), key=lambda x: x[0]):
    print(f"  {tt}: count={data['count']}, sum=${data['sum']}")

# --- Commission details ---
print()
print("=" * 60)
print("COMMISSION TRANSACTIONS")
print("=" * 60)
for t in transactions:
    if t['Type'] == 'Commission':
        print(f"  PosID={t['Position ID']} Amount={t['Amount']} Asset={t['Asset type']} Date={t['Date']} Details={t['Details']}")

# --- Withdrawal Conversion Fee details ---
print()
print("=" * 60)
print("WITHDRAWAL CONVERSION FEE TRANSACTIONS")
print("=" * 60)
for t in transactions:
    if t['Type'] == 'Withdrawal Conversion Fee':
        print(f"  PosID={t['Position ID']} Amount={t['Amount']} Date={t['Date']}")

# --- Refund/Adjustment/Weekend refund/Overnight refund details ---
print()
print("=" * 60)
print("REFUND/ADJUSTMENT TRANSACTIONS")
print("=" * 60)
refund_sum = Decimal('0')
adj_sum = Decimal('0')
for t in transactions:
    if t['Type'] in ['Overnight refund', 'Weekend refund']:
        amt = Decimal(str(t['Amount']))
        refund_sum += amt
        print(f"  {t['Type']}: PosID={t['Position ID']} Amount={t['Amount']} Details={t['Details']}")
    elif t['Type'] in ['Adjustment', 'Index price adjustment']:
        amt = Decimal(str(t['Amount']))
        adj_sum += amt
        print(f"  {t['Type']}: PosID={t['Position ID']} Amount={t['Amount']} Details={t['Details']}")

print(f"\n  Refund total: ${refund_sum}")
print(f"  Adjustment total: ${adj_sum}")

# --- Fees breakdown ---
print()
print("=" * 60)
print("FEE TRANSACTIONS (Overnight fee, SDRT)")
print("=" * 60)
fee_sum = Decimal('0')
for t in transactions:
    if t['Type'] in ['Overnight fee', 'SDRT']:
        amt = Decimal(str(t['Amount']))
        fee_sum += amt
print(f"  Fee total (Overnight fee + SDRT): ${fee_sum}")

# --- Check: does Commission show up in the summary anywhere? ---
print()
print("=" * 60)
print("TRYING TO RECONCILE")
print("=" * 60)
commission_sum = sum(Decimal(str(t['Amount'])) for t in transactions if t['Type'] == 'Commission')
withdrawal_conv_sum = sum(Decimal(str(t['Amount'])) for t in transactions if t['Type'] == 'Withdrawal Conversion Fee')
print(f"  Commission total: ${commission_sum}")
print(f"  Withdrawal Conversion Fee total: ${withdrawal_conv_sum}")

# Stock equity changes
stock_equity = Decimal('0')
for t in transactions:
    if t['Type'] == 'Position closed' and t['Asset type'] in ['Stocks', 'ETF', 'CFD']:
        stock_equity += Decimal(str(t['Realized Equity Change']))
print(f"  Stock/ETF/CFD equity changes sum: ${stock_equity}")

# Crypto equity changes
crypto_equity = Decimal('0')
for t in transactions:
    if t['Type'] in ['Position closed', 'Open Position'] and t['Asset type'] == 'Crypto':
        crypto_equity += Decimal(str(t['Realized Equity Change']))
print(f"  Crypto equity changes sum: ${crypto_equity}")

print()
print("Expected stock_sum from summary should = stock_equity + refunds?")
print(f"  stock_equity + refund_sum + adj_sum = {stock_equity + refund_sum + adj_sum}")
print(f"  stock_equity + commission_sum = {stock_equity + commission_sum}")
print(f"  stock_equity + commission_sum + withdrawal_conv_sum = {stock_equity + commission_sum + withdrawal_conv_sum}")
