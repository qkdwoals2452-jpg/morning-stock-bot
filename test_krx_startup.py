import contextlib
import importlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests
import stock_engine


def table(rows=None):
    rows = rows if rows is not None else [('원익', '032940', '반도체'), ('신규회사', '0123A0', '전자')]
    return '<table><tr><th>회사명</th><th>종목코드</th><th>업종</th></tr>' + ''.join(
        '<tr>' + ''.join(f'<td>{value}</td>' for value in row) + '</tr>' for row in rows
    ) + '</table>'


def response(html=None):
    return Mock(text=table() if html is None else html)


class KrxStartupTests(unittest.TestCase):
    def load(self, responses):
        with patch.object(stock_engine.requests, 'get', side_effect=responses) as get, \
                patch.object(stock_engine.time, 'sleep') as sleep, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            result = stock_engine.load_korean_stocks()
        return result, get, sleep, output.getvalue()

    def test_valid_table_preserves_numeric_and_alphanumeric_codes(self):
        result, get, sleep, _ = self.load([response()])
        self.assertEqual([row['code'] for row in result], ['032940', '0123A0'])
        self.assertEqual(result[0]['name'], '원익')
        self.assertEqual(result[0]['sector'], '반도체')
        get.assert_called_once()
        sleep.assert_not_called()

    def test_timeout_retries_once_and_recovers(self):
        result, get, sleep, output = self.load([requests.ReadTimeout('sensitive URL'), response()])
        self.assertEqual(len(result), 2)
        self.assertEqual(get.call_count, 2)
        sleep.assert_called_once()
        self.assertNotIn('sensitive URL', output)

    def test_terminal_timeout_raises_instead_of_returning_empty(self):
        with patch.object(stock_engine.requests, 'get', side_effect=requests.ReadTimeout('secret')), \
                patch.object(stock_engine.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, 'KRX.*확인불가') as error:
                stock_engine.load_korean_stocks()
        self.assertNotIn('secret', str(error.exception))

    def test_invalid_tables_are_not_used_as_stock_universe(self):
        invalid = [
            '<html>maintenance</html>',
            '<table><tr><th>회사명</th></tr><tr><td>원익</td></tr></table>',
            table([]), table([('', '032940', '반도체')]),
            table([('원익', '032940.0', '반도체')]),
            table([('원익', '1234567', '반도체')]),
            table([('원익', 'abcd', '반도체')]),
            table([('원익', '032940', '반도체'), ('다른회사', '032940', '전자')]),
        ]
        for html in invalid:
            with self.subTest(html=html), patch.object(stock_engine.requests, 'get', return_value=response(html)), \
                    patch.object(stock_engine.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, 'KRX.*확인불가'):
                    stock_engine.load_korean_stocks()

    def test_http_error_is_checked_and_redacted(self):
        res = response()
        res.raise_for_status.side_effect = requests.HTTPError('secret request URL')
        with patch.object(stock_engine.requests, 'get', return_value=res) as get, \
                patch.object(stock_engine.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaisesRegex(RuntimeError, 'HTTPError'):
                stock_engine.load_korean_stocks()
        self.assertEqual(get.call_count, 2)
        self.assertNotIn('secret request URL', output.getvalue())

    def test_invalid_first_response_can_recover(self):
        result, get, _, _ = self.load([response('<html>maintenance</html>'), response()])
        self.assertEqual(len(result), 2)
        self.assertEqual(get.call_count, 2)

    def test_numeric_code_padding(self):
        result, _, _, _ = self.load([response(table([('회사', '5930', '전자')]))])
        self.assertEqual(result[0]['code'], '005930')

    def test_missing_universe_stops_before_news_writes_and_telegram(self):
        previous = os.getcwd()
        modules = ('main', 'finance_engine', 'quality_engine')
        with tempfile.TemporaryDirectory() as directory:
            os.chdir(directory)
            try:
                Path('corp_code.csv').write_text('stock_code,corp_code\n005930,00126380\n')
                for name in modules:
                    sys.modules.pop(name, None)
                main = importlib.import_module('main')
                downstream = {name: Mock() for name in (
                    'get_us_news', 'get_korea_news', 'update_backtest_prices',
                    'save_recommendations', 'save_today_result', 'save_prediction', 'send_telegram')}
                for missing in ([], None):
                    with self.subTest(missing=missing), patch.multiple(main, **downstream), \
                            patch.object(main, 'load_korean_stocks', return_value=missing), \
                            contextlib.redirect_stdout(io.StringIO()):
                        with self.assertRaisesRegex(RuntimeError, 'KRX.*확인불가'):
                            main.run()
                    for function in downstream.values():
                        function.assert_not_called()
            finally:
                os.chdir(previous)
                for name in modules:
                    sys.modules.pop(name, None)


if __name__ == '__main__':
    unittest.main()
