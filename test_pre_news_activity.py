import copy
from datetime import date, datetime, timedelta
import json
from unittest.mock import Mock, patch
import unittest

import backtest_engine as bt
from pre_news_activity_engine import analyze_pre_news_activity, fetch_daily_activity, get_pre_news_activity


CUTOFF = '2026-09-02T08:00:00+09:00'
AS_OF = '2026-10-13T19:00:00+09:00'


def bars():
    days = []
    day = date(2026, 9, 1)
    while len(days) < 25:
        if day.weekday() < 5:
            days.append(day)
        day -= timedelta(days=1)
    days.reverse()
    return [{'localDate': day.strftime('%Y%m%d'), 'closePrice': 100,
             'accumulatedTradingVolume': 100 if i < 20 else 200}
            for i, day in enumerate(days)]


def connection(stamp=CUTOFF, source='fixture'):
    return {'pass': True, 'evidence': [{'published_at': stamp, 'source': source,
                                       'link': 'https://example.test/news', 'role': 'EVENT_ACTOR'}]}


class PreNewsActivityTests(unittest.TestCase):
    def analyze(self, rows, **kwargs):
        return analyze_pre_news_activity(rows, CUTOFF, AS_OF, **kwargs)

    def test_recent_and_baseline_windows_do_not_overlap(self):
        result = self.analyze(bars())
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['volume_ratio'], 2)
        self.assertEqual(result['estimated_value_ratio'], 2)
        self.assertEqual(len(result['baseline_dates']), 20)
        self.assertEqual(len(result['recent_dates']), 5)
        self.assertFalse(set(result['baseline_dates']) & set(result['recent_dates']))
        self.assertEqual(result['last_session_date'], '2026-09-01')
        self.assertEqual(result['score_effect'], 0)

    def test_news_day_and_future_spikes_cannot_change_result(self):
        data = bars()
        before = self.analyze(data)
        for day in ['20260902', '20260903', '20261013', '20261014']:
            data.append({'localDate': day, 'closePrice': 10000, 'accumulatedTradingVolume': 10**12})
        self.assertEqual(self.analyze(data), before)

    def test_even_after_close_news_day_is_excluded(self):
        result = analyze_pre_news_activity(bars() + [{'localDate': '20260902', 'closePrice': 100, 'accumulatedTradingVolume': 100000}],
                                           '2026-09-02T22:00:00+09:00', AS_OF)
        self.assertEqual(result['last_session_date'], '2026-09-01')

    def test_utc_news_timestamp_is_converted_before_date_cutoff(self):
        result = analyze_pre_news_activity(bars(), '2026-09-01T23:00:00Z', AS_OF)
        self.assertEqual(result['reference_at'], CUTOFF)
        self.assertEqual(result['last_session_date'], '2026-09-01')

    def test_order_and_identical_duplicates_do_not_change_metrics(self):
        data = bars()
        self.assertEqual(self.analyze(list(reversed(data)) + [dict(data[-1])]), self.analyze(data))

    def test_conflicting_daily_records_are_unavailable(self):
        data = bars(); extra = dict(data[-1]); extra['closePrice'] = 500; data.append(extra)
        self.assertEqual(self.analyze(data)['status'], 'conflicting_history')

    def test_missing_window_row_is_not_dropped_and_replaced_by_older_day(self):
        data = bars()
        data[-3]['accumulatedTradingVolume'] = None
        data.insert(0, {'localDate': '20260701', 'closePrice': 100, 'accumulatedTradingVolume': 100})
        self.assertEqual(self.analyze(data)['status'], 'invalid_window_data')

    def test_zero_volume_is_kept_and_zero_baseline_is_not_infinite(self):
        data = bars(); data[-1]['accumulatedTradingVolume'] = 0
        self.assertEqual(self.analyze(data)['volume_ratio'], 1.6)
        for row in data[:20]: row['accumulatedTradingVolume'] = 0
        self.assertEqual(self.analyze(data)['status'], 'zero_baseline')
        self.assertIsNone(self.analyze(data)['volume_ratio'])

    def test_close_price_change_affects_estimated_value_not_volume(self):
        data = bars()
        for row in data[-5:]: row['closePrice'] = 200
        result = self.analyze(data)
        self.assertEqual(result['volume_ratio'], 2)
        self.assertEqual(result['estimated_value_ratio'], 4)
        self.assertEqual(result['value_method'], 'close_x_volume_estimate')

    def test_invalid_numbers_do_not_become_signals(self):
        for value in [None, -1, float('nan'), float('inf'), True, 1.5]:
            with self.subTest(value=value):
                data = bars(); data[-1]['accumulatedTradingVolume'] = value
                self.assertEqual(self.analyze(data)['status'], 'invalid_window_data')

    def test_insufficient_history_and_malformed_dates_remain_unavailable(self):
        self.assertEqual(self.analyze(bars()[:24])['status'], 'insufficient_history')
        data = bars(); data[-1]['localDate'] = ''
        self.assertEqual(self.analyze(data)['status'], 'invalid_history_date')

    def test_naive_or_date_only_manual_cutoff_is_not_guessed(self):
        for cutoff in ['2026-09-02', '2026-09-02T08:00:00', 'bad']:
            with self.subTest(cutoff=cutoff):
                self.assertEqual(analyze_pre_news_activity(bars(), cutoff, AS_OF)['status'], 'invalid_timestamp')

    def test_future_reference_is_not_known_at_assessment(self):
        self.assertEqual(analyze_pre_news_activity(bars(), CUTOFF, '2026-09-01T08:00:00+09:00')['status'], 'reference_not_yet_available')

    def test_invalid_window_configuration_does_not_fetch(self):
        for size in [0, -1, True, 2.5]:
            self.assertEqual(self.analyze(bars(), baseline_sessions=size)['status'], 'invalid_window')

    def test_earliest_linked_article_is_used(self):
        conn = connection('2026-09-03T08:00:00+09:00')
        conn['evidence'].extend(connection()['evidence'])
        with patch('pre_news_activity_engine.fetch_daily_activity', return_value=(bars(), None)):
            result = get_pre_news_activity({'code': '032940'}, conn, AS_OF)
        self.assertEqual(result['reference_at'], CUTOFF)
        self.assertEqual(result['reference_scope'], 'earliest_available_linked_article')

    def test_unknown_news_timestamp_is_not_skipped(self):
        conn = connection(); conn['evidence'].append({'published_at': '', 'source': 'fixture'})
        with patch('pre_news_activity_engine.requests.get') as get:
            result = get_pre_news_activity({'code': '032940'}, conn, AS_OF)
        get.assert_not_called()
        self.assertEqual(result['status'], 'missing_news_timestamp')

    def test_known_domestic_naive_timestamp_is_explicit_assumption(self):
        with patch('pre_news_activity_engine.fetch_daily_activity', return_value=(bars(), None)):
            result = get_pre_news_activity({'code': '032940'}, connection('2026-09-02T08:00:00', '매일경제_기업'), AS_OF)
        self.assertTrue(result['news_timezone_assumed_kst'])
        self.assertEqual(result['reference_at'], CUTOFF)
        self.assertEqual(get_pre_news_activity({'code': '032940'}, connection('2026-09-02T08:00:00', 'unknown'), AS_OF)['status'], 'missing_news_timestamp')

    def test_request_ends_before_news_day_and_is_cached(self):
        response = Mock(); response.json.return_value = bars()
        cutoff = datetime.fromisoformat(CUTOFF); cache = {}
        with patch('pre_news_activity_engine.requests.get', return_value=response) as get:
            fetch_daily_activity('032940', cutoff, cache)
            fetch_daily_activity('032940', cutoff, cache)
        get.assert_called_once()
        self.assertEqual(get.call_args.kwargs['params']['endDateTime'], '20260901')

    def test_bad_code_and_request_failure_are_reported(self):
        import requests
        with patch('pre_news_activity_engine.requests.get', side_effect=requests.ReadTimeout()):
            result = get_pre_news_activity({'code': '032940'}, connection(), AS_OF)
        self.assertEqual(result['status'], 'history_unavailable')
        with patch('pre_news_activity_engine.requests.get') as get:
            self.assertEqual(get_pre_news_activity({'code': '000000'}, connection(), AS_OF)['status'], 'invalid_code')
        get.assert_not_called()

    def test_new_observation_survives_save_reload_without_rewriting_old_records(self):
        record = self.analyze(bars())
        old = {'date': '2026-09-02', 'name': '원익', 'code': '032940', 'grade': 'S+', 'rank': 1,
               'start_price': 7220, 'result_1d': 18.84}
        original = copy.deepcopy(old)
        blocks = [{'theme': {'name': '반도체'}, 'ranked': [{'name': '원익', 'code': '032940', 'price': 100,
                                                        'pre_news_activity': record}]}]
        with patch.object(bt, 'load_backtest', return_value=[old]), patch.object(bt, 'save_backtest') as save:
            bt.save_recommendations(blocks)
        data = json.loads(json.dumps(save.call_args.args[0], allow_nan=False))
        self.assertEqual(data[0], original)
        self.assertEqual(data[1]['pre_news_activity'], record)
        record['volume_ratio'] = 99
        self.assertEqual(save.call_args.args[0][1]['pre_news_activity']['volume_ratio'], 2)
        self.assertEqual(data[1]['pre_news_activity']['volume_ratio'], 2)


if __name__ == '__main__':
    unittest.main()
