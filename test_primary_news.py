import unittest
from unittest.mock import Mock,patch
from news_engine import parse_rss,_collect_feeds,PRIMARY_NEWS_FEEDS
from event_identity_engine import publisher,corroboration_bonus

class PrimaryNewsTests(unittest.TestCase):
    def xml(self,date='Thu, 22 Oct 2026 15:00:02 +0000',url='https://nvidianews.nvidia.com/news/test'):
        return f'<rss><channel><item><title>New AI factory supply contract</title><link>{url}</link><description>Issuer announcement</description><pubDate>{date}</pubDate></item></channel></rss>'.encode()
    def test_original_date_provenance_and_statement_kind(self):
        with patch('news_engine.requests.get',return_value=Mock(status_code=200,content=self.xml())):
            a=parse_rss('https://nvidianews.nvidia.com/releases.xml','US','NVIDIA_Newsroom')
        self.assertEqual(a[0]['published_at'],'2026-10-22T15:00:02+00:00')
        self.assertEqual(a[0]['publication_verified_by'],'Publisher_RSS')
        self.assertEqual(a[0]['content_kind'],'issuer_release')
    def test_wrong_domain_and_missing_date_rejected(self):
        for body in [self.xml(date=''),self.xml(url='https://evil.test/news')]:
            with patch('news_engine.requests.get',return_value=Mock(status_code=200,content=body)):
                self.assertEqual(parse_rss('https://nvidianews.nvidia.com/releases.xml','US','NVIDIA_Newsroom'),[])
    def test_press_releases_do_not_count_as_independent_media(self):
        self.assertEqual(publisher({'source':'NVIDIA_Newsroom'}),('nvidia',False))
        self.assertEqual(publisher({'source':'PRNewswire_Tech'}),('prnewswire',False))
    def test_new_feeds_use_real_parallel_collection_route(self):
        with patch('news_engine.parse_rss',return_value=[]) as parse:
            _collect_feeds(PRIMARY_NEWS_FEEDS,'US',{})
        self.assertEqual({c.args[2] for c in parse.call_args_list},{'NVIDIA_Newsroom','PRNewswire_Tech'})
