import contextlib
import io
from pathlib import Path
import tempfile
import os
import threading
import unittest
from unittest.mock import Mock, patch
import zipfile
import requests
import build_corp_db as dart
import news_engine as news
from test_dart_startup import streamed_response


class ParallelFeedTests(unittest.TestCase):
    def test_out_of_order_completion_preserves_source_order_and_reports(self):
        second_done = threading.Event()
        def parser(url, market, source, diagnostics=None):
            if source == 'first':
                self.assertTrue(second_done.wait(2))
            else:
                second_done.set()
            diagnostics[source] = {'status': 'ok'}
            return [{'source': source, 'market': market}]
        diagnostics = {}
        with patch.object(news, 'parse_rss', side_effect=parser):
            result = news._collect_feeds([('first', '1'), ('second', '2')], 'KR', diagnostics)
        self.assertEqual([r['source'] for r in result], ['first', 'second'])
        self.assertEqual(list(diagnostics), ['first', 'second'])
        self.assertEqual([r['market'] for r in result], ['KR', 'KR'])

    def test_at_most_four_workers_and_each_feed_once(self):
        lock = threading.Lock()
        four_started = threading.Event()
        active = peak = 0
        seen = []
        def parser(url, market, source, diagnostics=None):
            nonlocal active, peak
            with lock:
                seen.append(source)
                active += 1
                peak = max(peak, active)
                if active == 4:
                    four_started.set()
            self.assertTrue(four_started.wait(2))
            with lock:
                active -= 1
            return []
        with patch.object(news, 'parse_rss', side_effect=parser):
            news._collect_feeds([(str(i), str(i)) for i in range(9)], 'US')
        self.assertEqual(peak, 4)
        self.assertEqual(sorted(seen), [str(i) for i in range(9)])

    def test_diagnostics_are_thread_local(self):
        dictionaries = []
        lock = threading.Lock()
        def parser(url, market, source, diagnostics=None):
            with lock:
                dictionaries.append(diagnostics)
            diagnostics[source] = {'status': 'ok'}
            return []
        shared = {'old': {'status': 'old'}}
        with patch.object(news, 'parse_rss', side_effect=parser):
            news._collect_feeds([('a', 'a'), ('b', 'b')], 'KR', shared)
        self.assertIsNot(dictionaries[0], dictionaries[1])
        self.assertEqual(set(shared), {'old', 'a', 'b'})

    def test_connect_timeout_is_distinguished_without_url(self):
        diagnostics = {}
        output = io.StringIO()
        with patch.object(news.requests, 'get', side_effect=requests.ConnectTimeout('private-url')), \
                patch.object(news.time, 'sleep'), contextlib.redirect_stdout(output):
            self.assertEqual(news.parse_rss('https://example.test', 'US', 'test', diagnostics), [])
        self.assertEqual(diagnostics['test']['error'], 'connect_timeout')
        self.assertEqual(diagnostics['test']['attempts'], 2)
        self.assertNotIn('private-url', output.getvalue())

    def test_empty_feed_list_is_valid(self):
        self.assertEqual(news._collect_feeds([], 'KR', {}), [])

    def test_same_host_is_serial_but_other_host_can_progress(self):
        lock = threading.Lock()
        other_done = threading.Event()
        active = peak = 0
        def parser(url, market, source, diagnostics=None):
            nonlocal active, peak
            if source == 'other':
                other_done.set()
                return []
            with lock:
                active += 1
                peak = max(peak, active)
            self.assertTrue(other_done.wait(2))
            with lock:
                active -= 1
            return []
        with patch.object(news, 'parse_rss', side_effect=parser):
            news._collect_feeds([('first', 'https://same.test/a'), ('second', 'https://same.test/b'),
                                 ('other', 'https://other.test/feed')], 'US')
        self.assertEqual(peak, 1)


