from copy import deepcopy
from datetime import datetime, timezone
from email.utils import format_datetime
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

import news_engine as news
from event_engine import build_events
from event_identity_engine import corroboration_bonus, publisher


def article(title, source, summary='Original reporting', origin=''):
    return dict(title=title, summary=summary, source=source, origin_publisher=origin,
                link='https://example.test/' + source, market='US',
                published_at=datetime.now(timezone.utc).isoformat())


class MajorMediaTests(unittest.TestCase):
    def test_verified_new_publishers_and_feed_count(self):
        self.assertEqual(len(news.MAJOR_MEDIA_FEEDS), 7)
        self.assertEqual({publisher({'source': name})[0] for name, _ in news.MAJOR_MEDIA_FEEDS},
                         {'bloomberg', 'wsj', 'ft', 'bbc'})
        self.assertTrue(all(publisher({'source': name})[1] for name, _ in news.MAJOR_MEDIA_FEEDS))

    def test_new_feeds_are_used_in_actual_collector(self):
        calls = []
        def collect(feeds, market, diagnostics):
            calls.extend(feeds)
            return [article('Company update', name) for name, _ in feeds]
        with patch.object(news, '_collect_feeds', side_effect=collect), redirect_stdout(io.StringIO()):
            result = news.get_us_news({})
        self.assertTrue(set(news.MAJOR_MEDIA_FEEDS).issubset(set(calls)))
        self.assertEqual(len(calls), 19)
        self.assertTrue({'Bloomberg_Tech', 'WSJ_Business', 'FT_International', 'BBC_Business'}
                        .issubset({row['source'] for row in result}))

    def test_many_feeds_from_one_publisher_do_not_starve_last_publisher(self):
        many = [article(f'WSJ story {i}', 'WSJ_Tech' if i % 2 else 'WSJ_Business') for i in range(250)]
        many += [article('Late Bloomberg', 'Bloomberg_Tech'), article('Late FT', 'FT_International')]
        before = deepcopy(many)
        result = news.select_diverse_news(many, limit=200)
        self.assertEqual(len(result), 200)
        self.assertEqual({publisher(x)[0] for x in result[:3]}, {'wsj', 'bloomberg', 'ft'})
        self.assertEqual(many, before)
        self.assertEqual(news.select_diverse_news(many, limit=0), [])
        self.assertEqual(news.select_diverse_news([], limit=200), [])

    def test_rss_explicit_origin_is_preserved(self):
        body = ('<rss><channel><item><title>Company update</title>'
                '<source url="https://www.reuters.com">Reuters</source>'
                f'<pubDate>{format_datetime(datetime.now(timezone.utc))}</pubDate>'
                '<description>Reported news</description></item></channel></rss>')
        with patch.object(news.requests, 'get', return_value=Mock(status_code=200, content=body.encode())), redirect_stdout(io.StringIO()):
            rows = news.parse_rss('https://example.test/feed', 'US', 'YahooFinance')
        self.assertEqual(rows[0]['origin_publisher'], 'Reuters')
        self.assertEqual(rows[0]['source'], 'YahooFinance')
        self.assertEqual(publisher(rows[0]), ('reuters', True))

    def test_same_publisher_multiple_feeds_have_no_bonus(self):
        a = article('기가비스, 삼성전자와 111억원 검사장비 공급계약 체결', 'Bloomberg_Tech', 'Report A')
        b = article('기가비스, 삼성전자와 검사장비 111억원 공급계약 확정', 'Bloomberg_Markets', 'Report B')
        self.assertEqual(corroboration_bonus([a, b]), 0)

    def test_different_media_same_transaction_can_add_bounded_bonus(self):
        a = article('기가비스, 삼성전자와 111억원 검사장비 공급계약 체결', 'Bloomberg_Tech', 'Report A')
        b = article('기가비스, 삼성전자와 검사장비 111억원 공급계약 확정', 'WSJ_Business', 'Report B')
        c = article('기가비스, 삼성전자와 111억원 검사장비 공급계약 체결 확정', 'FT_International', 'Report C')
        self.assertEqual(corroboration_bonus([a, b, c]), 10)
        events = build_events(deepcopy([a, b, c]))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['source_count'], 3)
        self.assertEqual(events[0]['source_bonus'], 10)
        self.assertEqual(events[0]['event_score'], 90)

    def test_explicit_same_wire_reprints_are_not_independent(self):
        a = article('기가비스, 삼성전자와 111억원 검사장비 공급계약 체결', 'YahooFinance', 'Report A', 'Reuters')
        b = article('기가비스, 삼성전자와 검사장비 111억원 공급계약 확정', 'WSJ_Business', 'Report B', 'Thomson Reuters')
        self.assertEqual(corroboration_bonus([a, b]), 0)
        self.assertEqual({publisher(x)[0] for x in [a, b]}, {'reuters'})
        a['origin_publisher'] = b['origin_publisher'] = ''
        a['summary'], b['summary'] = '(Reuters) Report A', 'Reuters reported Report B'
        self.assertEqual(corroboration_bonus([a, b]), 0)

    def test_same_headline_or_copied_summary_does_not_add_bonus(self):
        a = article('기가비스, 삼성전자와 111억원 검사장비 공급계약 체결', 'Bloomberg_Tech', 'Report A')
        b = dict(a, source='FT_International', summary='Report B')
        self.assertEqual(corroboration_bonus([a, b]), 0)
        b['title'] = '기가비스, 삼성전자와 검사장비 111억원 공급계약 확정'
        b['summary'] = a['summary']
        self.assertEqual(corroboration_bonus([a, b]), 0)

    def test_attribution_cannot_make_unknown_feeds_verified(self):
        row = article('A report', 'unknown', '(Reuters) Report')
        self.assertEqual(publisher(row), ('reuters', False))

    def test_separate_contracts_do_not_gain_duplicate_bonus(self):
        a = article('기가비스, 삼성전자와 111억원 검사장비 공급계약 체결', 'Bloomberg_Tech', 'Report A')
        b = article('기가비스, LG전자와 220억원 냉각장비 공급계약 확정', 'WSJ_Business', 'Report B')
        self.assertEqual(corroboration_bonus([a, b]), 0)
        self.assertEqual(len(build_events([a, b])), 2)


if __name__ == '__main__':
    unittest.main()
