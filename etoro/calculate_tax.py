import os, sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from openpyxl import load_workbook
from datetime import datetime
from decimal import Decimal
from mapping import get_country_code, CryptoCountry, CfdCountry
from helpers import sum_dict, convert_rate, convert_sheet

# pos_types: crypto, stock, dividend, fee
tax_rate = Decimal("0.19")
use_t_plus_2 = True
ignored_transactions = ['Deposit',
                        'Start Copy',
                        'Account balance to mirror',
                        'Mirror balance to account',
                        'Stop Copy',
                        'Edit Stop Loss',
                        'corp action: Split',
                        'AirDrop',
                        'Staking']
excel_date_format = '%d/%m/%Y %H:%M:%S'

def group_by_pos_id(transactions):
    res = {}
    for x in transactions:
        pos_id = x["Position ID"]
        if pos_id not in res:
            res[pos_id] = []
        res[pos_id].append(x)

    return res

def get_ticker_country(position, transactions, closed_positions, dividends):
    pos_id = position['id']
    if pos_id not in transactions:
        raise Exception(f'Logic error. Unable to find position {pos_id} in transactions sheet')

    if 'interest' in position:
        return CfdCountry

    first_transaction = next((t for t in transactions[pos_id] if t['Type'] in ['Position closed', 'Open Position', 'Dividend']))
    if first_transaction['Asset type'] == 'CFD':
        return CfdCountry
    if first_transaction['Asset type'] == 'Crypto':
        return CryptoCountry
    if first_transaction['Asset type'] not in ['Stocks', 'ETF']:
        raise Exception('wtf')

    closed_position = closed_positions[pos_id][0] if pos_id in closed_positions else None
    stock_name = None if closed_position is None else closed_position["Action"]
    stock_isin = None if closed_position is None else closed_position["ISIN"]
    stock_symbol = first_transaction['Details']

    if closed_position is None:
        dividend = dividends[pos_id][0] if pos_id in dividends else None
        stock_name = None if dividend is None else dividend["Instrument Name"]
        stock_isin = None if dividend is None else dividend["ISIN"]

    return get_country_code(stock_name, stock_symbol, stock_isin)

def process_interest_payment(transaction):
    pos_id = transaction["Position ID"]
    amount = Decimal(str(transaction["Amount"]))
    date = datetime.strptime(transaction['Date'], excel_date_format)
    trans = {'id': pos_id, 'date': date, 'amount': amount, "type": 'stock', 'closed': True, 'equity_change': amount, 'interest': True}
    return trans

def process_rollover_fee(transaction):
    amount = Decimal(str(transaction["Amount"]))
    pos_id = transaction["Position ID"]
    date = datetime.strptime(transaction['Date'], excel_date_format)

    transaction_details = transaction['Details'].lower()
    transaction_type = transaction['Type'].lower()
    if transaction_details in ['weekend fee', 'over night fee'] or transaction_type == 'sdrt':
        pos_type = 'fee'
    elif transaction_type == 'dividend':
        pos_type = 'dividend'
    else:
        raise Exception(f"Unkown fee {transaction_details} for position {transaction['Position ID']}")

    return {'id': pos_id, 'date': date, 'amount': amount, "type": pos_type}

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
        x["Date of Payment"] = datetime.strptime(str(x["Date of Payment"]), '%d/%m/%Y')
        dividend_taxes[pos_id] += [x]

    return (dividend_taxes, sheet)

