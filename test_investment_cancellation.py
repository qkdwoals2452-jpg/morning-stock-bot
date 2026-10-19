"""Synthetic cancellation boundaries; these fixtures are not verified news reports."""
from copy import deepcopy
import unittest

from event_engine import build_events, calc_event_score
from event_understanding_engine import (
    assess_event_evidence, classify_article_role,
    has_confirmed_event_inside_reaction, understand_event,
)


class InvestmentCancellationTests(unittest.TestCase):
    def assert_excluded(self, article):
        original = deepcopy(article)
        self.assertEqual(classify_article_role(article['title'], article.get('summary', '')),
                         'INVESTMENT_CANCELLATION_CONTEXT')
        result = understand_event(article)
        self.assertFalse(result['is_real_event'])
        self.assertEqual(result['event_type'], 'NO_EVENT')
        self.assertEqual(assess_event_evidence(article, result)['evidence_strength'], 'WEAK')
        self.assertEqual(calc_event_score(article)[0], 0)
        self.assertEqual(build_events([deepcopy(article)]), [])
        self.assertEqual(article, original)

    def test_cancelled_investments_are_not_new_capex(self):
        for title in [
            'Company cancels $5 billion investment in new plant',
            'Company abandons plans to invest $5 billion in new plant',
            'Company scraps $5 billion capital spending plan',
            'Company shelves plans for new factory',
            'Company investment in new plant was cancelled',
            'Cancellation of $5 billion investment announced by Company',
            '기업, 500억원 공장 증설 투자 철회',
            '기업, 신규 공장 투자 계획 백지화',
            '기업, 500억원 투자 취소',
            '기업, 공장 증설 계획 중단',
            '기업, 철회한 500억원 투자 계획',
        ]:
            with self.subTest(title=title):
                self.assert_excluded({'title': title})

    def test_summary_and_reaction_cannot_revive_cancelled_investment(self):
        for summary in [
            'Company cancelled the $5 billion investment it announced last month.',
            '회사는 지난달 결정한 공장 증설 투자를 철회했다.',
        ]:
            with self.subTest(summary=summary):
                self.assert_excluded({'title': 'Company shares rise', 'summary': summary})
                self.assertFalse(has_confirmed_event_inside_reaction('Company shares rise', summary))

    def test_cancelled_title_cannot_borrow_confirmed_summary(self):
        self.assert_excluded({
            'title': 'Company cancels investment in new plant',
            'summary': 'Another company announces $5 billion investment in a new factory.',
        })

    def test_genuine_investments_and_unrelated_cancellations_remain(self):
        for title, summary in [
            ('Company announces $5 billion investment in new plant', ''),
            ('Company plans to invest $5 billion in new plant', ''),
            ('기업, 500억원 공장 증설 투자 결정', ''),
            ('기업, 공장 증설 투자 결정…행사 취소', ''),
            ('Company announces investment in new plant', 'The concert was cancelled.'),
            ('Company announces investment in new plant; concert cancelled', ''),
            ('Company cancels concert, announces investment in new plant', ''),
        ]:
            with self.subTest(title=title, summary=summary):
                self.assertEqual(understand_event({'title': title, 'summary': summary})['event_type'],
                                 'CAPEX')


if __name__ == '__main__':
    unittest.main()
