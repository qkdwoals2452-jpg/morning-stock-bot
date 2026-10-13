import contextlib
import copy
from datetime import date, timedelta
import io
import unittest
from unittest.mock import patch

import backtest_engine as bt
import memory_learning_engine as learning
from performance_validation_engine import completed_performance

AS_OF = '2026-10-13T08:00:00+09:00'


def record(value=10, day='2026-09-02', code='032940', **fields):
    row = {'date': day, 'name': '원익', 'code': code, 'start_price': 100,
           'checkpoint_method': 'trading_sessions_v1', 'result_5d': value,
           'checkpoint_dates': {'result_5d': '2026-09-09'},
           'checkpoint_observed_at': {'result_5d': '2026-09-10T08:00:00+09:00'}}
    row.update(fields)
    return row


class PerformanceValidationTests(unittest.TestCase):
    def report(self, rows):
        return completed_performance(rows, AS_OF)

    def score(self, rows, stock=None, **kwargs):
        with patch.object(bt, 'load_backtest', return_value=rows):
            return learning.get_learning_score(stock or {'name': '원익', 'code': '032940'}, AS_OF, **kwargs)

    def test_completed_fixed_horizon_is_the_only_outcome(self):
        rows = [record(10, current_return=99), record(-5, day='2026-09-01', current_return=80)]
        result = self.report(rows)
        self.assertEqual(result['count'], 2)
        self.assertEqual(result['accuracy'], 50)
        self.assertEqual(result['average'], 2.5)
        self.assertEqual(result['horizon'], 5)

    def test_pending_and_undated_manual_results_do_not_count(self):
        rows = [record(None), {'stock': '원익', 'result': 99}, record(50, checkpoint_dates={})]
        self.assertEqual(self.report(rows)['count'], 0)
        self.assertIsNone(self.report(rows)['accuracy'])

    def test_legacy_calendar_results_and_missing_observation_times_are_excluded(self):
        rows = [record(checkpoint_method='calendar_days'), record(checkpoint_observed_at={})]
        self.assertEqual(self.report(rows)['count'], 0)

    def test_future_outcome_and_same_day_close_do_not_count(self):
        rows = [record(checkpoint_dates={'result_5d': '2026-10-13'},
                       checkpoint_observed_at={'result_5d': '2026-10-13T18:00:00+09:00'}),
                record(checkpoint_dates={'result_5d': '2026-10-14'},
                       checkpoint_observed_at={'result_5d': '2026-10-15T08:00:00+09:00'})]
        self.assertEqual(self.report(rows)['count'], 0)

    def test_future_observation_cannot_be_used_even_with_old_checkpoint_date(self):
        self.assertEqual(self.report([record(checkpoint_observed_at={'result_5d': '2026-10-13T09:00:00+09:00'})])['count'], 0)

    def test_naive_observation_time_is_not_guessed(self):
        self.assertEqual(self.report([record(checkpoint_observed_at={'result_5d': '2026-09-10T08:00:00'})])['count'], 0)

    def test_same_stock_recommended_in_multiple_themes_counts_once(self):
        a, b = record(), record(theme='AI')
        result = self.report([a, b, copy.deepcopy(a)])
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['excluded']['duplicate_rows'], 2)
        self.assertEqual(self.score([a, b] * 5)['score'], 0)

    def test_conflicting_duplicate_results_are_not_averaged(self):
        result = self.report([record(10), record(20)])
        self.assertEqual(result['count'], 0)
        self.assertEqual(result['excluded']['conflicting_duplicate_group'], 2)

    def test_different_completion_dates_conflict(self):
        self.assertEqual(self.report([record(), record(checkpoint_dates={'result_5d': '2026-09-10'})])['count'], 0)

    def test_invalid_return_and_start_price_are_excluded(self):
        for value in [True, float('nan'), float('inf'), '10', -101]:
            with self.subTest(value=value):
                self.assertEqual(self.report([record(value)])['count'], 0)
        self.assertEqual(self.report([record(start_price=None)])['count'], 0)

    def test_impossible_checkpoint_order_is_excluded(self):
        self.assertEqual(self.report([record(day='2026-09-08')])['count'], 0)
        self.assertEqual(self.report([record(checkpoint_observed_at={'result_5d': '2026-09-08T08:00:00+09:00'})])['count'], 0)

    def test_flat_returns_are_not_positive_wins(self):
        result = self.report([record(0)])
        self.assertEqual(result['flat'], 1)
        self.assertEqual(result['accuracy'], 0)

    def test_single_success_does_not_award_twenty_points(self):
        result = self.score([record(40)])
        self.assertEqual(result['score'], 0)
        self.assertEqual(result['sample_count'], 1)

    def test_existing_point_ladder_requires_five_unique_completed_predictions(self):
        for value, expected in [(12, 20), (7, 10), (0, 3), (-3, -10)]:
            rows = [record(value, (date(2026, 9, 1) - timedelta(days=i)).isoformat()) for i in range(5)]
            with self.subTest(value=value):
                self.assertEqual(self.score(rows)['score'], expected)
        self.assertEqual(self.score([record(99)], minimum_samples=1)['score'], 0)

    def test_stock_code_survives_name_change_without_mixing_other_company(self):
        rows = [record(day=(date(2026, 9, 1) - timedelta(days=i)).isoformat(), name='이전 이름') for i in range(5)]
        rows.append(record(99, code='005930'))
        result = self.score(rows)
        self.assertEqual(result['sample_count'], 5)
        self.assertEqual(result['average_return'], 10)

    def test_display_rounding_cannot_push_average_over_score_threshold(self):
        rows = [record(value, (date(2026, 9, 1) - timedelta(days=i)).isoformat())
                for i, value in enumerate([4.99, 4.99, 5, 5, 5])]
        result = self.score(rows)
        self.assertEqual(result['score'], 3)
        self.assertLess(result['average_return'], 5)

    def test_legacy_name_call_refuses_two_different_codes(self):
        self.assertEqual(self.score([record(), record(code='005930')], stock='원익')['score'], 0)

    def test_future_spike_does_not_change_historical_score(self):
        rows = [record(day=(date(2026, 9, 1) - timedelta(days=i)).isoformat()) for i in range(5)]
        before = self.score(rows)
        rows.append(record(1000, day='2026-10-14', checkpoint_dates={'result_5d': '2026-10-21'},
                           checkpoint_observed_at={'result_5d': '2026-10-22T08:00:00+09:00'}))
        after = self.score(rows)
        self.assertEqual(after['score'], before['score'])
        self.assertEqual(after['sample_count'], before['sample_count'])

    def test_completed_summary_and_learning_report_share_same_population(self):
        rows = [record(10), record(99)]
        with patch.object(bt, 'load_backtest', return_value=rows):
            self.assertEqual(learning.get_project_report(AS_OF)['count'], self.report(rows)['count'])

    def test_prediction_save_is_dated_idempotent_and_preserves_legacy_entry(self):
        legacy = {'stock': '원익', 'theme': '반도체', 'result': 40}
        data = [copy.deepcopy(legacy)]
        with patch.object(learning, 'load_result', side_effect=lambda: copy.deepcopy(data)), \
                patch.object(learning, 'save_result', side_effect=lambda rows: data.__setitem__(slice(None), copy.deepcopy(rows))):
            learning.save_prediction('반도체', {'name': '원익', 'code': '032940'}, 90)
            learning.save_prediction('반도체', {'name': '원익', 'code': '032940'}, 90)
        self.assertEqual(data[0], legacy)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[1]['code'], '032940')
        self.assertIn('date', data[1])

    def test_checkpoint_observation_time_is_recorded_only_when_value_is_first_filled(self):
        item = {'date': '2026-09-02', 'start_price': 100}
        days = ['2026-09-02', '2026-09-03', '2026-09-04', '2026-09-07', '2026-09-08', '2026-09-09']
        bt.fill_trading_checkpoints(item, [(day, 110) for day in days], '2026-09-10')
        self.assertIn('result_5d', item['checkpoint_observed_at'])
        original = copy.deepcopy(item['checkpoint_observed_at'])
        bt.fill_trading_checkpoints(item, [(day, 110) for day in days], '2026-09-10')
        self.assertEqual(item['checkpoint_observed_at'], original)

    def test_old_completed_value_is_not_given_a_fabricated_observation_timestamp(self):
        item = record(checkpoint_observed_at={})
        bt.fill_trading_checkpoints(item, [('2026-09-02', 100), ('2026-09-09', 110)], '2026-09-10')
        self.assertNotIn('result_5d', item.get('checkpoint_observed_at', {}))

    def test_statistics_are_read_only_and_preserve_wonik_reference_metadata(self):
        item = record(41.27, grade='S+', rank=1, result_1d=18.84)
        original = copy.deepcopy(item)
        self.report([item])
        self.assertEqual(item, original)

    def test_print_summary_does_not_use_unfinished_current_return(self):
        stream = io.StringIO()
        with patch.object(bt, 'load_backtest', return_value=[{'current_return': 99}]), contextlib.redirect_stdout(stream):
            bt.print_backtest_summary()
        self.assertIn('검증 표본: 0', stream.getvalue())
        self.assertIn('미확인', stream.getvalue())
        self.assertNotIn('99.0%', stream.getvalue())

    def test_invalid_source_or_horizon_is_unavailable(self):
        self.assertEqual(completed_performance({}, AS_OF)['status'], 'invalid_input')
        self.assertEqual(completed_performance([], AS_OF, horizon=5.0)['status'], 'invalid_input')


if __name__ == '__main__':
    unittest.main()