def read(path):
    workbook = load_workbook(filename=path)
    transactions = convert_sheet(workbook['Account Activity'])
    grouped_transactions = group_by_pos_id(transactions)
    closed_positions = convert_sheet(workbook['Closed Positions'])
    grouped_closed_positions = group_by_pos_id(closed_positions)
    entries = []

    # sanity checks... because etoro does more bugs than I
    has_fatal_errors = False
    for row  in closed_positions:
        close_date = datetime.strptime(row['Close Date'], excel_date_format)
        open_date = datetime.strptime(row['Open Date'], excel_date_format)
        pos_id = row['Position ID']

        is_cfd = row["Type"] == "CFD"
        is_sell = row["Action"].startswith("Sell")        
        if is_sell and not is_cfd:
            raise Exception(f"Not CFD that is sell? Pos id {pos_id}")

        close_activity = next((x for x in grouped_transactions[pos_id] if x['Type'] == 'Position closed'), None)
        if close_activity is None:
            print(f'FATAL ERROR: Missing close position, report to ETORO! Position id: {pos_id}')
            has_fatal_errors = True

        if open_date.year == close_date.year:
            open_activity = next((x for x in grouped_transactions[pos_id] if x['Type'] == 'Open Position'), None)
            if open_activity is None:
                print(f'FATAL ERROR: Missing open position, report to ETORO! Position id: {pos_id}')
                has_fatal_errors = True

    # if has_fatal_errors:
    #     raise Exception('Aborting due to fatal errors')
    
    def get_asset_type(asset):
        if asset in ['Stocks', 'ETF', 'CFD']:
            return 'stock'
        elif asset == 'Crypto':
            return 'crypto'
        else:
            raise Exception(f'Failed to parse {asset}')

    open_positions = set()
    for row in transactions:
        pos_id = row['Position ID']
        date = datetime.strptime(row['Date'], excel_date_format)
        amount = Decimal(str(row["Amount"]))

        if pos_id is None:
            continue
        trans_type = row['Type']
        asset_type = row['Asset type']
        if trans_type in ['Rollover Fee', 'Dividend', 'SDRT']:
            entries.append(process_rollover_fee(row))
        elif trans_type == 'Interest Payment':
            entries.append(process_interest_payment(row))
        elif trans_type == "Open Position":
            trans = {
                'date': date,
                'amount': -amount,
                'id': pos_id,
                'closed': False,
                'type': get_asset_type(asset_type)
            }
            open_positions.add(pos_id)
            entries.append(trans)
        elif trans_type == "Position closed":
            profit = Decimal(str(row['Realized Equity Change']))
            trans = {
                    'date': date,
                    'id': pos_id,
                    'closed': True,
                    'type': get_asset_type(asset_type),
                    'equity_change': profit
                }
            if pos_id in grouped_closed_positions and datetime.strptime(grouped_closed_positions[pos_id][0]['Open Date'], excel_date_format).year < 2023:
                # backward compatility for years <= 2022 where we counted open positions differently
                trans['amount'] = profit
            else:
                trans['amount'] = amount

            entries.append(trans)
        elif trans_type not in ignored_transactions:
            raise Exception(f'Unknown transaction type "{trans_type}" for position {pos_id}')

    return (entries, grouped_transactions, grouped_closed_positions)

def read_summary(path):
    workbook = load_workbook(filename=path)
    summary = convert_sheet(workbook['Financial Summary'])
    stock_sum = Decimal('0')
    crypto_sum = Decimal('0')
    dividends_sum = Decimal('0')
    fees_sum = Decimal('0')

    for row in summary:
        if row['Name'] in ['CFDs (Profit or Loss)', 'Stocks (Profit or Loss)', 'ETFs (Profit or Loss)', 'Total Interest payments by eToro EU']:
            stock_sum += Decimal(str(row['Amount\n in (USD)']))
        elif row['Name'] == 'Crypto (Profit or Loss)':
            crypto_sum += Decimal(str(row['Amount\n in (USD)']))
        elif row['Name'] in ['Stock and ETF Dividends (Profit)', 'CFD Dividends (Profit or Loss)']:
            dividends_sum += Decimal(str(row['Amount\n in (USD)']))
        elif row['Name'] in ['Fees', 'SDRT Charge']:
            fees_sum += Decimal(str(row['Amount\n in (USD)']))
        elif row['Name'] in ['Total Return Swaps (Profit or Loss)', 'Income from Refunds', 'Income from Airdrops', 'Income from Staking', 'Income from Corporate Actions']:
            if Decimal(str(row['Amount\n in (USD)'])) != 0:
                raise Exception(f'Unupported: non-zero value for {row["Name"]} in Financial Summary')
        elif row['Name'] in ['Commissions (spread) on CFDs', 'Commissions (spread) on Crypto', 'Commissions (spread) on TRS', 'Commissions (spread) on Stocks', 'Commissions (spread) on ETFs']:
            continue
        else:
            raise Exception(f'Unupported: unknown column in {row["Name"]} in Financial Summary')

    return (stock_sum, crypto_sum, dividends_sum, fees_sum)

