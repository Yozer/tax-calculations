import requests, xlrd, re
from datetime import datetime, timedelta
from itertools import groupby
from decimal import Decimal

ignored_transactions = ['Deposit', 
                        'Start Copy', 
                        'Account balance to mirror', 
                        'Mirror balance to account',
                        'Stop Copy',
                        'Edit Stop Loss']

dividends_abroad_tax_rates = {'USA': Decimal("0.15"), 'GB': Decimal("0")}
tax_rate = Decimal("0.19")
crypto = set(["BTC/USD", "ETH/USD", "BCH/USD", "XRP/USD", "DASH/USD", "LTC/USD", "ETC/USD", "ADA/USD", "IOTA/USD", "MIOTA/USD", "XLM/USD", "EOS/USD", "NEO/USD", "TRX/USD", "ZEC/USD", "BNB/USD", "XTZ/USD"])
traded_cryptos = set()

def fetch_rates():
    response = requests.get('https://api.nbp.pl/api/exchangerates/rates/A/USD/2020-01-01/2020-12-31?format=json').json()
    parse_date = lambda x: datetime.strptime(x, '%Y-%m-%d').date()
    return dict([(parse_date(rate['effectiveDate']), Decimal(rate['mid'])) for rate in response['rates']])

rates = fetch_rates()
def get_rate(asOfDate):
    asOfDate = asOfDate.date()
    asOfDates = [asOfDate - timedelta(days=i) for i in range(1, 5)]
    return next(rates[day] for day in asOfDates if day in rates)

def convert_to_pln(asOfDate, amount):
    return get_rate(asOfDate) * amount

def get_position_type(row, closed_positions):
    pos_id = row['Position ID']
    if pos_id not in closed_positions:
        raise Exception(f'Logic error. Unable to find position {pos_id} in closed positions sheet')

    stock_name = row['Details']
    is_cfd = closed_positions[pos_id]["Is Real"] == "CFD"
    pos_type = "crypto" if stock_name in crypto and not is_cfd else "stock"
    if pos_type == "crypto":
        traded_cryptos.add(stock_name)

    return pos_type

def process_dividend(row, date, positions):
    dividend_id = row['Position ID']
    stock_name = positions[dividend_id]['Details']
    amount = Decimal(row["Amount"])
    match = re.match('(?P<symbol>.*?)(?P<exchange>\\..*?)?\\/(?P<currency>.*)', stock_name)
    is_usa_stock = match.group('exchange') in [None, '.US'] and match.group('currency') == 'USD'
    is_gb_stock = match.group('exchange') in ['.L', '.l', None] and match.group('currency') == 'GBX'
    if is_usa_stock:
        return {'date': date, 'amount': amount, 'dividend': 'USA', 'type': 'dividend'}
    elif is_gb_stock:
        return {'date': date, 'amount': amount, 'dividend': 'GB', 'type': 'dividend'}
    
    raise Exception(f'Ile niby trzeba oddać tym złodziejom?? {dividend_id}')

def process_profit_loss(date, row, closed_positions):
    amount = Decimal(row["Amount"])
    equity_change = Decimal(row['Realized Equity Change'])
    if amount != equity_change:
        raise Exception(f'Weird row on position id {row["Position ID"]}. Closing')

    return {'date': date, 'amount': amount, 'type': get_position_type(row, closed_positions)}

def process_rollover_fee(date, row, positions, closed_positions):
    amount = Decimal(row["Amount"])
    equity_change = Decimal(row['Realized Equity Change'])
    if amount != equity_change:
        raise Exception(f'Weird row on position id {row["Position ID"]}. Closing')

    if row['Details'] in ['Weekend fee', 'Over night fee']:
        return ({'date': date, 'amount': amount, "type": get_position_type(row, closed_positions)})
    elif row['Details'] == 'Payment caused by dividend':
        return process_dividend(row, date, positions)
    else:
        raise Exception(f"Unkown fee {row['Details']} for position {row['Position ID']}")

def convert_sheet(sheet):
    header = dict([(sheet.cell(0, col_index).value, col_index) for col_index in range(sheet.ncols)])
    get_row = lambda row: dict([(column, sheet.cell(row, col_index).value) for (column, col_index) in header.items()])
    return [get_row(idx) for idx in range(1, sheet.nrows)]

