"""Feeder documented JSON Feed fixtures; no paid-account live recovery claim."""
import contextlib
import io
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import requests
import news_engine as news
from event_identity_engine import publisher

URL = 'https://feeder.co/export/private-example.json?key=do-not-log'
LINK = 'https://www.nasdaq.com/articles/company-announces-investment'


def item(**updates):
    value = {'title': 'Company announces investment', 'url': LINK,
             'date_published': datetime.now(timezone.utc).isoformat(),
             'summary': '<b>New plant</b> &amp; equipment'}
    value.update(updates)
    return value


class NasdaqSyndicationTests(unittest.TestCase):
    def read(self, items=None, payload=None, status=200):
        response = Mock(status_code=status)
        response.json.return_value = payload if payload is not None else {
            'version': 'https://jsonfeed.org/version/1.1', 'items': items or []}
        reports = {}
        output = io.StringIO()
        with patch.object(news.requests, 'get', return_value=response) as get, contextlib.redirect_stdout(output):
            rows = news.get_nasdaq_syndicated_news(URL, reports)
        self.assertNotIn('do-not-log', output.getvalue())
        self.assertNotIn(URL, output.getvalue())
        return rows, reports['Nasdaq_Syndicated'], response, get

    def test_preserve_original_link_date_and_distinct_route(self):
        original = item()
        rows, report, response, get = self.read([original])
        self.assertEqual(rows[0]['link'], LINK)
        self.assertEqual(rows[0]['published_at'], original['date_published'])
        self.assertEqual(rows[0]['summary'], 'New plant & equipment')
        self.assertEqual(rows[0]['collection_route'], 'feeder_json_export')
        self.assertEqual(publisher(rows[0])[0], 'nasdaq')
        self.assertEqual(report['recent'], 1)
        self.assertFalse(get.call_args.kwargs['allow_redirects'])
        response.close.assert_called_once()

    def test_non_article_and_other_host_links_are_not_news(self):
        links = ['https://www.nasdaq.com/market-activity/stocks/nvda',
                 'https://www.nasdaq.com/articles/',
                 'https://nasdaq.com.evil.test/articles/story',
                 'https://example.test/articles/story',
                 'http://www.nasdaq.com/articles/story',
                 'https://www.nasdaq.com:bad/articles/story']
        rows, report, _, _ = self.read([item(url=url) for url in links] + [item()])
        self.assertEqual(len(rows), 1)
        self.assertEqual(report['received'], 7)

    def test_missing_relative_naive_and_modified_only_dates_rejected(self):
        invalid = [item(date_published=None), item(date_published='3 hours ago'),
                   item(date_published='2026-10-18T04:20:00'),
                   item(date_published='', date_modified=datetime.now(timezone.utc).isoformat())]
        rows, report, _, _ = self.read(invalid)
        self.assertEqual(rows, [])
        self.assertEqual(report['status'], 'no_relevant')

    def test_old_and_future_posts_do_not_count_as_recent(self):
        now = datetime.now(timezone.utc)
        rows, report, _, _ = self.read([item(date_published=(now-timedelta(days=4)).isoformat()),
                                      item(url=LINK+'-future', date_published=(now+timedelta(days=1)).isoformat())])
        self.assertEqual(len(rows), 2)
        self.assertEqual(report['status'], 'no_recent')
        self.assertEqual(news.filter_recent_news(rows), [])

    def test_duplicates_and_malformed_items_are_skipped(self):
        rows, _, _, _ = self.read([item(), item(), None, 'bad', item(title=12)])
        self.assertEqual(len(rows), 1)

    def test_bad_schema_redirect_and_http_failure_stay_visible(self):
        for payload, status in [({'items': []}, 200), ({'version': 'https://jsonfeed.org/version/1.1', 'items': {}}, 200),
                                ({}, 302), ({}, 503)]:
            with self.subTest(status=status, payload=payload):
                rows, report, response, _ = self.read(payload=payload, status=status)
                self.assertEqual(rows, [])
                self.assertEqual(report['status'], 'error')
                response.close.assert_called_once()

    def test_invalid_export_hosts_and_connection_errors_are_sanitized(self):
        for url in ['http://feeder.co/export', 'https://feeder.co.evil.test/export',
                    'https://user:password@feeder.co/export', 'https://feeder.co:8443/export']:
            with patch.object(news.requests, 'get') as get, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(news.get_nasdaq_syndicated_news(url, {}), [])
                get.assert_not_called()
        output = io.StringIO()
        reports = {}
        with patch.object(news.requests, 'get', side_effect=requests.ReadTimeout(URL)), contextlib.redirect_stdout(output):
            self.assertEqual(news.get_nasdaq_syndicated_news(URL, reports), [])
        self.assertNotIn('do-not-log', output.getvalue())
        self.assertEqual(reports['Nasdaq_Syndicated']['error'], 'export_request_error')

    def test_failed_configured_export_falls_back_to_existing_feed(self):
        reports = {}
        def export(url, diagnostics):
            diagnostics['Nasdaq_Syndicated'] = {'status': 'error', 'error': 'export_request_error'}
            return []
        def rss(url, market, source, diagnostics=None, **kwargs):
            diagnostics[source] = {'status': 'ok'}
            return [{'title': 'Direct feed works'}]
        with patch.dict(os.environ, {'NASDAQ_SYNDICATED_FEED_URL': URL}), \
                patch.object(news, 'get_nasdaq_syndicated_news', side_effect=export), \
                patch.object(news, 'parse_rss', side_effect=rss):
            self.assertEqual(news.get_nasdaq_news(reports), [{'title': 'Direct feed works'}])
        self.assertEqual(reports['Nasdaq_Syndicated']['status'], 'error')

    def test_configured_current_export_is_used_and_unconfigured_keeps_existing_path(self):
        with patch.dict(os.environ, {'NASDAQ_SYNDICATED_FEED_URL': URL}), \
                patch.object(news, 'get_nasdaq_syndicated_news', return_value=[{**item(), 'published_at': item()['date_published']}]) as export, \
                patch.object(news, 'parse_rss', side_effect=AssertionError('legacy path should not run')):
            self.assertEqual(len(news.get_nasdaq_news({})), 1)
            export.assert_called_once()
        def rss(url, market, source, diagnostics=None, **kwargs):
            diagnostics[source] = {'status': 'empty_feed'}
            return []
        with patch.dict(os.environ, {'NASDAQ_SYNDICATED_FEED_URL': ''}), \
                patch.object(news, 'get_nasdaq_syndicated_news') as export, patch.object(news, 'parse_rss', side_effect=rss):
            self.assertEqual(news.get_nasdaq_news({}), [])
            export.assert_not_called()


if __name__ == '__main__':
    unittest.main()
