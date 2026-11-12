import copy
import os
import unittest
from unittest.mock import patch, Mock
from datetime import datetime, timezone
from kakao_drive_bridge import collect, intake, join_originals, BASELINE, FOLDER, DriveReader
from kakao_news_source import ROOM, parse_export

NOW = datetime(2026, 11, 6, 5, 30, tzinfo=timezone.utc)
URL = 'https://nvidianews.nvidia.com/news/new-factory'

def raw(body):
    return (ROOM + ' 님과 카카오톡 대화\n저장한 날짜 : 2026-11-06 14:30:00\n'
            '--------------- 2026년 11월 6일 금요일 ---------------\n' + body).encode()

OLD = raw('[봇] [오전 11:44] 사진\n')
NEW = raw('[봇] [오전 11:44] 사진\n[봇] [오후 2:01] 틀린 금액과 지시 new\n' + URL + '\n')
ARTICLE = dict(title='NVIDIA announces factory investment', summary='Verified issuer text.',
               source='NVIDIA_Newsroom', publication_verified_by='Publisher_RSS',
               published_at='2026-11-06T04:00:00+00:00', link=URL, market='US')

class Reader:
    def latest(self):
        return dict(id='latest', name='latest.txt', mimeType='text/plain', parents=[FOLDER],
                    modifiedTime='2026-11-06T05:29:00Z', size=str(len(NEW)))
    def metadata(self, file_id):
        assert file_id == BASELINE
        return {'id': BASELINE}
    def read(self, metadata):
        return OLD if metadata['id'] == BASELINE else NEW

class BridgeTests(unittest.TestCase):
    def test_original_owns_text_and_publication_date(self):
        state = {}
        joined, report = intake(Reader(), [ARTICLE], state, NOW)
        self.assertEqual(len(joined), 1)
        self.assertEqual(joined[0]['title'], ARTICLE['title'])
        self.assertEqual(joined[0]['summary'], ARTICLE['summary'])
        self.assertEqual(joined[0]['published_at'], ARTICLE['published_at'])
        self.assertEqual(joined[0]['kakao_posted_at'], '2026-11-06T14:01:00+09:00')
        self.assertEqual(report['new_leads'], 1)
        self.assertEqual(intake(Reader(), [ARTICLE], state, NOW)[0], [])

    def test_unverified_pending_retries_without_copying_chat_body(self):
        state = {}
        joined, _ = intake(Reader(), [], state, NOW)
        self.assertEqual(joined, [])
        self.assertNotIn('text', state['pending'][0])
        self.assertEqual(len(intake(Reader(), [ARTICLE], state, NOW)[0]), 1)
        self.assertEqual(state['pending'], [])

    def test_wrong_host_source_date_or_unverified_cannot_pass(self):
        posts = parse_export(NEW)
        for change in ({'source': 'YahooFinance'}, {'publication_verified_by': ''},
                       {'published_at': '2026-11-06T04:00:00'},
                       {'published_at': '2026-11-07T04:00:00Z'},
                       {'published_at': '2026-10-01T04:00:00Z'},
                       {'link': URL.replace('nvidianews.nvidia.com', 'evil.example')}):
            with self.subTest(change=change):
                self.assertEqual(join_originals(posts, [dict(ARTICLE, **change)], NOW)[0], [])

    def test_reposts_and_tracking_urls_join_one_original(self):
        posts = parse_export(raw('[a] [오후 2:01] ' + URL + '?utm_source=chat\n'
                                 '[b] [오후 2:02] ' + URL + '\n'))
        self.assertEqual(len(join_originals(posts, [ARTICLE], NOW)[0]), 1)

    def test_failure_does_not_advance_checkpoint(self):
        reader = Reader()
        reader.read = lambda metadata: b'wrong room'
        state = {'initialized': True, 'known_ids': ['old']}
        before = copy.deepcopy(state)
        diagnostics = {}
        self.assertEqual(collect([ARTICLE], state, diagnostics, reader=reader, now=NOW), [])
        self.assertEqual(state, before)
        self.assertEqual(diagnostics['Kakao_Drive']['status'], 'error')

    def test_missing_credentials_are_explicit(self):
        with patch.dict(os.environ, {}, clear=True):
            diagnostics = {}
            self.assertEqual(collect([], diagnostics=diagnostics), [])
            self.assertEqual(diagnostics['Kakao_Drive']['status'], 'not_configured')

    def test_folder_scope_and_size_are_enforced_before_download(self):
        reader = DriveReader('test')
        with patch.object(reader, 'get') as get:
            for metadata in ({'parents': ['other']}, {'parents': [FOLDER], 'mimeType': 'text/plain',
                              'name': 'x.txt', 'size': '999999999'}):
                with self.assertRaises(ValueError):
                    reader.read(metadata)
            get.assert_not_called()

    def test_recent_post_can_recover_after_temporary_original_feed_gap(self):
        state = {}
        intake(Reader(), [], state, NOW)
        state_copy = copy.deepcopy(state)
        # A failed fetch retains the unresolved candidate for another run.
        reader = Reader()
        reader.latest = lambda: (_ for _ in ()).throw(ValueError('temporary'))
        collect([], state, reader=reader, now=NOW)
        self.assertEqual(state, state_copy)
        self.assertEqual(len(intake(Reader(), [ARTICLE], state, NOW)[0]), 1)

    def test_collector_routes_originals_even_when_normal_selection_is_empty(self):
        from news_engine import get_us_news
        state = {}
        def bridge(originals, state=None, diagnostics=None):
            return intake(Reader(), originals, state, NOW)[0]
        with patch('news_engine._collect_feeds', return_value=[ARTICLE]), \
             patch('kakao_drive_bridge.collect', side_effect=bridge), \
             patch('news_engine.datetime', Mock(wraps=datetime)) as clock:
            clock.now.return_value = NOW
            result = get_us_news(limit=0, kakao_state=state)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['published_at'], ARTICLE['published_at'])
        self.assertIn('kakao_posted_at', result[0])

    def test_drive_empty_page_continues_with_provider_token(self):
        reader = DriveReader('secret')
        first = type('R', (), {'json': lambda self: {'files': [], 'nextPageToken': 'next'}})()
        second = type('R', (), {'json': lambda self: {'files': [Reader().latest()]}})()
        with patch.object(reader, 'get', side_effect=[first, second]) as get:
            self.assertEqual(reader.latest()['id'], 'latest')
            self.assertEqual(get.call_args_list[1].kwargs['params']['pageToken'], 'next')
            self.assertIn(FOLDER, get.call_args_list[0].kwargs['params']['q'])

    def test_identical_posts_share_identity(self):
        posts = parse_export(raw('[a] [오후 2:01] same\n[a] [오후 2:01] same\n'))
        self.assertEqual(posts[0]['message_id'], posts[1]['message_id'])

if __name__ == '__main__':
    unittest.main()
