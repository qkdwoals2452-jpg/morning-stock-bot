import json
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock
from kakao_original_source import parse_original, fetch_original, MAX_BYTES

NOW = datetime(2026, 11, 20, 2, tzinfo=timezone.utc)
URL = 'https://www.reuters.com/business/company-contract-2026-11-20/'
NODE = {'@type': 'NewsArticle', 'url': URL, 'headline': 'Company signs supply agreement',
        'datePublished': '2026-11-20T01:00:00Z',
        'articleBody': 'Company announced a signed multiyear supply agreement. ' * 4}


def html(node):
    return '<script type="application/ld+json">' + json.dumps(node) + '</script>'


class OriginalTests(unittest.TestCase):
    def test_original_body_and_time_are_preserved(self):
        a = parse_original(html({'@graph': [NODE]}), URL, NOW)
        self.assertEqual(a['summary'], NODE['articleBody'].strip())
        self.assertEqual(a['published_at'], '2026-11-20T01:00:00+00:00')

    def test_unverified_metadata_never_substitutes_for_original(self):
        for change in ({'datePublished': ''}, {'datePublished': '2026-11-20'},
                       {'datePublished': '2026-11-21T01:00:00Z'},
                       {'datePublished': '2026-11-10T01:00:00Z'},
                       {'url': 'https://www.reuters.com/other/'},
                       {'articleBody': '', 'description': 'A chat claim'},
                       {'articleBody': {'text': 'unexpected'}}):
            with self.subTest(change=change):
                self.assertIsNone(parse_original(html(dict(NODE, **change)), URL, NOW))

    def test_conflicting_article_records_stay_unverified(self):
        self.assertIsNone(parse_original(html([NODE, dict(NODE, headline='Different')]), URL, NOW))

    def test_unknown_hosts_and_private_credentials_are_never_requested(self):
        session = Mock()
        for url in ('https://www.reuters.com.evil.example/x', 'http://www.reuters.com/x',
                    'https://user:secret@www.reuters.com/x', 'https://www.reuters.com:444/x',
                    'https://[broken', 'https://127.0.0.1/x'):
            self.assertIsNone(fetch_original(url, NOW, session))
        session.get.assert_not_called()

    def test_no_redirect_or_large_body_is_accepted(self):
        response = Mock(status_code=302, headers={})
        session = Mock(); session.get.return_value = response
        self.assertIsNone(fetch_original(URL, NOW, session))
        self.assertFalse(session.get.call_args.kwargs['allow_redirects'])
        response.close.assert_called_once()
        response.status_code = 200
        response.headers = {'Content-Type': 'text/html'}
        response.iter_content.return_value = [b'x' * (MAX_BYTES + 1)]
        self.assertIsNone(fetch_original(URL, NOW, session))


if __name__ == '__main__':
    unittest.main()
