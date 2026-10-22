from copy import deepcopy
import contextlib
from datetime import datetime, timezone
import io
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest
from unittest.mock import patch, Mock

import backtest_engine as backtest
import memory_engine as memory
from chart_engine import pass_long_term_trend
from scoring_engine import make_final_score, make_grade, make_stock_result, SCORE_VERSION
from telegram_bot import send_telegram, send_message

ROOT = Path(__file__).resolve().parent


class TelegramAnalysisStatusTests(unittest.TestCase):
    def render(self, analyzed=1, excluded=None, selected=0):
        messages = []
        status = {'saved_days': 10, 'saved_themes': 1, 'analysis_status': {
            'news_count': 380, 'strong_event_count': 7, 'analyzed_count': analyzed,
            'selected_count': selected, 'excluded': excluded or []}}
        with patch('telegram_bot.send_message', side_effect=messages.append), patch('telegram_bot.time.sleep'):
            send_telegram([], status)
        return '\n'.join(messages)

    def test_empty_recommendation_includes_real_rejection_and_escapes_html(self):
        item = {'code': '034220', 'name': 'LG<디스플레이>', 'reason': '120일선 아래'}
        text = self.render(excluded=[item, item])
        self.assertIn('분석 종목 1개 / 최종 검증 후보 0개', text)
        self.assertIn('LG&lt;디스플레이&gt;', text)
        self.assertEqual(text.count('120일선 아래'), 1)
        self.assertNotIn('이번 실행에서는 국내 직접 분석 후보가 연결되지 않았습니다.', text)

    def test_no_candidate_and_no_final_selection_are_distinct(self):
        self.assertIn('국내 직접 분석 후보가 연결되지 않았습니다.', self.render(analyzed=0))
        self.assertIn('최종 검증 기준을 통과한 종목이 없습니다.', self.render())
        self.assertNotIn('통과한 종목이 없습니다.', self.render(selected=1))

    def test_telegram_acknowledgement_required(self):
        with patch('telegram_bot.requests.post', return_value=Mock(
                status_code=200, json=lambda: {'ok': True, 'result': {'message_id': 123}})):
            send_message('fixture')
        for response in (Mock(status_code=500), Mock(status_code=200, json=lambda: {'ok': False})):
            with patch('telegram_bot.requests.post', return_value=response), self.assertRaises(RuntimeError):
                send_message('fixture')

    def test_send_error_does_not_expose_request_secrets(self):
        with patch('telegram_bot.requests.post', side_effect=RuntimeError('SECRET_TOKEN')):
            with self.assertRaises(RuntimeError) as caught:
                send_message('fixture')
        self.assertNotIn('SECRET_TOKEN', str(caught.exception))


def result(learning=None):
    with contextlib.redirect_stdout(io.StringIO()):
        return make_stock_result({'name': '포스코DX', 'code': '022100', 'relation_score': 100},
            theme_score=6, finance={'score': 12}, market={'score': -3}, verify={'score': 60},
            company={'score': 105}, chart={'score': -16}, learning=learning,
            impact={'score': 70}, event_score=80)


def blocks(code='022100', name='포스코DX', theme='AI'):
    return [{'theme': {'name': theme, 'score': 80, 'reason': 'fixture', 'articles': []},
             'ranked': [{'name': name, 'code': code, 'final_score': 33, 'grade': '🧪 검증중', 'reason': []}]}]


