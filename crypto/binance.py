import os, sys, re
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from helpers import convert_rate, read_csv, warsaw_timezone, fiat_currencies
from decimal import Decimal
from datetime import datetime

operations_to_skip = ["Deposit", "Withdraw", "Savings purchase", "Savings Principal redemption", "transfer_out", "transfer_in", "Binance Card Spending", "Fiat Deposit", "Transfer Between Main and Funding Wallet", "Fiat Withdraw", "Simple Earn Locked Subscription", "Simple Earn Flexible Subscription", "Simple Earn Flexible Redemption"]
operations_to_process = ["Transaction Related", "Savings Interest", "Sell", "Distribution", "Transaction Sold", "Transaction Buy", "Transaction Fee", 'Transaction Revenue', 'Binance Convert', 'Simple Earn Flexible Interest', 'Simple Earn Locked Rewards']

def calculate_tax():
    file_name = 'binance.csv'

    if not os.path.exists(file_name):
        print(f'WARNING: Binance {file_name} doesnt exist. Skipping')
        return(None, None, None, None)

    sheet = read_csv(file_name)

    przychod_total = Decimal(0)
    koszt_total = Decimal(0)
    fiat_staking_total = Decimal(0)

    for row in sheet:
        if row["Account"] == "Card" or row["User ID"] is None:
            continue
        coin = row["Coin"]
        if coin not in fiat_currencies:
            continue

        if row["Account"].upper() not in ["SPOT", "SAVINGS", "CARD", "FUNDING"]:
            raise Exception(f"Unknown account type for Binance: {row['Account']}")

        operation = row["Operation"]
        if operation in operations_to_skip:
            continue
        if operation not in operations_to_process:
            raise Exception(f'Unkown operation for Binance: {operation} for {row["Account"]} and {coin}')

        asOfDate = row['Time'] if isinstance(row['Time'], datetime) else datetime.strptime(row['Time'], '%y-%m-%d %H:%M:%S').astimezone(warsaw_timezone)
        change = Decimal(str(row["Change"]))
        pln = round(convert_rate(asOfDate, change, currency=coin), 2)

        if operation in ["Distribution", "Savings Interest", "Simple Earn Flexible Interest", "Simple Earn Locked Rewards"]:
            fiat_staking_total += pln
        elif operation == "Transaction Fee":
            if change >= 0:
                raise Exception(f"Found positive fee {change}")
            koszt_total -= pln
        elif change < 0:
            koszt_total -= pln
        else:
            przychod_total += pln

    return ("Binance", przychod_total, koszt_total, fiat_staking_total)

if __name__ == "__main__":
    result = calculate_tax()
    if result is not None:
        print(result)