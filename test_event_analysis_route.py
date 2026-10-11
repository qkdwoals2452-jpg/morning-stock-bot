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


ARTICLE = {'title': '포스코DX, AI 기업 인핸스에 20억 투자',
           'summary': '', 'market': 'KR', 'source': 'fixture'}


class EventAnalysisRouteTests(unittest.TestCase):
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

    def run_route(self, verify_pass=True, market_value=4000000000, missing_finance=False, missing_chart=False):
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
                    load_korean_stocks=Mock(return_value=[{'name': '포스코DX', 'code': '022100', 'sector': '소프트웨어'}]),
                    get_us_news=Mock(return_value=[]), get_korea_news=Mock(return_value=[dict(ARTICLE)]),
                    update_backtest_prices=Mock(), save_today_result=Mock(), save_recommendations=Mock(),
                    get_project_status=Mock(return_value={}), send_telegram=saved, save_prediction=Mock(),
                    verify_company_theme=Mock(return_value={'pass': verify_pass, 'score': 60, 'memo': '검증 결과'}),
                    get_market_score=Mock(return_value={'score': 0, 'trading_value': market_value}),
                    get_chart_score=Mock(return_value={'score': 0, 'details': {'high_52w_gap': None if missing_chart else -10}}),
                    get_learning_score=Mock(return_value={'score': 0}),
                    get_company_match_score=Mock(return_value={'score': 40, 'exclude': False}),
                    get_news_impact_score=Mock(return_value={'score': 70, 'exclude': False}),
                    pass_theme_sector_filter=Mock(return_value=(True, '')),
                )
                with patch.multiple(main, **calls), patch.object(finance_module, 'get_finance_score', finance), contextlib.redirect_stdout(io.StringIO()):
                    main.run()
                return finance.call_count, saved.call_args.args[0]
            finally:
                os.chdir(previous)
                for name in ('main', 'finance_engine', 'quality_engine'):
                    sys.modules.pop(name, None)

    def test_strong_candidate_reaches_finance_even_with_frequency_six(self):
        calls, results = self.run_route()
        self.assertEqual(calls, 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['theme']['event_score'], 80)
        self.assertEqual(results[0]['ranked'][0]['event_score'], 80)
        self.assertIn('사건 신호 80점', results[0]['ranked'][0]['reason'])
        self.assertNotIn('미국뉴스 키워드 감지', results[0]['ranked'][0]['reason'])

    def test_business_rejection_still_blocks_recommendation(self):
        calls, results = self.run_route(verify_pass=False)
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
