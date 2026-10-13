import importlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile
import requests

import build_corp_db


def streamed_response(content):
    response = Mock(content=content)
    response.iter_content.return_value = [content]
    return response


class DartStartupTests(unittest.TestCase):
    def setUp(self):
        self.previous_cwd = os.getcwd()
        self.directory = tempfile.TemporaryDirectory()
        os.chdir(self.directory.name)

    def tearDown(self):
        os.chdir(self.previous_cwd)
        self.directory.cleanup()
        for name in ('main', 'finance_engine', 'quality_engine'):
            sys.modules.pop(name, None)

    def test_import_without_csv_does_not_download(self):
        with patch('requests.get', side_effect=AssertionError('network on import')):
            importlib.import_module('main')
            importlib.reload(build_corp_db)
        self.assertFalse(Path('corp_code.csv').exists())

    def test_fresh_start_builds_csv_before_finance_import(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('CORPCODE.xml', '<result><list><corp_code>00126380</corp_code>'
                       '<corp_name>삼성전자</corp_name><stock_code>005930</stock_code>'
                       '</list></result>')
        response = streamed_response(archive.getvalue())
        main = importlib.import_module('main')
        class StopAfterStartup(Exception):
            pass
        with patch('requests.get', return_value=response) as get, patch.object(
            main, 'load_korean_stocks', side_effect=StopAfterStartup
        ):
            with self.assertRaises(StopAfterStartup):
                main.run()
        get.assert_called_once()
        from finance_engine import get_corp_code
        from quality_engine import get_corp_code as quality_lookup
        self.assertEqual(get_corp_code('005930'), '00126380')
        self.assertEqual(quality_lookup('005930'), '00126380')

    def test_existing_csv_skips_download(self):
        Path('corp_code.csv').write_text('stock_code,corp_code\n005930,00126380\n')
        main = importlib.import_module('main')
        with patch.object(build_corp_db, 'build_corp_db') as builder, patch.object(
            main, 'load_korean_stocks', side_effect=RuntimeError('startup complete')
        ):
            with self.assertRaisesRegex(RuntimeError, 'startup complete'):
                main.run()
        builder.assert_not_called()

    def test_dart_error_is_reported_without_creating_csv(self):
        response = streamed_response(b'<result><status>010</status><message>Invalid key</message></result>')
        with patch('requests.get', return_value=response):
            with self.assertRaisesRegex(RuntimeError, 'status=010, message=Invalid key'):
                build_corp_db.build_corp_db()
        self.assertFalse(Path('corp_code.csv').exists())

    def test_namespaced_error_is_reported(self):
        response = streamed_response(b'<result xmlns="urn:dart"><status>020</status>'
                                b'<message>Request limit</message></result>')
        with patch('requests.get', return_value=response):
            with self.assertRaisesRegex(RuntimeError, 'status=020, message=Request limit'):
                build_corp_db.build_corp_db()

    def test_non_api_page_explains_unknown_status(self):
        response = streamed_response(b'<html><body>Service unavailable</body></html>')
        with patch('requests.get', return_value=response):
            with self.assertRaisesRegex(RuntimeError, 'root=html, response=Service unavailable'):
                build_corp_db.build_corp_db()

    def test_connection_error_does_not_expose_key(self):
        with patch('requests.get', side_effect=requests.ConnectionError('secret URL')):
            with self.assertRaisesRegex(RuntimeError, r'연결 실패 \(ConnectionError\)') as error:
                build_corp_db.build_corp_db()
        self.assertNotIn('secret URL', str(error.exception))

    def test_empty_zip_does_not_create_broken_csv(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('CORPCODE.xml', '<result/>')
        with patch('requests.get', return_value=streamed_response(archive.getvalue())):
            with self.assertRaisesRegex(RuntimeError, '상장 종목이 없습니다'):
                build_corp_db.build_corp_db()
        self.assertFalse(Path('corp_code.csv').exists())


if __name__ == '__main__':
    unittest.main()
