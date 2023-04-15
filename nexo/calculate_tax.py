import os, sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from openpyxl import load_workbook
from datetime import datetime
from decimal import Decimal
from helpers import convert_rate, convert_sheet

tax_rate = Decimal("0.19")
income_types = []
cost_types = []

def calculate_tax(path):
    workbook = load_workbook(filename=path, read_only=False)
    income = Decimal("0")
    cost = Decimal("0")

    sheet = convert_sheet(workbook[workbook.sheetnames[0]])
    for row in sheet:
        if row['Date / Time'] is None:
            continue
        trans_type = row['Type']
        if trans_type not in ['Interest', 'FixedTermInterest']:
            continue
        if row['Input Currency'] not in ['EURX', 'USDT']:
            print(f"Waluta {row['Input Currency']} nieobsługiwana.")
            continue
        date = datetime.strptime(row['Date / Time'], '%Y-%m-%d %H:%M:%S')

        if row['Input Currency'] == 'EURX':
            amount = convert_rate(date, Decimal(str(row["Input Amount"])), 'EUR')

        if row['Input Currency'] == 'USDT':
            amount = convert_rate(date, Decimal(str(row["Input Amount"])), 'USD')

        income += amount

    return round(income, 2), round(cost, 2)

income, cost = calculate_tax('nexo.xlsx')
dochod = income - cost
tax = dochod * tax_rate

print("W KRYPTO TO WPISUJEMY!")
print(f"Przychód w pln: {income} zł")
print(f"Dochód w pln: {dochod} zł")
print(f"Koszt w pln: {cost} zł")
print(f"Podatek: ~{tax} zł")