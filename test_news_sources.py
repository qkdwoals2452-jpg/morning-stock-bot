import io
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import Mock, patch

import requests
import news_engine as news


def response(body, status=200):
    return Mock(status_code=status, content=body.encode())


def rss(date=None):
    date = date or datetime.now(timezone.utc)
    return ('<rss><channel><item><title>Company signs supply contract</title>'
            '<link>https://example.test/news</link><source url="https://www.nasdaq.com">Nasdaq</source>'
            '<description>&lt;b&gt;Signed&lt;/b&gt; &amp;amp; delivered</description>'
            f'<pubDate>{format_datetime(date)}</pubDate></item></channel></rss>')


def atom(form='8-K'):
    return ('<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
            f'<title>{form} - Company</title>'
            '<link rel="self" href="https://example.test/feed"/>'
            '<link rel="alternate" href="https://example.test/filing"/>'
            '<summary>Current filing</summary>'
            f'<updated>{datetime.now(timezone.utc).isoformat()}</updated>'
            '</entry></feed>')


class NewsSourceTests(unittest.TestCase):
    def setUp(self):
        self.output = io.StringIO()
        self.capture = redirect_stdout(self.output)
        self.capture.__enter__()
        self.addCleanup(self.capture.__exit__, None, None, None)

    def parse(self, effects, parser=news.parse_rss, source='Nasdaq_Tech'):
        diagnostics = {}
        with patch('news_engine.requests.get', side_effect=effects) as get, \
                patch('news_engine.time.sleep') as sleep:
            articles = parser('https://example.test/feed', 'US', source, diagnostics)
        return articles, diagnostics[source], get, sleep

    def test_rss_content_and_date_are_preserved(self):
        articles, report, get, _ = self.parse([response(rss())])
        self.assertEqual(articles[0]['summary'], 'Signed & delivered')
        self.assertEqual(articles[0]['market'], 'US')
        self.assertEqual(articles[0]['source'], 'Nasdaq_Tech')
        self.assertEqual(report['status'], 'ok')
        self.assertEqual((report['received'], report['parsed'], report['recent']), (1, 1, 1))
        self.assertIn('application/rss+xml', get.call_args.kwargs['headers']['Accept'])
        self.assertIn('ORION', get.call_args.kwargs['headers']['User-Agent'])
        self.assertEqual(get.call_args.kwargs['timeout'], (5, 15))

    def test_timeout_recovers_on_second_request(self):
        articles, report, get, sleep = self.parse([requests.ReadTimeout(), response(rss())])
        self.assertEqual(len(articles), 1)
        self.assertEqual(report['attempts'], 2)
        self.assertEqual(get.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_connection_failure_recovers(self):
        articles, report, _, _ = self.parse([requests.ConnectionError(), response(rss())])
        self.assertEqual(len(articles), 1)
        self.assertEqual(report['status'], 'ok')

    def test_persistent_timeout_is_bounded_and_sanitized(self):
        articles, report, get, _ = self.parse([requests.ReadTimeout('secret-url')] * 2)
        self.assertEqual(articles, [])
        self.assertEqual(report['error'], 'timeout')
        self.assertEqual(report['attempts'], 2)
        self.assertEqual(get.call_count, 2)
        self.assertNotIn('secret-url', self.output.getvalue())

    def test_server_error_recovers(self):
        articles, report, _, _ = self.parse([response('', 503), response(rss())])
        self.assertEqual(len(articles), 1)
        self.assertEqual(report['http_status'], 200)
        self.assertEqual(report['attempts'], 2)

    def test_persistent_server_error_is_bounded(self):
        _, report, get, _ = self.parse([response('', 502)] * 2)
        self.assertEqual(report['error'], 'http_error')
        self.assertEqual(report['http_status'], 502)
        self.assertEqual(get.call_count, 2)

    def test_access_denied_and_rate_limit_are_not_retried(self):
        for status, reason in [(403, 'access_denied'), (429, 'rate_limited'), (404, 'http_error')]:
            with self.subTest(status=status):
                _, report, get, sleep = self.parse([response('', status)])
                self.assertEqual(report['error'], reason)
                self.assertEqual(get.call_count, 1)
                sleep.assert_not_called()

    def test_other_request_error_is_reported(self):
        _, report, get, _ = self.parse([requests.RequestException('private-url')])
        self.assertEqual(report['error'], 'request_error')
        self.assertEqual(get.call_count, 1)
        self.assertNotIn('private-url', self.output.getvalue())

    def test_invalid_xml_is_not_empty_success(self):
        _, report, get, _ = self.parse([response('not xml')])
        self.assertEqual(report['status'], 'error')
        self.assertEqual(report['error'], 'invalid_xml')
        self.assertEqual(get.call_count, 1)

    def test_html_and_wrong_feed_formats_are_errors(self):
        for body, parser, reason in [('<html/>', news.parse_rss, 'unexpected_rss_root'),
                                     (atom(), news.parse_rss, 'unexpected_rss_root'),
                                     (rss(), news.parse_atom, 'unexpected_atom_root')]:
            with self.subTest(reason=reason):
                _, report, _, _ = self.parse([response(body)], parser)
                self.assertEqual(report['error'], reason)

    def test_empty_feed_is_distinct_from_failure(self):
        _, report, _, _ = self.parse([response('<rss><channel/></rss>')])
        self.assertEqual(report['status'], 'empty_feed')
        self.assertIsNone(report['error'])

    def test_old_articles_are_distinct_from_empty_feed(self):
        articles, report, _, _ = self.parse([response(rss(datetime.now(timezone.utc) - timedelta(days=3)))])
        self.assertEqual(len(articles), 1)
        self.assertEqual(report['status'], 'no_recent')
        self.assertEqual(report['recent'], 0)

    def test_sec_forms_and_alternate_filing_link(self):
        articles, report, _, _ = self.parse([response(atom())], news.parse_atom, 'SEC_Filings')
        self.assertEqual(articles[0]['link'], 'https://example.test/filing')
        self.assertEqual(report['status'], 'ok')

    def test_sec_non_core_forms_are_distinct_from_empty(self):
        articles, report, _, _ = self.parse([response(atom('4'))], news.parse_atom, 'SEC_Filings')
        self.assertEqual(articles, [])
        self.assertEqual(report['received'], 1)
        self.assertEqual(report['status'], 'no_relevant')

    def test_sec_is_requested_once_with_atom_parser(self):
        diagnostics = {}
        def fetch(url, **kwargs):
            return response(atom() if 'sec.gov' in url else '<feed xmlns="http://www.w3.org/2005/Atom"/>' if 'bls.gov' in url else '<rss><channel/></rss>')
        with patch('news_engine.requests.get', side_effect=fetch) as get:
            articles = news.get_us_news(diagnostics)
        sec_calls = [call for call in get.call_args_list if 'sec.gov' in call.args[0]]
        self.assertEqual(len(sec_calls), 1)
        self.assertIn('SEC_Filings', [a['source'] for a in articles])
        self.assertEqual(diagnostics['SEC_Filings']['received'], 1)

    def test_nasdaq_timeout_uses_named_index_fallback(self):
        diagnostics = {}
        with patch('news_engine.requests.get', side_effect=[requests.ReadTimeout(), response(rss())]) as get, patch('news_engine.time.sleep'):
            articles = news.get_nasdaq_news(diagnostics)
        self.assertEqual(articles[0]['source'], 'Nasdaq_GoogleRSS')
        self.assertEqual(diagnostics['Nasdaq_Tech']['status'], 'error')
        self.assertEqual(diagnostics['Nasdaq_GoogleRSS']['status'], 'ok')
        self.assertEqual(get.call_count, 2)
        self.assertEqual(get.call_args_list[0].kwargs['timeout'], (3, 5))
        self.assertEqual(get.call_args_list[1].kwargs['timeout'], (5, 15))
        self.assertEqual(diagnostics['Nasdaq_Tech']['attempts'], 1)
        self.assertIn('news.google.com/rss/search?', get.call_args.args[0])
        from urllib.parse import parse_qs, urlsplit
        self.assertEqual(parse_qs(urlsplit(get.call_args.args[0]).query)['q'][0], 'site:nasdaq.com when:2d')

    def test_nasdaq_connection_failure_does_not_retry_direct_feed(self):
        diagnostics = {}
        with patch('news_engine.requests.get', side_effect=[requests.ConnectTimeout(), response(rss())]) as get, patch('news_engine.time.sleep') as sleep:
            articles = news.get_nasdaq_news(diagnostics)
        self.assertEqual(len(articles), 1)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(diagnostics['Nasdaq_Tech']['error'], 'connect_timeout')
        sleep.assert_not_called()

    def test_nasdaq_server_failure_switches_to_index(self):
        diagnostics = {}
        with patch('news_engine.requests.get', side_effect=[response('', 503), response(rss())]) as get, patch('news_engine.time.sleep') as sleep:
            articles = news.get_nasdaq_news(diagnostics)
        self.assertEqual(len(articles), 1)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(diagnostics['Nasdaq_Tech']['http_status'], 503)
        sleep.assert_not_called()

    def test_nasdaq_timeout_and_empty_index_remain_distinct(self):
        diagnostics = {}
        with patch('news_engine.requests.get', side_effect=[requests.ReadTimeout(), response('<rss><channel/></rss>')]):
            self.assertEqual(news.get_nasdaq_news(diagnostics), [])
        self.assertEqual(diagnostics['Nasdaq_Tech']['status'], 'error')
        self.assertEqual(diagnostics['Nasdaq_GoogleRSS']['status'], 'empty_feed')

    def test_nasdaq_fallback_rejects_other_publishers(self):
        diagnostics = {}
        body = rss().replace('https://www.nasdaq.com', 'https://other.test')
        articles, report, _, _ = self.parse([response(body)], source='Nasdaq_GoogleRSS')
        self.assertEqual(articles, [])
        self.assertEqual(report['status'], 'no_relevant')

    def test_nasdaq_success_and_empty_do_not_use_fallback(self):
        for body in (rss(), '<rss><channel/></rss>'):
            with patch('news_engine.requests.get', return_value=response(body)) as get:
                diagnostics = {}
                news.get_nasdaq_news(diagnostics)
            self.assertEqual(get.call_count, 1)
            self.assertNotIn('Nasdaq_GoogleRSS', diagnostics)

    def test_nasdaq_fallback_failure_remains_visible(self):
        with patch('news_engine.requests.get', return_value=response('', 403)) as get:
            diagnostics = {}
            self.assertEqual(news.get_nasdaq_news(diagnostics), [])
        self.assertEqual(get.call_count, 2)
        self.assertEqual(diagnostics['Nasdaq_Tech']['error'], 'access_denied')
        self.assertEqual(diagnostics['Nasdaq_GoogleRSS']['error'], 'access_denied')

    def test_bls_rss_urls_use_atom_without_sec_form_filter(self):
        diagnostics = {}
        def fetch(url, **kwargs):
            return response(atom('CPI release') if 'bls.gov' in url else
                            atom('4') if 'sec.gov' in url else '<rss><channel/></rss>')
        with patch('news_engine.requests.get', side_effect=fetch) as get:
            articles = news.get_us_news(diagnostics)
        for source in ('BLS_Employment', 'BLS_CPI', 'BLS_PPI'):
            self.assertEqual(diagnostics[source]['status'], 'ok')
            self.assertEqual(diagnostics[source]['parsed'], 1)
        self.assertEqual(len([c for c in get.call_args_list if 'bls.gov' in c.args[0]]), 3)
        self.assertTrue(articles)
        self.assertEqual(diagnostics['SEC_Filings']['status'], 'no_relevant')

    def test_failed_source_does_not_stop_other_sources(self):
        diagnostics = {}
        def fetch(url, **kwargs):
            if 'nasdaq.com' in url:
                raise requests.ReadTimeout()
            return response(atom() if 'sec.gov' in url or 'bls.gov' in url else rss())
        with patch('news_engine.requests.get', side_effect=fetch), patch('news_engine.time.sleep'):
            articles = news.get_us_news(diagnostics)
        self.assertTrue(articles)
        self.assertEqual(diagnostics['Nasdaq_Tech']['error'], 'timeout')
        self.assertEqual(diagnostics['SEC_Filings']['status'], 'ok')
        self.assertEqual(diagnostics['BLS_PPI']['status'], 'ok')


if __name__ == '__main__':
    unittest.main()
