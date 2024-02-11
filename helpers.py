from datetime import datetime, timedelta, timezone
from decimal import Decimal
from dateutil import tz
import requests

warsaw_timezone = tz.gettz('Europe/Warsaw')
fiat_currencies = ['EUR', 'USD', 'GBP']
rates_cache = {}

def fetch_rates(currency:str, year:int):
    global rates_cache
    if year not in rates_cache:
        rates_cache[year] = {}

    if currency not in rates_cache[year]:
        response = requests.get(f'https://api.nbp.pl/api/exchangerates/rates/A/{currency}/{year-1}-12-31/{year}-12-31?format=json').json()
        parse_date = lambda x: datetime.strptime(x, '%Y-%m-%d').date()
        rates_cache[year][currency] = dict([(parse_date(rate['effectiveDate']), Decimal(str(rate['mid']))) for rate in response['rates']])
    return rates_cache[year][currency]

def get_rate(currency, asOfDate: datetime):
    rates = fetch_rates(currency, asOfDate.year)
    asOfDate = asOfDate.date()
    asOfDates = [asOfDate - timedelta(days=i) for i in range(1, 7)]
    rate =  next((rates[day] for day in asOfDates if day in rates), None)
    if rate is None:
        rates = fetch_rates(currency, asOfDate.year - 1)
        asOfDate = datetime(asOfDate.year - 1, 12, 31).date()
        asOfDates = [asOfDate - timedelta(days=i) for i in range(0, 6)]
        rate =  next((rates[day] for day in asOfDates if day in rates), None)
        if rate is None:
            raise Exception(f"Failed to get rate for {asOfDate} and {currency}")

    return rate

def convert_rate(asOfDate, amount, currency) -> Decimal:
    return amount if currency == 'PLN' else (get_rate(currency, asOfDate) * amount)

def convert_sheet(sheet):
    sheet.calculate_dimension()
    cols = sheet.max_column
    rows = sheet.max_row
    header = [(sheet.cell(row=1, column=col_index).value, col_index) for col_index in range(1, cols + 1)]
    get_row = lambda row: dict([(column, sheet.cell(row, col_index).value) for (column, col_index) in header])
    return [get_row(idx) for idx in range(2, rows + 1)]

def sum_dict(d):
    return sum([v for k,v in d.items()])

def add_working_days(date, d):
    business_days_to_add = d
    current_date = date
    while business_days_to_add > 0:
        current_date += timedelta(days=1)
        weekday = current_date.weekday()
        if weekday >= 5: # sunday = 6
            continue
        business_days_to_add -= 1
    return current_date

def from_utc_to_warsaw(dt: datetime):
    return dt.replace(tzinfo=timezone.utc).astimezone(tz=warsaw_timezone)