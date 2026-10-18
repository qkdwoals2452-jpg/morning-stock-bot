"""실공시 관계 + 합성 사건 검증. 합성 사건을 신규 수주 근거로 저장하지 않는다."""
from copy import deepcopy
import unittest

from event_engine import build_events, calc_event_score
from supply_chain_engine import build_supply_chain_watch, load_supply_chain_evidence

NOW = '2026-10-19T06:50:00+09:00'
STOCKS = [{'name': 'LS ELECTRIC', 'code': '010120'}]


def article(title='Bloom Energy announces $2 billion investment in fuel cell production', **changes):
    return dict({'title': title, 'summary': '', 'market': 'US',
                 'source': 'synthetic_fixture', 'published_at': '2026-10-19T06:40:00+09:00',
                 'link': 'https://example.test/synthetic-bloom-event'}, **changes)


class PowerSupplierEvidenceTests(unittest.TestCase):
    def report(self, a=None, stocks=None, now=NOW, book=None):
        return build_supply_chain_watch(build_events([a or article()]),
            STOCKS if stocks is None else stocks,
            load_supply_chain_evidence() if book is None else book, now,
            {'schema_version': 1, 'orders': []})

    def test_project_relationship_preserves_us_legal_intermediary(self):
        r = self.report()
        self.assertEqual(len(r['paths']), 1)
        p = r['paths'][0]
        self.assertEqual(p['path'], ['Bloom Energy', 'LS ELECTRIC AMERICA', 'LS ELECTRIC'])
        self.assertEqual(p['hops'], 2)
        self.assertEqual(len({e['id'] for e in p['evidence']}), 2)
        # 두 문서/독립 확인으로 과장하지 않는다. 동일 공시의 서로 다른 공급 관계다.
        self.assertEqual(len({e['source_url'] for e in p['evidence']}), 1)
        self.assertEqual(p['code'], '010120')
        self.assertEqual(p['knowledge_timing'], 'retrospective_review')

    def test_no_new_order_revenue_profit_or_recommendation_claim(self):
        r = self.report()
        p = r['paths'][0]
        for key in ['new_order_confirmed', 'revenue_attribution_confirmed',
                    'profit_effect_confirmed', 'recommendation_eligible']:
            self.assertFalse(p[key])
        self.assertEqual(p['score_effect'], 0)
        self.assertEqual(r['event_assessments'][0]['stage'], 'documented_relationship_only')
        self.assertFalse(p['order_review']['documented_order_confirmed'])

    def test_no_path_before_current_review(self):
        r = self.report(now='2026-10-19T06:45:00+09:00')
        self.assertFalse(r['paths'])
        self.assertEqual(r['excluded']['unavailable_at_assessment'], 2)

    def test_review_can_be_known_before_a_later_synthetic_event(self):
        r = self.report(article(published_at='2026-10-19T06:49:00+09:00'))
        self.assertEqual(r['paths'][0]['knowledge_timing'], 'known_before_event')
        self.assertFalse(r['paths'][0]['recommendation_eligible'])

    def test_generic_datacenter_or_other_product_not_borrowed(self):
        for title in ['Bloom Energy announces $2 billion investment in a data center',
                      'Bloom Energy announces $2 billion investment in HBM memory production',
                      'Anthropic announces $2 billion investment in fuel cell production']:
            with self.subTest(title=title):
                self.assertFalse(self.report(article(title))['paths'])

    def test_other_company_fuel_cell_summary_not_borrowed(self):
        a = article('Bloom Energy announces $2 billion investment in a factory',
                    summary='Another company begins fuel cell production.')
        self.assertFalse(self.report(a)['paths'])

    def test_rumor_or_denial_not_promoted_by_customer_relationship(self):
        for title in ['Bloom Energy could invest $2 billion in fuel cell production',
                      'Bloom Energy will not invest $2 billion in fuel cell production']:
            with self.subTest(title=title):
                self.assertFalse(self.report(article(title))['paths'])

    def test_requires_current_listed_code_and_exact_company_name(self):
        for stocks in [[], [{'name': '다른회사', 'code': '010120'}],
                       [{'name': 'LS ELECTRIC', 'code': '006260'}]]:
            with self.subTest(stocks=stocks):
                self.assertFalse(self.report(stocks=stocks)['paths'])

    def test_registry_and_events_not_mutated_and_scores_unchanged(self):
        a = article()
        book = load_supply_chain_evidence()
        events = build_events([a])
        before = deepcopy((book, events))
        raw_score = calc_event_score(a)[0]
        r = build_supply_chain_watch(events, STOCKS, book, NOW)
        self.assertEqual((book, events), before)
        self.assertEqual(events[0]['event_score'], raw_score)
        r['paths'][0]['evidence'][0]['evidence_summary'] = 'changed output'
        self.assertEqual(book, before[0])


if __name__ == '__main__':
    unittest.main()
