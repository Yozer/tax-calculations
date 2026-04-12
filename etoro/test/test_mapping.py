import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

import pytest
from unittest.mock import patch, MagicMock
import mapping as m


# ============================================================
# create_dict
# ============================================================

class TestCreateDict:
    def test_empty_list(self):
        assert m.create_dict([], lambda x: x) == {}

    def test_single_item(self):
        result = m.create_dict([{'k': 'a', 'v': 1}], lambda x: x['k'])
        assert result == {'a': [{'k': 'a', 'v': 1}]}

    def test_multiple_same_key(self):
        items = [{'k': 'a', 'v': 1}, {'k': 'a', 'v': 2}]
        result = m.create_dict(items, lambda x: x['k'])
        assert len(result['a']) == 2

    def test_multiple_different_keys(self):
        items = [{'k': 'a'}, {'k': 'b'}, {'k': 'c'}]
        result = m.create_dict(items, lambda x: x['k'])
        assert len(result) == 3
        assert len(result['a']) == 1

    def test_key_function_transform(self):
        items = [{'name': 'Apple'}, {'name': 'APPLE'}]
        result = m.create_dict(items, lambda x: x['name'].lower())
        assert len(result['apple']) == 2


# ============================================================
# get_country_code_from_match
# ============================================================

class TestGetCountryCodeFromMatch:
    def test_cryptocurrency(self):
        match = {'InstrumentType': 'Cryptocurrencies', 'Exchange': None, 'SymbolFull': 'BTC'}
        assert m.get_country_code_from_match(match) == m.CryptoCountry

    def test_exchange_none_returns_none(self):
        match = {'InstrumentType': 'Stocks', 'Exchange': None, 'SymbolFull': 'X'}
        assert m.get_country_code_from_match(match) is None

    def test_nasdaq(self):
        match = {'InstrumentType': 'Stocks', 'Exchange': 'Nasdaq', 'SymbolFull': 'AAPL'}
        assert m.get_country_code_from_match(match) == 'USA'

    def test_nyse(self):
        match = {'InstrumentType': 'Stocks', 'Exchange': 'NYSE', 'SymbolFull': 'GS'}
        assert m.get_country_code_from_match(match) == 'USA'

    def test_london(self):
        match = {'InstrumentType': 'Stocks', 'Exchange': 'London', 'SymbolFull': 'BARC.L'}
        assert m.get_country_code_from_match(match) == 'Wielka Brytania'

    def test_frankfurt(self):
        match = {'InstrumentType': 'Stocks', 'Exchange': 'Frankfurt', 'SymbolFull': 'SAP.DE'}
        assert m.get_country_code_from_match(match) == 'Niemcy'

    def test_paris(self):
        match = {'InstrumentType': 'Stocks', 'Exchange': 'Paris', 'SymbolFull': 'AIR.PA'}
        assert m.get_country_code_from_match(match) == 'Francja'

    def test_zurich(self):
        match = {'InstrumentType': 'Stocks', 'Exchange': 'Zurich', 'SymbolFull': 'NESN.ZU'}
        assert m.get_country_code_from_match(match) == 'Szwajcaria'

    def test_stockholm(self):
        match = {'InstrumentType': 'Stocks', 'Exchange': 'Stockholm', 'SymbolFull': 'VOLV.ST'}
        assert m.get_country_code_from_match(match) == 'Szwecja'

    def test_copenhagen(self):
        match = {'InstrumentType': 'Stocks', 'Exchange': 'Copenhagen', 'SymbolFull': 'NOVO.CO'}
        assert m.get_country_code_from_match(match) == 'Dania'

    def test_oslo(self):
        match = {'InstrumentType': 'Stocks', 'Exchange': 'Oslo', 'SymbolFull': 'EQNR.OL'}
        assert m.get_country_code_from_match(match) == 'Norwegia'

    def test_hongkong(self):
        match = {'InstrumentType': 'Stocks', 'Exchange': 'HongKong', 'SymbolFull': '0700.HK'}
        assert m.get_country_code_from_match(match) == 'Hong Kong'

    def test_helsinki(self):
        match = {'InstrumentType': 'Stocks', 'Exchange': 'Helsinki', 'SymbolFull': 'NOKIA.HE'}
        assert m.get_country_code_from_match(match) == 'Finlandia'

    def test_borsaitaliana(self):
        match = {'InstrumentType': 'Stocks', 'Exchange': 'BorsaItaliana', 'SymbolFull': 'ENI.MI'}
        assert m.get_country_code_from_match(match) == 'Włochy'

    def test_bolsademadrid(self):
        match = {'InstrumentType': 'Stocks', 'Exchange': 'BolsaDeMadrid', 'SymbolFull': 'TEF.MC'}
        assert m.get_country_code_from_match(match) == 'Hiszpania'

    def test_exchange_case_insensitive(self):
        match = {'InstrumentType': 'Stocks', 'Exchange': '  NASDAQ  ', 'SymbolFull': 'AAPL'}
        assert m.get_country_code_from_match(match) == 'USA'

    def test_currencies_returns_cfd_country(self):
        match = {'InstrumentType': 'Currencies', 'Exchange': 'SomeExchange', 'SymbolFull': 'EURUSD'}
        assert m.get_country_code_from_match(match) == m.CfdCountry

    def test_indices_returns_cfd_country(self):
        match = {'InstrumentType': 'Indices', 'Exchange': 'SomeExchange', 'SymbolFull': 'SPX500'}
        assert m.get_country_code_from_match(match) == m.CfdCountry

    def test_etf_returns_cfd_country(self):
        match = {'InstrumentType': 'ETF', 'Exchange': 'SomeExchange', 'SymbolFull': 'SPY'}
        assert m.get_country_code_from_match(match) == m.CfdCountry

    def test_commodities_returns_cfd_country(self):
        match = {'InstrumentType': 'Commodities', 'Exchange': 'SomeExchange', 'SymbolFull': 'GOLD'}
        assert m.get_country_code_from_match(match) == m.CfdCountry

    def test_unknown_exchange_stocks_raises(self):
        match = {'InstrumentType': 'Stocks', 'Exchange': 'MarsExchange', 'SymbolFull': 'MARS'}
        with pytest.raises(Exception, match='Missing mapping for marsexchange'):
            m.get_country_code_from_match(match)


