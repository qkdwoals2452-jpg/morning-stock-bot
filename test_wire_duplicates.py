from copy import deepcopy
from datetime import datetime, timezone
import unittest
from unittest.mock import Mock
from event_engine import build_events
from event_identity_engine import duplicate_article, same_event, canonical_link
from breaking_news import process

TITLE='Coveo Acquires Anglera to Make Product Data a Competitive Advantage in AI-Powered eCommerce'
SUMMARY="The acquisition combines Anglera's agentic product data enrichment engine with Coveo's platform, helping manufacturers, distributors and enterprise retailers make products easier to find, compare, and buy, both on their own eCommerce websites and through AI-powered shopping assistants...."

def article(number='302924144', **changes):
    return dict({'title':TITLE,'summary':SUMMARY,'link':'https://www.prnewswire.com/news-releases/coveo-acquires-anglera-to-make-product-data-a-competitive-advantage-in-ai-powered-ecommerce-'+number+'.html','source':'PRNewswire_Tech','market':'US','origin_publisher':'PR Newswire Association LLC.','publication_verified_by':'Publisher_RSS','content_kind':'distributed_press_release','published_at':'2026-10-29T20:01:00+00:00'},**changes)

class WireDuplicateTests(unittest.TestCase):
    def test_actual_copies_merge_without_deleting_url_identifiers_or_source_bonus(self):
        a,b=article(),article('895803317')
        self.assertNotEqual(canonical_link(a['link']), canonical_link(b['link']))
        self.assertTrue(duplicate_article(a,b))
        events=build_events([a,b])
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]['source_count'],1)
        self.assertEqual(events[0]['source_bonus'],0)

    def test_missing_or_different_evidence_never_uses_content_only_merge(self):
        for change in [{'summary':SUMMARY+' New contract.'}, {'published_at':'2026-10-29T20:02:00+00:00'}, {'published_at':'2026-10-29T20:01:00'}, {'publication_verified_by':''}, {'origin_publisher':'Another wire'}, {'link':'https://www.prnewswire.com.evil.test/news-releases/story-123.html'}, {'source':'WSJ_Tech'}, {'link':'https://www.prnewswire.com:bad/news-releases/story-123.html'}]:
            self.assertFalse(duplicate_article(article(),article('895803317',**change)),change)
        self.assertTrue(duplicate_article(article(),article('895803317',published_at='2026-10-30T05:01:00+09:00')))

    def test_one_notice_and_followup_across_persisted_restart(self):
        state={'version':1,'records':[],'activation':{'phase':'sent'},'initialized_at':'2026-10-29T19:00:00+00:00'}
        analyze=Mock(return_value=([],{'analysis_status':{'analyzed_count':0,'selected_count':0,'excluded':[]}}))
        send=Mock()
        now=datetime(2026,10,29,20,5,tzinfo=timezone.utc)
        r=process(state,Mock(),[article()],now,send,analyze)
        self.assertEqual((r['notices'],r['analyses']),(1,1))
        restored=deepcopy(state)
        r=process(restored,Mock(),[article('895803317')],now,send,analyze)
        self.assertEqual((r['new'],r['notices'],r['analyses']),(0,0,0))
        self.assertEqual(send.call_count,2)
        self.assertEqual(analyze.call_count,1)

    def test_additional_order_correction_and_amount_change_have_distinct_keys(self):
        base={'title':'기가비스, 삼성전자와 111억원 검사장비 공급계약 체결','summary':'','source':'한국경제_경제','market':'KR','link':'https://example.test/contract','published_at':'2026-10-29T20:01:00+00:00'}
        for title in ['기가비스, 삼성전자와 112억원 검사장비 공급계약 체결','[정정] '+base['title'],'기가비스, 삼성전자와 111억원 검사장비 추가 수주']:
            revised=dict(base,title=title)
            self.assertFalse(same_event(base,revised))
            events=build_events([deepcopy(base),revised])
            self.assertEqual(len(events),2)
            self.assertNotEqual(events[0]['event_key'],events[1]['event_key'])

    def test_additional_order_is_delivered_as_new_event(self):
        def contract(title):
            return {'title':title,'summary':'','source':'한국경제_경제','market':'KR','link':'https://example.test/contract','published_at':'2026-10-29T20:01:00+00:00'}
        state={'version':1,'records':[],'activation':{'phase':'sent'},'initialized_at':'2026-10-29T19:00:00+00:00'}
        analyze=Mock(return_value=([],{'analysis_status':{'analyzed_count':0,'selected_count':0,'excluded':[]}}))
        now=datetime(2026,10,29,20,5,tzinfo=timezone.utc)
        process(state,Mock(),[contract('기가비스, 삼성전자와 111억원 검사장비 공급계약 체결')],now,Mock(),analyze)
        r=process(state,Mock(),[contract('기가비스, 삼성전자와 111억원 검사장비 추가 수주')],now,Mock(),analyze)
        self.assertEqual((r['new'],r['notices'],r['analyses']),(1,1,1))