class ScoreRevisionTests(unittest.TestCase):
    def test_original_posco_309_inputs_become_33_ungraded_ranking_points(self):
        r = result()
        self.assertEqual(r['final_score'], 33)
        self.assertEqual(r['score_breakdown'], {'finance': 12, 'market': -3, 'business': 40,
                                               'chart': -16, 'learning': 0})
        self.assertEqual(sum(r['score_breakdown'].values()), r['final_score'])
        self.assertEqual(r['grade'], '🧪 검증중')
        self.assertEqual(r['score_version'], SCORE_VERSION)
        self.assertEqual(r['event_score'], 80)

    def test_mentions_event_relation_and_frequency_cannot_inflate_score(self):
        a = make_final_score(0, 0, 12, -3, 60, 105, -16, 0, 0)
        b = make_final_score(999999, 999999, 12, -3, 60, 105, -16, 0, 999999)
        self.assertEqual(a, b)

    def test_business_verifications_use_one_component_not_two(self):
        self.assertEqual(make_final_score(0, 0, 0, 0, verify_score=100, company_score=100), 40)

    def test_no_splus_even_for_arbitrarily_high_raw_score(self):
        for score in (-100, 33, 95, 100, 309, 999999):
            self.assertEqual(make_grade(score), '🧪 검증중')

    def test_invalid_numeric_scores_cannot_become_nan_or_infinity(self):
        for value in (True, None, 'invalid', float('nan'), float('inf')):
            self.assertTrue(math.isfinite(make_final_score(1, 1, value, 0)))

    def test_unverified_learning_bonus_not_added(self):
        for learning in ({'score': 20}, {'score': 20, 'sample_count': 1},
                         {'score': 20, 'sample_count': 5, 'source': 'unknown'}):
            self.assertEqual(result(learning)['final_score'], 33)
        self.assertEqual(result({'score': 20, 'sample_count': 5,
                                'source': 'completed_trading_checkpoints'})['final_score'], 53)

    def test_trend_gate_cannot_be_offset_by_score(self):
        self.assertFalse(pass_long_term_trend({'details': {'current': 100, 'ma120': 110}})[0])
        self.assertTrue(pass_long_term_trend({'details': {'current': 110, 'ma120': 110}})[0])
        self.assertTrue(pass_long_term_trend({'details': {'current': 120, 'ma120': 110}})[0])

    def test_missing_invalid_trend_data_fails_closed(self):
        for value in (None, 0, -1, True, float('nan'), float('inf'), 'bad'):
            self.assertFalse(pass_long_term_trend({'details': {'current': value, 'ma120': 110}})[0])
            self.assertFalse(pass_long_term_trend({'details': {'current': 120, 'ma120': value}})[0])
        self.assertFalse(pass_long_term_trend({'details': None})[0])

    def test_telegram_uses_ranking_and_coverage_labels(self):
        messages = []
        with patch('telegram_bot.send_message', side_effect=messages.append), patch('telegram_bot.time.sleep'):
            send_telegram(blocks(), {'saved_days': 2, 'saved_themes': 1})
        text = ''.join(messages)
        self.assertNotIn('AI점수', text)
        self.assertIn('수익확률 아님', text)
        self.assertIn('사건점수 80', text)
        self.assertIn('검증 후보 TOP1', text)
        self.assertNotIn('TOP5', text)
        self.assertIn('기록 확인일수', text)
        self.assertIn('남아 있는 기록 기준', text)
        self.assertNotIn('S+', text)


class MemoryPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.previous = os.getcwd()
        self.directory = tempfile.TemporaryDirectory()
        os.chdir(self.directory.name)
        self.patches = [patch.object(memory, 'MEMORY_FILE', 'data/history.json'),
                        patch.object(backtest, 'BACKTEST_FILE', 'orion_backtest.json')]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        os.chdir(self.previous)
        self.directory.cleanup()

    def test_missing_history_does_not_create_fake_records(self):
        status = memory.get_project_status()
        self.assertEqual(status['saved_days'], 0)
        self.assertFalse(Path('data/history.json').exists())

    def test_same_day_same_candidates_or_empty_rerun_do_not_duplicate(self):
        memory.save_today_result(blocks())
        memory.save_today_result(blocks())
        memory.save_today_result([])
        self.assertEqual(len(memory.load_memory()), 1)
        self.assertEqual(memory.get_project_status()['saved_days'], 1)
        self.assertEqual(memory.get_project_status()['saved_themes'], 1)

    def test_new_candidate_same_day_retains_first_record_without_duplication(self):
        original = blocks()
        memory.save_today_result(original)
        more = blocks() + blocks('032940', '원익')
        memory.save_today_result(more)
        saved = memory.load_memory()
        self.assertEqual(saved[0]['results'], original)
        self.assertEqual(saved[1]['results'], blocks('032940', '원익'))
        self.assertEqual(memory.get_project_status()['saved_themes'], 1)

    def test_backtest_and_memory_dates_merge_without_inventing_missing_days(self):
        memory.save_memory([{'date': '2026-10-14', 'results': blocks()},
                            {'date': '2026-10-14', 'results': blocks()}])
        backtest.save_backtest([{'date': '2026-10-12', 'theme': 'AI', 'code': '022100'},
                                {'date': '2026-10-12', 'theme': 'AI', 'code': '032940'},
                                {'date': '2026-10-14', 'theme': 'AI', 'code': '022100'}])
        status = memory.get_project_status()
        self.assertEqual(status['known_dates'], ['2026-10-12', '2026-10-14'])
        self.assertEqual(status['saved_days'], 2)
        self.assertEqual(status['saved_themes'], 2)
        self.assertFalse(status['continuous_history_confirmed'])

    def test_empty_run_counts_day_but_not_recommended_theme(self):
        memory.save_memory([{'date': '2026-10-14', 'results': []}])
        self.assertEqual(memory.get_project_status()['saved_days'], 1)
        self.assertEqual(memory.get_project_status()['saved_themes'], 0)

    def test_corrupt_history_not_overwritten(self):
        Path('data').mkdir()
        for content in ('broken', '{}', '[{"results":[null]}]'):
            Path('data/history.json').write_text(content)
            with self.assertRaises(RuntimeError):
                memory.save_today_result(blocks())
            self.assertEqual(Path('data/history.json').read_text(), content)

    def test_new_records_are_kst_even_when_utc_is_previous_date(self):
        # 10월 14일 22시 UTC는 한국시간 15일. 과거 기록의 시차는 추측해 고치지 않는다.
        actual = datetime(2026, 10, 14, 22, tzinfo=timezone.utc)
        with patch.object(memory, 'datetime') as clock:
            clock.now.side_effect = lambda zone: actual.astimezone(zone)
            memory.save_today_result([])
        row = memory.load_memory()[0]
        self.assertEqual(row['date'], '2026-10-15')
        self.assertEqual(row['date_timezone'], 'Asia/Seoul')
        self.assertTrue(row['recorded_at'].endswith('+09:00'))

    def test_save_is_atomic_and_does_not_mutate_inputs(self):
        incoming = blocks()
        before = deepcopy(incoming)
        memory.save_today_result(incoming)
        self.assertEqual(incoming, before)
        self.assertFalse(Path('data/history.json.tmp').exists())

    def test_historical_splus_and_wonik_reference_not_regraded(self):
        old = {'date': '2026-10-12', 'theme': 'AI', 'code': '022100', 'score': 309, 'grade': '💎 S+'}
        wonik = {'date': '2026-09-02', 'theme': '반도체', 'code': '032940', 'grade': 'S+', 'rank': 1}
        backtest.save_backtest([old, wonik])
        with patch.object(backtest, 'get_current_quote', return_value={
            'price': 100, 'date': '2026-10-21', 'source': 'YAHOO_REGULAR_CLOSE'}):
            backtest.save_recommendations([{'theme': {'name': 'AI'}, 'ranked': [result()]}])
        saved = backtest.load_backtest()
        self.assertEqual(saved[:2], [old, wonik])
        self.assertEqual(saved[-1]['score_version'], SCORE_VERSION)
        self.assertEqual(saved[-1]['grade_status'], 'uncalibrated')


class WorkflowPersistenceTests(unittest.TestCase):
    def run_script(self, files, fail_push=False):
        workflow = (ROOT / '.github/workflows/bot.yml').read_text()
        block = workflow.split('- name: 백테스트 및 표시용 이력 저장', 1)[1]
        script = textwrap.dedent(block.split('run: |', 1)[1])
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            for file in files:
                path = directory / file
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('[]')
            binary = directory / 'bin'
            binary.mkdir()
            git = binary / 'git'
            git.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$ORION_TEST_GIT_LOG"\n'
                           'if [ "$1" = "diff" ]; then exit 1; fi\n'
                           + ('if [ "$1" = "push" ]; then exit 1; fi\n' if fail_push else '')
                           + 'exit 0\n')
            git.chmod(0o700)
            log = directory / 'calls.log'
            env = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ['PATH'],
                       ORION_TEST_GIT_LOG=str(log))
            run = subprocess.run(['bash', '-e', '-c', script], cwd=directory, env=env,
                                 capture_output=True, text=True)
            return run.returncode, log.read_text()

    def test_both_tracking_files_staged_but_not_other_files(self):
        status, log = self.run_script(['orion_backtest.json', 'data/history.json', 'data/private.json'])
        self.assertEqual(status, 0)
        self.assertIn('add -- orion_backtest.json', log)
        self.assertIn('add -- data/history.json', log)
        self.assertNotIn('data/private.json', log)

    def test_history_only_is_not_skipped(self):
        status, log = self.run_script(['data/history.json'])
        self.assertEqual(status, 0)
        self.assertIn('add -- data/history.json', log)

    def test_push_failure_is_not_reported_as_success(self):
        status, _ = self.run_script(['data/history.json'], fail_push=True)
        self.assertNotEqual(status, 0)


if __name__ == '__main__':
    unittest.main()
