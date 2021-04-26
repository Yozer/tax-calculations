from datetime import datetime, timedelta
from decimal import Decimal
import requests
rates_cache = {}

def fetch_rates(currency):
    global rates_cache
    if currency not in rates_cache:
        response = requests.get(f'https://api.nbp.pl/api/exchangerates/rates/A/{currency}/2020-01-01/2020-12-31?format=json').json()
        parse_date = lambda x: datetime.strptime(x, '%Y-%m-%d').date()
        rates_cache[currency] = dict([(parse_date(rate['effectiveDate']), Decimal(str(rate['mid']))) for rate in response['rates']])
    return rates_cache[currency]

def get_rate(currency, asOfDate):
    rates = fetch_rates(currency)
    asOfDate = asOfDate.date()
    asOfDates = [asOfDate - timedelta(days=i) for i in range(1, 5)]
    return next(rates[day] for day in asOfDates if day in rates)

def convert_rate(asOfDate, amount):
    return get_rate('USD', asOfDate) * amount

def convert_sheet(sheet):
    header = dict([(sheet.cell(0, col_index).value, col_index) for col_index in range(sheet.ncols)])
    get_row = lambda row: dict([(column, sheet.cell(row, col_index).value) for (column, col_index) in header.items()])
    return [get_row(idx) for idx in range(1, sheet.nrows)]

def group_by_pos_id(transactions):
    res = {}
    for x in transactions:
        pos_id = x["Position ID"]
        if pos_id not in res:
            res[pos_id] = []
        res[pos_id].append(x)

    return res