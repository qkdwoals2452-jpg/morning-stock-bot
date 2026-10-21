import copy
from datetime import date, datetime, timedelta
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

import backtest_engine as bt
import chart_engine as chart
import market_engine as market
from test_chart_history import response, row


SOURCE = 'YAHOO_REGULAR_CLOSE'
NOW = datetime(2026, 10, 22, 8, tzinfo=ZoneInfo('Asia/Seoul'))


class RegularMarketTests(unittest.TestCase):
    def item(self):
        return {'code': '022100', 'name': '포스코DX', 'date': '2026-10-12',
                'grade': 'S+', 'rank': 1, 'score': 309, 'start_price': 20100,
                'current_price': 20100, 'current_return': 0,
                'last_updated': '2026-10-22', 'highest_price': 20550,
                'lowest_price': 19080, 'result_1d': -0.95,
                'price_history': [{'date': '2026-10-20', 'price': 20550, 'return': 2.24},
                                  {'date': '2026-10-21', 'price': 20050, 'return': -0.25},
                                  {'date': '2026-10-22', 'price': 20100, 'return': 0}]}

    def quote(self, price=20050, day='2026-10-21'):
        return {'price': price, 'date': day, 'source': SOURCE}

    def test_chart_market_and_backtest_share_one_regular_session_snapshot(self):
        end = date(2026, 10, 21)
        records = [row((end - timedelta(days=i)).isoformat(), 1000000) for i in range(120)]
        records[0] = row('2026-10-21', 1168000, accumulatedTradingVolume=573152)
        records[1] = row('2026-10-20', 1155000, accumulatedTradingVolume=680200)
        records.append(row('2026-10-22', 9999999))
        cache = {}
        with patch.object(chart.requests, 'get', return_value=response(records)) as get, patch.object(
            chart, 'datetime', wraps=datetime
        ) as clock:
            clock.now.return_value = NOW
            stock = {'code': '009150', 'name': '삼성전기'}
            m = market.get_market_score(stock, price_cache=cache)
            c = chart.get_chart_score(stock, price_cache=cache)
            q = bt.get_current_quote('009150', price_cache=cache)
        get.assert_called_once()
        self.assertEqual(m['change_rate'], 1.13)
        self.assertEqual(m['score'], 30)
        self.assertEqual(m['volume'], 573152)
        self.assertEqual(m['trading_value'], 1168000 * 573152)
        self.assertTrue(m['trading_value_is_estimate'])
        self.assertEqual(m['close_price'], c['details']['current'])
        self.assertEqual(q, self.quote(1168000))
        self.assertEqual(m['price_date'], c['details']['price_date'])

    def test_market_missing_volume_does_not_invent_trading_value(self):
        with patch.object(market, 'get_price_history', return_value=[
            {'date': '2026-10-21', 'close': 100, 'volume': None, 'source': SOURCE}]):
            result = market.get_market_score({'code': '009150'})
        self.assertIsNone(result['change_rate'])
        self.assertIsNone(result['trading_value'])

    def test_legacy_morning_observation_is_backed_up_and_actual_date_restored(self):
        item = self.item()
        original = copy.deepcopy(item)
        with patch.object(bt, 'datetime', wraps=datetime) as clock:
            clock.now.return_value = NOW
            self.assertTrue(bt.apply_regular_quote(item, self.quote()))
        archive = item['legacy_price_snapshot']
        self.assertEqual(archive['price_history'], original['price_history'])
        self.assertEqual(archive['current_price'], 20100)
        self.assertEqual(archive['last_updated'], '2026-10-22')
        self.assertEqual(item['last_updated'], '2026-10-21')
        self.assertEqual(item['current_price'], 20050)
        self.assertEqual(item['price_history'][-1]['price'], 20050)
        self.assertEqual(item['price_history'][-1]['date'], '2026-10-21')
        self.assertEqual(item['price_history'][0], original['price_history'][0])
        for field in ('date', 'name', 'grade', 'rank', 'score', 'start_price', 'result_1d'):
            self.assertEqual(item[field], original[field])

    def test_verified_earlier_quote_is_rejected_without_any_mutation(self):
        item = self.item()
        item['current_price_source'] = SOURCE
        original = copy.deepcopy(item)
        self.assertFalse(bt.apply_regular_quote(item, self.quote()))
        self.assertEqual(item, original)

    def test_stale_quote_cannot_move_older_unverified_dates_out_of_history(self):
        item = self.item()
        original = copy.deepcopy(item)
        with patch.object(bt, 'datetime', wraps=datetime) as clock:
            clock.now.return_value = NOW
            self.assertFalse(bt.apply_regular_quote(item, self.quote(day='2026-10-20')))
        self.assertEqual(item, original)

    def test_repeat_quote_is_idempotent_and_archive_is_not_overwritten(self):
        item = self.item()
        with patch.object(bt, 'datetime', wraps=datetime) as clock:
            clock.now.return_value = NOW
            bt.apply_regular_quote(item, self.quote())
            original = copy.deepcopy(item)
            clock.now.return_value = NOW + timedelta(minutes=3)
            self.assertTrue(bt.apply_regular_quote(item, self.quote()))
        self.assertEqual(item, original)

    def test_new_trading_day_appends_one_row_and_keeps_verified_previous_day(self):
        item = self.item()
        item['price_history'] = item['price_history'][:-1]
        item['last_updated'] = '2026-10-21'
        item['current_price_source'] = SOURCE
        old = copy.deepcopy(item['price_history'])
        with patch.object(bt, 'datetime', wraps=datetime) as clock:
            clock.now.return_value = NOW.replace(hour=16)
            self.assertTrue(bt.apply_regular_quote(item, self.quote(20200, '2026-10-22')))
        self.assertEqual(item['price_history'][:-1], old)
        self.assertEqual(item['current_price'], item['price_history'][-1]['price'])

    def test_invalid_source_or_unfinished_date_is_not_saved(self):
        for quote in (dict(self.quote(), source='NAVER'), self.quote(day='2026-10-22'),
                      self.quote(price=0), self.quote(price=True)):
            item = self.item()
            original = copy.deepcopy(item)
            with patch.object(bt, 'datetime', wraps=datetime) as clock:
                clock.now.return_value = NOW
                self.assertFalse(bt.apply_regular_quote(item, quote))
            self.assertEqual(item, original)

    def test_update_ignores_undated_krx_price_and_uses_quote_date(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
            bt, 'BACKTEST_FILE', str(Path(directory) / 'history.json')
        ), patch.object(bt, 'get_current_quote', return_value=self.quote()) as get, patch.object(
            bt, 'fetch_daily_closes', return_value=[]
        ), patch.object(bt, 'datetime', wraps=datetime) as clock:
            clock.now.return_value = NOW
            bt.save_backtest([self.item()])
            bt.update_backtest_prices([{'code': '022100', 'price': 999999}])
            saved = bt.load_backtest()[0]
        get.assert_called_once_with('022100', price_cache=None)
        self.assertEqual(saved['current_price'], 20050)
        self.assertEqual(saved['last_updated'], '2026-10-21')

    def test_recommendation_reference_uses_verified_market_price_and_date(self):
        stock = {'code': '009150', 'name': '삼성전기', 'price': 1184000,
                 'market': {'close_price': 1168000, 'price_date': '2026-10-21',
                            'price_source': SOURCE}}
        with tempfile.TemporaryDirectory() as directory, patch.object(
            bt, 'BACKTEST_FILE', str(Path(directory) / 'history.json')
        ), patch.object(bt, 'get_current_quote') as get:
            bt.save_recommendations([{'theme': {'name': 'AI'}, 'ranked': [stock]}])
            item = bt.load_backtest()[0]
        get.assert_not_called()
        self.assertEqual(item['start_price'], 1168000)
        self.assertEqual(item['start_price_date'], '2026-10-21')
        self.assertEqual(item['start_price_source'], SOURCE)

    def test_missing_historical_close_keeps_session_position(self):
        records = [row('2026-10-12', 100), row('2026-10-13', 110),
                   row('2026-10-14', 100, closePrice=None), row('2026-10-15', 130)]
        with patch.object(chart.requests, 'get', return_value=response(records, symbol='022100.KS')):
            prices = bt.fetch_daily_closes('022100', '2026-10-12', '2026-10-21')
        self.assertEqual(prices[2], ('2026-10-14', None))
        item = {'date': '2026-10-12', 'start_price': 100}
        bt.fill_trading_checkpoints(item, prices, '2026-10-21')
        self.assertEqual(item['result_3d'], 30)
        self.assertEqual(item['checkpoint_dates']['result_3d'], '2026-10-15')


if __name__ == '__main__':
    unittest.main()
