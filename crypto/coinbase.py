import os, sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from helpers import read_csv, fiat_currencies, warsaw_timezone, convert_rate
from decimal import Decimal
from datetime import datetime

operations_to_skip = ["deposit", "withdrawal", "send", "receive", "reward income"]
operations_to_process = ["advanced trade buy", "advanced trade sell",]

def calculate_tax():
    file_name = 'coinbase.csv'

    if not os.path.exists(file_name):
        print(f'WARNING: Coinbase {file_name} doesnt exist. Skipping')
        return (None, None, None, None)

    transactions = read_csv(file_name)
    przychod_total = Decimal(0)
    koszt_total = Decimal(0)
    fiat_staking_total = Decimal(0)

    for row in transactions:
        if row.get('Transaction Type') is None:
            raise Exception("Coinbase. Missing 'Transaction Type' column")

        type = row['Transaction Type'].lower()
        if type in operations_to_skip:
            continue
        if type == 'convert' and 'USDT' in row['Notes'] and 'USDC' in row['Notes']:
            continue
        if type not in operations_to_process:
            raise Exception(f'Coinbase. Unknown transaction type {type}')

        raw_time = row["Timestamp"].replace('UTC', '').strip() 
        asset = row["Asset"]
        price_currency = row["Price Currency"]
        asOfDate = datetime.strptime(raw_time, '%Y-%m-%d %H:%M:%S').astimezone(warsaw_timezone)
        total = Decimal(str(row["Total (inclusive of fees and/or spread)"].replace('€', '')))
        total_pln = round(convert_rate(asOfDate, total, currency=price_currency), 2)
        if price_currency not in fiat_currencies:
            raise Exception(f"Coinbase. Unknown price currency {price_currency}")
        
        if type == 'advanced trade buy':
            koszt_total += total_pln
        elif type == 'advanced trade sell':
            przychod_total += total_pln
        if asset not in ['USDC', 'USDT']:
            raise Exception(f"Coinbase. Unknown asset {asset}")

    return ("Coinbase", przychod_total, koszt_total, fiat_staking_total)