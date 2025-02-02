import os, sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from datetime import datetime
from decimal import Decimal
from helpers import convert_rate, read_csv, warsaw_timezone

tax_rate = Decimal("0.19")
income_types = []
cost_types = []

trans_types_to_ignore = ['Interest','Fixed Term Interest', 'Unlocking Term Deposit']

def calculate_tax():
    income = Decimal("0")
    cost = Decimal("0")

    sheet = read_csv('nexo.csv')
    for row in sheet:
        if row['Date / Time (UTC)'] is None:
            continue
        trans_type = row['Type']
        if trans_type in trans_types_to_ignore:
            continue

        input_currency = row['Input Currency']
        output_currency = row['Output Currency']
        amount = Decimal(str(row["Input Amount"]))
        date = row['Date / Time (UTC)'] if isinstance(row['Date / Time (UTC)'], datetime) else datetime.strptime(row['Date / Time (UTC)'], '%Y-%m-%d %H:%M:%S').astimezone(warsaw_timezone)

        if trans_type == 'Exchange To Withdraw':
            if output_currency == 'EUR' or 'USD':
                income += convert_rate(date, amount, output_currency)
            else:
                raise Exception("invalid output currency")
        elif trans_type == 'Exchange Deposited On':
            if input_currency == 'EUR' or 'USD':
                cost += convert_rate(date, amount, input_currency)
            else:
                raise Exception("invalid output currency")

    return ('Nexo', round(income, 2), round(cost, 2), Decimal("0"))