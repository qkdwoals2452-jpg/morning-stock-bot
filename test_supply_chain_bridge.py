from copy import deepcopy
import contextlib
from datetime import datetime
import io
import importlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from event_engine import build_events
from event_understanding_engine import understand_event
from impact_engine import assess_company_event_relation
from stock_engine import find_direct_mentions
from supply_chain_engine import build_supply_chain_watch, load_supply_chain_evidence
from telegram_bot import send_telegram

NOW = datetime.fromisoformat('2026-10-14T08:00:00+09:00')
STOCKS = [{'name': '한미반도체', 'code': '042700'}, {'name': 'SK하이닉스', 'code': '000660'},
          {'name': '원익', 'code': '032940', 'grade': 'S+', 'rank': 1}]


def article(title='Micron will invest $7 billion in HBM advanced packaging factory', **kwargs):
    return {'title': title, 'summary': '', 'source': 'fixture', 'market': 'US',
            'published_at': '2026-10-14T07:30:00+09:00',
            'link': 'https://example.test/us-event', **kwargs}


class SupplyChainBridgeTests(unittest.TestCase):
    def setUp(self):
        self.book = deepcopy(load_supply_chain_evidence())

    def report(self, a=None, stocks=None, book=None, now=NOW):
        a = a or article()
        return build_supply_chain_watch(build_events([a]), STOCKS if stocks is None else stocks,
                                        self.book if book is None else book, now)

    def test_micron_path_without_korean_name_in_us_news(self):
        result = self.report()
        self.assertEqual([p['path'] for p in result['paths']], [['Micron', '한미반도체']])
        p = result['paths'][0]
        self.assertEqual(p['code'], '042700')
        self.assertEqual(p['knowledge_timing'], 'known_before_event')
        self.assertFalse(p['new_order_confirmed'])
        self.assertFalse(p['revenue_attribution_confirmed'])
        self.assertFalse(p['profit_effect_confirmed'])
        self.assertEqual(p['evidence'][0]['relationship'], 'REPORTED_CUSTOMER')

    def test_nvidia_to_hynix_to_hanmi_has_two_distinct_proofs(self):
        r = self.report(article('NVIDIA will invest $8 billion in HBM memory AI factory'))
        p = next(p for p in r['paths'] if p['code'] == '042700')
        self.assertEqual(p['path'], ['NVIDIA', 'SK하이닉스', '한미반도체'])
        self.assertEqual(len(p['evidence']), 2)
        self.assertNotEqual(p['evidence'][0]['source_url'], p['evidence'][1]['source_url'])
        self.assertFalse(p['recommendation_eligible'])

    def test_watch_does_not_open_direct_recommendation_gate(self):
        a = article()
        self.assertFalse(assess_company_event_relation(STOCKS[0], [a])['pass'])
        self.assertEqual(find_direct_mentions({'articles': [a]}, STOCKS, [a]), {})
        self.assertEqual(self.report(a)['score_effect'], 0)

    def test_books_stocks_and_events_are_not_mutated(self):
        events = build_events([article()])
        before = deepcopy((events, STOCKS, self.book))
        r = build_supply_chain_watch(events, STOCKS, self.book, NOW)
        r['paths'][0]['evidence'][0]['evidence_summary'] = 'changed output'
        self.assertEqual((events, STOCKS, self.book), before)

    def test_future_review_not_usable_at_past_assessment(self):
        r = self.report(article(published_at='2026-10-13T07:30:00+09:00'),
                        now=datetime.fromisoformat('2026-10-13T08:00:00+09:00'))
        self.assertFalse(r['paths'])
        self.assertEqual(r['excluded']['unavailable_at_assessment'], 3)

    def test_later_review_is_explicitly_retrospective_not_historical_signal(self):
        r = self.report(article(published_at='2026-09-30T20:00:00+00:00'))
        self.assertEqual(r['paths'][0]['knowledge_timing'], 'retrospective_review')
        self.assertFalse(r['paths'][0]['recommendation_eligible'])

    def test_source_published_after_event_does_not_establish_then_relation(self):
        r = self.report(article(published_at='2026-05-14T08:00:00+09:00'))
        self.assertFalse(r['paths'])
        self.assertIn('source_published_after_event', r['excluded'])

    def test_date_only_publication_not_assumed_known_at_day_start(self):
        r = self.report(article(published_at='2026-05-15T08:00:00+09:00'))
        self.assertFalse(r['paths'])

    def test_missing_naive_and_future_event_times_rejected(self):
        for stamp in ('', '2026-10-14', '2026-10-14T07:30:00', '2026-10-15T07:30:00+09:00'):
            with self.subTest(stamp=stamp):
                self.assertFalse(self.report(article(published_at=stamp))['paths'])

    def test_missing_link_rejected(self):
        self.assertFalse(self.report(article(link=''))['paths'])

    def test_non_us_article_not_a_us_spending_trigger(self):
        self.assertFalse(self.report(article(market='KR'))['paths'])

    def test_unknown_supplier_not_added_without_krx_membership(self):
        self.assertFalse(self.report(stocks=[])['paths'])
        self.assertFalse(self.report(stocks=[{'name': '다른회사', 'code': '042700'}])['paths'])

    def test_substring_hana_micron_not_us_micron_actor(self):
        self.assertFalse(self.report(article('Hana Micron will invest $7 billion in HBM factory'))['paths'])
        self.assertFalse(self.report(article('Micronics will invest $7 billion in HBM factory'))['paths'])

    def test_named_commentator_or_different_actor_not_spending_trigger(self):
        for title in ('Micron says NVIDIA will invest $7 billion in HBM memory factory',
                      'Micron, NVIDIA will invest $7 billion in HBM memory factory'):
            with self.subTest(title=title):
                self.assertFalse(self.report(article(title))['paths'])

    def test_no_connection_from_separate_product_sentence(self):
        a = article('Micron will invest $7 billion in a new factory',
                    summary='NVIDIA uses HBM memory in a different product.')
        self.assertFalse(self.report(a)['paths'])

    def test_unknown_customer_or_wrong_domain_does_not_infer_supplier(self):
        self.assertFalse(self.report(article('Amazon will invest $7 billion in HBM memory factory'))['paths'])
        self.assertFalse(self.report(article('Micron will invest $7 billion in a new office'))['paths'])

    def test_rumors_denials_and_stock_recommendations_not_money_flow(self):
        for title in ('Micron could invest $7 billion in HBM factory',
                      'Micron will not invest $7 billion in HBM factory',
                      'Why investors should buy Micron on HBM factory investment'):
            with self.subTest(title=title):
                self.assertFalse(self.report(article(title))['paths'])

    def test_research_lab_not_a_manufacturing_equipment_order(self):
        self.assertFalse(self.report(article('Micron will invest $10 billion in memory research labs'))['paths'])

    def test_future_source_date_and_missing_proof_rejected(self):
        for field, value in [('published_on', '2026-10-15'), ('reviewed_at', ''),
                             ('reviewed_at', '2026-10-14T07:04:59'),
                             ('evidence_summary', ''), ('section', ''), ('id', ''),
                             ('review_method', 'news_keyword_guess'), ('relationship_as_of', '2026-12-31')]:
            with self.subTest(field=field):
                self.book = deepcopy(load_supply_chain_evidence())
                self.book['edges'][0][field] = value
                self.assertFalse(self.report()['paths'])

    def test_unapproved_or_spoofed_source_not_proof(self):
        for url in ('https://kind.krx.co.kr.evil.test/filing', 'https://news.test/filing',
                    'http://kind.krx.co.kr/filing', 'https://user@kind.krx.co.kr/filing'):
            with self.subTest(url=url):
                self.book['edges'][0]['source_url'] = url
                self.assertFalse(self.report()['paths'])

    def test_stale_document_requires_review_of_new_source(self):
        self.book['edges'][0]['published_on'] = '2024-05-15'
        self.book['edges'][0]['relationship_as_of'] = '2024-03-31'
        r = self.report()
        self.assertFalse(r['paths'])
        self.assertIn('stale_source', r['excluded'])

    def test_cycle_does_not_create_self_path_or_infinite_walk(self):
        reverse = deepcopy(self.book['edges'][0])
        reverse.update(id='reverse_fixture', buyer='hanmi', supplier='micron')
        self.book['edges'].append(reverse)
        self.assertEqual(len(self.report()['paths']), 1)

    def test_repeated_event_evidence_not_multiple_votes(self):
        events = build_events([article()])
        r = build_supply_chain_watch(events + deepcopy(events), STOCKS, self.book, NOW)
        self.assertEqual(len(r['paths']), 1)

    def test_empty_or_corrupt_book_is_explicitly_unavailable(self):
        for book in ({}, {'schema_version': 1, 'entities': [], 'edges': []},
                     {'schema_version': 1, 'entities': {}, 'edges': 'invalid'}):
            self.assertEqual(self.report(book=book)['status'], 'evidence_unavailable')

    def test_malformed_edge_does_not_crash_or_create_a_path(self):
        for field in ('buyer', 'supplier', 'relationship', 'source_kind'):
            with self.subTest(field=field):
                self.book = deepcopy(load_supply_chain_evidence())
                self.book['edges'][0][field] = []
                self.assertFalse(self.report()['paths'])

    def test_low_scored_event_not_watch_candidate(self):
        events = build_events([article()])
        events[0]['event_score'] = 60
        self.assertFalse(build_supply_chain_watch(events, STOCKS, self.book, NOW)['paths'])

    def test_official_spelled_quarter_earnings_with_actual_capex_is_observation(self):
        # 원제만 재현. 요약은 테스트용 짧은 바꿔쓰기이며 원문 전체가 아니다.
        a = article('Micron Technology, Inc. Reports Record Fiscal Fourth-Quarter and Full-Year 2026 Results',
                    summary='Capital expenditures were $27.37 billion in 2026. Memory spending disclosure.',
                    link='https://investors.micron.com/news/press-release/2026/fixture',
                    published_at='2026-09-30T20:00:00+00:00')
        self.assertTrue(understand_event(a)['is_real_event'])
        self.assertEqual(understand_event(a)['event_type'], 'EARNINGS')
        self.assertEqual(self.report(a)['paths'][0]['path'], ['Micron', '한미반도체'])
        self.assertEqual(self.report(a)['paths'][0]['spending_scope'], 'companywide_not_supplier_allocation')

    def test_future_earnings_release_not_actual_completed_result(self):
        a = article('Micron will report record fiscal fourth-quarter 2026 results', summary='HBM memory outlook')
        self.assertFalse(self.report(a)['paths'])

    def test_earnings_cannot_borrow_another_company_spending(self):
        a = article('Micron Reports Record Fiscal Fourth-Quarter 2026 Results',
                    summary='NVIDIA will invest $7 billion in HBM memory factory.')
        self.assertFalse(self.report(a)['paths'])

    def test_telegram_watch_is_separate_from_recommendations_and_has_source_links(self):
        r = self.report(article(published_at='2026-09-30T20:00:00+00:00'))
        messages = []
        with patch('telegram_bot.send_message', side_effect=messages.append), patch('telegram_bot.time.sleep'):
            send_telegram([], {'saved_days': 0, 'saved_themes': 0, 'supply_chain_watch': r})
        text = ''.join(messages)
        self.assertIn('추천·신규 수주 확정 아님', text)
        self.assertIn('관계 근거', text)
        self.assertIn('당시 탐지 실적이 아닙니다', text)
        self.assertNotIn('💎 S+', text)
        self.assertTrue(all(len(m) <= 3500 for m in messages))

    def test_existing_wonik_direct_gate_and_reference_metadata_preserved(self):
        a = article('원익, 100억원 반도체 장비 공급계약 체결', market='KR')
        self.assertTrue(assess_company_event_relation(STOCKS[2], [a])['pass'])
        self.report(a)
        self.assertEqual((STOCKS[2]['grade'], STOCKS[2]['rank']), ('S+', 1))

    def test_main_sends_watch_metadata_without_recommending_unattributed_supplier(self):
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            os.chdir(directory)
            try:
                Path('corp_code.csv').write_text('stock_code,corp_code\n042700,00126380\n')
                for name in ('main', 'finance_engine', 'quality_engine'):
                    sys.modules.pop(name, None)
                main = importlib.import_module('main')
                finance = importlib.import_module('finance_engine')
                with contextlib.ExitStack() as stack:
                    stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                    stack.enter_context(patch.object(main, 'load_korean_stocks', return_value=STOCKS))
                    stack.enter_context(patch.object(main, 'get_us_news', return_value=[article()]))
                    stack.enter_context(patch.object(main, 'get_korea_news', return_value=[]))
                    stack.enter_context(patch.object(main, 'build_supply_chain_watch',
                        side_effect=lambda events, stocks: build_supply_chain_watch(events, stocks, self.book, NOW)))
                    stack.enter_context(patch.object(main, 'update_backtest_prices'))
                    saved = stack.enter_context(patch.object(main, 'save_recommendations'))
                    stack.enter_context(patch.object(main, 'save_today_result'))
                    prediction = stack.enter_context(patch.object(main, 'save_prediction'))
                    stack.enter_context(patch.object(main, 'get_project_status', return_value={'saved_days': 0, 'saved_themes': 0}))
                    sender = stack.enter_context(patch.object(main, 'send_telegram'))
                    finance_call = stack.enter_context(patch.object(finance, 'get_finance_score'))
                    main.run()
                results, status = sender.call_args.args
                self.assertEqual(results, [])
                saved.assert_called_once_with([])
                prediction.assert_not_called()
                finance_call.assert_not_called()
                self.assertEqual(status['supply_chain_watch']['paths'][0]['code'], '042700')
                self.assertEqual(status['supply_chain_watch']['score_effect'], 0)
            finally:
                os.chdir(previous)
                for name in ('main', 'finance_engine', 'quality_engine'):
                    sys.modules.pop(name, None)