# ============================================================
# ask_etoro_cached
# ============================================================

class TestAskEtoroCached:
    def _mock_response(self, hits, status_code=200):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = {'results': [{'hits': hits}]}
        return mock_resp

    def setup_method(self):
        m.etoro_cache.clear()

    @patch('mapping.requests.post')
    def test_basic_match_by_symbol(self, mock_post):
        mock_post.return_value = self._mock_response([
            {'instrumentDisplayName': 'Apple', 'symbolFull': 'AAPL', 'countryFull': 'United States'}
        ])
        result = m.ask_etoro_cached('apple', 'AAPL')
        assert result == ['United States']

    @patch('mapping.requests.post')
    def test_match_by_display_name(self, mock_post):
        mock_post.return_value = self._mock_response([
            {'instrumentDisplayName': 'Apple', 'symbolFull': 'AAPL', 'countryFull': 'United States'}
        ])
        result = m.ask_etoro_cached('apple', 'Apple')
        assert result == ['United States']

    @patch('mapping.requests.post')
    def test_match_by_query_exact(self, mock_post):
        mock_post.return_value = self._mock_response([
            {'instrumentDisplayName': 'Apple', 'symbolFull': 'AAPL', 'countryFull': 'United States'}
        ])
        result = m.ask_etoro_cached('Apple', 'SOMETHING_ELSE')
        assert result == ['United States']

    @patch('mapping.requests.post')
    def test_match_by_query_no_ticker_suffix(self, mock_post):
        """Handles 'S&P Global Inc (SPGI)' -> strips '(SPGI)' -> matches 'S&P Global Inc'"""
        mock_post.return_value = self._mock_response([
            {'instrumentDisplayName': 'S&P Global Inc', 'symbolFull': 'SPGI', 'countryFull': 'United States'}
        ])
        result = m.ask_etoro_cached('S&P Global Inc (SPGI)', 'MHFI/USD')
        assert result == ['United States']

    @patch('mapping.requests.post')
    def test_no_false_positive_substring_match(self, mock_post):
        """'My Cool' should NOT match query 'my cool company (mcc)'"""
        mock_post.return_value = self._mock_response([
            {'instrumentDisplayName': 'My Cool', 'symbolFull': 'MC', 'countryFull': 'Germany'},
            {'instrumentDisplayName': 'My Cool Company', 'symbolFull': 'MCC', 'countryFull': 'United States'}
        ])
        result = m.ask_etoro_cached('my cool company (mcc)', 'MCC/USD')
        # 'My Cool' should not match (not equal to query or query_no_ticker)
        # 'My Cool Company' matches query_no_ticker
        assert result == ['United States']

    @patch('mapping.requests.post')
    def test_no_match_returns_empty(self, mock_post):
        mock_post.return_value = self._mock_response([
            {'instrumentDisplayName': 'Unrelated', 'symbolFull': 'UNR', 'countryFull': 'France'}
        ])
        result = m.ask_etoro_cached('apple', 'AAPL')
        assert result == []

    @patch('mapping.requests.post')
    def test_missing_country_full_skipped(self, mock_post):
        mock_post.return_value = self._mock_response([
            {'instrumentDisplayName': 'Apple', 'symbolFull': 'AAPL'},  # no countryFull
            {'instrumentDisplayName': 'Apple', 'symbolFull': 'AAPL', 'countryFull': ''},  # empty
            {'instrumentDisplayName': 'Apple', 'symbolFull': 'AAPL', 'countryFull': 'United States'},
        ])
        result = m.ask_etoro_cached('apple', 'AAPL')
        assert result == ['United States']

    @patch('mapping.requests.post')
    def test_cache_hit(self, mock_post):
        mock_post.return_value = self._mock_response([
            {'instrumentDisplayName': 'Apple', 'symbolFull': 'AAPL', 'countryFull': 'United States'}
        ])
        m.ask_etoro_cached('apple', 'AAPL')
        m.ask_etoro_cached('apple', 'AAPL')
        assert mock_post.call_count == 1

    @patch('mapping.requests.post')
    def test_stock_symbol_defaults_to_query(self, mock_post):
        mock_post.return_value = self._mock_response([
            {'instrumentDisplayName': 'test_query', 'symbolFull': 'TQ', 'countryFull': 'France'}
        ])
        result = m.ask_etoro_cached('test_query')
        assert result == ['France']

    @patch('mapping.requests.post')
    def test_api_failure_raises(self, mock_post):
        mock_post.return_value = self._mock_response([], status_code=500)
        with pytest.raises(Exception, match='failed query'):
            m.ask_etoro_cached('apple', 'AAPL')

    @patch('mapping.requests.post')
    def test_case_insensitive_matching(self, mock_post):
        mock_post.return_value = self._mock_response([
            {'instrumentDisplayName': 'APPLE INC', 'symbolFull': 'aapl', 'countryFull': 'United States'}
        ])
        result = m.ask_etoro_cached('apple inc', 'AAPL')
        assert result == ['United States']


