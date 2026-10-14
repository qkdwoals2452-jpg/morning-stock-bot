import contextlib
import io
import unittest
from unittest.mock import Mock, patch
import zipfile
import requests

import dart_document_engine as engine

RECEIPT = '20261013999999'
TEXT = '<html><body>한미반도체 단일판매ㆍ공급계약체결 계약상대 Micron 계약금액 100,000,000</body></html>'
PAGE = '<title>한미반도체/단일판매ㆍ공급계약체결</title><script>viewDoc("20261013999999", "1234", "0", "0", "0", "HTML", "");</script>'


def res(content, status=200):
    r = Mock(status_code=status)
    r.iter_content.return_value = [content.encode('utf-8') if isinstance(content, str) else content]
    return r


def archive(xml=TEXT):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as z:
        z.writestr('original.xml', xml)
    return stream.getvalue()


class DartDocumentTests(unittest.TestCase):
    def fetch(self, responses, key='secret-key'):
        with patch.object(engine.requests, 'get', side_effect=responses) as get, \
                patch.object(engine.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()) as output:
            result = engine.fetch_contract_document(RECEIPT, '한미반도체', api_key=key)
        return result, get, output.getvalue()

    def test_api_zip_returns_raw_evidence_without_order_registration(self):
        result, get, _ = self.fetch([res(archive())])
        self.assertEqual(result['route'], 'opendart_xml')
        self.assertEqual(len(result['document_sha256']), 64)
        self.assertFalse(result['order_registered'])
        self.assertEqual(result['score_effect'], 0)
        get.assert_called_once()

    def test_missing_api_document_uses_observed_public_viewer(self):
        result, get, _ = self.fetch([res('<result><status>014</status></result>'), res(PAGE), res(TEXT)])
        self.assertEqual(result['route'], 'dart_public_viewer')
        self.assertEqual(result['api_failures'], ['API_status_014'])
        self.assertEqual(get.call_args.kwargs['params']['dcmNo'], '1234')
        self.assertNotIn('crtfc_key', get.call_args.kwargs['params'])

    def test_timeout_retries_then_public_lookup(self):
        result, get, output = self.fetch([requests.ReadTimeout('secret URL'), requests.ReadTimeout('secret URL'), res(PAGE), res(TEXT)])
        self.assertEqual(get.call_count, 4)
        self.assertEqual(result['route'], 'dart_public_viewer')
        self.assertNotIn('secret URL', output)

    def test_access_auth_and_rate_limit_do_not_retry_or_fallback(self):
        for status in ('010', '011', '012', '020', '101', '901'):
            with self.subTest(status=status), patch.object(engine.requests, 'get', return_value=res(f'<result><status>{status}</status></result>')) as get:
                with self.assertRaises(engine.AccessDenied):
                    engine.fetch_contract_document(RECEIPT, '한미반도체', api_key='secret')
                get.assert_called_once()

    def test_http_denial_does_not_fallback(self):
        with patch.object(engine.requests, 'get', return_value=res('',403)) as get:
            with self.assertRaises(engine.AccessDenied):
                engine.fetch_contract_document(RECEIPT, '한미반도체', api_key='secret')
            get.assert_called_once()

    def test_redirect_not_followed(self):
        with patch.object(engine.requests, 'get', return_value=res('',302)) as get:
            with self.assertRaisesRegex(engine.DocumentUnavailable, 'redirect_not_followed'):
                engine.fetch_contract_document(RECEIPT, '한미반도체')
            self.assertFalse(get.call_args.kwargs['allow_redirects'])

    def test_wrong_issuer_or_no_observed_original_fails(self):
        for page in (PAGE.replace('한미반도체','다른회사'), PAGE.replace(RECEIPT,'20261012999999'), PAGE.replace('viewDoc','somethingElse')):
            with patch.object(engine.requests, 'get', return_value=res(page)) as get:
                with self.assertRaises(engine.DocumentUnavailable):
                    engine.fetch_contract_document(RECEIPT, '한미반도체')
                get.assert_called_once()

    def test_wrong_body_not_accepted(self):
        with patch.object(engine.requests, 'get', return_value=res(archive('<html>maintenance</html>'))):
            with self.assertRaisesRegex(engine.DocumentUnavailable, 'content_mismatch'):
                engine.fetch_contract_document(RECEIPT, '한미반도체', api_key='secret')

    def test_multiple_xml_documents_not_guessed(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream,'w') as z:
            z.writestr('one.xml',TEXT); z.writestr('two.xml',TEXT)
        with self.assertRaisesRegex(engine.DocumentUnavailable,'ambiguous'):
            engine._api_xml(stream.getvalue())

    def test_size_limit_and_response_closed(self):
        response = res(b'long content')
        with patch.object(engine, 'MAX_BYTES', 3), patch.object(engine.requests,'get',return_value=response):
            with self.assertRaisesRegex(engine.DocumentUnavailable,'size_limit'):
                engine.fetch_contract_document(RECEIPT,'한미반도체')
        response.close.assert_called_once()

    def test_expired_budget_stops_without_network(self):
        with patch.object(engine.time,'monotonic',side_effect=[0,121]), patch.object(engine.requests,'get') as get:
            with self.assertRaisesRegex(engine.DocumentUnavailable,'budget'):
                engine.fetch_contract_document(RECEIPT,'한미반도체')
            get.assert_not_called()

    def test_invalid_receipt_has_no_network(self):
        for receipt in ('wrong', '20261313999999', RECEIPT+'?token=secret'):
            with patch.object(engine.requests,'get') as get:
                with self.assertRaises(ValueError):
                    engine.fetch_contract_document(receipt,'한미반도체')
                get.assert_not_called()

    def test_scripts_hidden_and_key_not_in_returned_text(self):
        text = TEXT.replace('</body>','secret-key<script>hidden key</script></body>')
        result, _, output = self.fetch([res(archive(text))])
        self.assertNotIn('secret-key', result['text'])
        self.assertNotIn('hidden key', result['text'])
        self.assertNotIn('secret-key', output)


if __name__ == '__main__':
    unittest.main()
