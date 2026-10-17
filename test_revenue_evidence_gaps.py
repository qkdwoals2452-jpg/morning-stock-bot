"""근거 부족·예정 납기 표시 검사. 합성 데이터로 신규 실제 관계를 등록하지 않는다."""
from copy import deepcopy
import unittest

from event_engine import build_events
from supply_chain_engine import build_supply_chain_watch, load_supply_chain_evidence
from supply_order_engine import review_supply_orders
from test_supply_chain_bridge import article, STOCKS, NOW
from test_supply_order_evidence import fixture_order, ENTITIES, EVENT_AT


class RevenueEvidenceGapTests(unittest.TestCase):
    def report(self, a=None, orders=None):
        return build_supply_chain_watch(build_events([a or article()]), STOCKS,
            load_supply_chain_evidence(), NOW,
            {'schema_version': 1, 'orders': [] if orders is None else orders})

    def test_relationship_without_order_lists_next_required_proof(self):
        r = self.report()
        stage = r['event_assessments'][0]
        self.assertEqual(stage['stage'], 'documented_relationship_only')
        self.assertEqual(stage['listed_supplier_codes'], ['042700'])
        self.assertIn('matching_individual_order_primary_document', stage['missing_evidence'])
        self.assertFalse(stage['recommendation_eligible'])
        self.assertEqual(stage['score_effect'], 0)

    def test_documented_order_does_not_claim_revenue(self):
        stage = self.report(orders=[fixture_order()])['event_assessments'][0]
        self.assertEqual(stage['stage'], 'documented_order_event_unattributed')
        self.assertNotIn('matching_individual_order_primary_document', stage['missing_evidence'])
        self.assertIn('specific_us_event_order_allocation', stage['missing_evidence'])
        self.assertIn('contract_specific_revenue_recognition', stage['missing_evidence'])

    def test_unknown_actor_is_not_invented_supplier_or_no_order_claim(self):
        r = self.report(article('Amazon will invest $7 billion in HBM memory factory'))
        stage = r['event_assessments'][0]
        self.assertEqual(stage['stage'], 'no_reviewed_spending_actor')
        self.assertFalse(stage['listed_supplier_codes'])
        self.assertFalse(r['paths'])

    def test_known_actor_wrong_product_explains_missing_path(self):
        r = self.report(article('Micron will invest $7 billion in a new office'))
        stage = r['event_assessments'][0]
        self.assertEqual(stage['stage'], 'no_verified_listed_supplier_path')
        self.assertIn('product_context_mismatch', stage['excluded'])

    def test_recorded_anthropic_contract_has_no_invented_korean_supplier(self):
        a = article('Anthropic Signs First Data-Center Deal in Canada With EverWind')
        stage = self.report(a)['event_assessments'][0]
        self.assertEqual(stage['stage'], 'no_reviewed_spending_actor')
        self.assertFalse(stage['listed_supplier_codes'])
        self.assertFalse(stage['recommendation_eligible'])

    def test_bad_event_timestamp_is_not_reported_as_no_spending(self):
        stage = self.report(article(published_at=''))['event_assessments'][0]
        self.assertEqual(stage['stage'], 'event_input_unverified')
        self.assertIn('invalid_event_timestamp_or_link', stage['excluded'])

    def test_expired_contract_is_not_completed_delivery_or_revenue(self):
        r = review_supply_orders('sk_hynix', 'hanmi', 'HBM4 TC BONDER', EVENT_AT,
            ENTITIES, '2026-10-17T21:00:00+09:00')
        d = r['documented_orders'][0]
        self.assertEqual(d['delivery_period_state'], 'scheduled_end_passed_completion_unverified')
        for key in ['delivery_completion_confirmed', 'revenue_recognition_confirmed',
                    'profit_effect_confirmed', 'revision_search_complete', 'recommendation_eligible']:
            self.assertFalse(d[key])

    def test_scheduled_end_day_uses_korean_date_not_utc_or_completion(self):
        order = fixture_order(delivery_end_on='2026-10-14')
        def state(now):
            return review_supply_orders('micron', 'hanmi', 'HBM', EVENT_AT, ENTITIES, now,
                {'schema_version': 1, 'orders': [order]})['documented_orders'][0]['delivery_period_state']
        self.assertEqual(state('2026-10-14T14:59:59+00:00'), 'within_scheduled_period_completion_unverified')
        self.assertEqual(state('2026-10-14T15:00:00+00:00'), 'scheduled_end_passed_completion_unverified')

    def test_outputs_are_detached_and_claims_cannot_unlock_recommendation(self):
        a = article()
        events = build_events([a])
        before = deepcopy(events)
        r = build_supply_chain_watch(events, STOCKS, load_supply_chain_evidence(), NOW,
            {'schema_version': 1, 'orders': []})
        r['event_assessments'][0]['missing_evidence'].clear()
        self.assertEqual(events, before)
        self.assertFalse(r['recommendation_eligible'])
        self.assertEqual(r['score_effect'], 0)


if __name__ == '__main__':
    unittest.main()