# ============================================================
# get_country_code - with mocked load_instruments
# ============================================================

def _setup_instruments(by_symbol=None, by_name=None):
    """Patch the global instrument dicts."""
    m.instruments_by_full_symbol = by_symbol or {}
    m.instruments_by_display_name = by_name or {}


class TestGetCountryCode:
    def setup_method(self):
        m.etoro_cache.clear()

    @patch('mapping.load_instruments')
    def test_manual_mapping(self, mock_li):
        _setup_instruments()
        assert m.get_country_code(None, 'UBSG/CHF') == 'Szwajcaria'
        assert m.get_country_code(None, 'ANA/EUR') == 'Hiszpania'
        assert m.get_country_code(None, 'LQDE/USD') == 'Irlandia'
        assert m.get_country_code(None, 'IBE/EUR') == 'Hiszpania'

    @patch('mapping.load_instruments')
    def test_match_by_display_name(self, mock_li):
        _setup_instruments(
            by_name={'apple': [{'InstrumentType': 'Stocks', 'Exchange': 'Nasdaq', 'SymbolFull': 'AAPL'}]}
        )
        result = m.get_country_code('Buy Apple', 'AAPL/USD')
        assert result == 'USA'

    @patch('mapping.load_instruments')
    def test_match_by_symbol_usd_stripped(self, mock_li):
        _setup_instruments(
            by_symbol={'aapl': [{'InstrumentType': 'Stocks', 'Exchange': 'Nasdaq', 'SymbolFull': 'AAPL'}]}
        )
        result = m.get_country_code(None, 'AAPL/USD')
        assert result == 'USA'

    @patch('mapping.load_instruments')
    def test_gbx_suffix_mapped_to_l(self, mock_li):
        _setup_instruments(
            by_symbol={'barc.l': [{'InstrumentType': 'Stocks', 'Exchange': 'London', 'SymbolFull': 'BARC.L'}]}
        )
        result = m.get_country_code(None, 'BARC/GBX')
        assert result == 'Wielka Brytania'

    @patch('mapping.load_instruments')
    def test_dkk_suffix_mapped_to_co(self, mock_li):
        _setup_instruments(
            by_symbol={'novo.co': [{'InstrumentType': 'Stocks', 'Exchange': 'Copenhagen', 'SymbolFull': 'NOVO.CO'}]}
        )
        result = m.get_country_code(None, 'NOVO/DKK')
        assert result == 'Dania'

    @patch('mapping.load_instruments')
    def test_chf_suffix_mapped_to_zu(self, mock_li):
        _setup_instruments(
            by_symbol={'nesn.zu': [{'InstrumentType': 'Stocks', 'Exchange': 'Zurich', 'SymbolFull': 'NESN.ZU'}]}
        )
        result = m.get_country_code(None, 'NESN/CHF')
        assert result == 'Szwajcaria'

    @patch('mapping.load_instruments')
    def test_sek_suffix_mapped_to_st(self, mock_li):
        _setup_instruments(
            by_symbol={'volv.st': [{'InstrumentType': 'Stocks', 'Exchange': 'Stockholm', 'SymbolFull': 'VOLV.ST'}]}
        )
        result = m.get_country_code(None, 'VOLV/SEK')
        assert result == 'Szwecja'

    @patch('mapping.load_instruments')
    def test_eur_suffix_tries_mi_and_pa(self, mock_li):
        _setup_instruments(
            by_symbol={'eni.mi': [{'InstrumentType': 'Stocks', 'Exchange': 'BorsaItaliana', 'SymbolFull': 'ENI.MI'}]}
        )
        result = m.get_country_code(None, 'ENI/EUR')
        assert result == 'Włochy'

    @patch('mapping.load_instruments')
    def test_eur_suffix_pa(self, mock_li):
        _setup_instruments(
            by_symbol={'air.pa': [{'InstrumentType': 'Stocks', 'Exchange': 'Paris', 'SymbolFull': 'AIR.PA'}]}
        )
        result = m.get_country_code(None, 'AIR/EUR')
        assert result == 'Francja'

    @patch('mapping.load_instruments')
    def test_dotted_symbol_no_suffix_processing(self, mock_li):
        """Symbol with dot in first part (e.g. 'SMTH.UK') should be used as-is"""
        _setup_instruments(
            by_symbol={'smth.uk': [{'InstrumentType': 'Stocks', 'Exchange': 'London', 'SymbolFull': 'SMTH.UK'}]}
        )
        result = m.get_country_code(None, 'SMTH.UK/GBX')
        assert result == 'Wielka Brytania'

    @patch('mapping.load_instruments')
    def test_sell_prefix_stripped_from_name(self, mock_li):
        _setup_instruments(
            by_name={'apple': [{'InstrumentType': 'Stocks', 'Exchange': 'Nasdaq', 'SymbolFull': 'AAPL'}]}
        )
        result = m.get_country_code('Sell Apple', 'AAPL/USD')
        assert result == 'USA'

    @patch('mapping.load_instruments')
    def test_buy_prefix_stripped_from_name(self, mock_li):
        _setup_instruments(
            by_name={'apple': [{'InstrumentType': 'Stocks', 'Exchange': 'Nasdaq', 'SymbolFull': 'AAPL'}]}
        )
        result = m.get_country_code('Buy Apple', 'AAPL/USD')
        assert result == 'USA'

    @patch('mapping.load_instruments')
    @patch('mapping.ask_etoro_cached', return_value=['United States'])
    def test_fallback_to_etoro_api(self, mock_ask, mock_li):
        _setup_instruments()
        result = m.get_country_code('Apple Inc', 'AAPL/USD')
        assert result == 'USA'
        mock_ask.assert_called()

    @patch('mapping.load_instruments')
    @patch('mapping.ask_etoro_cached', return_value=[])
    def test_unknown_country_raises(self, mock_ask, mock_li):
        _setup_instruments()
        with pytest.raises(Exception, match='Unknown country'):
            m.get_country_code('NonExistent Corp', 'XXXX/USD')

    @patch('mapping.load_instruments')
    def test_more_than_one_country_raises(self, mock_li):
        _setup_instruments(
            by_name={'ambiguous': [
                {'InstrumentType': 'Stocks', 'Exchange': 'Nasdaq', 'SymbolFull': 'AMB'},
                {'InstrumentType': 'Stocks', 'Exchange': 'London', 'SymbolFull': 'AMB.L'},
            ]}
        )
        with pytest.raises(Exception, match='More than one country'):
            m.get_country_code('Ambiguous', 'SOMETHING/USD')

    @patch('mapping.load_instruments')
    @patch('mapping.ask_etoro_cached', return_value=['Narnia'])
    def test_missing_mapping_raises(self, mock_ask, mock_li):
        _setup_instruments()
        with pytest.raises(Exception, match='Missing mapping'):
            m.get_country_code('Narnia Corp', 'NARN/USD')

    @patch('mapping.load_instruments')
    @patch('mapping.ask_etoro_cached')
    def test_fallback_to_symbol_parsed_query(self, mock_ask, mock_li):
        """If first ask_etoro_cached returns empty, tries with parsed symbol"""
        _setup_instruments()
        mock_ask.side_effect = [[], ['United States']]
        result = m.get_country_code('NonExistent', 'AAPL/USD')
        assert result == 'USA'
        assert mock_ask.call_count == 2
        # Second call should use parsed symbol 'aapl'
        assert mock_ask.call_args_list[1][0][0] == 'aapl'

    @patch('mapping.load_instruments')
    def test_name_match_takes_priority(self, mock_li):
        """If name matches one instrument, don't try symbol"""
        _setup_instruments(
            by_name={'apple': [{'InstrumentType': 'Stocks', 'Exchange': 'Nasdaq', 'SymbolFull': 'AAPL'}]},
            by_symbol={'aapl': [
                {'InstrumentType': 'Stocks', 'Exchange': 'Nasdaq', 'SymbolFull': 'AAPL'},
                {'InstrumentType': 'Stocks', 'Exchange': 'London', 'SymbolFull': 'AAPL.L'},
            ]}
        )
        result = m.get_country_code('Buy Apple', 'AAPL/USD')
        assert result == 'USA'

    @patch('mapping.load_instruments')
    def test_symbol_only_no_currency(self, mock_li):
        _setup_instruments(
            by_symbol={'tsla': [{'InstrumentType': 'Stocks', 'Exchange': 'Nasdaq', 'SymbolFull': 'TSLA'}]}
        )
        result = m.get_country_code(None, 'TSLA')
        assert result == 'USA'


