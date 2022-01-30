import os, sys, re
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from openpyxl import load_workbook
from helpers import convert_rate, convert_sheet, warsaw_timezone, fiat_currencies
from decimal import Decimal

operations_to_skip = ["Deposit", "Withdraw", "Savings purchase", "Savings Principal redemption", "transfer_out", "transfer_in"]
operations_to_process = ["Transaction Related", "Savings Interest", "Sell", "Fee", "Distribution"]

# export Wallet -> Transaction history -> Generate all statements for EUR only
def calculate_tax():
    file_name = 'binance_transaction_history.xlsx'

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
        if operation not in operations_to_process:
            raise Exception(f'Unkown operation for Binance: {operation}')

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

# used for checks
# export: "Trade History" and put to 'Trade History' sheet
# export Earn history of interest only and put to 'Interest' sheet
def calculate_tax2():
    file_name = 'binance_trade_interest.xlsx'

    if not os.path.exists(file_name):
        print(f'WARNING: Binance {file_name} doesnt exist. Skipping')
        return

    workbook = load_workbook(filename=file_name)
    interest = convert_sheet(workbook['Interest'])
    transactions = convert_sheet(workbook['Trade History'])

    przychod_total = Decimal(0)
    koszt_total = Decimal(0)
    fiat_staking_total = Decimal(0)

    for row in interest:
        if row['Date(UTC)'] is None or row['Product Name'] not in ['EUR', 'USD']:
            continue

        asOfDate = row["Date(UTC)"].astimezone(warsaw_timezone)
        change = Decimal(str(row["Amount"]))
        pln = convert_rate(asOfDate, change, currency=row["Product Name"])
        fiat_staking_total += pln

    for row in transactions:
        executed = str(row['Executed'])
        amount = row['Amount']
        fee = row['Fee']

        asOfDate = row["Date(UTC)"].astimezone(warsaw_timezone)
        pair = row["Pair"]
        side = row["Side"]

        executed_value = re.sub(r'[a-zA-Z]+', '', executed, re.I) 
        amount_value = re.sub(r'[a-zA-Z]+', '', amount, re.I) 
        fee_value = re.sub(r'[a-zA-Z]+', '', fee, re.I) 
        executed = executed.replace(executed_value, '')
        amount = amount.replace(amount_value, '')
        fee = fee.replace(fee_value, '')
        executed_value = Decimal(executed_value.replace(',', ''))
        amount_value = Decimal(amount_value.replace(',', ''))
        fee_value = Decimal(fee_value.replace(',', ''))

        if fee in fiat_currencies:
            koszt_total += convert_rate(asOfDate, fee_value, currency=fee)

        if pair != (executed + amount):
            raise Exception(f"Unknown ticker: {pair}")
        if side not in ["SELL", "BUY"]:
            raise Exception(f"Unknown side: {side}")
        if executed in fiat_currencies and amount in fiat_currencies:
            raise Exception("Fiat to fiat?")
        
        if amount in fiat_currencies:
            pln = convert_rate(asOfDate, amount_value, currency=amount)
            if side == 'SELL':
                przychod_total += pln
            else:
                koszt_total += pln

        elif executed in fiat_currencies:
            pln = convert_rate(asOfDate, executed_value, currency=executed)
            if side == 'SELL':
                koszt_total += pln
            else:
                przychod_total += pln

    return ("Binance", round(przychod_total, 2), round(koszt_total, 2), round(fiat_staking_total, 2))