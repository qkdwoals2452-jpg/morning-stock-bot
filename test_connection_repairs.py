import unittest
from impact_engine import assess_company_event_relation
from event_engine import build_events
from stock_engine import build_analysis_routes
from finance_model_policy import financial_model_unsupported
from breaking_news import followup

SOMA = {'title': '소마젠, 50억 규모 저커버그 재단 세포 분석 사업 추가 수주', 'market': 'KR'}


class ConnectionRepairTests(unittest.TestCase):
    def test_actual_cell_analysis_order_retains_original_evidence_and_route(self):
        stock = {'name': '소마젠', 'code': '950200', 'sector': '자연과학 및 공학 연구개발업'}
        proof = assess_company_event_relation(stock, [SOMA])
        self.assertTrue(proof['pass'])
        self.assertEqual(proof['evidence'][0]['text'], SOMA['title'])
        routes = build_analysis_routes(build_events([dict(SOMA)]), [], [stock], [], 3)
        self.assertEqual(routes[0]['candidate_codes'], ['950200'])

    def test_technical_service_does_not_erase_analyst_or_competitor_context(self):
        for title in ['소마젠, 세포 분석 추가 수주 기대',
                      '소마젠, 세포 분석 수주 전망 분석',
                      '소마젠, 경쟁사가 세포 분석 사업 추가 수주',
                      '소마젠, 지난해 세포 분석 사업 수주',
                      '소마젠, 세포 분석 사업 추가 수주 취소']:
            with self.subTest(title=title):
                self.assertFalse(assess_company_event_relation({'name': '소마젠'}, [{'title': title}])['pass'])

    def test_reviewed_shipbuilding_holding_uses_normal_consolidated_model(self):
        self.assertFalse(financial_model_unsupported({'name': 'HD한국조선해양', 'code': '009540', 'sector': '기타 금융업'}))
        for stock in [
            {'name': '하나금융지주', 'code': '086790', 'sector': '기타 금융업'},
            {'name': '우리금융지주', 'code': '316140', 'sector': '기타 금융업'},
            {'name': '미확인 지주회사', 'code': '123456', 'sector': '기타 금융업'},
            {'name': '잘못된 회사명', 'code': '009540', 'sector': '기타 금융업'},
            {'name': 'HD한국조선해양', 'code': '009540', 'sector': '보험업'},
        ]:
            self.assertTrue(financial_model_unsupported(stock))

    def test_industrial_holding_keeps_financial_and_price_hard_gates(self):
        from test_financial_data import FinancialDataTests
        from unittest.mock import patch
        helper = FinancialDataTests()
        helper.setUp()
        try:
            with patch.object(helper.finance, 'get_naver_basic', return_value={'per': 10, 'pbr': 1}), \
                 patch.object(helper.finance, 'get_dart_finance', return_value={'op_margin': -1, 'debt_ratio': 400}), \
                 patch.object(helper.finance, 'get_quality_score', return_value={'score': 0}):
                result = helper.finance.get_finance_score({'name': 'HD한국조선해양', 'code': '009540', 'sector': '기타 금융업'})
            self.assertTrue(result['exclude'])
            self.assertNotIn('model_coverage', result)
        finally:
            helper.tearDown()
        from test_event_analysis_route import EventAnalysisRouteTests
        route = EventAnalysisRouteTests()
        _, results = route.run_route(article=SOMA,
            stock={'name': '소마젠', 'code': '950200', 'sector': '연구개발업'},
            breaking=True, below_ma120=True)
        self.assertEqual(results, [])
        self.assertEqual(route.last_analysis_status['excluded'][0]['stage'], 'chart')

    def test_followup_exposes_reviewed_source_without_claiming_new_order(self):
        status = {'analysis_status': {'analyzed_count': 0, 'selected_count': 0, 'excluded': []},
                  'supply_chain_watch': {'paths': [{'path': ['미국기업', '국내기업'],
                    'evidence': [{'source_url': 'https://kind.krx.co.kr/proof?a=1&b=2'}]}]}}
        text = followup({'event_title': '새 사건'}, [], status)
        self.assertIn('관계 근거 원자료', text)
        self.assertIn('신규 수주·매출·이익 귀속은 미확정', text)
        self.assertIn('&amp;', text)

    def test_equity_offering_is_not_a_manufacturing_supplier_order(self):
        from test_supply_chain_bridge import SupplyChainBridgeTests, article
        helper = SupplyChainBridgeTests()
        helper.setUp()
        report = helper.report(article('NVIDIA to invest $3 billion in Meta share offering',
            summary='NVIDIA will invest $3 billion in HBM memory through a Meta equity offering.'))
        self.assertEqual(report['paths'], [])
        self.assertFalse(report['recommendation_eligible'])
        self.assertEqual(report['excluded']['non_manufacturing_spending'], 1)

    def test_rejected_stock_keeps_article_actor_proof_in_followup(self):
        status = {'analysis_status': {'analyzed_count': 1, 'selected_count': 0,
            'connections': [{'name': '소마젠', 'code': '950200', 'role': 'EVENT_ACTOR',
                'evidence': [{'amount_text': ['50억'], 'link': 'https://example.com/order'}]}],
            'excluded': [{'name': '소마젠', 'code': '950200', 'reason': '영업적자 제외'}]}}
        text = followup({'event_title': SOMA['title']}, [], status)
        self.assertIn('기사상 사건 주체', text)
        self.assertIn('50억', text)
        self.assertIn('영업적자 제외', text)
        self.assertIn('매출 인식·이익 효과는 별도 검증', text)

    def test_very_long_proof_does_not_break_telegram_html_or_length(self):
        status = {'analysis_status': {'analyzed_count': 1, 'selected_count': 0, 'excluded': [],
                  'connections': [{'name': '소마젠', 'code': '950200', 'role': 'EVENT_ACTOR',
                      'evidence': [{'link': 'https://example.com/' + 'a' * 4000}]}]}}
        text = followup({'event_title': SOMA['title']}, [], status)
        self.assertLessEqual(len(text), 3500)
        self.assertNotIn('<a ', text)
