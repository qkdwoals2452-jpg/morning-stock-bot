"""합성 주문 문서는 로직 검증 전용이며 실제 수주 근거로 저장하지 않는다."""
from copy import deepcopy
from datetime import datetime
import contextlib
import io
import importlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

from event_engine import build_events
from supply_chain_engine import build_supply_chain_watch, load_supply_chain_evidence
from supply_order_engine import load_supply_order_evidence, review_supply_orders
from telegram_bot import send_telegram

NOW = datetime.fromisoformat('2026-10-14T15:40:00+09:00')
EVENT_AT = '2026-10-14T07:30:00+09:00'
ENTITIES = load_supply_chain_evidence()['entities']


def fixture_order(**changes):
    # 실공시·실주문을 재현한 데이터가 아니다.
    return dict({
        'contract_id': 'synthetic_contract_only', 'buyer': 'micron', 'supplier': 'hanmi',
        'receipt_no': '20261013999999',
        'source_url': 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261013999999',
        'review_method': 'manual_primary_source', 'state': 'disclosed_contract',
        'published_on': '2026-10-13', 'ordered_on': '2026-10-12', 'delivery_end_on': '2026-12-31',
        'reviewed_at': '2026-10-14T07:00:00+09:00', 'amount': 100000000,
        'currency': 'KRW', 'product_terms': ['HBM'],
        'source_fields': {'supplier': '한미반도체', 'buyer': 'Micron', 'product': 'HBM TC BONDER',
                          'amount': '100,000,000', 'section': 'synthetic fields, not real disclosure'},
    }, **changes)


class SupplyOrderEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.order = fixture_order()

    def report(self, orders=None, **kwargs):
        return review_supply_orders('micron', 'hanmi', 'Micron HBM memory factory', EVENT_AT,
                                    ENTITIES, NOW, {'schema_version': 1,
                                    'orders': [self.order] if orders is None else orders}, **kwargs)

    def test_documented_order_is_separate_from_event_attribution_and_profit(self):
        r = self.report()
        self.assertTrue(r['documented_order_confirmed'])
        self.assertFalse(r['event_order_attribution_confirmed'])
        self.assertFalse(r['revenue_recognition_confirmed'])
        self.assertFalse(r['profit_effect_confirmed'])
        self.assertFalse(r['recommendation_eligible'])
        self.assertEqual(r['score_effect'], 0)
        self.assertEqual(r['documented_orders'][0]['order_timing'], 'predates_event')

    def test_default_registry_does_not_promote_unread_candidates(self):
        book = load_supply_order_evidence()
        self.assertEqual(book['orders'], [])
        self.assertEqual(len(book['review_log']['unverified_filing_candidates']), 2)
        r = review_supply_orders('micron', 'hanmi', 'HBM', EVENT_AT, ENTITIES, NOW)
        self.assertEqual(r['status'], 'no_verified_order')
        self.assertFalse(r['documented_order_confirmed'])
        self.assertIn('주문이 없다는 뜻이 아닙니다', r['note'])

    def test_wrong_customer_order_not_borrowed_for_micron_event(self):
        self.order['buyer'] = 'sk_hynix'
        self.order['source_fields']['buyer'] = 'SK하이닉스'
        r = self.report()
        self.assertFalse(r['documented_orders'])
        self.assertEqual(r['excluded']['different_order_counterparty'], 1)

    def test_entity_and_primary_field_must_agree(self):
        self.order['source_fields']['buyer'] = 'SK하이닉스'
        self.assertEqual(self.report()['excluded']['counterparty_evidence_mismatch'], 1)

    def test_hana_micron_not_us_micron_counterparty(self):
        self.order['source_fields']['buyer'] = 'Hana Micron'
        self.assertFalse(self.report()['documented_order_confirmed'])

    def test_legal_suffix_does_not_change_party_identity(self):
        self.order['source_fields']['buyer'] = 'Micron Technology, Inc.'
        self.order['source_fields']['supplier'] = '한미반도체 주식회사'
        self.assertTrue(self.report()['documented_order_confirmed'])

    def test_product_mismatch_rejected(self):
        self.order['product_terms'] = ['MSVP']
        self.order['source_fields']['product'] = 'MSVP substrate equipment'
        self.assertEqual(self.report()['excluded']['different_order_product'], 1)

    def test_product_term_must_be_supported_by_primary_field(self):
        self.order['source_fields']['product'] = 'office equipment'
        self.assertEqual(self.report()['excluded']['missing_product_evidence'], 1)

    def test_future_review_not_usable_at_earlier_assessment(self):
        self.order['reviewed_at'] = '2026-10-15T07:00:00+09:00'
        self.assertFalse(self.report()['documented_orders'])

    def test_review_after_event_marked_retrospective(self):
        self.order['reviewed_at'] = '2026-10-14T15:00:00+09:00'
        self.assertEqual(self.report()['documented_orders'][0]['knowledge_timing'], 'retrospective_review')

    def test_later_order_is_not_proof_of_causality(self):
        self.order.update(ordered_on='2026-10-14', published_on='2026-10-14',
                          reviewed_at='2026-10-15T07:00:00+09:00')
        r = review_supply_orders('micron', 'hanmi', 'HBM', EVENT_AT, ENTITIES,
            '2026-10-15T08:00:00+09:00', {'schema_version': 1, 'orders': [self.order]})
        self.assertTrue(r['documented_order_confirmed'])
        self.assertFalse(r['event_order_attribution_confirmed'])
        self.assertEqual(r['documented_orders'][0]['order_timing'], 'same_day_or_later_not_causal_proof')

    def test_missing_or_naive_review_date_rejected(self):
        for value in ('', '2026-10-14T07:00:00'):
            self.order['reviewed_at'] = value
            self.assertFalse(self.report()['documented_orders'])

    def test_date_only_publication_not_available_at_day_start(self):
        self.order.update(published_on='2026-10-14', reviewed_at='2026-10-14T07:00:00+09:00')
        self.assertFalse(self.report()['documented_orders'])

    def test_inconsistent_order_dates_rejected(self):
        for changes in ({'ordered_on': '2026-10-15'}, {'delivery_end_on': '2026-01-01'}):
            self.order = fixture_order(**changes)
            self.assertEqual(self.report()['excluded']['invalid_order_timeline'], 1)

    def test_amount_must_match_primary_and_is_not_revenue(self):
        for value in (True, -1, 0, float('inf'), 100000001):
            self.order['amount'] = value
            self.assertFalse(self.report()['documented_orders'])

    def test_unapproved_source_or_receipt_mismatch_rejected(self):
        for url in ('https://dart.fss.or.kr.evil.test/dsaf001/main.do?rcpNo=20261013999999',
                    'https://news.test/contract', 'http://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261013999999',
                    'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261013999998'):
            self.order['source_url'] = url
            self.assertFalse(self.report()['documented_orders'])

    def test_news_guess_and_unverified_primary_not_order_evidence(self):
        self.order['review_method'] = 'secondary_news'
        self.assertFalse(self.report()['documented_orders'])
        self.order = fixture_order(state='primary_document_unavailable')
        self.assertFalse(self.report()['documented_orders'])

    def test_duplicates_not_added_or_summed(self):
        r = self.report([self.order, deepcopy(self.order)])
        self.assertEqual(len(r['documented_orders']), 1)
        conflict = deepcopy(self.order)
        conflict['amount'] = 200000000
        conflict['source_fields']['amount'] = '200,000,000'
        self.assertEqual(self.report([self.order, conflict])['excluded']['conflicting_order_evidence'], 1)

    def test_cancelled_order_supersedes_original_at_assessment(self):
        cancellation = fixture_order(receipt_no='20261013999998', state='cancelled_contract',
                                     published_on='2026-10-14', amount=0,
                                     source_url='https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261013999998',
                                     reviewed_at='2026-10-15T07:00:00+09:00')
        cancellation['source_fields']['amount'] = '0'
        book = {'schema_version': 1, 'orders': [self.order, cancellation]}
        early = review_supply_orders('micron', 'hanmi', 'HBM', EVENT_AT, ENTITIES, NOW, book)
        self.assertTrue(early['documented_order_confirmed'])
        late = review_supply_orders('micron', 'hanmi', 'HBM', EVENT_AT, ENTITIES,
                                    '2026-10-15T08:00:00+09:00', book)
        self.assertFalse(late['documented_order_confirmed'])
        self.assertEqual(late['excluded']['cancelled_order'], 1)

    def test_same_day_amendment_without_ordering_not_selected(self):
        other = fixture_order(receipt_no='20261013999998', state='amended_contract',
                              source_url='https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261013999998')
        self.assertFalse(self.report([self.order, other])['documented_orders'])

    def test_malformed_book_or_time_explicitly_unavailable(self):
        for book in ({}, [], {'schema_version': 1, 'orders': 'bad'}):
            r = review_supply_orders('micron', 'hanmi', 'HBM', EVENT_AT, ENTITIES, NOW, book)
            self.assertEqual(r['status'], 'order_evidence_unavailable')

    def test_inputs_not_mutated_and_output_detached(self):
        before = deepcopy(self.order)
        self.report()['documented_orders'][0]['source_fields']['product'] = 'changed'
        self.assertEqual(self.order, before)

    def test_injected_claims_cannot_enable_attribution_or_recommendation(self):
        self.order.update(event_order_attribution_confirmed=True, recommendation_eligible=True, score_effect=100)
        r = self.report()
        self.assertFalse(r['event_order_attribution_confirmed'])
        self.assertFalse(r['recommendation_eligible'])
        self.assertEqual(r['score_effect'], 0)
        self.assertFalse(r['documented_orders'][0]['event_order_attribution_confirmed'])
        self.assertFalse(r['documented_orders'][0]['recommendation_eligible'])
        self.assertEqual(r['documented_orders'][0]['score_effect'], 0)

    def test_main_order_documents_never_enter_recommendations_or_backtest(self):
        article = {'title': 'Micron will invest $7 billion in HBM memory factory', 'summary': '',
                   'published_at': EVENT_AT, 'market': 'US', 'source': 'fixture',
                   'link': 'https://example.test/synthetic-event'}
        previous = os.getcwd()
        modules = ('main', 'finance_engine', 'quality_engine')
        with tempfile.TemporaryDirectory() as directory:
            os.chdir(directory)
            try:
                Path('corp_code.csv').write_text('stock_code,corp_code\n042700,00126380\n')
                for name in modules:
                    sys.modules.pop(name, None)
                main = importlib.import_module('main')
                finance = importlib.import_module('finance_engine')
                sender, saved, prediction = Mock(), Mock(), Mock()
                calls = dict(load_korean_stocks=Mock(return_value=[{'name': '한미반도체', 'code': '042700'}]),
                    get_us_news=Mock(return_value=[article]), get_korea_news=Mock(return_value=[]),
                    update_backtest_prices=Mock(), save_today_result=Mock(), save_recommendations=saved,
                    save_prediction=prediction, send_telegram=sender,
                    get_project_status=Mock(return_value={'saved_days': 0, 'saved_themes': 0}),
                    build_supply_chain_watch=lambda events, stocks: build_supply_chain_watch(events, stocks,
                        as_of=NOW, order_evidence={'schema_version': 1, 'orders': [self.order]}))
                with patch.multiple(main, **calls), patch.object(finance, 'get_finance_score') as finance_call, \
                        contextlib.redirect_stdout(io.StringIO()):
                    main.run()
                results, status = sender.call_args.args
                self.assertEqual(results, [])
                self.assertTrue(status['supply_chain_watch']['paths'][0]['order_review']['documented_order_confirmed'])
                saved.assert_called_once_with([])
                prediction.assert_not_called()
                finance_call.assert_not_called()
            finally:
                os.chdir(previous)
                for name in modules:
                    sys.modules.pop(name, None)

    def test_watch_integrates_order_review_but_keeps_all_recommendation_flags_false(self):
        article = {'title': 'Micron will invest $7 billion in HBM memory factory', 'summary': '',
                   'published_at': EVENT_AT, 'market': 'US', 'source': 'fixture',
                   'link': 'https://example.test/synthetic-event'}
        stocks = [{'name': '한미반도체', 'code': '042700'}]
        r = build_supply_chain_watch(build_events([article]), stocks, as_of=NOW,
                                     order_evidence={'schema_version': 1, 'orders': [self.order]})
        path = r['paths'][0]
        self.assertTrue(path['order_review']['documented_order_confirmed'])
        self.assertFalse(path['new_order_confirmed'])
        self.assertFalse(path['recommendation_eligible'])
        self.assertEqual(path['score_effect'], 0)
        messages = []
        with patch('telegram_bot.send_message', side_effect=messages.append), patch('telegram_bot.time.sleep'):
            send_telegram([], {'saved_days': 0, 'saved_themes': 0, 'supply_chain_watch': r})
        text = ''.join(messages)
        self.assertIn('이 미국 사건과의 인과·매출 인식은 미확정', text)
        self.assertIn('개별 주문 근거', text)
        self.assertNotIn('💎 S+', text)


if __name__ == '__main__':
    unittest.main()
