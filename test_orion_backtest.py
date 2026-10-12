import copy
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import backtest_engine as bt


class TradingCheckpointTests(unittest.TestCase):
    def item(self, **extra):
        item = {'date': '2026-10-02', 'start_price': 100, 'name': '검증 종목', 'code': '005930'}
        item.update({f'result_{n}d': None for n in (1, 3, 5, 10, 20)})
        item.update(extra)
        return item

    def test_skips_weekends_and_holidays_using_observed_sessions(self):
        item = self.item()
        rows = [('2026-10-02', 100), ('2026-10-05', 110), ('2026-10-06', 120),
                ('2026-10-07', 130), ('2026-10-08', 140), ('2026-10-12', 150)]
        self.assertEqual(bt.fill_trading_checkpoints(item, rows, '2026-10-13'), 3)
        self.assertEqual(item['result_1d'], 10)
        self.assertEqual(item['result_3d'], 30)
        self.assertEqual(item['result_5d'], 50)
        self.assertEqual(item['checkpoint_dates']['result_5d'], '2026-10-12')
        self.assertIsNone(item['result_10d'])

    def test_no_future_session_does_not_fill(self):
        item = self.item(date='2026-10-10')
        self.assertEqual(bt.fill_trading_checkpoints(item, [('2026-10-08', 150)], '2026-10-11'), 0)
        self.assertIsNone(item['result_1d'])

    def test_historical_yahoo_response_is_parsed_as_fallback(self):
        sample = {'chart': {'result': [{'timestamp': [1791244800],
                  'indicators': {'quote': [{'close': [123.0]}]}}]}}
        response = Mock(json=lambda: sample)
        with patch.object(bt.requests, 'get', return_value=response):
            result = bt.fetch_daily_closes('005930', as_of='2026-10-11')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][1], 123.0)

    def test_current_quote_cannot_fill_past_checkpoints(self):
        item = self.item()
        self.assertTrue(bt.update_single_item(item, 180, '2026-10-12'))
        self.assertEqual(item['current_return'], 80)
        self.assertTrue(all(item[f'result_{n}d'] is None for n in (1, 3, 5, 10, 20)))

    def test_intraday_and_future_rows_are_not_counted(self):
        item = self.item()
        rows = [('2026-10-02', 100), ('2026-10-12', 150), ('2026-10-13', 200)]
        self.assertEqual(bt.fill_trading_checkpoints(item, rows, '2026-10-11'), 0)

    def test_duplicates_do_not_create_extra_sessions(self):
        item = self.item()
        rows = [('2026-10-02', 100), ('2026-10-05', 110), ('2026-10-05', 110)]
        self.assertEqual(bt.fill_trading_checkpoints(item, rows, '2026-10-11'), 1)
        self.assertIsNone(item['result_3d'])

    def test_missing_price_is_not_skipped_and_renumbered(self):
        item = self.item()
        rows = [('2026-10-02', 100), ('2026-10-05', 110), ('2026-10-06', None),
                ('2026-10-07', 130), ('2026-10-08', 140)]
        bt.fill_trading_checkpoints(item, rows, '2026-10-11')
        self.assertEqual(item['result_3d'], 30)
        self.assertEqual(item['checkpoint_dates']['result_3d'], '2026-10-07')

    def test_conflicting_same_date_prices_remain_unverified(self):
        item = self.item()
        bt.fill_trading_checkpoints(item, [('2026-10-02', 100),
            ('2026-10-05', 110), ('2026-10-05', 120)], '2026-10-11')
        self.assertIsNone(item['result_1d'])

    def test_truncated_history_does_not_guess_first_session(self):
        item = self.item(date='2026-09-02')
        bt.fill_trading_checkpoints(item, [('2026-10-05', 110)], '2026-10-11')
        self.assertIsNone(item['result_1d'])
        self.assertEqual(item['checkpoint_status'], 'history_unavailable')

    def test_legacy_calendar_values_are_backed_up_and_recomputed(self):
        item = self.item(date='2026-09-02', code='032940', name='원익', grade='S+', rank=1,
                         result_1d=99, result_3d=99)
        original = copy.deepcopy(item)
        bt.fill_trading_checkpoints(item, [('2026-09-02', 100), ('2026-09-03', 110)], '2026-10-11')
        self.assertEqual(item['legacy_calendar_checkpoints'], {'result_1d': 99, 'result_3d': 99})
        self.assertEqual(item['result_1d'], 10)
        self.assertIsNone(item['result_3d'])
        for field in ['date', 'code', 'name', 'grade', 'rank', 'start_price']:
            self.assertEqual(item[field], original[field])

    def test_lookup_failure_keeps_legacy_backup_without_fake_returns(self):
        item = self.item(result_1d=99)
        bt.fill_trading_checkpoints(item, [], '2026-10-11')
        self.assertEqual(item['legacy_calendar_checkpoints']['result_1d'], 99)
        self.assertIsNone(item['result_1d'])

    def test_completed_verified_results_are_idempotent(self):
        item = self.item()
        rows = [('2026-10-02', 100), ('2026-10-05', 110)]
        bt.fill_trading_checkpoints(item, rows, '2026-10-11')
        original = copy.deepcopy(item)
        self.assertEqual(bt.fill_trading_checkpoints(item, rows, '2026-10-11'), 0)
        self.assertEqual(item, original)

    def test_nonfinite_and_nonpositive_prices_cannot_be_used(self):
        for value in ['NaN', 'inf', '-inf', 0, -1]:
            with self.subTest(value=value):
                item = self.item(start_price=value)
                self.assertEqual(bt.fill_trading_checkpoints(item, [('2026-10-02', 100),
                    ('2026-10-05', 110)], '2026-10-11'), 0)

    def test_completed_date_uses_seoul_time(self):
        self.assertEqual(bt.last_completed_date(datetime(2026, 10, 12, 9, tzinfo=ZoneInfo('Asia/Seoul'))).isoformat(), '2026-10-11')
        self.assertEqual(bt.last_completed_date(datetime(2026, 10, 12, 16, tzinfo=ZoneInfo('Asia/Seoul'))).isoformat(), '2026-10-12')

    def test_naver_response_sorts_and_excludes_unfinished_date(self):
        response = Mock(json=lambda: [
            {'localDate': '20261012', 'closePrice': 150},
            {'localDate': '20261002', 'closePrice': 100},
            {'localDate': '20261005', 'closePrice': 110},
        ])
        with patch.object(bt.requests, 'get', return_value=response):
            result = bt.fetch_daily_closes('005930', '2026-10-02', '2026-10-11')
        self.assertEqual(result, [('2026-10-02', 100), ('2026-10-05', 110)])

    def test_start_date_controls_request_for_old_recommendations(self):
        response = Mock(json=lambda: [{'localDate': '20200101', 'closePrice': 100}])
        with patch.object(bt.requests, 'get', return_value=response) as get:
            bt.fetch_daily_closes('005930', '2020-01-01', '2026-10-11')
        self.assertEqual(get.call_args.kwargs['params']['startDateTime'], '20191218')

    def test_update_persists_checkpoints_even_if_current_quote_fails(self):
        item = self.item()
        with tempfile.TemporaryDirectory() as directory, patch.object(bt, 'BACKTEST_FILE', str(Path(directory) / 'test.json')):
            bt.save_backtest([item])
            with patch.object(bt, 'get_current_price', return_value=None), patch.object(bt, 'fetch_daily_closes',
                return_value=[('2026-10-02', 100), ('2026-10-05', 110)]) as history:
                bt.update_backtest_prices()
            saved = bt.load_backtest()
            self.assertEqual(saved[0]['result_1d'], 10)
            self.assertEqual(history.call_args.args, ('005930', '2026-10-02'))

    def test_same_stock_reuses_quote_and_earliest_history(self):
        items = [self.item(date='2026-10-01'), self.item(date='2026-10-02')]
        rows = [('2026-10-01', 100), ('2026-10-02', 105), ('2026-10-05', 110)]
        with tempfile.TemporaryDirectory() as directory, patch.object(bt, 'BACKTEST_FILE', str(Path(directory) / 'test.json')):
            bt.save_backtest(items)
            with patch.object(bt, 'get_current_price', return_value=110) as quote, patch.object(
                bt, 'fetch_daily_closes', return_value=rows
            ) as history:
                bt.update_backtest_prices()
            quote.assert_called_once_with('005930')
            history.assert_called_once_with('005930', '2026-10-01')

    def test_recommendation_dates_use_seoul_and_preserve_event_metadata(self):
        block = {'theme': {'name': 'AI', 'score': 80, 'frequency_score': 6},
                 'ranked': [{'name': '검증 종목', 'code': '005930', 'price': 100,
                             'event_score': 80, 'reason': '사건 신호 80점'}]}
        from datetime import timezone
        utc = datetime(2026, 10, 11, 23, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as directory, patch.object(bt, 'BACKTEST_FILE', str(Path(directory) / 'test.json')), patch.object(bt, 'datetime', wraps=datetime) as clock:
            clock.now.side_effect = lambda zone: utc.astimezone(zone)
            bt.save_recommendations([block])
            saved = bt.load_backtest()[0]
        self.assertEqual(saved['date'], '2026-10-12')
        self.assertEqual(saved['recommended_at'], '2026-10-12 08:00:00')
        self.assertEqual(saved['date_timezone'], 'Asia/Seoul')
        self.assertEqual(saved['event_score'], 80)
        self.assertEqual(saved['frequency_score'], 6)
        self.assertEqual(saved['reasons'], '사건 신호 80점')

    def test_invalid_stock_codes_are_not_saved(self):
        block = {'theme': {'name': 'AI'}, 'ranked': [
            {'name': '검증 종목', 'code': code, 'price': 100}
            for code in ['', None, '000000', 'ABC', '005930.KS']]}
        with tempfile.TemporaryDirectory() as directory, patch.object(bt, 'BACKTEST_FILE', str(Path(directory) / 'test.json')), patch.object(bt, 'get_current_price') as quote:
            bt.save_recommendations([block])
            self.assertEqual(bt.load_backtest(), [])
            quote.assert_not_called()


if __name__ == '__main__':
    unittest.main()
