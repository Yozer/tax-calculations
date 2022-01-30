import os, sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from openpyxl import load_workbook
from helpers import convert_rate, convert_sheet, warsaw_timezone
from decimal import Decimal

file_name = 'all_binance.xlsx'
operations_to_skip = ["Deposit", "Withdraw", "Savings purchase", "Savings Principal redemption", "transfer_out", "transfer_in"]
operations_to_process = ["Transaction Related", "Savings Interest", "Distribution", "Sell", "Fee"]

def calculate_tax():
    if not os.path.exists(file_name):
        print(f'WARNING: Binance {file_name} doesnt exist. Skipping')
        return

    workbook = load_workbook(filename=file_name)
    sheet = convert_sheet(workbook[workbook.sheetnames[0]])

    przychod_total = Decimal(0)
    koszt_total = Decimal(0)
    fiat_staking_total = Decimal(0)

    for row in sheet:
        if row["Account"] == "Card" or row["User_ID"] is None:
            continue
        if row["Account"] != "Spot":
            raise Exception(f"Unknown account type for Binance {row['Account']}")

        operation = row["Operation"]
        if operation in operations_to_skip:
            continue

        if row["Coin"] != "EUR":
            raise Exception(F"Unknown coin for Binance {row['Coin']}")

        asOfDate = row["UTC_Time"].astimezone(warsaw_timezone)
        change = Decimal(str(row["Change"]))
        pln = convert_rate(asOfDate, change, currency=row["Coin"])

        if operation in ["Distribution", "Savings Interest"]:
            fiat_staking_total += pln
        elif operation == "Fee":
            if change >= 0:
                raise Exception(f"Found positive fee {change}")
            koszt_total -= pln
        elif change < 0:
            koszt_total -= pln
        else:
            przychod_total += pln

    return ("Binance", round(przychod_total, 2), round(koszt_total, 2), round(fiat_staking_total, 2))