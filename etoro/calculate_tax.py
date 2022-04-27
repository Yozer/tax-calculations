import os, sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from openpyxl import load_workbook
from datetime import datetime
from decimal import Decimal
from mapping import get_country_code, CryptoCountry, CfdCountry
from helpers import sum_dict, convert_rate, convert_sheet

# pos_types: crypto, stock, dividend, fee
dividends_abroad_tax_rates = {'USA': Decimal("0.15")}
tax_rate = Decimal("0.19")
ignored_transactions = ['Deposit',
                        'Start Copy',
                        'Account balance to mirror',
                        'Mirror balance to account',
                        'Stop Copy',
                        'Edit Stop Loss',
                        'corp action: Split',
                        'AirDrop']
excel_date_format = '%d/%m/%Y %H:%M:%S'

def group_by_pos_id(transactions):
    res = {}
    for x in transactions:
        pos_id = x["Position ID"]
        if pos_id not in res:
            res[pos_id] = []
        res[pos_id].append(x)

    return res

def get_country_raw(pos_id, transactions, closed_positions):
    if pos_id not in transactions:
        raise Exception(f'Logic error. Unable to find position {pos_id} in transactions sheet')

    all_dividends = all(t['Details'].lower() == 'payment caused by dividend' for t in transactions[pos_id])
    if all_dividends:
        return ''
    first_transaction = next(t for t in transactions[pos_id] if t['Details'].lower() != 'payment caused by dividend')
    closed_position = closed_positions[pos_id][0]
    stock_name = first_transaction['Details']

    return get_country_code(closed_position["Action"], stock_name, closed_position['ISIN'])

def get_position_type(pos_id, transactions, closed_positions):
    closed_position = closed_positions[pos_id][0]
    is_cfd = closed_position["Type"] == "CFD"

    country= get_country_raw(pos_id, transactions, closed_positions)
    return "crypto" if country == CryptoCountry and not is_cfd else "stock"

def get_ticker_country(pos_id, transactions, closed_positions):
    closed_position = closed_positions[pos_id][0]
    is_cfd = closed_position["Type"] == "CFD"
    if is_cfd: #is it ok?
        return CfdCountry

    return get_country_raw(pos_id, transactions, closed_positions)

def process_rollover_fee(transaction, transactions, closed_positions):
    amount = Decimal(str(transaction["Amount"]))
    pos_id = transaction["Position ID"]
    date = datetime.strptime(transaction['Date'], excel_date_format)
    equity_change = Decimal(str(transaction['Realized Equity Change']))

    if amount != equity_change:
        raise Exception(f'Weird row on position id {transaction["Position ID"]}. Closing')

    transaction_details = transaction['Details'].lower()
    transaction_type = transaction['Type'].lower()
    if transaction_details in ['weekend fee', 'over night fee']:
        country = get_ticker_country(pos_id, transactions, closed_positions)
        if amount < 0:
            pos_type = 'fee'
            if country == CryptoCountry:
                raise Exception(f"Found a rollover fee for crypto position {pos_id}. Should be marked as cfd?")
        else:
            return {
                'open_date': date,
                'close_date': date,
                'open_amount': Decimal("0"),
                'close_amount': amount,
                'is_cfd': True,
                'id': pos_id,
                'type': 'stock',
                'status': 'open',
                'country': country
            }
    elif transaction_details == 'payment caused by dividend' or transaction_type == 'dividend':
        if amount > 0:
            pos_type = 'dividend'
            country = None
        else:
            # ujemne dywidendy traktujemy jako koszt
            if get_country_raw(pos_id, transactions, closed_positions) == CryptoCountry:
                raise Exception(f"Found a rollover fee for crypto position {pos_id}. Should be marked as cfd?")

            pos_type = 'fee'
            country = get_ticker_country(pos_id, transactions, closed_positions)
    else:
        raise Exception(f"Unkown fee {transaction_details} for position {transaction['Position ID']}")

    return ({'id': pos_id, 'date': date, 'amount': amount, 'country': country, "type": pos_type})

def read_dividend_taxes(path):
    workbook = load_workbook(filename=path)
    sheet = convert_sheet(workbook['Dividends'])
    dividend_taxes = {}
    for x in sheet:
        pos_id = str(x["Position ID"])
        if x["Position ID"] is None:
            continue
        if pos_id not in dividend_taxes:
            dividend_taxes[pos_id] = []

        x["Withholding Tax Rate (%)"] = Decimal(str(x["Withholding Tax Rate (%)"].replace('%', ''))) / Decimal("100")
        x["Net Dividend Received (USD)"] = Decimal(str(x["Net Dividend Received (USD)"]))
        x["Withholding Tax Amount (USD)"] = Decimal(str(x["Withholding Tax Amount (USD)"]))
        x["Date of Payment"] = datetime.strptime(str(x["Date of Payment"]), excel_date_format)
        dividend_taxes[pos_id] += [x]

    return dividend_taxes

