"""Recorded headline regressions and synthetic certainty boundary tests.

These fixtures do not claim to replay historical article bodies or verify facts.
"""
import unittest
from copy import deepcopy

from event_engine import build_events, calc_event_score
from event_understanding_engine import (
    assess_event_evidence,
    classify_article_role,
    has_confirmed_event_inside_reaction,
    understand_event,
)


class EventCertaintyTests(unittest.TestCase):
    def test_signed_company_purchase_is_ma_not_supply_contract(self):
        # 운영 제목 + 공개 기사 첫 문장의 짧은 발췌. 운영 요약 전체 재생은 아니다.
        article = {
            'title': 'Salesforce to Buy Customer-Engagement Platform for Nearly $5.7 Billion',
            'summary': 'Salesforce signed a deal to buy Braze for about $5.66 billion including debt.',
            'market': 'US',
        }
        original = deepcopy(article)
        result = understand_event(article)
        self.assertEqual(result['event_type'], 'M&A')
        self.assertIn('계약', result['reason'])
        self.assertEqual(assess_event_evidence(article, result)['evidence_strength'], 'STRONG')
        self.assertEqual(build_events([deepcopy(article)])[0]['event_type'], 'M&A')
        self.assertEqual(article, original)

    def test_signed_acquisition_variants_preserve_transaction_stage(self):
        for text in [
            'Company signed an agreement to buy a software company for $2 billion.',
            'Company signs a deal to acquire a startup for $2 billion.',
            'Company entered into a definitive agreement to buy Target, with Target shareholders receiving cash.',
            'Company signed a merger agreement to buy Target for $2 billion.',
        ]:
            with self.subTest(text=text):
                article = {'title': 'Company transaction update', 'summary': text}
                self.assertEqual(understand_event(article)['event_type'], 'M&A')

    def test_signed_purchase_of_goods_stays_contract(self):
        for title in [
            'Company signed a deal to buy GPUs for $2 billion',
            'Company signed an agreement to buy electricity from a power company',
            'Company signed a deal to buy a software platform for its employees',
        ]:
            with self.subTest(title=title):
                self.assertEqual(understand_event({'title': title})['event_type'], 'CONTRACT')

    def test_purchase_intent_and_unconfirmed_signed_deals_remain_excluded(self):
        for text in [
            'Company in talks to buy a software company for $2 billion',
            'Company reportedly signed a deal to buy a software company',
            'Company has not signed an agreement to buy a startup',
            'Company signed a non-binding agreement to buy a software company',
        ]:
            with self.subTest(text=text):
                self.assert_not_confirmed({'title': text}, 'UNCONFIRMED_TRANSACTION')

    def test_not_only_does_not_negate_signed_contract(self):
        for title in [
            'Company not only signs supply contract but also expands factory',
            'Company not only signed a supply agreement but also increased production',
        ]:
            with self.subTest(title=title):
                article = {'title': title}
                self.assertEqual(understand_event(article)['event_type'], 'CONTRACT')
                self.assertGreater(calc_event_score(article)[0], 0)
                self.assertEqual(len(build_events([deepcopy(article)])), 1)

    def test_not_only_summary_preserves_confirmed_reaction_exception(self):
        summary = 'Company not only signed a supply contract but also increased production.'
        article = {'title': 'Company stock rises', 'summary': summary}
        self.assertTrue(has_confirmed_event_inside_reaction(article['title'], summary))
        self.assertEqual(understand_event(article)['event_type'], 'CONTRACT')
        self.assertGreater(calc_event_score(article)[0], 0)

    def test_not_only_does_not_override_actual_uncertainty_or_denial(self):
        for text in [
            'Company has not signed a supply contract',
            'Company never signed a supply contract',
            'Company denied signing a supply contract',
            'Company not only did not sign a supply contract but also lost a customer',
            'Company not only plans to sign a supply contract but also seeks funding',
            'Company not only aims to sign a supply contract but also seeks funding',
            'Company not only reportedly signed a supply contract but also expanded production',
        ]:
            with self.subTest(text=text):
                self.assert_not_confirmed({'title': text}, 'UNCONFIRMED_TRANSACTION')
                self.assertFalse(has_confirmed_event_inside_reaction('Company stock rises', text))

    def test_contract_intentions_are_not_signed_orders(self):
        for title in [
            '기업, 500억원 공급계약 체결 추진',
            '기업, 500억원 공급계약 추진',
            '기업, 500억원 공급계약 체결 목표',
            '기업, 공급계약 체결을 위한 협의 중',
            '기업, 공급계약 체결 협의 중',
            '기업, 공급계약을 협의 중',
            'Company seeks to sign $500 million supply contract',
            'Company aims to sign supply contract',
            'Company hopes to sign a supply agreement',
        ]:
            with self.subTest(title=title):
                article = {'title': title}
                self.assert_not_confirmed(article, 'UNCONFIRMED_TRANSACTION')
                self.assertEqual(build_events([deepcopy(article)]), [])

    def test_contract_intent_summary_cannot_enable_reaction_override(self):
        for summary in ['기업은 공급계약 체결을 위한 협의 중이다.',
                        'Company aims to sign a supply contract.']:
            with self.subTest(summary=summary):
                self.assert_not_confirmed({'title': 'Company stock rises', 'summary': summary},
                                          'UNCONFIRMED_TRANSACTION')
                self.assertFalse(has_confirmed_event_inside_reaction('Company stock rises', summary))

    def test_signed_contract_and_separate_expansion_intent_remain(self):
        for title in ['기업, 500억원 공급계약 체결',
                      '기업, 공급계약 체결 후 공장 증설 추진',
                      '기업, 공급계약 체결…추가 수주 목표',
                      'Company signs supply contract and aims to expand factory',
                      'Company signs supply agreement',
                      'Company signs supply contract to meet production targets']:
            with self.subTest(title=title):
                self.assertEqual(understand_event({'title': title})['event_type'], 'CONTRACT')

    def assert_not_confirmed(self, article, role):
        self.assertEqual(classify_article_role(article['title'], article.get('summary', '')), role)
        result = understand_event(article)
        self.assertFalse(result['is_real_event'])
        self.assertEqual(result['event_type'], 'NO_EVENT')
        self.assertEqual(assess_event_evidence(article, result)['evidence_strength'], 'WEAK')
        score, reasons = calc_event_score(article)
        self.assertEqual(score, 0)
        self.assertNotIn('사건신분:CONFIRMED', reasons)

    def test_recorded_headlines_do_not_become_confirmed_events(self):
        for title, role in [
            ('Blackstone in talks to invest up to $500m in Accord Systems- Mint', 'UNCONFIRMED_TRANSACTION'),
            ('"은행 예금보다 낫네"…배당 쏠쏠한 13조 수주 건설사', 'ANALYSIS'),
            ('Exclusive-Galderma agrees to buy ZO Skin Health for around $1.5 billion, sources say', 'UNCONFIRMED_TRANSACTION'),
        ]:
            with self.subTest(title=title):
                self.assert_not_confirmed({'title': title}, role)

    def test_negotiation_denial_and_preliminary_deals(self):
        for title in [
            'Company negotiating to invest $5 billion in a new plant',
            'Company considering a supply contract',
            'Company has not signed a supply agreement',
            'Company denied having signed a supply contract',
            'Company signed no supply agreement',
            'Company expects to sign a supply contract',
            'Company will sign a supply agreement next month',
            'Company signs non-binding agreement to invest $5 billion',
            'Company signs MOU to build a new factory',
            'Company signs letter of intent to invest $5 billion',
            'Company signed a memorandum of understanding to explore a supply agreement',
            'Company reportedly agrees to buy startup',
            '기업, 500억원 투자 협상 중',
            '기업, 500억원 공급계약 체결 검토',
            '기업, 공급계약 체결 사실무근',
            '기업, 500억원 공급계약 체결 예정',
            '기업, 투자 양해각서 체결',
        ]:
            with self.subTest(title=title):
                self.assert_not_confirmed({'title': title}, 'UNCONFIRMED_TRANSACTION')

    def test_summary_uncertainty_cannot_promote_keywords(self):
        for summary in [
            'Company is in talks to invest $5 billion in a new plant.',
            'The company has not signed a supply contract.',
            'The company agreed to acquire a startup, sources say.',
        ]:
            with self.subTest(summary=summary):
                self.assert_not_confirmed({'title': 'Company business update', 'summary': summary},
                                          'UNCONFIRMED_TRANSACTION')
                self.assertFalse(has_confirmed_event_inside_reaction('Shares rise', summary))

    def test_unconfirmed_headline_cannot_borrow_other_confirmed_action(self):
        self.assert_not_confirmed({
            'title': 'Company in talks to invest $5 billion',
            'summary': 'Another company signed a supply agreement today.',
        }, 'UNCONFIRMED_TRANSACTION')

    def test_promotion_cannot_borrow_confirmed_contract_summary(self):
        self.assert_not_confirmed({
            'title': '배당 쏠쏠한 13조 수주 건설사',
            'summary': '건설사는 오늘 공급계약을 체결했다.',
        }, 'ANALYSIS')

    def test_actual_announcements_remain_eligible(self):
        for title, expected in [
            ('Company announces $5 billion investment in new plant', 'CAPEX'),
            ('Company plans to invest $5 billion in new plant', 'CAPEX'),
            ('Company signs supply contract worth $5 billion', 'CONTRACT'),
            ('Company agrees to acquire startup for $5 billion', 'M&A'),
            ('기업, 500억원 공급계약 체결', 'CONTRACT'),
            ('건설사, 13조원 규모 공사 수주', 'CONTRACT'),
        ]:
            with self.subTest(title=title):
                self.assertTrue(understand_event({'title': title})['is_real_event'])
                self.assertEqual(understand_event({'title': title})['event_type'], expected)

    def test_dividend_keyword_alone_is_not_promotion(self):
        self.assertEqual(classify_article_role('기업, 주당 1000원 배당 결정'), 'EVENT_CANDIDATE')


if __name__ == '__main__':
    unittest.main()