# ============================================================
# load_instruments
# ============================================================

class TestLoadInstruments:
    def setup_method(self):
        m.instruments_by_full_symbol = None
        m.instruments_by_display_name = None

    @patch('mapping.requests.get')
    def test_loads_and_caches(self, mock_get):
        groups_response = MagicMock()
        groups_response.json.return_value = {
            'InstrumentTypes': [{'InstrumentTypeID': 5, 'InstrumentTypeDescription': 'Stocks'}],
            'ExchangeInfo': [{'ExchangeID': 4, 'ExchangeDescription': 'Nasdaq'}],
        }
        data_response = MagicMock()
        data_response.json.return_value = {
            'InstrumentDisplayDatas': [
                {
                    'IsInternalInstrument': False,
                    'InstrumentTypeID': 5,
                    'InstrumentDisplayName': 'Apple',
                    'ExchangeID': 4,
                    'SymbolFull': 'AAPL',
                },
            ]
        }
        mock_get.side_effect = [groups_response, data_response]

        m.load_instruments()

        assert 'aapl' in m.instruments_by_full_symbol
        assert 'apple' in m.instruments_by_display_name
        assert m.instruments_by_full_symbol['aapl'][0]['Exchange'] == 'Nasdaq'

        # Second call should not fetch again
        m.load_instruments()
        assert mock_get.call_count == 2  # only from first call

    @patch('mapping.requests.get')
    def test_skips_internal_instruments(self, mock_get):
        groups_response = MagicMock()
        groups_response.json.return_value = {
            'InstrumentTypes': [{'InstrumentTypeID': 5, 'InstrumentTypeDescription': 'Stocks'}],
            'ExchangeInfo': [{'ExchangeID': 4, 'ExchangeDescription': 'Nasdaq'}],
        }
        data_response = MagicMock()
        data_response.json.return_value = {
            'InstrumentDisplayDatas': [
                {
                    'IsInternalInstrument': True,
                    'InstrumentTypeID': 5,
                    'InstrumentDisplayName': 'Internal',
                    'ExchangeID': 4,
                    'SymbolFull': 'INT',
                },
                {
                    'IsInternalInstrument': False,
                    'InstrumentTypeID': 5,
                    'InstrumentDisplayName': 'Public',
                    'ExchangeID': 4,
                    'SymbolFull': 'PUB',
                },
            ]
        }
        mock_get.side_effect = [groups_response, data_response]

        m.load_instruments()

        assert 'int' not in m.instruments_by_full_symbol
        assert 'pub' in m.instruments_by_full_symbol

    @patch('mapping.requests.get')
    def test_unknown_exchange_id_sets_none(self, mock_get):
        groups_response = MagicMock()
        groups_response.json.return_value = {
            'InstrumentTypes': [{'InstrumentTypeID': 5, 'InstrumentTypeDescription': 'Stocks'}],
            'ExchangeInfo': [],  # no exchanges
        }
        data_response = MagicMock()
        data_response.json.return_value = {
            'InstrumentDisplayDatas': [
                {
                    'IsInternalInstrument': False,
                    'InstrumentTypeID': 5,
                    'InstrumentDisplayName': 'Mystery',
                    'ExchangeID': 999,
                    'SymbolFull': 'MYS',
                },
            ]
        }
        mock_get.side_effect = [groups_response, data_response]

        m.load_instruments()

        assert m.instruments_by_full_symbol['mys'][0]['Exchange'] is None


