import unittest
from company_identity_engine import has_company_mention
from impact_engine import assess_company_event_relation
from stock_engine import find_direct_mentions

class CompanyAmbiguityTests(unittest.TestCase):
    def test_dictionary_words_and_headline_capitalization_never_become_issuers(self):
        for name,title in [('NEW','Vusion Completes Acquisition, Opening a New Chapter'),('NEW','NEW factory receives $100 million investment'),('NICE','Nice expansion secures $100 million deal'),('ONE','One factory wins a new supply contract'),('TOP','Top semiconductor firm signs new contract'),('AI','AI investment reaches $100 billion')]:
            stock={'name':name,'code':'123456'}
            a={'title':title,'summary':'새로운 한국 시장 진출','market':'US'}
            self.assertFalse(has_company_mention(name,title))
            self.assertFalse(assess_company_event_relation(stock,[a])['pass'])
            self.assertEqual(find_direct_mentions({'articles':[a]},[stock],[]),{})

    def test_korean_sentence_elsewhere_does_not_license_english_token(self):
        for text in ['New chapter for chip industry. 한국 사업 확대.', 'NEW factory invests $100 million. 한국 공장 투자.', 'NEW product launched; 한국 상장사 관련 뉴스']:
            self.assertFalse(has_company_mention('NEW',text))

    def test_explicit_correct_ticker_identifies_real_english_named_issuer(self):
        stock={'name':'NEW','code':'160550'}
        a={'title':'NEW(160550), 영화 배급 계약 체결','market':'KR'}
        self.assertTrue(assess_company_event_relation(stock,[a])['pass'])
        self.assertIn('NEW',find_direct_mentions({'articles':[a]},[stock],[]))
        self.assertFalse(has_company_mention('NEW','NEW(005930) signs distribution agreement',code='160550'))
        self.assertFalse(has_company_mention('NEW','New(160550) signs distribution agreement',code='160550'))

    def test_actual_korean_acronym_actors_kept_but_product_mentions_rejected(self):
        for name,code in [('GST','083450'),('ISC','095340'),('HPSP','403870'),('NEW','160550')]:
            stock={'name':name,'code':code}
            a={'title':f'{name}, 150억원 공급계약 체결','market':'KR'}
            self.assertTrue(assess_company_event_relation(stock,[a])['pass'])
            self.assertIn(name,find_direct_mentions({'articles':[a]},[stock],[]))
        for title in ['삼성전자, NEW 제품 150억원 공급계약 체결','NEW 관련주, 삼성전자가 150억원 계약 체결','NEW, 경쟁사가 150억원 계약 체결','NEW, 150억원 계약 기대']:
            a={'title':title,'market':'KR'}
            self.assertEqual(find_direct_mentions({'articles':[a]},[{'name':'NEW','code':'160550'}],[]),{})

    def test_explicit_ticker_elsewhere_cannot_license_generic_actor(self):
        a={'title':'New factory signs $150 million contract with NEW(160550) as an observer','summary':'','market':'US'}
        self.assertFalse(assess_company_event_relation({'name':'NEW','code':'160550'},[a])['pass'])

    def test_reference_only_policy_precedes_business_keyword_search(self):
        from test_event_analysis_route import EventAnalysisRouteTests
        helper=EventAnalysisRouteTests()
        calls,results=helper.run_route(article={'title':'삼성전자, 반도체 공장에 150억원 투자 결정','summary':'','market':'KR'},stock={'name':'삼성전자','code':'005930','sector':'반도체 제조업'},verify_pass=False)
        self.assertEqual(results,[])
        self.assertEqual(calls,0)
        self.assertEqual(helper.last_analysis_status['excluded'][0]['stage'],'policy')
        self.assertIn('참고용',helper.last_analysis_status['excluded'][0]['reason'])
