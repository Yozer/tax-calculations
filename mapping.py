from openpyxl import load_workbook
from helpers import convert_sheet

instruments_fname = 'instruments.xlsx'
instruments_by_symbol = None
instruments_by_full_symbol = None
instruments_by_display_name = None

def get_country_code(stock_name, stock_symbol, pos_id, by_stock = False):
    load_instruments()

    matched = None
    stock_symbol = stock_symbol.lower().split('/')[0]
    stock_name = stock_name.lower().replace("buy ", "").replace("sell ", "")

    if stock_symbol in instruments_by_full_symbol:
        matched = instruments_by_full_symbol[stock_symbol]
    elif stock_symbol in instruments_by_symbol:
        matched = instruments_by_symbol[stock_symbol]
    elif stock_name in instruments_by_display_name:
        matched = instruments_by_display_name[stock_name]

    if matched is None:
        raise Exception(f'Unknown country for pos {pos_id} {stock_name}')
    if len(matched) > 1:
        raise Exception(f'More than one country for pos {pos_id} {stock_name}')
    
    if by_stock:
        country_code = matched[0]['ISINCountryCode']
        return country_code if country_code not in country_codes else country_codes[country_code]
    else:
        exchange = matched[0]['Exchange'].lower()
        return exchange if exchange not in mapping else mapping[exchange]

def load_instruments():
    global instruments_by_symbol
    global instruments_by_full_symbol
    global instruments_by_display_name

    if instruments_by_full_symbol is None:
        workbook = load_workbook(filename=instruments_fname, read_only=False)
        sheet = workbook['Instruments Offered']
        x = [y for y in convert_sheet(sheet) if y['SymbolFull'] is not None]

        instruments_by_symbol = create_dict(x, lambda y: str(y['Symbol']).lower())
        instruments_by_full_symbol = create_dict(x, lambda y: str(y['SymbolFull']).lower())
        instruments_by_display_name = create_dict(x, lambda y: str(y['InstrumentDisplayName']).lower())

def create_dict(a, keyFunc):
    result = {}
    for x in a:
        k = keyFunc(x)
        if k not in result:
            result[k] = []
        result[k] += [x]
    
    return result

country_codes = {
    'US': 'USA',
    'CA': 'Kanada',
    'CY': 'Cypr',
    'KY': 'Kajmany',
    'GB': 'Wielka Brytania',
    'CHF': 'Szwajcaria',
    'CN': 'Chiny',
    'ES': 'Hiszpania',
    'FR': 'Francja',
    'DE': 'Niemcy',
    'IL': 'Izrael'
}

mapping = {
    'nsdq': 'USA',
    'nasdaq': 'USA',
    'nyse': 'USA',
    'hong kong exchanges': 'Hong Kong',
    'lse': 'Wielka Brytania',
    'six': 'Szwajcaria',
    'bolsa de madrid': 'Hiszpania',
    'euronext paris': 'Francja',
    'fra': 'Niemcy'
}