"""Recorded headline regressions and synthetic certainty boundary tests.

These fixtures do not claim to replay historical article bodies or verify facts.
"""
import unittest

from event_engine import calc_event_score
from event_understanding_engine import (
    assess_event_evidence,
    classify_article_role,
    has_confirmed_event_inside_reaction,
    understand_event,
)


class EventCertaintyTests(unittest.TestCase):
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
