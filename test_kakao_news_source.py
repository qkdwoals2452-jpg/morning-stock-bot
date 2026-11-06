import unittest
from datetime import datetime
from kakao_news_source import ROOM, KST, parse_export, select_new_posts


def export(body, room=ROOM):
    return (room + ' 님과 카카오톡 대화\n저장한 날짜 : 2026-11-06 14:00:00\n' + body).encode('utf-8-sig')


class KakaoSourceTests(unittest.TestCase):
    def test_multiline_links_and_time_are_preserved(self):
        posts = parse_export(export('--------------- 2026년 11월 6일 금요일 ---------------\n'
            '[캐롤라인] [오후 12:01] 증설 계약\n둘째 줄\n[원문](https://example.com/news)\n'
            '[캐롤라인] [오후 12:02] 사진\n'))
        self.assertEqual(posts[0]['posted_at'], '2026-11-06T12:01:00+09:00')
        self.assertEqual(posts[0]['urls'], ['https://example.com/news'])
        self.assertIn('둘째 줄', posts[0]['text'])
        self.assertFalse(posts[0]['publication_verified'])
        self.assertTrue(posts[1]['media_only'])

    def test_reexport_is_idempotent_and_new_append_survives(self):
        body = '--------------- 2026년 11월 6일 금요일 ---------------\n[봇] [오전 12:01] 계약\n'
        first = parse_export(export(body))
        second = parse_export(export(body + '[봇] [오전 12:02] 증설\n'))
        result = select_new_posts(second, {p['message_id'] for p in first}, now=datetime(2026,11,6,1,tzinfo=KST))
        self.assertEqual([p['text'] for p in result], ['증설'])
        self.assertEqual(first[0]['posted_at'], '2026-11-06T00:01:00+09:00')

    def test_wrong_room_and_malformed_time_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'wrong_room'):
            parse_export(export('', room='경제공부방'))
        with self.assertRaisesRegex(ValueError, 'invalid_message_time'):
            parse_export(export('[봇] [오전 9:01] 날짜 없음'))

    def test_old_future_media_and_system_are_not_new_leads(self):
        posts = parse_export(export('--------------- 2026년 11월 2일 월요일 ---------------\n'
            '[봇] [오전 9:01] 과거 계약\n'
            '--------------- 2026년 11월 6일 금요일 ---------------\n'
            '[봇] [오전 9:01] 사진\n방 장님이 들어왔습니다.\n'
            '[봇] [오후 11:01] 미래\n'))
        self.assertEqual(select_new_posts(posts, set(), now=datetime(2026,11,6,14,tzinfo=KST)), [])
        self.assertNotIn('방 장', posts[1]['text'])

    def test_korean_encodings(self):
        text = export('--------------- 2026년 11월 6일 금요일 ---------------\n[봇] [오전 9:01] 수주').decode('utf-8-sig')
        for encoding in ('utf-16', 'cp949'):
            self.assertEqual(parse_export(text.encode(encoding))[0]['text'], '수주')


if __name__ == '__main__':
    unittest.main()
