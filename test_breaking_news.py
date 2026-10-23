import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from breaking_news import (GitState, deliver, followup, process, scan, timestamp)
from event_engine import build_events

NOW = datetime(2026, 10, 23, 3, 0, tzinfo=timezone.utc)


def article(minutes=2, **changes):
    return dict({'title': '검증기업, 신규 공장에 150억원 투자 결정', 'summary': '',
                 'market': 'KR', 'source': '한국경제_경제',
                 'link': 'https://example.com/news/1',
                 'published_at': (NOW - timedelta(minutes=minutes)).isoformat()}, **changes)


def empty_state():
    return {'version': 1, 'records': [], 'activation': {'phase': 'ready'}}


def analysis(event):
    return [], {'analysis_status': {'analyzed_count': 1, 'selected_count': 0,
                                    'excluded': [{'name': '검증기업', 'code': '123456',
                                                  'reason': '120일선 아래'}]}}


class BreakingTests(unittest.TestCase):
    def test_initial_history_is_baseline_but_recent_article_alerts(self):
        state = empty_state()
        old = article(40, link='https://example.com/old', title='다른기업, 신규 공장에 250억원 투자 결정')
        send = Mock()
        result = process(state, Mock(), [old, article()], NOW, send, analysis)
        self.assertEqual((result['new'], result['baseline'], result['notices'], result['analyses']), (1, 1, 1, 1))
        self.assertEqual(send.call_count, 3)  # Activation + first + follow-up.
        self.assertIn('150억원', send.call_args_list[1].args[0])
        self.assertIn('120일선 아래', send.call_args_list[2].args[0])

    def test_persisted_restart_and_tracking_url_dont_resend(self):
        state = empty_state()
        process(state, Mock(), [article()], NOW, Mock(), analysis)
        restored = json.loads(json.dumps(state))
        send = Mock()
        result = process(restored, Mock(), [article(link='https://example.com/news/1?utm_source=rss')],
                         NOW + timedelta(minutes=5), send, analysis)
        self.assertEqual(result['notices'], 0)
        self.assertEqual(result['analyses'], 0)
        send.assert_not_called()

    def test_changed_amount_same_url_is_new_event(self):
        state = empty_state()
        process(state, Mock(), [article()], NOW, Mock(), analysis)
        result = process(state, Mock(), [article(title='검증기업, 신규 공장에 250억원 투자 결정')],
                         NOW + timedelta(minutes=5), Mock(), analysis)
        self.assertEqual(result['notices'], 1)

    def test_late_scheduler_catches_unseen_story_and_labels_delay(self):
        state = empty_state()
        scan(state, [], NOW - timedelta(hours=2))
        send = Mock()
        result = process(state, Mock(), [article(90)], NOW, send, analysis)
        self.assertEqual(result['notices'], 1)
        self.assertIn('지연 발견', send.call_args_list[1].args[0])

    def test_invalid_unknown_zone_future_and_old_dates_are_not_alerted(self):
        news = [article(published_at=value) for value in ('', 'invalid', '2026-10-23T02:59:00',
                (NOW + timedelta(minutes=1)).isoformat(), (NOW - timedelta(hours=37)).isoformat())]
        news.append(article(link='javascript:alert(1)'))
        state = empty_state()
        self.assertEqual(scan(state, news, NOW), (0, 0))
        self.assertIsNone(timestamp('2026-10-23T02:59:00'))
        self.assertEqual(timestamp('2026-10-23T11:59:00+09:00').hour, 2)

    def test_interview_without_earnings_numbers_does_not_alert(self):
        state = empty_state()
        self.assertEqual(scan(state, [article(title='Huntington Bancshares CEO Stephen Steinour on 3Q Results')], NOW), (0, 0))

    def test_save_reservation_fails_before_send(self):
        state = empty_state()
        send = Mock()
        with self.assertRaises(OSError):
            deliver(state['activation'], 'message', state, Mock(side_effect=OSError), send)
        send.assert_not_called()

    def test_reservation_is_durable_before_send_and_uncertain_is_not_retried(self):
        state = empty_state()
        checkpoints = []
        def save(current):
            checkpoints.append(copy.deepcopy(current))
        def failing_send(message):
            self.assertEqual(checkpoints[-1]['activation']['phase'], 'sending')
            raise TimeoutError()
        with self.assertRaisesRegex(RuntimeError, '불확실'):
            process(state, save, [article()], NOW, failing_send, analysis)
        self.assertEqual(state['activation']['phase'], 'uncertain')
        # A later poll still sends new event notices, while flagging the uncertain startup.
        send = Mock()
        with self.assertRaisesRegex(RuntimeError, '미확정'):
            process(state, save, [article()], NOW, send, analysis)
        self.assertEqual(send.call_count, 2)
        self.assertFalse(any('시작했습니다' in call.args[0] for call in send.call_args_list))

    def test_crash_after_ack_leaves_durable_reservation_not_duplicate(self):
        state = empty_state()
        persisted = []
        def save(value):
            if value['activation']['phase'] == 'sent':
                raise OSError('checkpoint failed after API ack')
            persisted.append(copy.deepcopy(value))
        send = Mock()
        with self.assertRaises(OSError):
            deliver(state['activation'], 'message', state, save, send)
        restored = persisted[-1]
        self.assertEqual(restored['activation']['phase'], 'sending')
        self.assertFalse(deliver(restored['activation'], 'message', restored, Mock(), send))
        self.assertEqual(send.call_count, 1)

    def test_failed_analysis_retries_without_repeating_first_notice(self):
        state = empty_state()
        send = Mock()
        fail = Mock(side_effect=ValueError('not a token-safe message'))
        for _ in range(3):
            process(state, Mock(), [article()], NOW, send, fail)
        self.assertEqual(send.call_count, 3)
        self.assertIn('3회 실패', send.call_args.args[0])
        self.assertEqual(state['records'][0]['analysis']['phase'], 'sent')

    def test_first_notices_all_precede_analysis_and_queue_limits_survive_restart(self):
        state = empty_state()
        calls = []
        news = [article(title=f'기업{i}, 신규 공장에 {i+100}억원 투자 결정',
                        link=f'https://example.com/{i}') for i in range(7)]
        def send(message):
            calls.append('notice' if '· 1차' in message else 'other')
        def analyze(event):
            calls.append('analysis')
            return analysis(event)
        first = process(state, Mock(), news, NOW, send, analyze)
        self.assertEqual((first['notices'], first['analyses'], first['pending']), (5, 2, 5))
        self.assertEqual(calls[1:6], ['notice'] * 5)
        second = process(state, Mock(), news, NOW, send, analyze)
        self.assertEqual((second['new'], second['notices'], second['analyses']), (0, 2, 2))

    def test_html_is_escaped_and_real_earnings_are_eligible(self):
        state = empty_state()
        a = article(title='LG디스플레이 3분기, 전기比 흑자전환…영업이익 2506억원')
        self.assertEqual(scan(state, [a], NOW), (1, 0))
        event = build_events([a])[0]
        _, status = analysis(event)
        status['analysis_status']['excluded'][0]['reason'] = '<미확인 & 보류>'
        text = followup(event, [], status)
        self.assertIn('&lt;미확인 &amp; 보류&gt;', text)


class GitStateTests(unittest.TestCase):
    def test_checkpoint_survives_fresh_worktree_and_does_not_touch_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote, work, restored = [root / name for name in ('remote.git', 'work', 'restored')]
            def git(*args):
                return subprocess.run(['git', *map(str, args)], check=True, capture_output=True)
            git('init', '--bare', remote)
            git('init', work)
            git('-C', work, 'remote', 'add', 'origin', remote)
            state = empty_state()
            GitState(work).save(state)
            git('clone', '-b', 'orion-alert-state', remote, restored)
            self.assertEqual(GitState(restored).load(), state)
            refs = git('--git-dir', remote, 'show-ref').stdout.decode()
            self.assertIn('refs/heads/orion-alert-state', refs)
            self.assertNotIn('refs/heads/main', refs)

    def test_corrupt_state_is_never_silently_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GitState(tmp)
            store.path.parent.mkdir()
            store.path.write_text('{"version": 99, "records": []}')
            with self.assertRaises(RuntimeError):
                store.load()


if __name__ == '__main__':
    unittest.main()
