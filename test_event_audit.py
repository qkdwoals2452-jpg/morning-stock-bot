import contextlib
from copy import deepcopy
import io
import json
import unittest

from event_audit_engine import print_event_audit
from event_engine import build_events


class EventAuditTests(unittest.TestCase):
    def capture(self, decisions, count, **options):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            print_event_audit(decisions, count, **options)
        return output.getvalue()

    def test_diagnostic_mode_preserves_events_and_article_decisions(self):
        articles = [
            {'title': 'Company signs supply contract worth $5 billion', 'market': 'US', 'source': 'fixture'},
            {'title': 'Company signs supply contract worth $5 billion', 'market': 'US', 'source': 'fixture'},
            {'title': 'Blackstone in talks to invest up to $500m in Accord Systems- Mint', 'market': 'US'},
            {'title': '"은행 예금보다 낫네"…배당 쏠쏠한 13조 수주 건설사', 'market': 'KR'},
            {'title': 'Company business update', 'market': 'US'},
        ]
        expected = build_events(deepcopy(articles))
        decisions = []
        actual = build_events(deepcopy(articles), decisions=decisions)
        self.assertEqual(actual, expected)
        self.assertEqual(len(decisions), len(articles))
        self.assertEqual(sum(row['accepted'] for row in decisions), 2)
        self.assertEqual(len(actual), 1)
        output = self.capture(decisions, len(actual))
        counts = json.loads(output.splitlines()[0].split(': ', 1)[1])
        self.assertEqual(counts, {'input_articles': 5, 'accepted_articles': 2,
                                  'rejected_articles': 3, 'merged_events': 1})
        self.assertIn('UNCONFIRMED_TRANSACTION', output)
        self.assertIn('ANALYSIS', output)
        self.assertIn('EVENT_CANDIDATE', output)

    def test_zero_events_keeps_distinct_exclusion_reasons_visible(self):
        decisions = []
        events = build_events([
            {'title': 'Company expects to sign a supply contract', 'market': 'US'},
            {'title': '기업 일반 소식', 'market': 'KR'},
        ], decisions=decisions)
        self.assertEqual(events, [])
        self.assertEqual(len({x['reason'] for x in decisions}), 2)
        output = self.capture(decisions, 0)
        self.assertIn('"rejected_articles": 2', output)
        self.assertIn('"accepted_articles": 0', output)

    def test_all_exclusions_counted_while_samples_are_bounded_and_sanitized(self):
        rows = [{'market': 'US', 'role': 'EVENT_CANDIDATE', 'score': 0,
                 'accepted': False, 'reason': 'no action', 'source': 'fixture',
                 'title': 'Title\nhttps://example.test/private?token=SECRET token=HIDDEN ' + 'x' * 1000}
                for _ in range(100)]
        rows.append(dict(rows[0], market='KR', reason='another reason'))
        output = self.capture(rows, 0, sample_limit=2)
        self.assertNotIn('SECRET', output)
        self.assertNotIn('HIDDEN', output)
        self.assertNotIn('example.test', output)
        samples = [json.loads(line.split(': ', 1)[1]) for line in output.splitlines()
                   if line.startswith('사건 제외 표본:')]
        self.assertEqual(len(samples), 2)
        self.assertEqual({x['market'] for x in samples}, {'US', 'KR'})
        self.assertTrue(all(len(x['title']) <= 240 for x in samples))
        self.assertIn('"rejected_articles": 101', output)
        self.assertIn('"omitted": 99', output)
        self.assertIn('headline_only_not_full_article_replay', output)

    def test_empty_input_is_explicit(self):
        output = self.capture([], 0)
        self.assertIn('"input_articles": 0', output)
        self.assertIn('"shown": 0', output)


if __name__ == '__main__':
    unittest.main()
