import requests, re
from openpyxl import load_workbook
from datetime import datetime, timedelta
from itertools import groupby
from decimal import Decimal

tax_rate = Decimal("0.19")
year = 2020

def fetch_rates():
    response = requests.get(f'https://api.nbp.pl/api/exchangerates/rates/A/EUR/{(year-1)}-12-30/{year}-12-31?format=json').json()
    parse_date = lambda x: datetime.strptime(x, '%Y-%m-%d').date()
    return dict([(parse_date(rate['effectiveDate']), Decimal(str(rate['mid']))) for rate in response['rates']])

rates_eur = fetch_rates()
def get_rate(asOfDate):
    asOfDate = asOfDate.date()
    asOfDates = [asOfDate - timedelta(days=i) for i in range(1, 5)]
    return next(rates_eur[day] for day in asOfDates if day in rates_eur)

def convert_to_pln(asOfDate, amount, currency):
    return amount if currency == 'PLN' else (get_rate(asOfDate) * amount)

def convert_sheet(sheet):
    sheet.calculate_dimension()
    cols = sheet.max_column
    rows = sheet.max_row
    header = [(sheet.cell(row=1, column=col_index).value, col_index) for col_index in range(1, cols + 1)]
    get_row = lambda row: dict([(column, sheet.cell(row, col_index).value) for (column, col_index) in header])
    return [get_row(idx) for idx in range(2, rows + 1)]

def calculate_tax(path):
    workbook = load_workbook(filename=path, read_only=False)
    income = Decimal("0")

    for currency in ["EUR", "PLN"]:
        sheet = convert_sheet(workbook[currency])
        for row in sheet:
            date = datetime.strptime(row['Date'], '%Y-%m-%d %H:%M:%S')
            amount = convert_to_pln(date, Decimal(str(row["Turnover"])), currency)
            income += amount

    return round(income, 4)

income = calculate_tax('mintos.xlsx')
tax = income * tax_rate

print(f"Dochód w pln: {income} zł")
print(f"Podatek: ~{tax} zł")