def read(path):
    workbook = load_workbook(filename=path)
    transactions = convert_sheet(workbook['Account Activity'])
    grouped_transactions = group_by_pos_id(transactions)
    closed_positions = convert_sheet(workbook['Closed Positions'])
    grouped_closed_positions = group_by_pos_id(closed_positions)
    entries = []

    for row in closed_positions:
        pos_id = row['Position ID']
        if pos_id is None:
            continue
        amount = Decimal(str(row['Amount']).replace(',', '.'))
        profit = Decimal(str(row['Profit']).replace(',', '.'))
        pos_type = get_position_type(pos_id, grouped_transactions, grouped_closed_positions)
        is_cfd = row["Type"] == "CFD"
        is_sell = row["Action"].startswith("Sell")

        trans = {
            'open_date': datetime.strptime(row['Open Date'], excel_date_format),
            'close_date': datetime.strptime(row['Close Date'], excel_date_format),
            'is_cfd': is_cfd,
            'id': pos_id,
            'type': pos_type,
            'status': 'closed',
            'country': get_ticker_country(pos_id, grouped_transactions, grouped_closed_positions)
        }

        if is_sell and not is_cfd:
            raise Exception(f"Not CFD that is sell? Pos id {pos_id}")

        if is_cfd:
            # dla cfd przychodem będzie sprzedaż z zyskiem
            if profit > Decimal("0"):
                trans['open_amount'] = Decimal("0")
                trans['close_amount'] = profit
            else:
                # a kosztem strata
                trans['open_amount'] = -profit
                trans['close_amount'] = Decimal("0")
                # co jesli otworzony cfd byl w 2020 a zamkniety w 2021?
                trans["open_date"], trans["close_date"] = trans["close_date"], trans["open_date"]
        else:
            # dla akcji albo krypto przychodem jest cena sprzedaży a kosztem cena kupna
            trans["open_amount"] = amount
            trans["close_amount"] = amount + profit

        entries.append(trans)

    for row in transactions:
        pos_id = row['Position ID']
        if pos_id is None:
            continue
        trans_type = row['Type']
        if trans_type in ['Rollover Fee', 'Dividend']:
            entries.append(process_rollover_fee(row, grouped_transactions, grouped_closed_positions))
        elif trans_type == "Open Position":
            if pos_id not in grouped_closed_positions and get_country_code(None, row["Details"], None, throw=False) == CryptoCountry:
                print(f"Found crypto that was bought but not sold. Unable to determine CFD. Assuming not. Verify {pos_id}")

                trans = {
                    'open_date': datetime.strptime(row['Date'], excel_date_format),
                    'close_date': datetime.strptime(row['Date'], excel_date_format),
                    'open_amount': Decimal(str(row["Amount"])),
                    'close_amount': Decimal("0"),
                    'is_cfd': False,
                    'id': pos_id,
                    'type': 'crypto',
                    'status': 'open',
                    'country': CryptoCountry
                }

                entries.append(trans)
        elif trans_type == "Profit/Loss of Trade":
            if pos_id not in grouped_closed_positions:
                raise Exception(f"Closed but not in closed? wtf {pos_id}")
        elif trans_type not in ignored_transactions:
            raise Exception(f'Unknown transaction type "{trans_type}" for position {pos_id}')

    return entries

def process_positions(positions, typ):
    positions = [x for x in positions if x["type"] == typ or (typ == "stock" and x['type'] == "fee")]
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

        if pos["type"] == "fee":
            if pos["amount"] > 0:
                raise Exception(f"Positive fee {pos['amount']} for {pos['id']}")

            rate_pln = convert_rate(pos["date"], -pos["amount"], currency='USD')
            koszty[country] += rate_pln
            dochod[country] -= rate_pln
        else:
            if pos["status"] == "closed":
                income_usd[country] += pos["close_amount"] - pos["open_amount"]
            open_rate_pln = convert_rate(pos["open_date"], pos["open_amount"], currency='USD')
            close_rate_pln = convert_rate(pos["close_date"], pos["close_amount"], currency='USD')
            przychod[country] += close_rate_pln
            koszty[country] += open_rate_pln
            dochod[country] += close_rate_pln - open_rate_pln

    return (income_usd, przychod, koszty, dochod)

