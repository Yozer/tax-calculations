import requests, json, re

instruments_link = 'https://api.etorostatic.com/sapi/app-data/web-client/app-data/instruments-groups.json'
data_link = 'https://api.etorostatic.com/sapi/instrumentsmetadata/V1.1/instruments/bulk?bulkNumber=1&totalBulks=1'

CryptoCountry = 'CryptoCountry'
CfdCountry = 'Cypr'
instruments_by_full_symbol = None
instruments_by_display_name = None

def get_country_code(stock_name, stock_symbol, isin_code, throw=True):
    load_instruments()

    matched = None
    stock_symbol = None if stock_symbol is None else stock_symbol.lower().split(' ')[0].split('/')
    if stock_symbol is not None:

        # deal with cases like META/USD or SMTH.UK/GPB
        stock_symbol[0] = stock_symbol[0].lower().strip()
        if '.' not in stock_symbol[0] and len(stock_symbol) > 1:
            stock_symbol[1] = stock_symbol[1].lower().strip()
            if stock_symbol[1] == 'usd':
                stock_symbol[1] = ''
            elif stock_symbol[1] in stock_symbols_suffix_mapping:
                stock_symbol[1] = stock_symbols_suffix_mapping[stock_symbol[1]]
            if stock_symbol[1] in ['', None]:
                stock_symbol = stock_symbol[0]
            else:
                stock_symbol = stock_symbol[0] + '.' + stock_symbol[1]
        else:
            stock_symbol = stock_symbol[0]

    stock_name = None if stock_name is None else re.sub(r"^(buy |sell )", "", stock_name.lower()).strip()

    if (matched is None or len(matched) > 1) and stock_symbol is not None and stock_symbol in instruments_by_full_symbol:
        matched = instruments_by_full_symbol[stock_symbol]
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
    if match['InstrumentType'] == 'Cryptocurrencies':
        return CryptoCountry

    exchange = None if match['Exchange'] is None else match['Exchange'].lower().strip()
    if exchange in mapping:
        return mapping[exchange]

    if match['InstrumentType'] in ['Currencies', 'Indices', 'ETF', 'Commodities']:
        return CfdCountry

    raise Exception(f'Missing mapping for {exchange}. SymbolName: {match["SymbolFull"]}')

def load_instruments():
    global instruments_by_full_symbol
    global instruments_by_display_name

    if instruments_by_full_symbol is None:
        parsed_types = requests.get(instruments_link).json()
        instruments = parsed_types['InstrumentTypes']
        exchanges = parsed_types['ExchangeInfo']

        data = requests.get(data_link).json()['InstrumentDisplayDatas']
        all_instruments = []
        for d in data:
            # If the instrument is not available for the users, we don't need it
            if d['IsInternalInstrument']:
                continue

            instrument_typeID = d['InstrumentTypeID']
            name = d['InstrumentDisplayName']
            exchangeID = d['ExchangeID']
            symbol = d['SymbolFull']
            instrument_type = next(item for item in instruments if item['InstrumentTypeID'] == instrument_typeID)['InstrumentTypeDescription']

            try:
                exchange = next(item for item in exchanges if item['ExchangeID'] == exchangeID)['ExchangeDescription']
            except StopIteration:
                exchange = None

            # Sum up the gathered data
            all_instruments.append({
                'InstrumentDisplayName': name,
                'SymbolFull': symbol,
                'InstrumentType': instrument_type,
                'Exchange': exchange
            })

        instruments_by_full_symbol = create_dict(all_instruments, lambda y: str(y['SymbolFull']).lower())
        instruments_by_display_name = create_dict(all_instruments, lambda y: str(y['InstrumentDisplayName']).lower())

def create_dict(a, keyFunc):
    result = {}
    for x in a:
        k = keyFunc(x)
        if k not in result:
            result[k] = []
        result[k] += [x]

    return result

stock_symbols_suffix_mapping = {
    'dkk': 'co',
    'gbx': 'l',
    'chf': 'zu',
}
mapping = {

    # 'nsdq': 'USA',
    'nasdaq': 'USA',
    'nyse': 'USA',

    'stockholm': 'Szwecja',
    'copenhagen': 'Dania',
    'frankfurt': 'Niemcy',
    'london': 'Wielka Brytania',
    'bolsademadrid': 'Hiszpania',
    'zurich': 'Szwajcaria',
    'paris': 'Francja',
    'oslo': 'Norwegia',
    'hongkong': 'Hong Kong',
    'helsinki': 'Finlandia'

    # 'hong kong exchanges': 'Hong Kong',
    # 'lse': 'Wielka Brytania',
    # 'six': 'Szwajcaria',
    # 'bolsa de madrid': 'Hiszpania',
    # 'euronext paris': 'Francja',
    # 'fra': 'Niemcy',
    # 'cse': 'Kanada',
    # 'hel': 'Finlandia'
}