def read_incomes(path):
    workbook = xlrd.open_workbook(path)
    sheet = convert_sheet(workbook.sheet_by_name('Transactions Report'))
    closed_positions = convert_sheet(workbook.sheet_by_name('Closed Positions'))
    closed_positions = dict((row['Position ID'], row) for row in closed_positions) # this doesn't handle duplicated ids i.e. partial closes, for know it's enough
    incomes = []
    positions = {}

    for row in sheet:
        id = row['Position ID']
        date = datetime.strptime(row['Date'], '%Y-%m-%d %H:%M:%S')
        trans_type = row['Type']

        if trans_type == 'Open Position':
            positions[id] = row
        elif trans_type == 'Profit/Loss of Trade':
            incomes.append(process_profit_loss(date, row, closed_positions))
            positions[id] = row
        elif trans_type == 'Rollover Fee':
            incomes.append(process_rollover_fee(date, row, positions, closed_positions))
        elif trans_type not in ignored_transactions:
            raise Exception(f'Unknown transaction type {trans_type} for position {id}')

    tmp = list([x for x in incomes if "type" not in x])
    return incomes

def process_dividends(incomes):
    get_key = lambda x: (x["date"], x["dividend"])
    dividends = sorted([x for x in incomes if x["type"] == "dividend"], key=get_key)
    dividends = groupby(dividends, key=get_key)
    income_usd = {"USA": Decimal("0"), "GB": Decimal("0")}
    income_pln = dict(income_usd)

    for dividend, data in dividends:
        total_usd = sum(Decimal(x["amount"]) for x in data)
        if dividend[1] == 'USA':
            total_usd /= Decimal("0.7")
        income_usd[dividend[1]] += total_usd
        income_pln[dividend[1]] += convert_to_pln(dividend[0], total_usd)

    tax_taken_abroad = {}
    tax = {}
    tax_to_pay = {}
    for dividend in income_usd.keys():
        tax_taken_abroad[dividend] = str(round(income_pln[dividend] * dividends_abroad_tax_rates[dividend], 2))
        tax[dividend] = str(round(income_pln[dividend] * tax_rate, 2))
        tax_to_pay[dividend] = str(Decimal(tax[dividend]) - Decimal(tax_taken_abroad[dividend]))

        income_usd[dividend] = str(round(income_usd[dividend], 4))
        income_pln[dividend] = str(round(income_pln[dividend], 4))

    return (income_usd, income_pln, tax, tax_taken_abroad, tax_to_pay)

def process_positions(incomes, typ):
    stocks = [x for x in incomes if x['type'] == typ]
    income_usd = Decimal("0")
    income_pln = Decimal("0")
    cost_pln = Decimal("0")

    for stock in stocks:
        amount = Decimal(stock["amount"])
        amount_pln = convert_to_pln(stock['date'], amount)
        income_usd += amount
        income_pln += amount_pln
        if amount < 0:
            cost_pln += amount_pln

    tax = round(income_pln * tax_rate)
    income_pln = round(income_pln, 4)
    cost_pln = round(cost_pln, 4)
    profit_pln = -1*cost_pln + income_pln

    return (round(income_usd, 4), income_pln, -cost_pln, profit_pln, tax)

incomes = read_incomes('statement_2020.xlsx')
income_stocks_usd, income_stocks_pln, cost_stocks_pln, profit_brutto_stocks_pln, tax_stocks = process_positions(incomes, "stock")
income_crypto_usd, income_crypto_pln, cost_crypto_pln, profit_brutto_crypto_pln, tax_crypto = process_positions(incomes, "crypto")
income_dividends_usd, income_dividends_pln, tax_dividends, tax_dividends_taken_abroad, tax_dividends_to_pay = process_dividends(incomes)
total_tax = tax_stocks + tax_crypto + sum([Decimal(tax) for _, tax in tax_dividends_to_pay.items()])

print(f"Dochód $ za stocks: ${income_stocks_usd}")
print(f"Przychód w pln za stocks: {profit_brutto_stocks_pln} zł")
print(f"Dochód w pln za stocks: {income_stocks_pln} zł")
print(f"Koszt w pln za stocks: {cost_stocks_pln} zł")
print(f"Podatek stocks: ~{tax_stocks} zł")

print()
print(f"Cryptos: {list(traded_cryptos)}")
print(f"Dochód $ za crypto: ${income_crypto_usd}")
print(f"Przychód w pln za crypto: {profit_brutto_crypto_pln} zł")
print(f"Dochód w pln za crypto: {income_crypto_pln} zł")
print(f"Koszt w pln za crypto: {cost_crypto_pln} zł")
print(f"Podatek crypto: ~{tax_crypto} zł")

print()
print(f"Przychód $ za dywidendy ${income_dividends_usd}")
print(f"Przychód w pln za dywidendy: {income_dividends_pln} zł")
print(f"Podatek należny (PIT36L pole K-132): {tax_dividends} zł ZAOKRĄGLIĆ!")
print(f"Podatek zapłacony za granicą (PIT36L pole K-133): {tax_dividends_taken_abroad} zł  ZAOKRĄGLIĆ!")
print(f"Podatek za dywidendy (różnica pól): ~{tax_dividends_to_pay} zł")

print()
print(f"Podatek w sumie {total_tax} zł")