class DartTransferTests(unittest.TestCase):
    def setUp(self):
        self.previous_cwd = os.getcwd()
        self.directory = tempfile.TemporaryDirectory()
        os.chdir(self.directory.name)
        self.output = io.StringIO()
        self.capture = contextlib.redirect_stdout(self.output)
        self.capture.__enter__()

    def tearDown(self):
        self.capture.__exit__(None, None, None)
        os.chdir(self.previous_cwd)
        self.directory.cleanup()

    def archive(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            archive.writestr('CORPCODE.xml', '<result><list><stock_code>005930</stock_code>'
                             '<corp_code>00126380</corp_code><corp_name>삼성전자</corp_name></list></result>')
        return data.getvalue()

    def test_stream_timeout_parameters_and_close(self):
        response = streamed_response(b'body')
        response.iter_content.return_value = [b'b', b'', b'ody']
        with patch.object(dart.requests, 'get', return_value=response) as get:
            self.assertEqual(dart._download_corp_bytes(), b'body')
        self.assertEqual(get.call_args.kwargs['timeout'], (5, 20))
        self.assertTrue(get.call_args.kwargs['stream'])
        response.close.assert_called_once()

    def test_progress_does_not_disclose_key_or_url(self):
        with patch.object(dart.requests, 'get', return_value=streamed_response(b'body')), \
                patch.object(dart.time, 'monotonic', side_effect=[0, 16, 17, 17]):
            dart._download_corp_bytes()
        self.assertIn('4 bytes / 16.0초', self.output.getvalue())
        self.assertNotIn('crtfc_key', self.output.getvalue())

    def test_transfer_budget_checked_and_existing_csv_unchanged(self):
        Path('corp_code.csv').write_bytes(b'original')
        response = streamed_response(b'partial')
        with patch.object(dart.requests, 'get', return_value=response), \
                patch.object(dart.time, 'monotonic', side_effect=[0, 241]):
            with self.assertRaisesRegex(RuntimeError, '시간 예산 초과'):
                dart.build_corp_db()
        self.assertEqual(Path('corp_code.csv').read_bytes(), b'original')
        response.close.assert_called_once()

    def test_budget_checked_at_end_of_empty_stream(self):
        response = streamed_response(b'')
        response.iter_content.return_value = []
        with patch.object(dart.requests, 'get', return_value=response), \
                patch.object(dart.time, 'monotonic', side_effect=[0, 241]):
            with self.assertRaisesRegex(RuntimeError, '시간 예산 초과'):
                dart._download_corp_bytes()
        response.close.assert_called_once()

    def test_size_limit_closes_response_and_preserves_csv(self):
        Path('corp_code.csv').write_bytes(b'original')
        response = streamed_response(b'four')
        with patch.object(dart.requests, 'get', return_value=response), patch.object(dart, 'MAX_DOWNLOAD_BYTES', 3):
            with self.assertRaisesRegex(RuntimeError, '크기 제한 초과'):
                dart.build_corp_db()
        response.close.assert_called_once()
        self.assertEqual(Path('corp_code.csv').read_bytes(), b'original')

    def test_partial_transfer_failure_is_sanitized_and_closed(self):
        response = streamed_response(b'')
        def chunks(**kwargs):
            yield b'partial'
            raise requests.ConnectionError('secret URL')
        response.iter_content.side_effect = chunks
        with patch.object(dart.requests, 'get', return_value=response):
            with self.assertRaisesRegex(RuntimeError, 'ConnectionError') as caught:
                dart.build_corp_db()
        self.assertNotIn('secret URL', str(caught.exception))
        self.assertFalse(Path('corp_code.csv').exists())
        response.close.assert_called_once()

    def test_success_replaces_csv_without_temp_files(self):
        Path('corp_code.csv').write_bytes(b'old')
        with patch.object(dart.requests, 'get', return_value=streamed_response(self.archive())):
            dart.build_corp_db()
        self.assertIn('005930', Path('corp_code.csv').read_text(encoding='utf-8-sig'))
        self.assertEqual(list(Path('.').glob('corp_code.*.tmp')), [])

    def test_write_failure_preserves_previous_csv_and_removes_temp(self):
        Path('corp_code.csv').write_bytes(b'old')
        def failed_write(frame, path, **kwargs):
            Path(path).write_bytes(b'partial')
            raise OSError('disk full')
        with patch.object(dart.requests, 'get', return_value=streamed_response(self.archive())), \
                patch.object(dart.pd.DataFrame, 'to_csv', failed_write):
            with self.assertRaisesRegex(OSError, 'disk full'):
                dart.build_corp_db()
        self.assertEqual(Path('corp_code.csv').read_bytes(), b'old')
        self.assertEqual(list(Path('.').glob('corp_code.*.tmp')), [])

    def test_replace_failure_preserves_previous_csv(self):
        Path('corp_code.csv').write_bytes(b'old')
        with patch.object(dart.requests, 'get', return_value=streamed_response(self.archive())), \
                patch.object(dart.os, 'replace', side_effect=OSError('replace failed')):
            with self.assertRaisesRegex(OSError, 'replace failed'):
                dart.build_corp_db()
        self.assertEqual(Path('corp_code.csv').read_bytes(), b'old')
        self.assertEqual(list(Path('.').glob('corp_code.*.tmp')), [])

    def test_cache_validator_rejects_missing_empty_or_malformed_codes(self):
        self.assertFalse(dart.valid_corp_csv('missing.csv'))
        for content in ('', 'stock_code,corp_code,corp_name\n',
                        'stock_code,corp_code,corp_name\n005930,abc,삼성전자\n',
                        'stock_code,corp_code,corp_name\n5930,00126380,삼성전자\n',
                        'stock_code,corp_code,corp_name\n005930,00126380,\n'):
            with self.subTest(content=content):
                Path('cache.csv').write_text(content, encoding='utf-8')
                self.assertFalse(dart.valid_corp_csv('cache.csv'))

    def test_bom_cache_validator_keeps_leading_zeros(self):
        Path('cache.csv').write_text('stock_code,corp_code,corp_name\n005930,00126380,삼성전자\n', encoding='utf-8-sig')
        self.assertTrue(dart.valid_corp_csv('cache.csv'))

    def test_real_alphanumeric_stock_codes_are_preserved(self):
        Path('cache.csv').write_text('stock_code,corp_code,corp_name\n0068Y0,01933981,비엔케이제3호스팩\n', encoding='utf-8-sig')
        self.assertTrue(dart.valid_corp_csv('cache.csv'))
        self.assertIn('0068Y0', Path('cache.csv').read_text(encoding='utf-8-sig'))

    def test_invalid_downloaded_code_preserves_existing_csv(self):
        Path('corp_code.csv').write_bytes(b'old')
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            archive.writestr('CORPCODE.xml', '<result><list><stock_code>005930</stock_code><corp_name>삼성전자</corp_name></list></result>')
        with patch.object(dart.requests, 'get', return_value=streamed_response(data.getvalue())):
            with self.assertRaisesRegex(RuntimeError, 'CSV 검증 실패'):
                dart.build_corp_db()
        self.assertEqual(Path('corp_code.csv').read_bytes(), b'old')
        self.assertEqual(list(Path('.').glob('corp_code.*.tmp')), [])

    def test_valid_cache_skips_download(self):
        Path('corp_code.csv').write_text('stock_code,corp_code,corp_name\n005930,00126380,삼성전자\n', encoding='utf-8-sig')
        with patch.object(dart.requests, 'get', side_effect=AssertionError('network on cache hit')):
            dart.ensure_corp_db()

    def test_missing_or_invalid_cache_is_built_once_and_then_reused(self):
        for existing in (False, True):
            with self.subTest(existing=existing):
                if existing:
                    Path('corp_code.csv').write_bytes(b'invalid')
                with patch.object(dart.requests, 'get', return_value=streamed_response(self.archive())) as get:
                    dart.ensure_corp_db()
                    dart.ensure_corp_db()
                self.assertEqual(get.call_count, 1)
                self.assertTrue(dart.valid_corp_csv('corp_code.csv'))
                Path('corp_code.csv').unlink()
