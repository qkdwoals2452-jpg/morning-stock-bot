import contextlib
import io
import unittest

from impact_engine import assess_company_event_relation, get_news_impact_score
from stock_engine import find_direct_mentions


def article(title, summary=''):
    return {'title': title, 'summary': summary, 'source': 'fixture',
            'link': 'https://example.test/proof', 'published_at': '2026-10-12T06:00:00+00:00'}


class MoneyFlowRelationTests(unittest.TestCase):
    def relation(self, name, title, summary=''):
        return assess_company_event_relation({'name': name}, [article(title, summary)])

    def test_supplier_has_source_sentence_amount_and_link(self):
        result = self.relation('기가비스', '기가비스, 중국 반도체 기판 업체와 111억 검사장비 공급계약')
        self.assertTrue(result['pass'])
        self.assertEqual(result['role'], 'EVENT_ACTOR')
        proof = result['evidence'][0]
        self.assertEqual(proof['event_type'], 'CONTRACT')
        self.assertEqual(proof['amount_text'], ['111억'])
        self.assertEqual(proof['source'], 'fixture')
        self.assertEqual(proof['link'], 'https://example.test/proof')
        self.assertIn('검사장비', proof['text'])

    def test_capex_is_connection_not_confirmed_profit(self):
        result = self.relation('포스코DX', '포스코DX, AI 기업 인핸스에 20억 투자')
        self.assertTrue(result['pass'])
        self.assertIn('이익 효과는 별도 검증', result['reason'])
        self.assertEqual(result['evidence'][0]['event_type'], 'CAPEX')

    def test_live_posco_headline_preserves_actor_across_ellipsis(self):
        result = self.relation('포스코DX', '포스코DX, ‘에이전틱 AI’ 승부수…인핸스에 20억 투자')
        self.assertTrue(result['pass'])
        self.assertEqual(result['role'], 'EVENT_ACTOR')
        self.assertEqual(result['evidence'][0]['amount_text'], ['20억'])

    def test_actor_after_headline_prefix_is_preserved(self):
        result = self.relation('심텍', '엔비디아 수요 대응…심텍, 반도체 공장 증설 결정')
        self.assertTrue(result['pass'])

    def test_named_counterparty_is_not_labeled_supplier(self):
        result = self.relation('삼성전자', '기가비스, 삼성전자와 검사장비 공급계약 체결')
        self.assertTrue(result['pass'])
        self.assertEqual(result['role'], 'NAMED_COUNTERPARTY')

    def test_analyst_comment_cannot_borrow_contract(self):
        result = self.relation('유진투자증권', '엔비디아, 데이터센터 공급계약 체결',
                               '유진투자증권은 이번 계약을 긍정적으로 평가했다.')
        self.assertFalse(result['pass'])

    def test_company_name_alone_is_not_benefit(self):
        result = self.relation('GST', '엔비디아, 데이터센터 공급계약 체결',
                               '관련 업계에는 GST도 있다.')
        self.assertFalse(result['pass'])

    def test_competitor_or_comment_source_is_not_counterparty(self):
        for title in ['GST와 경쟁하는 엔비디아가 데이터센터 공급계약 체결',
                      'GST에 따르면 엔비디아가 데이터센터 공급계약 체결']:
            with self.subTest(title=title):
                self.assertFalse(self.relation('GST', title)['pass'])

    def test_other_subject_after_company_name_is_not_actor(self):
        result = self.relation('GST', 'GST, 엔비디아가 데이터센터 공급계약 체결')
        self.assertFalse(result['pass'])

    def test_keyword_overlap_is_not_customer_contract(self):
        result = get_news_impact_score({'name': '검증대상기업', 'code': '123456'}, {},
                                      [article('엔비디아, HBM 공급계약 체결')],
                                      {'matched': {'products': ['HBM'], 'customers': ['엔비디아']}})
        self.assertEqual(result['raw_score'], 25)
        self.assertEqual(result['score'], 0)
        self.assertTrue(result['exclude'])

    def test_same_stock_in_separate_article_cannot_borrow_event(self):
        result = assess_company_event_relation({'name': 'GST'}, [
            article('엔비디아, 데이터센터 공급계약 체결'),
            article('GST 기업 소개', 'GST는 냉각장비를 생산한다.')])
        self.assertFalse(result['pass'])

    def test_separate_summary_sentences_do_not_make_relationship(self):
        result = self.relation('GST', '엔비디아, 데이터센터 공급계약 체결',
                               'GST는 냉각 장비 기업이다. 엔비디아가 공급계약을 체결했다.')
        self.assertFalse(result['pass'])

    def test_historical_tentative_and_denied_relations_are_blocked(self):
        for summary in ['GST는 지난해 데이터센터 공급계약을 체결했다.',
                        'GST는 데이터센터 공급계약 체결을 검토한다.',
                        'GST는 데이터센터 공급계약 체결 사실을 부인했다.']:
            with self.subTest(summary=summary):
                self.assertFalse(self.relation('GST', '엔비디아, 데이터센터 공급계약 체결', summary)['pass'])

    def test_price_reaction_borrows_only_own_confirmed_body_event(self):
        self.assertTrue(self.relation('GST', 'GST 주가 상승',
                                      'GST는 데이터센터 냉각장비 공급계약을 체결했다.')['pass'])
        self.assertFalse(self.relation('GST', 'GST 주가 상승',
                                       '엔비디아는 데이터센터 공급계약을 체결했다.')['pass'])

    def test_alias_is_preserved(self):
        result = self.relation('삼성중공업', '삼성重, LNG 운반선 2척 수주 계약 체결')
        self.assertTrue(result['pass'])
        score = get_news_impact_score({'name': '삼성중공업', 'code': '010140'}, {},
                                     [article('삼성重, LNG 운반선 2척 수주 계약 체결')], {})
        self.assertEqual(score['score'], 70)
        self.assertFalse(score['exclude'])

    def test_exact_two_character_actor_is_candidate(self):
        stocks = [{'name': '원익', 'code': '032940'}, {'name': '원익IPS', 'code': '240810'}]
        proof = article('원익, 100억원 반도체 장비 공급계약 체결')
        found = find_direct_mentions({'articles': [proof]}, stocks, [proof])
        self.assertEqual(found, {'원익': 100})

    def test_long_company_name_does_not_select_short_stock(self):
        stocks = [{'name': '원익', 'code': '032940'}, {'name': '원익IPS', 'code': '240810'}]
        proof = article('원익IPS, 100억원 반도체 장비 공급계약 체결')
        found = find_direct_mentions({'articles': [proof]}, stocks, [proof])
        self.assertEqual(found, {'원익IPS': 100})
        self.assertFalse(self.relation('이닉스', 'SK하이닉스, HBM 공급계약 체결')['pass'])

    def test_named_actor_keeps_existing_impact_weight(self):
        result = get_news_impact_score({'name': '기가비스', 'code': '420770'}, {},
                                      [article('기가비스, 반도체 검사장비 공급계약 체결')], {})
        self.assertEqual(result['score'], 70)
        self.assertFalse(result['exclude'])
        self.assertNotIn('수혜 가능성 높음', result['memo'])

    def test_missing_name_and_empty_articles_are_unverified(self):
        self.assertFalse(assess_company_event_relation({}, [])['pass'])
        self.assertFalse(assess_company_event_relation({'name': 'GST'}, [])['pass'])


if __name__ == '__main__':
    unittest.main()
