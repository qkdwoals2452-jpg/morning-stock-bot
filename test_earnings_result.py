"""Headline replay: reported results versus estimates, not source verification."""
from copy import deepcopy
import unittest

from event_engine import build_events, calc_event_score
from event_understanding_engine import classify_article_role, understand_event


RECORDED_TITLE = '[속보] TSMC 3분기 순익 69% 급증·사상 최대…시장 예상 상회'


class EarningsResultTests(unittest.TestCase):
    def test_recorded_headline_reaches_earnings_pipeline(self):
        article = {'title': RECORDED_TITLE, 'market': 'KR', 'source': 'fixture'}
        original = deepcopy(article)
        self.assertEqual(classify_article_role(RECORDED_TITLE), 'EVENT_CANDIDATE')
        result = understand_event(article)
        self.assertTrue(result['is_real_event'])
        self.assertEqual(result['event_type'], 'EARNINGS')
        self.assertEqual(calc_event_score(article)[0], 70)
        self.assertEqual(article, original)
        decisions = []
        events = build_events([deepcopy(article)], decisions=decisions)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['event_type'], 'EARNINGS')
        self.assertTrue(decisions[0]['accepted'])

    def test_comparison_is_not_a_forecast(self):
        for metric in ['순익', '순이익', '매출', '영업이익']:
            for comparison in ['시장 예상 상회', '예상치 하회', '예상치를 웃돌았다',
                               '예상을 밑돌아', '예상 상회했다']:
                title = f'TSMC 3분기 {metric} 69% 증가…{comparison}'
                with self.subTest(title=title):
                    self.assertEqual(understand_event({'title': title})['event_type'], 'EARNINGS')

    def test_other_future_language_still_blocks_comparison_titles(self):
        for title in [
            'TSMC 3분기 순익 69% 급증 예상',
            'TSMC 3분기 순익 69% 급증 전망…시장 예상 상회',
            'TSMC 3분기 순익 예상 상회할 전망',
            'TSMC 3분기 순익 예상 상회 가능성',
            'TSMC 3분기 순익 69% 급증할 것으로 예상',
            'TSMC 3분기 순익 69% 급증…예상 상회 기대',
            'TSMC 3분기 순이익 69% 급증 추정…예상 상회',
            'TSMC expected to report record quarterly profit',
        ]:
            with self.subTest(title=title):
                self.assertFalse(understand_event({'title': title})['is_real_event'])
                self.assertEqual(calc_event_score({'title': title})[0], 0)

    def test_benchmark_phrase_alone_is_not_an_earnings_event(self):
        for title in ['TSMC 시장 예상 상회', 'TSMC 3분기 순익 예상 상회',
                      'TSMC 주가 69% 상승…시장 예상 상회']:
            with self.subTest(title=title):
                self.assertFalse(understand_event({'title': title})['is_real_event'])

    def test_analysis_reaction_and_unconfirmed_guards_remain(self):
        for title, summary in [
            ('TSMC 3분기 순익 69% 급증…시장 예상 상회, 추천주', ''),
            ('[특징주] TSMC 주가 급등…3분기 순익 69% 증가, 예상 상회', ''),
            (RECORDED_TITLE, 'The company is in talks to acquire a startup.'),
        ]:
            with self.subTest(title=title, summary=summary):
                self.assertFalse(understand_event({'title': title, 'summary': summary})['is_real_event'])

    def test_same_fix_reaches_existing_profit_turnaround_path(self):
        title = '기업 3분기 영업이익 흑자전환…시장 예상 상회'
        self.assertEqual(understand_event({'title': title})['event_type'], 'EARNINGS')


if __name__ == '__main__':
    unittest.main()
