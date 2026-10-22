import unittest
from feeder_news_engine import verified_feeder_articles

class FeederVerificationTests(unittest.TestCase):
    def original(self, **kw):
        return dict(dict(link='https://www.nasdaq.com/articles/test',title='Original title',
                         summary='Original summary',published_at='2026-10-22T14:16:07+00:00'),**kw)
    def test_conflicting_duplicate_uses_original_time_and_content(self):
        items=[dict(url='https://www.nasdaq.com/articles/test?utm_source=a',title='Changed',date_published='2026-10-22T14:27:37Z'),
               dict(url='https://www.nasdaq.com/articles/test',date_published='2026-10-22T14:16:07Z')]
        a,c=verified_feeder_articles(items,[self.original()])
        self.assertEqual(len(a),1)
        self.assertEqual(a[0]['published_at'],'2026-10-22T14:16:07+00:00')
        self.assertEqual(a[0]['title'],'Original title')
        self.assertEqual(c['duplicates'],1)
        self.assertEqual(c['date_conflicts'],1)
    def test_recent_feeder_time_cannot_revive_old_original(self):
        o=self.original(); o['published_at']='2020-01-01T00:00:00Z'
        a,_=verified_feeder_articles([dict(url=o['link'],date_published='2026-10-22T14:27:37Z')],[o])
        self.assertTrue(a[0]['published_at'].startswith('2020-01-01'))
    def test_missing_original_rejected_even_with_valid_feeder_time(self):
        a,c=verified_feeder_articles([dict(url=self.original()['link'],date_published='2026-10-22T14:27:37Z')],[])
        self.assertEqual(a,[]); self.assertEqual(c['unverified'],1)
    def test_ambiguous_or_naive_original_rejected(self):
        o=self.original(); b=self.original(); b['published_at']='2026-10-21T14:16:07Z'
        item=dict(url=o['link'])
        self.assertEqual(verified_feeder_articles([item],[o,b])[0],[])
        o['published_at']='2026-10-22T14:16:07'
        self.assertEqual(verified_feeder_articles([item],[o])[0],[])
    def test_other_host_and_malformed_items_rejected(self):
        self.assertEqual(verified_feeder_articles([None,dict(url='https://evil.test/articles/test')],[self.original()])[0],[])

class FeederFetchTests(unittest.TestCase):
    def test_network_failure_sanitized_and_no_redirect_followed(self):
        from unittest.mock import patch
        import requests
        from feeder_news_engine import fetch_verified_feeder
        d={}
        with patch('requests.get',side_effect=requests.Timeout('secret-address')) as get:
            self.assertEqual(fetch_verified_feeder('https://feeder.co/out/f/test.json',[],d),[])
        self.assertFalse(get.call_args.kwargs['allow_redirects'])
        self.assertNotIn('secret-address',str(d))
    def test_verified_fetch_and_unverified_rejection(self):
        from unittest.mock import Mock,patch
        from feeder_news_engine import fetch_verified_feeder
        o=FeederVerificationTests().original()
        response=Mock(status_code=200)
        response.json.return_value={'version':'https://jsonfeed.org/version/1.1','items':[{'url':o['link']}]}
        with patch('requests.get',return_value=response):
            self.assertEqual(len(fetch_verified_feeder('https://feeder.co/out/f/test.json',[o])),1)
            self.assertEqual(fetch_verified_feeder('https://feeder.co/out/f/test.json',[]),[])

class FeederIntegrationTests(unittest.TestCase):
    def test_collector_routes_verified_feed_and_preserves_diagnostics(self):
        from unittest.mock import patch
        from news_engine import _collect_feeds
        article=FeederVerificationTests().original()
        def collect(reports):
            reports['Nasdaq_Feeder_Verified']={'status':'ok','verified':1}
            return [article]
        d={}
        with patch('news_engine.get_verified_feeder_news',side_effect=collect):
            self.assertEqual(_collect_feeds([('Nasdaq_Feeder_Verified',None)],'US',d),[article])
        self.assertEqual(d['Nasdaq_Feeder_Verified']['verified'],1)
    def test_original_failure_cannot_admit_proxy_only_articles(self):
        from unittest.mock import patch,Mock
        from news_engine import get_verified_feeder_news
        r=Mock(status_code=200)
        r.json.return_value={'version':'https://jsonfeed.org/version/1.1','items':[{'url':'https://www.nasdaq.com/articles/test'}]}
        d={}
        with patch('news_engine.parse_rss',return_value=[]),patch('requests.get',return_value=r):
            self.assertEqual(get_verified_feeder_news(d),[])
        self.assertEqual(d['Nasdaq_Feeder_Verified']['verified'],0)