def process_positions(input_positions, typ, unmatched_dividend_position_ids, transactions, closed_positions, dividends):
    positions = list([x for x in input_positions if x["type"] == typ or (typ == "stock" and x['type'] == "fee")])
    income_usd = {}
    fees_usd = {}
    przychod = {}
    koszty = {}
    dochod = {}
    negative_dividend_sum = Decimal('0')
    dividends = group_by_pos_id(dividends)

    if unmatched_dividend_position_ids is not None:
        for negative_dividend in [x for x in input_positions if x['type'] == 'dividend' and x['amount'] < 0 and x['id'] in unmatched_dividend_position_ids]:
            # ujemne dywidendy traktujemy jako koszt, ale tylko dla niezmatchowanych wczesniej dywidend z sheetu 'Dividends'
            pos_id = negative_dividend['id']
            country = get_ticker_country(negative_dividend, transactions, closed_positions, dividends)
            if country == CryptoCountry:
                raise Exception(f"Found a rollover fee for crypto position {pos_id}. Should be marked as cfd?")
            fee = {'id': pos_id, 'date': negative_dividend['date'], 'amount': negative_dividend['amount'], 'country': country, "type": 'fee'}
            positions.append(fee)
            negative_dividend_sum -= negative_dividend['amount']

    for pos in positions:
        pos_id = pos['id']
        country = get_ticker_country(pos, transactions, closed_positions, dividends)
        if country not in income_usd:
            income_usd[country] = Decimal("0")
            fees_usd[country] = Decimal("0")
            przychod[country] = Decimal("0")
            koszty[country] = Decimal("0")
            dochod[country] = Decimal("0")

        rate_pln = convert_rate(pos["date"], pos["amount"], currency='USD')
        if pos["type"] == "fee":
            fees_usd[country] += pos["amount"]
            if rate_pln > 0:
                # take positive fee for CFD and count it as interest profit
                przychod[country] += rate_pln
            else:
                koszty[country] += -rate_pln
        else:
            if rate_pln < 0:
                koszty[country] += -rate_pln
            else:
                przychod[country] += rate_pln
            if pos['closed']:
                income_usd[country] += pos["equity_change"]

    for country in dochod.keys():
        dochod[country] = przychod[country] - koszty[country]

    return (sum_dict(income_usd), sum_dict(fees_usd), przychod, koszty, dochod, round(negative_dividend_sum, 2))

def process_dividends(incomes, dividend_taxes):
    dividends = [x for x in incomes if x["type"] == 'dividend']
    sum_from_dividend_taxes = sum([item["Net Dividend Received (USD)"] for sublist in dividend_taxes.values() for item in sublist])
    unmatched_dividend_position_ids = set()

    income_dividends_usd = Decimal("0")
    income_dividends_usd2 = Decimal("0")
    income_dividends_usd_brutto = Decimal("0")
    przychod_dywidendy = Decimal("0")
    podatek_nalezny_dywidendy = Decimal("0")
    podatek_zaplacony_dywidendy = Decimal("0")

    for dividend in dividends:
        pos_id = dividend["id"]
        total_usd = dividend["amount"]

        if pos_id not in dividend_taxes:
            unmatched_dividend_position_ids.add(pos_id)
            continue

        income_dividends_usd += total_usd
        dividend_tax = next((x for x in dividend_taxes[pos_id] if x["Net Dividend Received (USD)"] == total_usd and x["Date of Payment"].date()== dividend["date"].date()), None)
        if dividend_tax is None:
            raise Exception(f"Unable to match dividend for {pos_id} amount {total_usd} on {dividend['date']}")

        dividend_taxes[pos_id].remove(dividend_tax)
        if len(dividend_taxes[pos_id]) == 0:
            del dividend_taxes[pos_id]

        income_dividends_usd2 += dividend_tax["Net Dividend Received (USD)"]
        force_witholding_tax_rate = Decimal("0.15") if dividend_tax["ISIN"].startswith("US") and dividend_tax["Withholding Tax Rate (%)"] == Decimal("0.3") else dividend_tax["Withholding Tax Rate (%)"]
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
        for pos_id, tax in dividend_taxes.items():
            print(f'Pos id: {pos_id} {tax}')
        raise Exception("Suma dywidend między Dywidendy i Transaction Report się nie zgadza. Prawdopodobnie negatywne dywidendy (adjustmenty przez etoro). Zweryfikuj transakcje i manualnie zrób reconciliation w excelu.")

    if len(dividend_taxes) != 0:
        raise Exception("Niewykorzystano wszystkich dywidend do rozdzielenia podatku!")

    income_dividends_usd = round(income_dividends_usd, 2)
    income_dividends_usd_brutto = round(income_dividends_usd_brutto, 4)
    przychod_dywidendy = round(przychod_dywidendy, 4)
    podstawa_dywidendy = round(przychod_dywidendy)
    podatek_nalezny_dywidendy = round(podatek_nalezny_dywidendy)
    podatek_zaplacony_dywidendy = round(podatek_zaplacony_dywidendy)
    return (income_dividends_usd, income_dividends_usd_brutto, przychod_dywidendy, podstawa_dywidendy, podatek_nalezny_dywidendy, podatek_zaplacony_dywidendy, unmatched_dividend_position_ids)