def process_dividends(incomes, dividend_taxes):
    dividends = [x for x in incomes if x["type"] == 'dividend']
    sum_from_dividend_taxes = sum([item["Net Dividend Received (USD)"] for sublist in dividend_taxes.values() for item in sublist])

    income_dividends_usd = Decimal("0")
    income_dividends_usd2 = Decimal("0")
    income_dividends_usd_brutto = Decimal("0")
    przychod_dywidendy = Decimal("0")
    podatek_nalezny_dywidendy = Decimal("0")
    podatek_zaplacony_dywidendy = Decimal("0")

    for dividend in dividends:
        pos_id = dividend["id"]
        total_usd = dividend["amount"]
        income_dividends_usd += total_usd

        dividend_tax = next((x for x in dividend_taxes[pos_id] if x["Net Dividend Received (USD)"] == total_usd and x["Date of Payment"] == dividend["date"]), None)
        if dividend_tax is None:
            raise Exception(f"Unable to match dividend for {pos_id} amount {total_usd} on {dividend['date']}")

        dividend_taxes[pos_id].remove(dividend_tax)
        if len(dividend_taxes[pos_id]) == 0:
            del dividend_taxes[pos_id]

        income_dividends_usd2 += dividend_tax["Net Dividend Received (USD)"]
        country = get_country_code(dividend_tax["Instrument Name"], None, dividend_tax["ISIN"])
        force_witholding_tax_rate = dividends_abroad_tax_rates["USA"] if country == "USA" else dividend_tax["Withholding Tax Rate (%)"]
        total_usd = dividend_tax["Withholding Tax Amount (USD)"] + dividend_tax["Net Dividend Received (USD)"]
        income_dividends_usd_brutto += total_usd

        total_pln = convert_rate(dividend["date"], total_usd, currency='USD')
        przychod_dywidendy += total_pln
        podatek_zaplacony_dywidendy += force_witholding_tax_rate * total_pln

        if tax_rate - force_witholding_tax_rate > 0:
            podatek_nalezny_dywidendy += tax_rate * total_pln
        else:
            podatek_nalezny_dywidendy += force_witholding_tax_rate * total_pln

    # validate
    if sum_from_dividend_taxes != income_dividends_usd:
        duplicated_pos_ids = "\r\n".join(dividend_taxes.keys())
        raise Exception("Suma dywidend między Dywidendy i Transaction Report się nie zgadza: " + duplicated_pos_ids)
    if len(dividend_taxes) != 0:
        raise Exception("Niewykorzystano wszystkich dywidend do rozdzielenia podatku!")

    income_dividends_usd = round(income_dividends_usd, 2)
    income_dividends_usd_brutto = round(income_dividends_usd_brutto, 4)
    przychod_dywidendy = round(przychod_dywidendy, 4)
    podstawa_dywidendy = round(przychod_dywidendy)
    podatek_nalezny_dywidendy = round(podatek_nalezny_dywidendy)
    podatek_zaplacony_dywidendy = round(podatek_zaplacony_dywidendy)
    return (income_dividends_usd, income_dividends_usd_brutto, przychod_dywidendy, podstawa_dywidendy, podatek_nalezny_dywidendy, podatek_zaplacony_dywidendy)

fname = 'statement_2021.xlsx'
entries = read(fname)
dividend_taxes = read_dividend_taxes(fname)
income_stock_usd, przychod_stock, koszty_stock, dochod_stock = process_positions(entries, 'stock')
print()
print("Stocks na Pit-38 sekcja C jako inne przychody. Koniecznie z załącznikiem PIT/ZG")
print(f"Dochód $ za stocks: ${sum_dict(income_stock_usd)}")
print(f"Przychód w pln za stocks: {sum_dict(przychod_stock)} zł")
print(f"Koszt w pln za stocks: {sum_dict(koszty_stock)} zł")
print(f"Dochód w pln za stocks: {sum_dict(dochod_stock)} zł")
print(f'Dochód per kraj (na PIT/ZG wpisujemy tylko dodatnie): {dict([(x, str(y)) for x, y in dochod_stock.items()])}')

income_crypto_usd, przychod_crypto, koszty_crypto, dochod_crypto = process_positions(entries, 'crypto')
print()
print("Crypto rozliczamy na PIT-38 sekcja E")
print(f"Dochód $ za crypto: ${sum_dict(income_crypto_usd)}")
print(f"Przychód w pln za crypto: {sum_dict(przychod_crypto)} zł")
print(f"Koszt w pln za crypto: {sum_dict(koszty_crypto)} zł")
print(f"Dochód w pln za crypto: {sum_dict(dochod_crypto)} zł")

income_dividends_usd, income_dividends_usd_brutto, przychod_dywidendy, podstawa_dywidendy, podatek_nalezny_dywidendy, podatek_zaplacony_dywidendy = process_dividends(entries, dividend_taxes)
podatek_do_zaplaty_dywidendy = podatek_nalezny_dywidendy - podatek_zaplacony_dywidendy
print()
print("Dywidendy na PIT-38 sekcja G (podatek poza granicami pln)")
print(f"Przychód $ za dywidendy ${income_dividends_usd}")
print(f"Przychód $ za dywidendy brutto ${income_dividends_usd_brutto}")
print(f"Przychód w pln za dywidendy: {przychod_dywidendy} zł")
print(f"Podstawa w pln za dywidendy: {podstawa_dywidendy} zł")
print(f"Podatek należny: {podatek_nalezny_dywidendy} zł")
print(f"Podatek zapłacony za granicą: {podatek_zaplacony_dywidendy} zł")
print(f"Podatek za dywidendy: {podatek_do_zaplaty_dywidendy} zł")