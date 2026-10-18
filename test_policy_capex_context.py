"""Run #375 titles; Bloomberg RSS re-read on 2026-10-19 KST.

The Korean article's historical summary was not logged/recovered. Its summaries
below are synthetic boundary fixtures, not a reconstruction of that article.
"""
from copy import deepcopy
import unittest

from event_engine import build_events, calc_event_score
from event_understanding_engine import understand_event

COPPER_TITLE = 'Traders Grow Wary of Copper Bull Market With No Sign of Tariffs'
COPPER_RSS_SUMMARY = (
    'Since Donald Trump came back into office, copper has surged on a seismic '
    'reshuffling of global inventories linked to the risk that he’ll impose '
    'tariffs on the metal. But as Trump nears the halfway mark on his second '
    'term, the market’s many bulls are growing wary that prices could crash '
    'if he doesn’t follow through.'
)
IPO_TITLE = '장비 제조 넘어 통합 EPC 기업으로…제이피이노베이 “내년 IPO 도전”'


class PolicyCapexContextTests(unittest.TestCase):
    def assert_excluded(self, title, summary=''):
        article = {'title': title, 'summary': summary}
        before = deepcopy(article)
        self.assertFalse(understand_event(article)['is_real_event'])
        self.assertEqual(calc_event_score(article)[0], 0)
        self.assertEqual(build_events([deepcopy(article)]), [])
        self.assertEqual(article, before)

    def test_recorded_copper_title_and_reread_rss_summary(self):
        self.assert_excluded(COPPER_TITLE, COPPER_RSS_SUMMARY)

    def test_recorded_titles_cannot_borrow_background_policy(self):
        for title in [COPPER_TITLE, IPO_TITLE, 'Copper inventories shift across markets']:
            with self.subTest(title=title):
                self.assert_excluded(title, 'The government imposes tariffs on copper imports.')

    def test_recorded_ipo_title_cannot_borrow_capex_background(self):
        for summary in ['', '회사는 생산능력 확대를 추진하며 내년 상장에 도전한다.',
                        'The company discusses a new factory and a spending plan.',
                        'Company announced investment in a new plant last year.']:
            with self.subTest(summary=summary):
                self.assert_excluded(IPO_TITLE, summary)

    def test_uncertain_negative_historical_policy_titles_are_excluded(self):
        for title in ['US export restrictions under consideration',
                      'US may impose tariff on copper imports',
                      'US did not impose tariff on copper imports',
                      'No sign of new export restrictions on chips',
                      'US imposed export restrictions last year',
                      '미국 관세 부과 검토', '미국 관세 부과 여부에 시장 긴장',
                      'US announces tariff on chips?']:
            with self.subTest(title=title):
                self.assert_excluded(title)

    def test_direct_policy_announcements_and_implementation_retained(self):
        for title in ['US imposes new export restrictions on advanced AI chips',
                      'Trump announces 25% tariff on semiconductor imports',
                      'US export ban takes effect', '미국, 자동차에 25% 관세 부과',
                      '정부, 반도체 수출 규제 시행']:
            with self.subTest(title=title):
                self.assertEqual(understand_event({'title': title})['event_type'], 'POLICY')
                self.assertEqual(calc_event_score({'title': title})[0], 90)

    def test_real_corporate_action_survives_policy_background(self):
        for title, expected in [
            ('Company signs $2 billion supply contract with Nvidia', 'CONTRACT'),
            ('Company announces $5 billion investment in new plant', 'CAPEX'),
        ]:
            article = {'title': title, 'summary': 'US imposes tariffs on imports.'}
            self.assertEqual(understand_event(article)['event_type'], expected)

    def test_confirmed_investments_and_mixed_reaction_exception_retained(self):
        for title, summary in [
            ('TSMC to invest $29.4 billion in advanced chip production', ''),
            ('Company plans to invest $5 billion in new plant', ''),
            ('포스코DX, 인핸스에 20억 투자', ''),
            ('기업, 500억원 공장 증설 투자 결정', ''),
            ('Company stock rises 5%', 'Company announced a $3 billion investment to build a new data center.'),
        ]:
            with self.subTest(title=title):
                self.assertEqual(understand_event({'title': title, 'summary': summary})['event_type'], 'CAPEX')

    def test_unrelated_summary_confirmation_does_not_promote_capex(self):
        for background in ['It discusses a new factory.',
                           'Last year company announced investment in a new plant.']:
            article = {'title': 'Company stock rises 5%',
                       'summary': 'Company reports revenue of $5 billion. ' + background}
            self.assertEqual(understand_event(article)['event_type'], 'EARNINGS')


if __name__ == '__main__':
    unittest.main()