def do_checks(fname, income_dividends_usd, income_stock_usd, fees_stock_usd, negative_dividends, income_crypto_usd, fees_crypto_usd):
    stock_sum, crypto_sum, dividends_sum, fees_sum = read_summary(fname)
    warnings = []

    if income_dividends_usd != dividends_sum:
        warnings += [f'Dividends check failed. Expected: ${dividends_sum} got {income_dividends_usd}']
    if income_stock_usd != stock_sum:
        warnings += [f'Stock check failed. Expected: ${stock_sum} got {income_stock_usd}']
    if fees_stock_usd + negative_dividends != fees_sum:
        warnings += [f'Fees check failed. Expected: ${fees_sum} got {fees_stock_usd + negative_dividends}']
    if income_crypto_usd != crypto_sum:
        warnings += [f'Crypto check failed. Expected: ${crypto_sum} got {income_crypto_usd}']

    print()
    print("-------------------------IMPORTANT----------------------------")
    if len(warnings) == 0:
        print("Congratulations! All checks with the 'Financial Summary sheet' passed!")
    else:
        [print(x) for x in warnings]
    print("-------------------------IMPORTANT----------------------------")
    print()

fname = 'statement_2023.xlsx'
entries, grouped_transactions, grouped_closed_positions = read(fname)
dividend_taxes, raw_dividends = read_dividend_taxes(fname)

income_dividends_usd, income_dividends_usd_brutto, przychod_dywidendy, podstawa_dywidendy, podatek_nalezny_dywidendy, podatek_zaplacony_dywidendy, unmatched_dividend_position_ids = process_dividends(entries, dividend_taxes)
podatek_do_zaplaty_dywidendy = podatek_nalezny_dywidendy - podatek_zaplacony_dywidendy
print()
print("Dywidendy na PIT-38 sekcja G (podatek poza granicami pln)")
print(f"Przychód $ za dywidendy ${income_dividends_usd} (w summary 'Stock and ETF Dividends (Profit)' + 'CFD Dividends (Profit or Loss)')")
print(f"Przychód $ za dywidendy brutto ${income_dividends_usd_brutto}")
print(f"Przychód w pln za dywidendy: {przychod_dywidendy} zł")
print(f"Podstawa w pln za dywidendy: {podstawa_dywidendy} zł")
print(f"Podatek należny: {podatek_nalezny_dywidendy} zł")
print(f"Podatek zapłacony za granicą: {podatek_zaplacony_dywidendy} zł")
print(f"Podatek za dywidendy: {podatek_do_zaplaty_dywidendy} zł")

income_stock_usd, fees_stock_usd, przychod_stock, koszty_stock, dochod_stock, negative_dividend_sum = process_positions(entries, 'stock', unmatched_dividend_position_ids, grouped_transactions, grouped_closed_positions, raw_dividends)
print()
print("Stocks na Pit-38 sekcja C jako inne przychody. Koniecznie z załącznikiem PIT/ZG")
print(f"Dochód $ za stocks: ${income_stock_usd} (w summary suma 'CFDs (Profit or Loss)' + 'Stocks (Profit or Loss)' + 'ETFs (Profit or Loss)' + 'Total Interest payments by eToro EU'")
print(f"Koszty $ za stocks: ${fees_stock_usd} (w tym negatywne dywidendy: ${negative_dividend_sum}) (w summary suma 'Fees' + 'SDRT Charge' - te negatywne dywidendy czyli ${fees_stock_usd+negative_dividend_sum})")
print(f"Przychód w pln za stocks: {sum_dict(przychod_stock)} zł")
print(f"Koszt w pln za stocks: {sum_dict(koszty_stock)} zł")
print(f"Dochód w pln za stocks: {sum_dict(dochod_stock)} zł")
print(f"Podatek: {max(round(sum_dict(dochod_stock) * tax_rate, 0), 0)} zł")
print(f'Dochód per kraj (na PIT/ZG wpisujemy tylko dodatnie): {dict([(x, str(y)) for x, y in dochod_stock.items() if y > 0])}')

income_crypto_usd, fees_crypto_usd, przychod_crypto, koszty_crypto, dochod_crypto, _ = process_positions(entries, 'crypto', None, grouped_transactions, grouped_closed_positions, raw_dividends)
print()
print("Crypto rozliczamy na PIT-38 sekcja E")
print(f"Dochód $ za crypto: ${income_crypto_usd} (w summary 'Crypto (Profit or Loss)')")
print(f"Koszty $ za crypto: ${fees_crypto_usd} (powinno być zawsze zero)")
print(f"Przychód w pln za crypto: {sum_dict(przychod_crypto)} zł")
print(f"Koszt w pln za crypto: {sum_dict(koszty_crypto)} zł")
print(f"Dochód w pln za crypto: {sum_dict(dochod_crypto)} zł")
print(f"Podatek: {max(round(sum_dict(dochod_crypto) * tax_rate, 0), 0)} zł")

do_checks(fname, income_dividends_usd, income_stock_usd, fees_stock_usd, negative_dividend_sum, income_crypto_usd, fees_crypto_usd)