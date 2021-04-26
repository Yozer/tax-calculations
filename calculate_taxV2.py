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
exchanges = {
    'USA': {'suffix': '.US', 'currencies': ['USD']},
    'GB': {'suffix': '.L', 'currencies': ['GBX', 'GBP', 'USD', 'EUR'], 'exceptions': ['UK100/GBP']},
    'DE': {'suffix': '.DE', 'currencies': ['EUR'], 'exceptions': ['GER30/EUR']},
    'HK': {'suffix': '.HK', 'currencies': ['HKD']},
    'CHF': {'suffix': '.ZU', 'currencies': ['CHF']},
    'DKK': {'suffix': '', 'currencies': ['DKK'], 'exceptions': ['ORSTED/DKK', 'VWS/DKK']},
    'FR': {'suffix': '', 'currencies': ['EUR'], 'exceptions': ['MC/EUR', 'KER/EUR']},
    'ES': {'suffix': '', 'currencies': ['EUR'], 'exceptions': ['SGRE.MC/EUR']},
}
forex_ignore = set(['USD/PLN', 'USD/CAD'])
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

def get_ticker_country(row, positions):
    trans_id = row['Position ID']
    stock_name = positions[trans_id]['Details']
    match = re.match('(?P<symbol>.*?)(?P<exchange>\\..*?)?\\/(?P<currency>.*)', stock_name)

    symbol = match.group('symbol')
    suffix = match.group('exchange')
    currency = match.group('currency')
    if stock_name in forex_ignore:
        return 'USA'

    for country, details in exchanges.items():
        if currency not in details['currencies']:
            continue
        if suffix is not None and suffix.upper() == details['suffix']:
            return country
        if 'exceptions' in details and stock_name in details['exceptions']:
            return country

    if suffix is None and currency == 'USD':
        return 'USA'

    raise Exception(f'Unable to find country for ticker {stock_name} with id {row["Position ID"]}. Closing')

def process_dividend(row, date, positions):
    amount = Decimal(row["Amount"])
    country = get_ticker_country(row, positions)
    if country in ['USA', 'GB']:
        return {'date': date, 'amount': amount, 'country': country, 'type': 'dividend'}
    
    raise Exception(f'Ile niby trzeba oddać tym złodziejom?? {row["Position ID"]}')

def process_profit_loss(date, row, positions, closed_positions):
    amount = Decimal(row["Amount"])
    equity_change = Decimal(row['Realized Equity Change'])
    if amount != equity_change:
        raise Exception(f'Weird row on position id {row["Position ID"]}. Closing')

    return {'date': date, 'amount': amount, 'country': get_ticker_country(row, positions), 'type': get_position_type(row, closed_positions)}

def process_rollover_fee(date, row, positions, closed_positions):
    amount = Decimal(row["Amount"])
    equity_change = Decimal(row['Realized Equity Change'])
    if amount != equity_change:
        raise Exception(f'Weird row on position id {row["Position ID"]}. Closing')

    if row['Details'] in ['Weekend fee', 'Over night fee']:
        return ({'date': date, 'amount': amount, 'country': get_ticker_country(row, positions), "type": get_position_type(row, closed_positions)})
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
            positions[id] = row
            incomes.append(process_profit_loss(date, row, positions, closed_positions))
        elif trans_type == 'Rollover Fee':
            incomes.append(process_rollover_fee(date, row, positions, closed_positions))
        elif trans_type not in ignored_transactions:
            raise Exception(f'Unknown transaction type {trans_type} for position {id}')

    tmp = list([x for x in incomes if "type" not in x])
    return incomes

def process_dividends(incomes):
    get_key = lambda x: (x["date"], x["country"])
    dividends = sorted([x for x in incomes if x["type"] == "dividend"], key=get_key)
    dividends = groupby(dividends, key=get_key)
    income_usd = {}
    income_pln = {}

    for dividend, data in dividends:
        total_usd = sum(Decimal(x["amount"]) for x in data)
        country = dividend[1]
        if country == 'USA':
            total_usd /= Decimal("0.7")
        if country not in income_usd:
            income_usd[country] = Decimal("0")
            income_pln[country] = Decimal("0")

        income_usd[country] += total_usd
        income_pln[country] += convert_to_pln(dividend[0], total_usd)

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
    get_key = lambda x: (x["date"], x["country"])
    dividends = sorted([x for x in incomes if x["type"] == typ], key=get_key)
    dividends = groupby(dividends, key=get_key)
    income_usd = {}
    income_pln = {}
    cost_pln = {}

    for stock, data in dividends:
        total_usd = sum(Decimal(x["amount"]) for x in data)
        amount_pln = convert_to_pln(stock[0], total_usd)

        country = stock[1]
        if country not in income_usd:
            income_usd[country] = Decimal("0")
            income_pln[country] = Decimal("0")
            cost_pln[country] = Decimal("0")

        income_usd[country] += total_usd
        income_pln[country] += amount_pln
        if total_usd < 0:
            cost_pln[country] += amount_pln

    tax = {}
    profit_pln = {}

    for country in income_usd.keys():
        profit_pln[country] = round(Decimal("-1") * cost_pln[country] + income_pln[country], 4)
        tax[country] = round(income_pln[country] * tax_rate, 4)
        income_pln[country] = round(income_pln[country], 4)
        cost_pln[country] = round(-cost_pln[country], 4)

    return (income_usd, income_pln, cost_pln, profit_pln, tax)

incomes = read_incomes('statement_2020.xlsx')
income_stocks_usd, income_stocks_pln, cost_stocks_pln, profit_brutto_stocks_pln, tax_stocks = process_positions(incomes, "stock")
income_crypto_usd, income_crypto_pln, cost_crypto_pln, profit_brutto_crypto_pln, tax_crypto = process_positions(incomes, "crypto")
income_dividends_usd, income_dividends_pln, tax_dividends, tax_dividends_taken_abroad, tax_dividends_to_pay = process_dividends(incomes)
# total_tax = tax_stocks + tax_crypto + sum([Decimal(tax) for _, tax in tax_dividends_to_pay.items()])

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
# print(f"Podatek w sumie {total_tax} zł")