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

class ArticleVerificationTests(unittest.TestCase):
    url='https://www.nasdaq.com/articles/test'
    def body(self, date='2026-10-22T14:16:07Z', identity=None):
        import json
        return '<link rel="canonical" href="'+self.url+'"><script type="application/ld+json">'+json.dumps({'@type':'NewsArticle','url':identity or self.url,'headline':'Original headline','description':'Original description','datePublished':date})+'</script>'
    def test_original_article_without_rss_verifies(self):
        from feeder_news_engine import original_from_article
        a=original_from_article(self.body(),self.url)
        self.assertEqual(a['publication_verified_by'],'Nasdaq_Article_JSONLD')
        self.assertEqual(a['published_at'],'2026-10-22T14:16:07+00:00')
    def test_missing_naive_or_conflicting_identity_rejected(self):
        from feeder_news_engine import original_from_article
        self.assertIsNone(original_from_article(self.body(date=''),self.url))
        self.assertIsNone(original_from_article(self.body(date='2026-10-22T14:16:07'),self.url))
        self.assertIsNone(original_from_article(self.body(identity='https://evil.test/'),self.url))
        self.assertIsNone(original_from_article(self.body().replace('rel="canonical"','rel="alternate"'),self.url))
    def test_conflicting_original_publication_dates_rejected(self):
        from feeder_news_engine import original_from_article
        self.assertIsNone(original_from_article(self.body()+self.body(date='2026-10-21T14:16:07Z'),self.url))
    def test_live_adapter_fallback_uses_original_not_proxy_date(self):
        from unittest.mock import patch,Mock
        from feeder_news_engine import fetch_verified_feeder
        export=Mock(status_code=200)
        export.json.return_value={'version':'https://jsonfeed.org/version/1.1','items':[{'url':self.url,'date_published':'2026-10-22T20:00:00Z'}]}
        article=Mock(status_code=200,text=self.body(),content=self.body().encode())
        d={}
        with patch('requests.get',side_effect=[export,article]):
            a=fetch_verified_feeder('https://feeder.co/out/f/test.json',[],d,verify_articles=True)
        self.assertEqual(a[0]['published_at'],'2026-10-22T14:16:07+00:00')
        self.assertEqual(a[0]['publication_verified_by'],'Nasdaq_Article_JSONLD')
        self.assertEqual(d['Nasdaq_Feeder_Verified']['article_verified'],1)

class ArticleNetworkFailureTests(unittest.TestCase):
    def test_timeout_and_forbidden_never_admit_proxy_timestamp(self):
        from unittest.mock import Mock, patch
        import requests
        from feeder_news_engine import fetch_article_originals
        items = [{'url': 'https://www.nasdaq.com/articles/one'},
                 {'url': 'https://www.nasdaq.com/articles/two'}]
        with patch('requests.get', side_effect=[requests.Timeout(), Mock(status_code=403)]):
            articles, report = fetch_article_originals(items, [])
        self.assertEqual(articles, [])
        self.assertEqual(report['article_attempted'], 2)
        self.assertEqual(report['article_verified'], 0)
        self.assertEqual(report['article_results'], {'timeout': 1, 'http_or_size_rejected': 1})

    def test_modified_date_alone_is_not_original_publication(self):
        from feeder_news_engine import original_from_article
        sample = ArticleVerificationTests()
        self.assertIsNone(original_from_article(sample.body().replace('datePublished', 'dateModified'), sample.url))
