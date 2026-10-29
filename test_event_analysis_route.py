import contextlib
import importlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from event_engine import build_events
from theme_engine import build_event_analysis_themes, extract_themes
from stock_engine import select_analysis_themes, build_analysis_routes


ARTICLE = {'title': '포스코DX, AI 기업 인핸스에 20억 투자',
           'summary': '', 'market': 'KR', 'source': 'fixture'}
MEDICAL_ARTICLE = {
    'title': '포인터스PE, 리메드에 150억원 투자…"글로벌 뉴로테크 성장 기회"',
    'summary': '', 'market': 'KR', 'source': 'fixture'}
MEDICAL_STOCK = {'name': '리메드', 'code': '302550',
                 'sector': '의료용 기기 제조업'}
DISPLAY_ARTICLE = {
    'title': 'LG디스플레이 3분기, 전기比 흑자전환…영업이익 2506억원',
    'summary': '', 'market': 'KR', 'source': 'fixture'}
DISPLAY_STOCK = {'name': 'LG디스플레이', 'code': '034220',
                 'sector': '전자부품 제조업'}


class EventAnalysisRouteTests(unittest.TestCase):
    def test_unclassified_domestic_actor_routes_with_own_event_score(self):
        events = build_events([dict(DISPLAY_ARTICLE)])
        themes = build_event_analysis_themes(events)
        self.assertEqual(themes, [])
        routes = build_analysis_routes(events, themes, [DISPLAY_STOCK], [], 3)
        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0]['candidate_codes'], ['034220'])
        self.assertEqual(routes[0]['event_score'], events[0]['event_score'])
        self.assertEqual(routes[0]['articles'], events[0]['articles'])
        self.assertEqual(routes[0]['frequency_score'], 0)

    def test_direct_route_requires_actor_not_just_company_mention(self):
        for title in ['LG디스플레이 주가 상승 기대, 실적 개선 전망',
                      '과거 LG디스플레이 실적과 관련한 투자자 관심',
                      '경쟁사, 150억원 투자…LG디스플레이 수혜주 관심']:
            with self.subTest(title=title):
                events = [{'event_score': 80, 'articles': [{'title': title}]}]
                self.assertEqual(build_analysis_routes(events, [], [DISPLAY_STOCK], [], 3), [])

    def test_direct_route_not_lost_at_theme_limit_and_no_cross_event_articles(self):
        other = {'name': '검증기업', 'code': '123456', 'sector': '제조업'}
        events = build_events([dict(DISPLAY_ARTICLE), {
            'title': '검증기업, 신규 공장에 150억원 투자', 'market': 'KR'}])
        themes = [{'name': 'AI', 'score': 90, 'articles': [{'title': 'OpenAI AI 투자'}]}]
        routes = build_analysis_routes(events, themes, [DISPLAY_STOCK, other], [], 1)
        direct = [route for route in routes if route.get('analysis_route') == 'DIRECT_EVENT']
        self.assertEqual(len(direct), 2)
        self.assertEqual({tuple(route['candidate_codes']) for route in direct},
                         {('034220',), ('123456',)})
        for route in direct:
            self.assertEqual(len(route['articles']), 1)
        self.assertEqual(len(build_analysis_routes(events + events, [], [DISPLAY_STOCK, other], [], 1)), 2)

    def test_existing_supported_route_not_duplicated(self):
        events = build_events([dict(ARTICLE)])
        themes = build_event_analysis_themes(events)
        stock = {'name': '포스코DX', 'code': '022100', 'sector': '소프트웨어'}
        self.assertEqual(build_analysis_routes(events, themes, [stock], [], 3), themes)

    def test_direct_verification_requires_listed_identity_and_sector(self):
        from company_verify_engine import verify_direct_company_event
        self.assertTrue(verify_direct_company_event(DISPLAY_STOCK, [DISPLAY_ARTICLE])['pass'])
        self.assertEqual(verify_direct_company_event(DISPLAY_STOCK, [DISPLAY_ARTICLE])['score'], 0)
        for stock in (dict(DISPLAY_STOCK, code=''), dict(DISPLAY_STOCK, sector=''),
                      dict(DISPLAY_STOCK, name='무관기업')):
            self.assertFalse(verify_direct_company_event(stock, [DISPLAY_ARTICLE])['pass'])

    def test_actual_neurotech_event_retains_article_and_direct_candidate(self):
        from stock_engine import find_related_stocks
        events = build_events([dict(MEDICAL_ARTICLE)])
        themes = build_event_analysis_themes(events)
        self.assertEqual([theme['name'] for theme in themes], ['의료기기'])
        self.assertEqual(themes[0]['articles'], events[0]['articles'])
        self.assertEqual(themes[0]['articles'][0]['title'], MEDICAL_ARTICLE['title'])
        self.assertEqual(themes[0]['event_score'], events[0]['event_score'])
        candidates = find_related_stocks(themes[0], [MEDICAL_STOCK], [])
        self.assertEqual([stock['code'] for stock in candidates], ['302550'])

    def test_medical_route_still_requires_business_evidence(self):
        from company_verify_engine import verify_company_theme
        with patch('company_verify_engine.search_company_text', return_value=''):
            self.assertFalse(verify_company_theme(MEDICAL_STOCK, '의료기기')['pass'])
        with patch('company_verify_engine.search_company_text', return_value=
                   '의료기기 의료용 기기 뉴로테크 신경조절 자기자극 재활기기'):
            self.assertTrue(verify_company_theme(MEDICAL_STOCK, '의료기기')['pass'])

    def test_missing_domain_is_logged_without_inventing_theme(self):
        event = {'event_score': 80, 'event_key': 'unknown_domain',
                 'event_title': '검증회사, 150억원 투자 유치',
                 'articles': [{'title': '검증회사, 150억원 투자 유치'}]}
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(build_event_analysis_themes([event]), [])
        self.assertIn('사건 분석 경로 없음:', output.getvalue())
        self.assertIn('unknown_domain', output.getvalue())

    def test_direct_candidate_survives_top_three_without_borrowing_articles(self):
        themes = [{'name': name, 'articles': [{'title': title}], 'score': score}
                  for name, title, score in [('AI', 'OpenAI AI investment', 80),
                    ('우주항공', 'SpaceX rocket profit', 70), ('자율주행', 'Tesla profit', 70),
                    ('바이오', '검증제약, 치료제 공급계약 체결', 70)]]
        selected = select_analysis_themes(themes, [{'name': '검증제약', 'code': '123456'}], [], 3)
        self.assertEqual([t['name'] for t in selected], ['바이오', 'AI', '우주항공'])
        self.assertEqual(selected[0], themes[3])
        self.assertEqual(select_analysis_themes(themes, [], [], 3), themes[:3])

    def test_biopharma_contract_has_explicit_analysis_route(self):
        article = {'title': '삼성바이오에피스, 브라질 정부와 희귀질환 치료제 단독 공급계약',
                   'summary': '', 'market': 'KR'}
        themes = build_event_analysis_themes([
            {'event_score': 80, 'articles': [article]}])
        self.assertEqual([theme['name'] for theme in themes], ['바이오'])
        self.assertEqual(themes[0]['articles'], [article])

    def test_strong_event_uses_its_score_and_explicit_theme(self):
        event = {'event_score': 80, 'event_key': '포스코DX_CAPEX', 'articles': [ARTICLE]}
        themes = build_event_analysis_themes([event], extract_themes([ARTICLE]))
        self.assertEqual([t['name'] for t in themes], ['AI'])
        self.assertEqual(themes[0]['score'], 80)
        self.assertEqual(themes[0]['event_score'], 80)
        self.assertEqual(themes[0]['frequency_score'], 6)
        self.assertEqual(themes[0]['articles'], [ARTICLE])

    def test_weak_event_cannot_borrow_another_events_score(self):
        weak = {'event_score': 60, 'articles': [ARTICLE]}
        strong = {'event_score': 80, 'articles': [
            {'title': '신한울 원전에 구동기 공급계약 체결'}]}
        themes = build_event_analysis_themes([weak, strong])
        self.assertEqual([t['name'] for t in themes], ['원전'])
        self.assertNotIn(ARTICLE, themes[0]['articles'])

    def test_no_explicit_theme_does_not_invent_one(self):
        event = {'event_score': 80, 'articles': [{'title': 'A사, B사 인수 확정'}]}
        self.assertEqual(build_event_analysis_themes([event]), [])

    def test_ai_is_not_inferred_from_taiwan_substring(self):
        event = {'event_score': 80, 'articles': [{'title': 'Taiwan 업체, 신규 공장 투자 확정'}]}
        self.assertEqual(build_event_analysis_themes([event]), [])

    def run_route(self, verify_pass=True, market_value=4000000000, missing_finance=False, missing_chart=False, connection_pass=True, below_ma120=False, missing_trend=False, article=None, stock=None, breaking=False):
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            os.chdir(directory)
            try:
                Path('corp_code.csv').write_text('stock_code,corp_code\n022100,00126380\n')
                for name in ('main', 'finance_engine', 'quality_engine'):
                    sys.modules.pop(name, None)
                main = importlib.import_module('main')
                finance_module = importlib.import_module('finance_engine')
                finance = Mock(return_value={'score': 10, 'exclude': False,
                                            'op_margin': None if missing_finance else 8,
                                            'debt_ratio': 50})
                saved = Mock()
                calls = dict(
                    load_korean_stocks=Mock(return_value=[stock or {'name': '포스코DX', 'code': '022100', 'sector': '소프트웨어'}]),
                    get_us_news=Mock(return_value=[]), get_korea_news=Mock(return_value=[dict(article or ARTICLE)]),
                    update_backtest_prices=Mock(), save_today_result=Mock(), save_recommendations=Mock(),
                    get_project_status=Mock(return_value={}), send_telegram=saved, save_prediction=Mock(),
                    verify_company_theme=Mock(return_value={'pass': verify_pass, 'score': 60, 'memo': '검증 결과'}),
                    get_market_score=Mock(return_value={'score': 0, 'trading_value': market_value}),
                    get_chart_score=Mock(return_value={'score': 0, 'details': {
                        'high_52w_gap': None if missing_chart else -10, 'current': 100,
                        'ma120': None if missing_trend else 120 if below_ma120 else 90}}),
                    get_learning_score=Mock(return_value={'score': 0}),
                    get_company_match_score=Mock(return_value={'score': 40, 'exclude': False}),
                    get_news_impact_score=Mock(return_value={'score': 70, 'exclude': False}),
                    pass_theme_sector_filter=Mock(return_value=(True, '')),
                )
                if not connection_pass:
                    calls['assess_company_event_relation'] = Mock(return_value={
                        'pass': False, 'reason': '사건 당사자 관계 미확인'})
                with patch.multiple(main, **calls), patch.object(finance_module, 'get_finance_score', finance), contextlib.redirect_stdout(io.StringIO()):
                    if breaking:
                        results, status = main.run(news_override=[dict(article or ARTICLE)],
                                                   notify=False, track_history=False)
                        for name in ('get_us_news', 'get_korea_news', 'update_backtest_prices',
                                     'save_today_result', 'save_recommendations', 'save_prediction',
                                     'send_telegram'):
                            calls[name].assert_not_called()
                        self.last_analysis_status = status['analysis_status']
                        return finance.call_count, results
                    main.run()
                self.last_analysis_status = saved.call_args.args[1]['analysis_status']
                return finance.call_count, saved.call_args.args[0]
            finally:
                os.chdir(previous)
                for name in ('main', 'finance_engine', 'quality_engine'):
                    sys.modules.pop(name, None)

    def test_actual_medical_candidate_reaches_finance_and_preserves_gates(self):
        calls, results = self.run_route(article=MEDICAL_ARTICLE, stock=MEDICAL_STOCK)
        self.assertEqual(calls, 1)
        self.assertEqual(results[0]['theme']['name'], '의료기기')
        self.assertEqual(results[0]['ranked'][0]['code'], '302550')
        for failures in ({'verify_pass': False}, {'connection_pass': False},
                         {'missing_finance': True}, {'below_ma120': True},
                         {'missing_chart': True}, {'market_value': None}):
            with self.subTest(failures=failures):
                _, results = self.run_route(article=MEDICAL_ARTICLE,
                                            stock=MEDICAL_STOCK, **failures)
                self.assertEqual(results, [])

    def test_breaking_followup_reuses_finance_and_price_gates_without_daily_writes(self):
        calls, results = self.run_route(article=DISPLAY_ARTICLE, stock=DISPLAY_STOCK, breaking=True)
        self.assertEqual(calls, 1)
        self.assertEqual(results[0]['ranked'][0]['code'], '034220')
        _, results = self.run_route(article=DISPLAY_ARTICLE, stock=DISPLAY_STOCK,
                                    breaking=True, below_ma120=True)
        self.assertEqual(results, [])
        self.assertIn('120일선 아래', self.last_analysis_status['excluded'][0]['reason'])

    def test_unclassified_lg_display_runs_finance_and_retains_safety_gates(self):
        calls, results = self.run_route(article=DISPLAY_ARTICLE, stock=DISPLAY_STOCK)
        self.assertEqual(calls, 1)
        self.assertEqual(results[0]['theme']['analysis_route'], 'DIRECT_EVENT')
        self.assertEqual(results[0]['ranked'][0]['code'], '034220')
        self.assertEqual(results[0]['ranked'][0]['company']['score'], 0)
        self.assertEqual(results[0]['ranked'][0]['verify']['score'], 0)
        for failures in ({'connection_pass': False}, {'missing_finance': True},
                         {'below_ma120': True}, {'missing_chart': True},
                         {'market_value': None}):
            with self.subTest(failures=failures):
                _, results = self.run_route(article=DISPLAY_ARTICLE,
                                            stock=DISPLAY_STOCK, **failures)
                self.assertEqual(results, [])
        calls, results = self.run_route(article=DISPLAY_ARTICLE,
                                       stock=dict(DISPLAY_STOCK, sector=''))
        self.assertEqual(calls, 0)
        self.assertEqual(results, [])

    def test_telegram_status_uses_actual_candidate_decision(self):
        cases = [({'below_ma120': True}, 'chart', '120일선 아래'),
                 ({'missing_finance': True}, 'finance', '핵심 재무 데이터 확인불가'),
                 ({'connection_pass': False}, 'connection', '사건 당사자 관계 미확인'),
                 ({'missing_chart': True}, 'chart', '52주 고점 대비 낙폭 확인불가'),
                 ({'market_value': None}, 'market', '거래대금 확인불가')]
        for failures, stage, reason in cases:
            with self.subTest(failures=failures):
                self.run_route(article=DISPLAY_ARTICLE, stock=DISPLAY_STOCK, **failures)
                status = self.last_analysis_status
                self.assertEqual(status['analyzed_count'], 1)
                self.assertEqual(status['selected_count'], 0)
                self.assertEqual([{k:v for k,v in item.items() if k != 'evidence'} for item in status['excluded']], [dict(
                    name='LG디스플레이', code='034220', stage=stage, reason=reason)])
                if stage == 'chart':
                    self.assertEqual(status['excluded'][0]['evidence']['current'], 100)
                    self.assertEqual(status['excluded'][0]['evidence']['ma120'], 120 if failures.get('below_ma120') else 90)
        self.run_route(article=DISPLAY_ARTICLE, stock=DISPLAY_STOCK)
        self.assertEqual(self.last_analysis_status['selected_count'], 1)
        self.assertEqual(self.last_analysis_status['excluded'], [])

    def test_strong_candidate_reaches_finance_even_with_frequency_six(self):
        calls, results = self.run_route()
        self.assertEqual(calls, 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['theme']['event_score'], 80)
        self.assertEqual(results[0]['ranked'][0]['event_score'], 80)
        self.assertEqual(results[0]['ranked'][0]['theme_score'], 6)
        self.assertEqual(results[0]['ranked'][0]['pre_news_activity']['status'], 'missing_news_timestamp')
        self.assertEqual(results[0]['ranked'][0]['pre_news_activity']['score_effect'], 0)
        self.assertIn('사건 신호 80점', results[0]['ranked'][0]['reason'])
        self.assertNotIn('미국뉴스 키워드 감지', results[0]['ranked'][0]['reason'])

    def test_business_rejection_still_blocks_recommendation(self):
        calls, results = self.run_route(verify_pass=False)
        self.assertEqual(calls, 0)
        self.assertEqual(results, [])

    def test_below_ma120_blocked_even_with_strong_event(self):
        calls, results = self.run_route(below_ma120=True)
        self.assertEqual(calls, 1)
        self.assertEqual(results, [])

    def test_missing_ma120_not_assumed_to_pass(self):
        calls, results = self.run_route(missing_trend=True)
        self.assertEqual(calls, 1)
        self.assertEqual(results, [])

    def test_unverified_connection_blocks_before_finance_even_if_impact_mock_passes(self):
        calls, results = self.run_route(connection_pass=False)
        self.assertEqual(calls, 0)
        self.assertEqual(results, [])

    def test_missing_market_data_blocks_recommendation(self):
        calls, results = self.run_route(market_value=None)
        self.assertEqual(calls, 1)
        self.assertEqual(results, [])

    def test_missing_finance_data_blocks_recommendation(self):
        calls, results = self.run_route(missing_finance=True)
        self.assertEqual(calls, 1)
        self.assertEqual(results, [])

    def test_missing_chart_data_blocks_recommendation(self):
        calls, results = self.run_route(missing_chart=True)
        self.assertEqual(calls, 1)
        self.assertEqual(results, [])


if __name__ == '__main__':
    unittest.main()
