"""Synthetic events test reviewed primary relationships; they are never live alerts."""
import unittest
from copy import deepcopy
from event_engine import build_events
from supply_chain_engine import build_supply_chain_watch, load_supply_chain_evidence
from supply_order_engine import load_supply_order_evidence

class TechwingBridgeTests(unittest.TestCase):
    def report(self, title='Micron announces $2 billion investment in India semiconductor test and assembly factory', stamp='2026-10-30T08:04:00+09:00', book=None, stocks=None):
        article={'title':title,'summary':'','market':'US','source':'synthetic_fixture','published_at':stamp,'link':'https://example.test/synthetic-micron-india'}
        return build_supply_chain_watch(build_events([article]), stocks if stocks is not None else [{'name':'테크윙','code':'089030'}],book or load_supply_chain_evidence(),'2026-10-30T08:05:00+09:00')

    def test_parent_and_contracting_subsidiary_are_not_collapsed(self):
        r=self.report(); p=r['paths'][0]
        self.assertEqual(p['path'], ['Micron','Micron Semiconductor Technology India','테크윙'])
        self.assertEqual(p['evidence'][0]['relationship'], 'REPORTED_SUBSIDIARY')
        self.assertFalse(p['new_order_confirmed'])
        self.assertFalse(p['recommendation_eligible'])
        self.assertEqual(p['score_effect'],0)

    def test_no_other_country_or_generic_capex_borrowing(self):
        for title in ['Micron announces $2 billion investment in Taiwan semiconductor test factory', 'Micron announces $2 billion investment in India HBM memory factory','Micron announces $2 billion investment in India research labs']:
            self.assertFalse(self.report(title)['paths'])

    def test_no_retroactive_contract_or_wrong_listing(self):
        self.assertFalse(self.report(stamp='2026-10-20T08:04:00+09:00')['paths'])
        self.assertFalse(self.report(stocks=[{'name':'다른기업','code':'089030'}])['paths'])
        b=deepcopy(load_supply_chain_evidence()); b['edges']=[e for e in b['edges'] if e['id']!='micron_india_subsidiary_2026']
        self.assertFalse(self.report(book=b)['paths'])

    def test_individual_order_is_not_us_event_revenue_attribution(self):
        p=self.report('Micron announces $2 billion investment in India 검사장비 test factory')['paths'][0]
        review=p['order_review']
        self.assertTrue(review['documented_order_confirmed'])
        self.assertFalse(review['event_order_attribution_confirmed'])
        self.assertFalse(review['revenue_recognition_confirmed'])
        self.assertFalse(review['profit_effect_confirmed'])
        o=next(o for o in load_supply_order_evidence()['orders'] if o['supplier']=='techwing')
        self.assertEqual(o['amount'],9497217450)
        self.assertEqual(o['source_fields']['product'],'반도체 검사장비 공급계약 체결')
