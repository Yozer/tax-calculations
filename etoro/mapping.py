from openpyxl import load_workbook
from helpers import convert_sheet

CryptoCountry = 'CryptoCountry'
CfdCountry = 'Cypr'
instruments_fname = 'instruments.xlsx'
instruments_by_symbol = None
instruments_by_full_symbol = None
instruments_by_display_name = None
instruments_by_isin = None

def get_country_code(stock_name, stock_symbol, isin_code, throw=True):
    load_instruments()

    matched = None
    stock_symbol = None if stock_symbol is None else stock_symbol.lower().split('/')[0]
    stock_name = None if stock_name is None else stock_name.lower().replace("buy ", "").replace("sell ", "")
    isin_code = None if isin_code is None else isin_code.lower()

    if isin_code is not None and isin_code in instruments_by_isin:
        matched = instruments_by_isin[isin_code]
    if (matched is None or len(matched) > 1) and stock_symbol is not None and stock_symbol in instruments_by_full_symbol:
        matched = instruments_by_full_symbol[stock_symbol]
    if (matched is None or len(matched) > 1) and stock_symbol is not None and stock_symbol in instruments_by_symbol:
        matched = instruments_by_symbol[stock_symbol]
    if (matched is None or len(matched) > 1) and stock_name is not None and stock_name in instruments_by_display_name:
        matched = instruments_by_display_name[stock_name]

    if matched is None:
        if throw:
            raise Exception(f'Unknown country for ISIN: "{isin_code}" stock name: "{stock_name}"')
        else:
            return None

    countries = set(map(get_country_code_from_match, matched))
    if len(countries) > 1:
        raise Exception(f'More than one country for isin {isin_code} {stock_name}')

    return countries.pop()

def get_country_code_from_match(match):
    countryCode = None if match['ISINCountryCode'] is None else match['ISINCountryCode'].lower().strip()

    if countryCode in country_mapping:
        return country_mapping[countryCode]
    elif countryCode not in [None, '', 'null']:
        raise Exception(f'Missing country {countryCode}')

    exchange = None if match['Exchange'] is None else match['Exchange'].lower().strip()
    if exchange in mapping:
        return mapping[exchange]

    raise Exception(f'Missing mapping for {exchange}')

def load_instruments():
    global instruments_by_symbol
    global instruments_by_full_symbol
    global instruments_by_display_name
    global instruments_by_isin

    if instruments_by_full_symbol is None:
        workbook = load_workbook(filename=instruments_fname, read_only=False)
        sheet = workbook['Instruments Offered']
        x = [y for y in convert_sheet(sheet) if y['SymbolFull'] is not None]

        instruments_by_symbol = create_dict(x, lambda y: str(y['Symbol']).lower())
        instruments_by_full_symbol = create_dict(x, lambda y: str(y['SymbolFull']).lower())
        instruments_by_display_name = create_dict(x, lambda y: str(y['InstrumentDisplayName']).lower())
        instruments_by_isin = create_dict(x, lambda y: str(y['ISINCode']).lower())

def create_dict(a, keyFunc):
    result = {}
    for x in a:
        k = keyFunc(x)
        if k not in result:
            result[k] = []
        result[k] += [x]

    return result

country_mapping = {
    'bm': 'Bermudy',
    'us': 'USA',
    'se': 'Szwecja',
    'fr': 'Francja',
    'gg': 'Guernsey (GB jak nie ma w formularzu)',
    'je': 'Jersey  (GB jak nie ma w formularzu)',
    'gb': 'Wielka Brytania',
    'ca': 'Kanada',
    'de': 'Niemcy',
    'lu': 'Luksemburg',
    'es': 'Hiszpania',
    'chf': 'Szwajcaria',
    'ch': 'Szwajcaria',
    'il': 'Izrael',
    'ky': 'Kajmany',
    'nl': 'Holandia',
    'cn': 'Chiny',
    'no': 'Norwegia',
    'ie': 'Irlandia',
    'hk': 'Hong Kong'
}

mapping = {
    'fx': CfdCountry,
    'commodity': CfdCountry,
    'digital currency': CryptoCountry,

    'nsdq': 'USA',
    'nasdaq': 'USA',
    'nyse': 'USA',

    'hong kong exchanges': 'Hong Kong',
    'lse': 'Wielka Brytania',
    'six': 'Szwajcaria',
    'bolsa de madrid': 'Hiszpania',
    'euronext paris': 'Francja',
    'fra': 'Niemcy',
    'cse': 'Kanada',
    'hel': 'Finlandia'
}