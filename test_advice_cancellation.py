"""Recorded headline replay and synthetic boundary checks, not article fact checks."""
from copy import deepcopy
import unittest

from event_engine import build_events, calc_event_score
from event_understanding_engine import (assess_event_evidence, classify_article_role,
                                       has_confirmed_event_inside_reaction, understand_event)


class AdviceCancellationTests(unittest.TestCase):
    def assert_excluded(self, article, role):
        original = deepcopy(article)
        self.assertEqual(classify_article_role(article['title'], article.get('summary', '')), role)
        result = understand_event(article)
        self.assertFalse(result['is_real_event'])
        self.assertEqual(calc_event_score(article)[0], 0)
        self.assertEqual(assess_event_evidence(article, result)['evidence_strength'], 'WEAK')
        self.assertEqual(build_events([deepcopy(article)]), [])
        self.assertEqual(article, original)

    def test_recorded_advice_headline_is_not_capex(self):
        self.assert_excluded({'title': 'How to Invest for the Middle Class Blues'}, 'ANALYSIS')

    def test_advice_for_any_preposition_cannot_borrow_investment_summary(self):
        for title in ['How to Invest for Retirement', 'How to Invest During Inflation',
                      'How to Invest With $1,000', 'How to Invest in AI Stocks',
                      'How to Invest: A Guide for Beginners']:
            with self.subTest(title=title):
                self.assert_excluded({'title': title,
                                      'summary': 'Company announces $5 billion investment in a new plant.'}, 'ANALYSIS')

    def test_recorded_cancelled_land_contract_is_not_new_order(self):
        self.assert_excluded({
            'title': '[단독]LH 토지 계약해제, 4년 만에 6.9배…11조 규모 토지는 미재공급',
        }, 'CONTRACT_CANCELLATION_CONTEXT')

    def test_korean_contract_reversal_terms(self):
        for title in ['기업, 500억원 공급계약 해지', '기업, 500억원 공급 계약 해제',
                      '기업, 반도체 장비 수주 취소', '기업, 500억원 계약 파기',
                      '기업, 장비 발주 철회']:
            with self.subTest(title=title):
                self.assert_excluded({'title': title}, 'CONTRACT_CANCELLATION_CONTEXT')

    def test_english_contract_reversal_terms(self):
        for title in ['Company terminates $5 billion supply contract',
                      'Company cancels supply agreement with customer',
                      'Company supply contract was cancelled',
                      'Company rescinded purchase order',
                      'Termination of supply agreement with Company announced']:
            with self.subTest(title=title):
                self.assert_excluded({'title': title}, 'CONTRACT_CANCELLATION_CONTEXT')

    def test_cancellation_summary_cannot_be_promoted_by_signed_keyword(self):
        summary = 'The company terminated the supply agreement it signed last month.'
        self.assert_excluded({'title': 'Company update', 'summary': summary},
                             'CONTRACT_CANCELLATION_CONTEXT')
        self.assertFalse(has_confirmed_event_inside_reaction('Company stock rises', summary))

    def test_cancelled_title_cannot_borrow_other_confirmed_contract(self):
        self.assert_excluded({'title': '기업, 공급계약 해지',
                              'summary': '다른 기업이 오늘 공급계약을 체결했다.'},
                             'CONTRACT_CANCELLATION_CONTEXT')

    def test_new_investments_and_contracts_are_preserved(self):
        for title, event_type in [
            ('Company to invest $5 billion in new plant', 'CAPEX'),
            ('Company announces $5 billion investment in new plant', 'CAPEX'),
            ('기업, 삼성전자와 500억원 공급계약 체결', 'CONTRACT'),
            ('Company signs supply contract with customer', 'CONTRACT'),
            ('기업, 해지 조건 없이 500억원 공급계약 체결', 'CONTRACT'),
            ('기업, 공급계약 체결…해지 조건은 별도 협의', 'CONTRACT'),
        ]:
            with self.subTest(title=title):
                self.assertEqual(understand_event({'title': title})['event_type'], event_type)

    def test_unrelated_cancellation_does_not_block_contract(self):
        self.assertEqual(understand_event({'title': '기업, 공급계약 체결…행사 취소'})['event_type'],
                         'CONTRACT')
        self.assertEqual(understand_event({'title': 'Company signs supply contract',
                                          'summary': 'The concert was cancelled.'})['event_type'],
                         'CONTRACT')


if __name__ == '__main__':
    unittest.main()