# ============================================================
# stock_symbols_suffix_mapping
# ============================================================

class TestSuffixMapping:
    def test_all_suffixes_present(self):
        assert m.stock_symbols_suffix_mapping['dkk'] == 'co'
        assert m.stock_symbols_suffix_mapping['gbx'] == 'l'
        assert m.stock_symbols_suffix_mapping['chf'] == 'zu'
        assert m.stock_symbols_suffix_mapping['sek'] == 'st'


# ============================================================
# mapping dict
# ============================================================

class TestMappingDict:
    def test_us_exchanges(self):
        assert m.mapping['nasdaq'] == 'USA'
        assert m.mapping['nyse'] == 'USA'

    def test_european_exchanges(self):
        assert m.mapping['stockholm'] == 'Szwecja'
        assert m.mapping['copenhagen'] == 'Dania'
        assert m.mapping['frankfurt'] == 'Niemcy'
        assert m.mapping['london'] == 'Wielka Brytania'
        assert m.mapping['paris'] == 'Francja'
        assert m.mapping['zurich'] == 'Szwajcaria'
        assert m.mapping['oslo'] == 'Norwegia'
        assert m.mapping['helsinki'] == 'Finlandia'
        assert m.mapping['borsaitaliana'] == 'Włochy'
        assert m.mapping['bolsademadrid'] == 'Hiszpania'

    def test_country_name_mappings(self):
        assert m.mapping['United States'] == 'USA'
        assert m.mapping['France'] == 'Francja'
        assert m.mapping['Germany'] == 'Niemcy'
