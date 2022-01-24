from openpyxl import load_workbook
from datetime import datetime
from decimal import Decimal
from ..helpers import convert_rate, convert_sheet

tax_rate = Decimal("0.19")
def convert_to_pln(asOfDate, amount, currency):
    return amount if currency == 'PLN' else (get_rate(currency, asOfDate) * amount)

def calculate_tax(path):
    workbook = load_workbook(filename=path, read_only=False)
    income = Decimal("0")

    # ten dropdown ze screena może nie być dobry,
    # minusowe powinny leciec do kosztów a dodatnie do przychodu
    # i wypluwamy dochód, nie zmienia podatku ale fajniej wylgada
    for currency in ["EUR", "PLN"]:
        sheet = convert_sheet(workbook[currency])
        for row in sheet:
            if row['Date'] is None:
                continue
            date = datetime.strptime(row['Date'], '%Y-%m-%d %H:%M:%S')
            amount = convert_rate(date, Decimal(str(row["Turnover"])), currency)
            income += amount

    return round(income, 4)

income = calculate_tax('mintos.xlsx')
tax = income * tax_rate

print(f"Dochód w pln: {income} zł")
print(f"Podatek: ~{tax} zł")