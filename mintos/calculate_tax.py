import os, sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from openpyxl import load_workbook
from datetime import datetime
from decimal import Decimal
from helpers import convert_rate, convert_sheet

tax_rate = Decimal("0.19")
income_types = ["Interest received", "Interest received from loan repurchase", "Late fees received", "Delayed interest income on transit rebuy", "Interest received from pending payments"]
cost_types = ["Tax withholding", "Strata"]

def calculate_tax(path):
    workbook = load_workbook(filename=path, read_only=False)
    income = Decimal("0")
    cost = Decimal("0")

    for currency in ["EUR", "PLN"]:
        if currency not in workbook.sheetnames:
            print("Skipping sheet: " + currency)
            continue

        sheet = convert_sheet(workbook[currency])
        for row in sheet:
            if row['Date'] is None:
                continue
            trans_type = row['Payment Type']
            date = datetime.strptime(row['Date'], '%Y-%m-%d %H:%M:%S')
            amount = convert_rate(date, Decimal(str(row["Turnover"])), currency)

            if trans_type in income_types:
                income += amount
            elif trans_type in cost_types:
                cost -= amount
            else:
                print(f"Unknown transaction type {trans_type}")
                exit(1)

    return round(income, 2), round(cost, 2)

income, cost = calculate_tax('mintos.xlsx')
dochod = income - cost
tax = dochod * tax_rate

print(f"Przychód w pln: {income} zł")
print(f"Dochód w pln: {dochod} zł")
print(f"Koszt w pln: {cost} zł")
print(f"Podatek: ~{tax} zł")