import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo
import dart_statement_reader as reader
import rejected_candidate_engine as review


class StatementFallbackTests(unittest.TestCase):
    def response(self, status, rows=None):
        return Mock(json=lambda: {'status': status, 'list': rows or []})

    def test_same_period_separate_before_older_period(self):
        rows = [{'rcept_no': '20260814000123'}]
        with patch.object(reader.requests, 'get', side_effect=[self.response('013'), self.response('000', rows)]) as get:
            data, report = reader.read_statement('00651901', [(2026, '11012'), (2025, '11011')], date(2026, 11, 5))
        self.assertEqual(data, rows)
        self.assertEqual(report['fs_div'], 'OFS')
        self.assertEqual([(c.kwargs['params']['bsns_year'], c.kwargs['params']['fs_div']) for c in get.call_args_list], [('2026', 'CFS'), ('2026', 'OFS')])

    def test_consolidated_success_does_not_mix_separate(self):
        with patch.object(reader.requests, 'get', return_value=self.response('000', [{'rcept_no': '20260814000123'}])) as get:
            _, report = reader.read_statement('x', [(2026, '11012')], date(2026, 11, 5))
        self.assertEqual(report['fs_div'], 'CFS')
        self.assertEqual(get.call_count, 1)

    def test_errors_do_not_turn_into_older_or_separate_success(self):
        for status in ('010', '020', '100', '000'):
            with self.subTest(status=status), patch.object(reader.requests, 'get', return_value=self.response(status)) as get:
                data, report = reader.read_statement('x', [(2026, '11012'), (2025, '11011')])
                self.assertIsNone(data)
                self.assertEqual(get.call_count, 1)
                self.assertNotEqual(report['status'], 'ok')

    def test_future_receipt_and_transport_error_are_explicit(self):
        with patch.object(reader.requests, 'get', return_value=self.response('000', [{'rcept_no': '20261114000123'}])):
            data, report = reader.read_statement('x', [(2026, '11014')], date(2026, 11, 5))
            self.assertIsNone(data)
            self.assertEqual(report['status'], 'not_available_as_of')
        with patch.object(reader.requests, 'get', side_effect=RuntimeError('PRIVATE_KEY')):
            _, report = reader.read_statement('x', [(2026, '11014')])
            self.assertEqual(report['status'], 'transport_error')
            self.assertNotIn('PRIVATE_KEY', json.dumps(report))


class RejectionReviewTests(unittest.TestCase):
    def test_daily_dedup_actual_trading_sessions_and_no_recommendation(self):
        item = {'name': '에어부산', 'code': '298690', 'stage': 'finance', 'reason': '자료 확인불가'}
        rows = [{'date': day, 'close': close, 'source': 'YAHOO_REGULAR_CLOSE'} for day, close in [('2026-11-05', 100), ('2026-11-06', 105), ('2026-11-09', 110), ('2026-11-10', 120)]]
        now = datetime(2026, 11, 12, tzinfo=ZoneInfo('Asia/Seoul'))
        historical = {'decision_at': '2026-11-05T12:09:45+09:00', 'source': 'verified_run_url'}
        with tempfile.TemporaryDirectory() as d, patch.object(review, 'FILE', Path(d) / 'audit.json'), patch.object(review, 'get_price_history', return_value=rows):
            review.track_rejections([item], now=now, historical=historical)
            records = review.track_rejections([item], now=now, historical=historical)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]['decision'], 'rejected_or_held')
            e = records[0]['evaluation']
            self.assertEqual(e['checkpoints']['3']['date'], '2026-11-10')
            self.assertEqual(e['checkpoints']['3']['return_pct'], 20)
            self.assertNotIn('5', e['checkpoints'])
            self.assertNotIn('score', records[0])

    def test_missing_reference_is_not_replaced_or_fabricated(self):
        rows = [{'date': '2026-11-06', 'close': 110, 'source': 'YAHOO_REGULAR_CLOSE'}]
        with tempfile.TemporaryDirectory() as d, patch.object(review, 'FILE', Path(d) / 'audit.json'), patch.object(review, 'get_price_history', return_value=rows):
            records = review.track_rejections([{'name': 'x', 'code': '123456', 'stage': 'chart', 'reason': 'trend'}], now=datetime(2026,11,5,12,tzinfo=ZoneInfo('Asia/Seoul')))
        self.assertEqual(records[0]['evaluation']['status'], 'missing_decision_close')
        self.assertEqual(records[0]['evaluation']['checkpoints'], {})

if __name__ == '__main__':
    unittest.main()
