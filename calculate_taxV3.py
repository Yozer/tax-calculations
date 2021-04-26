import xlrd, re
from datetime import datetime, timedelta
from itertools import groupby
from decimal import Decimal
from helpers import convert_rate, convert_sheet, group_by_pos_id

tax_rate = Decimal("0.19")
crypto = set(["BTC/USD", "ETH/USD", "BCH/USD", "XRP/USD", "DASH/USD", "LTC/USD", "ETC/USD", "ADA/USD", "IOTA/USD", "MIOTA/USD", "XLM/USD", "EOS/USD", "NEO/USD", "TRX/USD", "ZEC/USD", "BNB/USD", "XTZ/USD"])
traded_cryptos = set()

def get_position_type(row, transactions):
    # pos_types: crypto, stock, dividend
    pos_id = row['Position ID']
    if pos_id not in transactions:
        raise Exception(f'Logic error. Unable to find position {pos_id} in closed positions sheet')

    first_transaction = transactions[pos_id][0] # we might have different types
    stock_name = first_transaction['Details']
    is_cfd = row["Is Real"] == "CFD"
    pos_type = "crypto" if stock_name in crypto and not is_cfd else "stock"
    if pos_type == "crypto":
        traded_cryptos.add(stock_name)

    return pos_type

def get_ticker_country(row, transactions):
    return "USA"

def read_closed_positions(path):
    workbook = xlrd.open_workbook(path)
    transactions = convert_sheet(workbook.sheet_by_name('Transactions Report'))
    transactions = group_by_pos_id(transactions)
    closed_positions = convert_sheet(workbook.sheet_by_name('Closed Positions'))
    entries = []

    for row in closed_positions:
        amount = Decimal(row['Amount'].replace(',', '.'))
        profit = Decimal(row['Profit'].replace(',', '.'))
        trans = {
            'open_date': datetime.strptime(row['Open Date'], '%d-%m-%Y %H:%M'),
            'close_date': datetime.strptime(row['Close Date'], '%d-%m-%Y %H:%M'),
            'open_amount': amount,
            'close_amount': amount + profit,
            'is_cfd': row["Is Real"] == "CFD",
            'id': row['Position ID'],
            'type': get_position_type(row, transactions),
            'country': get_ticker_country(row, transactions)
        }
        entries.append(trans)

    return entries

def process_positions(positions, typ, d = 0):
    positions = [x for x in positions if x["type"] == typ]
    income_usd = {}
    przychod = {}
    koszty = {}
    dochod = {}

    for pos in positions:
        country = pos["country"]
        if country not in income_usd:
            income_usd[country] = Decimal("0")
            przychod[country] = Decimal("0")
            koszty[country] = Decimal("0")
            dochod[country] = Decimal("0")

        income_usd[country] += pos["close_amount"] - pos["open_amount"]
        open_rate_pln = convert_rate(pos["open_date"], pos["open_amount"])
        close_rate_pln = convert_rate(pos["close_date"], pos["close_amount"])
        przychod[country] += close_rate_pln
        koszty[country] += open_rate_pln
        dochod[country] += close_rate_pln - open_rate_pln

    return (income_usd, przychod, koszty, dochod)

positions = read_closed_positions('statement_2020.xlsx')
# positions = read_closed_positions('statement_2020 - Copy.xlsx')
income_crypto_usd, przychod_crypto, koszty_crypto, dochod_crypto = process_positions(positions, 'crypto')

print(f"Cryptos: {list(traded_cryptos)}")
print(f"Dochód $ za crypto: ${income_crypto_usd}")
print(f"Przychód w pln za crypto: {przychod_crypto} zł")
print(f"Dochód w pln za crypto: {dochod_crypto} zł")
print(f"Koszt w pln za crypto: {koszty_crypto} zł")