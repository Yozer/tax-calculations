import requests, json, re

instruments_link = 'https://api.etorostatic.com/sapi/app-data/web-client/app-data/instruments-groups.json'
data_link = 'https://api.etorostatic.com/sapi/instrumentsmetadata/V1.1/instruments/bulk?bulkNumber=1&totalBulks=1'
etoro_url = 'https://x9rg52m4oj-dsn.algolia.net/1/indexes/*/queries?x-algolia-agent=Algolia%20for%20JavaScript%20(4.24.0)%3B%20Browser%20(lite)&x-algolia-api-key=7334b1dccb57b5813a853855dfa41ce8&x-algolia-application-id=X9RG52M4OJ'

CryptoCountry = 'CryptoCountry'
CfdCountry = 'Cypr'
instruments_by_full_symbol = None
instruments_by_display_name = None
eur_exchange_suffixes = ['mi', 'pa']
manual_mapping = {'UBSG/CHF': 'Szwajcaria', 'ANA/EUR': 'Hiszpania', 'LQDE/USD': 'Irlandia', 'IBE/EUR': 'Hiszpania'}
etoro_cache = {}

def ask_etoro_cached(query, stock_symbol=None):
    if query in etoro_cache:
        return etoro_cache[query]
    
    if stock_symbol is None:
        stock_symbol = query

    raw = '{"requests":[{"indexName":"prod_Instruments","query":"' + query + '","ruleContexts":["country_poland","remove_futures"],"params":"hitsPerPage=15&clickAnalytics=true"}]}'
    r = requests.post(etoro_url, data=raw)
    if r.status_code != 200:
        raise Exception('failed query!')
    result = r.json()['results'][0]['hits']
    result_filtered = list([r['countryFull'] for r in result if r['name'].lower() == stock_symbol.lower() or r['symbolFull'].lower() == stock_symbol.lower()])
    etoro_cache[query] = result_filtered
    return result_filtered

def get_country_code(stock_name, stock_symbol):
    load_instruments()

    if stock_symbol in manual_mapping:
        return manual_mapping[stock_symbol]

    stock_symbol_original = stock_symbol
    matched = []
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
                stock_symbol_parsed = stock_symbol[0]
            else:
                stock_symbol_parsed = stock_symbol[0] + '.' + stock_symbol[1]
        else:
            stock_symbol_parsed = stock_symbol[0]

    stock_name = None if stock_name is None else re.sub(r"^(buy |sell )", "", stock_name.lower()).strip()

    if len(matched) != 1 and stock_name is not None and stock_name in instruments_by_display_name:
        matched += instruments_by_display_name[stock_name]
    if len(matched) != 1 and stock_symbol_parsed is not None and stock_symbol_parsed in instruments_by_full_symbol:
        matched += instruments_by_full_symbol[stock_symbol_parsed]
    if len(matched) != 1 and len(stock_symbol) == 2 and stock_symbol[1] == 'eur':
        for suffix in eur_exchange_suffixes:
            stock_symbol_parsed = stock_symbol[0] + '.' + suffix
            if stock_symbol_parsed is not None and stock_symbol_parsed in instruments_by_full_symbol:
                matched += instruments_by_full_symbol[stock_symbol_parsed]

    countries = set([x for x in map(get_country_code_from_match, matched) if x != None])
    if len(countries) == 0:
        countries_etoro = ask_etoro_cached(stock_name, stock_symbol_original)
        if len(countries_etoro) == 0:
            countries_etoro = ask_etoro_cached(stock_symbol_parsed)
        countries = set([mapping[x] for x in countries_etoro if x != None and x != '' and x in mapping])
        if len(countries) == 0 and len(countries_etoro) > 0:
            raise Exception("Missing mapping for " + str(countries_etoro))
    if len(countries) == 0:
        raise Exception(f'Unknown country stock name: "{stock_name}" stock symbol: "{stock_symbol_original}"')

    if len(countries) > 1:
        raise Exception(f'More than one country "{stock_name}" and "{stock_symbol_original}" {countries}')

    return countries.pop()

def get_country_code_from_match(match):
    if match['InstrumentType'] == 'Cryptocurrencies':
        return CryptoCountry

    exchange = None if match['Exchange'] is None else match['Exchange'].lower().strip()
    if exchange is None:
        return None
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
                'Exchange': exchange,
                'ExchangeId': exchangeID
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
    'sek': 'st'
}
mapping = {

    # 'nsdq': 'USA',
    'nasdaq': 'USA',
    'nyse': 'USA',
    'USA': 'USA',
    'United States': 'USA',
    
    'stockholm': 'Szwecja',
    'copenhagen': 'Dania',
    'frankfurt': 'Niemcy',
    'london': 'Wielka Brytania',
    'bolsademadrid': 'Hiszpania',
    'zurich': 'Szwajcaria',
    'paris': 'Francja',
    'oslo': 'Norwegia',
    'hongkong': 'Hong Kong',
    'helsinki': 'Finlandia',
    'borsaitaliana': 'Włochy',

    'France': 'Francja',
    'Germany': 'Niemcy',

    # 'hong kong exchanges': 'Hong Kong',
    # 'lse': 'Wielka Brytania',
    # 'six': 'Szwajcaria',
    # 'bolsa de madrid': 'Hiszpania',
    # 'euronext paris': 'Francja',
    # 'fra': 'Niemcy',
    # 'cse': 'Kanada',
    # 'hel': 'Finlandia'
}