import unittest
from company_identity_engine import has_company_mention
from event_engine import build_events
from impact_engine import assess_company_event_relation
from stock_engine import find_direct_mentions, build_analysis_routes

ARTICLE = {'title': '하나·우리금융, 3분기 순이익 1조 돌파', 'summary': '', 'market': 'KR'}
STOCKS = [{'name': '하나금융지주', 'code': '086790', 'sector': '금융업'},
          {'name': '우리금융지주', 'code': '316140', 'sector': '금융업'}]


class CompanyIdentityTests(unittest.TestCase):
    def test_recorded_article_connects_both_listed_actors_with_original_evidence(self):
        mentions = find_direct_mentions({'articles': [ARTICLE]}, STOCKS, [])
        self.assertEqual(set(mentions), {s['name'] for s in STOCKS})
        for stock in STOCKS:
            relation = assess_company_event_relation(stock, [ARTICLE])
            self.assertTrue(relation['pass'])
            self.assertEqual(relation['role'], 'EVENT_ACTOR')
            self.assertEqual(relation['evidence'][0]['text'], ARTICLE['title'])
        routes = build_analysis_routes(build_events([dict(ARTICLE)]), [], STOCKS, [], 3)
        self.assertEqual({r['candidate_codes'][0] for r in routes}, {'086790', '316140'})

    def test_aliases_full_joint_subjects_and_reversed_compact_subject(self):
        for title in ['하나금융·우리금융, 3분기 순이익 1조 돌파',
                      '하나금융지주·우리금융지주, 3분기 순이익 1조 돌파',
                      '우리·하나금융, 3분기 순이익 1조 돌파',
                      '하나 ㆍ 우리금융, 3분기 순이익 1조 돌파']:
            for stock in STOCKS:
                with self.subTest(title=title, stock=stock):
                    self.assertTrue(assess_company_event_relation(stock, [{'title': title}])['pass'])

    def test_generic_words_subsidiaries_and_longer_names_are_not_parent_aliases(self):
        for text in ['하나, 3분기 순이익 1조 돌파', '우리, 150억원 투자 결정',
                     '하나은행, 3분기 순이익 1조 돌파', '우리은행, 3분기 순이익 1조 돌파',
                     '하나금융투자, 150억원 투자 결정', '우리금융캐피탈, 150억원 투자 결정']:
            for stock in STOCKS:
                with self.subTest(text=text, stock=stock):
                    self.assertFalse(has_company_mention(stock['name'], text))
                    self.assertFalse(assess_company_event_relation(stock, [{'title': text}])['pass'])

    def test_joint_names_cannot_borrow_competitor_or_outlook_actions(self):
        for title in ['하나·우리금융, 경쟁사가 150억원 투자 결정',
                      '하나·우리금융, 3분기 실적 개선 기대',
                      '하나·우리금융 관련주, 경쟁사 150억원 투자 결정',
                      '하나·우리금융의 과거 실적 분석',
                      '경쟁사, 150억원 투자 결정…하나·우리금융 수혜주 관심']:
            for stock in STOCKS:
                with self.subTest(title=title, stock=stock):
                    self.assertFalse(assess_company_event_relation(stock, [{'title': title}])['pass'])

    def test_alias_cannot_invent_a_route_without_a_listed_krx_row(self):
        a = {'title': '삼성重, LNG 운반선 2척 수주 계약 체결'}
        self.assertEqual(build_analysis_routes(build_events([a]), [], STOCKS, [], 3), [])

    def test_both_actors_reach_finance_and_retain_price_exclusion(self):
        from test_event_analysis_route import EventAnalysisRouteTests
        for stock in STOCKS:
            helper = EventAnalysisRouteTests()
            calls, results = helper.run_route(article=ARTICLE, stock=stock, breaking=True)
            self.assertEqual(calls, 1)
            self.assertEqual(results[0]['ranked'][0]['code'], stock['code'])
            _, results = helper.run_route(article=ARTICLE, stock=stock,
                                          breaking=True, below_ma120=True)
            self.assertEqual(results, [])
            self.assertEqual(helper.last_analysis_status['excluded'][0]['stage'], 'chart')


if __name__ == '__main__':
    unittest.main()
