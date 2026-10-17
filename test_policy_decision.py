"""Recorded title + synthetic summaries: classification boundaries, not source fact checks."""
from copy import deepcopy
import unittest

from event_engine import build_events, calc_event_score
from event_understanding_engine import understand_event


class PolicyDecisionTests(unittest.TestCase):
    def assert_excluded(self, title, summary=''):
        article = {'title': title, 'summary': summary, 'market': 'US'}
        original = deepcopy(article)
        self.assertFalse(understand_event(article)['is_real_event'])
        self.assertEqual(calc_event_score(article)[0], 0)
        self.assertEqual(build_events([deepcopy(article)]), [])
        self.assertEqual(article, original)

    def test_recorded_pimco_title_cannot_borrow_summary_rate_cut(self):
        for summary in ['', 'The Federal Reserve cut interest rates by 25 basis points.',
                        'The Fed rate cut supported demand for longer-dated bonds.']:
            self.assert_excluded('Pimco’s Balls Sees Good Value in Long End of Yield Curve', summary)

    def test_other_market_opinions_cannot_borrow_policy_decision(self):
        for title in ['Fund manager prefers long-term bonds',
                      'Pimco sees good value after Fed rate cut',
                      'Analyst says Fed cuts rates too slowly',
                      '펀드매니저, 장기채 투자 매력 평가']:
            self.assert_excluded(title, 'The Federal Reserve cut interest rates by 25 basis points.')

    def test_direct_english_decisions_are_retained(self):
        for title in ['Federal Reserve cuts interest rates by 25 basis points',
                      'Fed raises rates by 25 basis points',
                      'The Fed has cut rates by 25 basis points',
                      'Breaking: FOMC cuts rates by 50 basis points']:
            with self.subTest(title=title):
                article = {'title': title}
                self.assertEqual(understand_event(article)['event_type'], 'FOMC')
                self.assertEqual(calc_event_score(article)[0], 95)

    def test_direct_korean_decisions_are_retained(self):
        for title in ['미국, 기준금리 0.25%p 인하', '연준, 기준금리 인상',
                      '미국 기준금리 동결', '미 연준, 기준금리 0.25%p 인하']:
            with self.subTest(title=title):
                self.assertEqual(understand_event({'title': title})['event_type'], 'FOMC')

    def test_future_negative_and_historical_decisions_are_excluded(self):
        for title in ['Fed expected to cut rates by 25 basis points',
                      'Fed cuts interest rates?',
                      'Fed cuts rates? Investors bet on next meeting',
                      'Fed did not cut interest rates',
                      'Fed cut interest rates last year',
                      '연준, 기준금리 인하 전망', '미국 기준금리 인하하지 않았다']:
            with self.subTest(title=title):
                self.assert_excluded(title)

    def test_other_central_banks_cannot_borrow_fed_summary(self):
        for title in ['Bank of Korea cuts interest rates', 'ECB cuts interest rates']:
            self.assert_excluded(title, 'The Federal Reserve cut interest rates by 25 basis points.')

    def test_real_corporate_event_is_not_removed_by_fed_background(self):
        article = {'title': 'Company signs $2 billion supply contract with Nvidia',
                   'summary': 'The Federal Reserve cut interest rates by 25 basis points.'}
        # 정책 배경 때문에 기업 계약이 FOMC로 잘못 승격되어서도 안 된다.
        self.assertEqual(understand_event(article)['event_type'], 'CONTRACT')


if __name__ == '__main__':
    unittest.main()
