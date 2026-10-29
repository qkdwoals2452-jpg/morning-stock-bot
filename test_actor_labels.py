import unittest
from impact_engine import assess_company_event_relation
from stock_engine import build_analysis_routes
from event_engine import build_events
from event_understanding_engine import understand_event
from breaking_event_gate import headline_action
from company_identity_engine import joint_subject_end

HYUNDAI='[속보] 현대차 3분기 영업이익 2조6772억…연간 판매 목표는 하향'
COLA="Here's How Much You'd Need to Invest in Coca-Cola to Generate $1,000 in Yearly Dividends"
STOCK={'name':'현대차','code':'005380'}

class ActorLabelTests(unittest.TestCase):
    def test_observed_headline_keeps_original_proof_and_routes_actor(self):
        a={'title':HYUNDAI,'summary':'','market':'KR','link':'https://www.hankyung.com/article/202610293377i','published_at':'2026-10-29T13:57:00+09:00'}
        relation=assess_company_event_relation(STOCK,[a])
        self.assertTrue(relation['pass'])
        self.assertEqual(relation['evidence'][0]['text'],HYUNDAI)
        routes=build_analysis_routes(build_events([a]),[],[STOCK],[],3)
        self.assertEqual(routes[0]['candidate_codes'],['005380'])

    def test_labels_do_not_promote_other_actor_or_rumor(self):
        for title in ['[관련주] 현대차 3분기 영업이익 2조원', '[속보] 현대차, 기아가 500억원 공급계약 체결', '[속보] 현대차 500억원 수주 기대', '[속보] 현대차 계약 체결 부인']:
            self.assertFalse(assess_company_event_relation(STOCK,[{'title':title}])['pass'],title)

    def test_compact_shared_subject_also_accepts_news_label(self):
        self.assertIsNotNone(joint_subject_end('하나금융지주','[속보] 하나·우리금융, 3분기 순이익 1조 돌파'))
        self.assertIsNone(joint_subject_end('하나금융지주','[관련주] 하나·우리금융, 3분기 순이익 1조 돌파'))

    def test_personal_allocation_article_not_corporate_capex(self):
        for title in [COLA, COLA.replace("Here's",'Here’s'), 'How Much Should You Invest in Nvidia to Earn $500 in Dividends']:
            self.assertFalse(understand_event({'title':title,'summary':'Company invests $5 billion in factory.'})['is_real_event'])
            self.assertFalse(headline_action({'event_title':title,'event_type':'CAPEX'}))

    def test_actual_capex_and_dividend_announcement_still_classified(self):
        for title in ['Coca-Cola invests $1 billion in new factory', 'Micron will invest $7 billion in HBM packaging factory']:
            self.assertTrue(understand_event({'title':title})['is_real_event'])
            self.assertTrue(headline_action({'event_title':title,'event_type':'CAPEX'}))
