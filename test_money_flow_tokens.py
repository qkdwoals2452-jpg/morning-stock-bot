"""분야 힌트의 영문 부분 문자열 오탐 회귀 검사. 원문 사실·수혜 검증이 아니다."""
from copy import deepcopy
import unittest

from event_engine import build_events, calc_event_score, extract_money_flow


class MoneyFlowTokenTests(unittest.TestCase):
    def flows(self, title):
        return extract_money_flow({'event_title': title})

    def test_recorded_travelers_gains_is_not_ai(self):
        self.assertEqual(self.flows('Travelers Profit Ticks Up on Investment Gains'), [])

    def test_embedded_english_fragments_do_not_infer_sectors(self):
        for title in ['Company shipping segment expands after normal operations',
                      'Retail chain sees gains in shopping segment',
                      'Staffed offices report powerful performance',
                      'AI2026 GM2 GPU3 HBM4X CPI2 PPI9']:
            with self.subTest(title=title):
                self.assertEqual(self.flows(title), [])

    def test_explicit_english_sector_tokens_and_punctuation_are_preserved(self):
        expected = {'AI': ['AI'], 'GPU': ['GPU', 'HBM', '반도체'],
                    'HBM': ['HBM', '반도체'], 'GM': ['차량용 반도체', 'SDV'],
                    'NOR': ['차량용 메모리'], 'CPI': ['금리', '환율'],
                    'PPI': ['금리', '환율'], 'Fed': ['금리', '환율', '은행']}
        for term, flows in expected.items():
            with self.subTest(term=term):
                self.assertEqual(self.flows(f'Company announces ({term}) project'), flows)

    def test_hyphenated_datacenter_and_ai_are_supported(self):
        for title in ['Company invests in data center', 'Company invests in DATA-CENTER',
                      'Company invests in data  center']:
            self.assertEqual(self.flows(title), ['데이터센터', '전력', '냉각'])
        self.assertIn('AI', self.flows('Company announces AI-powered products'))
        self.assertIn('AI', self.flows('기업 AI반도체 투자 확정'))

    def test_federal_reserve_remains_explicit_not_substring(self):
        self.assertEqual(self.flows('Federal Reserve cuts interest rates'), ['금리', '환율', '은행'])
        self.assertEqual(self.flows('Staffed offices gain revenue'), [])

    def test_explicit_product_versions_and_plural_words_not_lost(self):
        for term in ['HBM2', 'HBM2E', 'HBM3', 'HBM3E', 'HBM4']:
            self.assertEqual(self.flows(f'Company invests in {term} production'), ['HBM', '반도체'])
        self.assertEqual(self.flows('Company invests in GPUs'), ['GPU', 'HBM', '반도체'])
        self.assertEqual(self.flows('Government imposes tariffs'), ['관세', '수출입'])
        for title in ['Company invests in data centers', 'Company invests in data-centers',
                      'Company invests in datacenters']:
            self.assertEqual(self.flows(title), ['데이터센터', '전력', '냉각'])

    def test_company_name_alone_does_not_establish_ai_field(self):
        self.assertEqual(self.flows('OpenAI announces new investment'), [])
        self.assertIn('AI', self.flows('OpenAI announces investment in AI infrastructure'))

    def test_korean_sector_hints_are_retained_and_not_duplicated(self):
        flows = self.flows('기업 AI AI 데이터센터 투자 공급계약…반도체 메모리 증설')
        self.assertEqual(flows.count('AI'), 1)
        for term in ['데이터센터', '전력', '냉각', 'CAPEX', '공급망', '반도체', '메모리', '장비']:
            self.assertIn(term, flows)

    def test_earnings_event_is_kept_without_ai_tag_or_score_change(self):
        a = {'title': 'Travelers Profit Ticks Up on Investment Gains',
             'summary': 'Travelers reports quarterly profit up 10%.', 'market': 'US'}
        before = deepcopy(a)
        events = build_events([deepcopy(a)])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['event_type'], 'EARNINGS')
        self.assertEqual(events[0]['event_score'], 70)
        self.assertEqual(events[0]['event_score'], calc_event_score(a)[0])
        self.assertEqual(events[0]['money_flow'], [])
        self.assertEqual(a, before)

    def test_empty_title_and_input_are_safe(self):
        for event in [{}, {'event_title': None}, {'event_title': ''}]:
            before = deepcopy(event)
            self.assertEqual(extract_money_flow(event), [])
            self.assertEqual(event, before)


if __name__ == '__main__':
    unittest.main()
