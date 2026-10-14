"""개별 공시 원문 조회. 반환은 원자료이며 주문 등록/점수 반영은 수행하지 않는다."""
from datetime import datetime
from hashlib import sha256
from html.parser import HTMLParser
import io
import re
import time
import xml.etree.ElementTree as ET
import zipfile

import requests

MAX_BYTES = 8 * 1024 * 1024
TIMEOUT = (5, 15)
ACCESS_CODES = {'010', '011', '012', '020', '021', '100', '101', '901'}


class DocumentUnavailable(RuntimeError):
    pass


class AccessDenied(DocumentUnavailable):
    pass


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in ('script', 'style'):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag.lower() in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, text):
        if not self.hidden and text.strip():
            self.parts.append(text.strip())


def visible_text(html):
    parser = VisibleText()
    parser.feed(html)
    return ' '.join(parser.parts)


def _decode(content):
    declared = re.search(br'charset\s*=\s*["\']?([a-zA-Z0-9-]+)', content[:2048], re.I)
    encoding = declared.group(1).decode('ascii').lower() if declared else 'utf-8'
    if encoding not in ('utf-8', 'euc-kr', 'cp949'):
        raise DocumentUnavailable('unsupported_document_encoding')
    try:
        return content.decode(encoding)
    except UnicodeError:
        raise DocumentUnavailable('invalid_document_encoding') from None


def _download(url, params, stage, deadline):
    last = 'unknown'
    for attempt in range(1, 3):
        if time.monotonic() >= deadline:
            raise DocumentUnavailable('document_time_budget_exceeded')
        response = None
        try:
            remaining = max(0.1, deadline - time.monotonic())
            response = requests.get(url, params=params, timeout=(min(TIMEOUT[0], remaining), min(TIMEOUT[1], remaining)),
                                    headers={'User-Agent': 'ORION Disclosure Research'}, stream=True,
                                    allow_redirects=False)
            if response.status_code in (401, 403):
                raise AccessDenied(f'{stage}:HTTP_{response.status_code}')
            if 300 <= response.status_code < 400:
                raise DocumentUnavailable(f'{stage}:redirect_not_followed')
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if time.monotonic() >= deadline:
                    raise DocumentUnavailable('document_time_budget_exceeded')
                data.extend(chunk)
                if len(data) > MAX_BYTES:
                    raise DocumentUnavailable('document_size_limit_exceeded')
            if time.monotonic() >= deadline:
                raise DocumentUnavailable('document_time_budget_exceeded')
            print(f'DART DOCUMENT {stage}: downloaded {len(data)} bytes / attempt {attempt}')
            return bytes(data)
        except requests.RequestException as exc:
            last = type(exc).__name__
            print(f'DART DOCUMENT {stage}: attempt {attempt}/2 / {last}')
        finally:
            if response is not None:
                response.close()
        if attempt < 2:
            time.sleep(min(1, max(0, deadline - time.monotonic())))
    raise DocumentUnavailable(f'{stage}:{last}') from None


def _api_xml(content):
    if not zipfile.is_zipfile(io.BytesIO(content)):
        try:
            root = ET.fromstring(content)
            status = next((node.text for node in root.iter() if node.tag.rsplit('}', 1)[-1] == 'status'), None)
        except ET.ParseError:
            status = None
        status = status if isinstance(status, str) and re.fullmatch(r'[0-9]{3}', status) else 'unknown'
        if status in ACCESS_CODES:
            raise AccessDenied('API_status_' + status)
        raise DocumentUnavailable('API_status_' + status)
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = [item for item in archive.infolist() if item.filename.lower().endswith('.xml')]
            if len(entries) != 1 or entries[0].file_size > MAX_BYTES or entries[0].flag_bits & 1:
                raise DocumentUnavailable('ambiguous_or_oversized_xml')
            return archive.read(entries[0]).decode('utf-8')
    except (zipfile.BadZipFile, UnicodeError, RuntimeError) as exc:
        if isinstance(exc, DocumentUnavailable):
            raise
        raise DocumentUnavailable('invalid_xml_archive') from None


def fetch_contract_document(receipt, issuer, api_key=None, budget_seconds=120):
    """제한된 재시도와 공개 뷰어 대체 경로. 접근/인증/요청 제한은 우회하지 않는다.

    예산은 요청·청크 경계에서 검사하며 DNS/소켓 내부의 강제 종료 타이머는 아니다.
    본문 회사명·공급계약 표제 검사 후에도 거래상대·금액은 수동 원문 검토가 필요하다.
    """
    if not isinstance(receipt, str) or not re.fullmatch(r'[0-9]{14}', receipt):
        raise ValueError('invalid_receipt')
    datetime.strptime(receipt[:8], '%Y%m%d')
    if not isinstance(issuer, str) or not issuer.strip():
        raise ValueError('missing_issuer')
    if isinstance(budget_seconds, bool) or not isinstance(budget_seconds, (int, float)) or not 0 < budget_seconds <= 240:
        raise ValueError('invalid_budget')
    deadline = time.monotonic() + budget_seconds
    errors = []
    raw = None
    route = None
    if api_key:
        try:
            data = _download('https://opendart.fss.or.kr/api/document.xml',
                             {'crtfc_key': api_key, 'rcept_no': receipt}, 'API', deadline)
            raw = _api_xml(data)
            route = 'opendart_xml'
        except AccessDenied:
            raise
        except (DocumentUnavailable, UnicodeError) as exc:
            errors.append(str(exc) if isinstance(exc, DocumentUnavailable) else 'API_encoding_error')
    if raw is None:
        page = _decode(_download('https://dart.fss.or.kr/dsaf001/main.do', {'rcpNo': receipt}, 'PUBLIC_PAGE', deadline))
        title = re.search(r'<title[^>]*>(.*?)</title>', page, re.I | re.S)
        if not title or issuer not in visible_text(title.group(1)):
            raise DocumentUnavailable('public_page_issuer_mismatch')
        # 공개 페이지에서 확인한 원본 경로만 사용한다. 문서번호를 추측하지 않는다.
        matches = re.findall(r'viewDoc\(\s*["\'](\d+)["\']\s*,\s*["\'](\d+)["\']\s*,\s*["\']0["\']\s*,\s*["\']0["\']\s*,\s*["\']0["\']\s*,\s*["\']HTML["\']', page)
        refs = {(r, d) for r, d in matches if r == receipt}
        if len(refs) != 1:
            raise DocumentUnavailable('original_viewer_reference_unavailable')
        _, document_id = refs.pop()
        raw = _decode(_download('https://dart.fss.or.kr/report/viewer.do',
            {'rcpNo': receipt, 'dcmNo': document_id, 'eleId': '0', 'offset': '0', 'length': '0', 'dtd': 'HTML'},
            'PUBLIC_VIEWER', deadline))
        route = 'dart_public_viewer'
    text = visible_text(raw)
    if issuer not in text or '공급계약' not in text.replace(' ', '') or '단일판매' not in text.replace(' ', ''):
        raise DocumentUnavailable('contract_document_content_mismatch')
    if api_key:
        text = text.replace(api_key, '[REDACTED]')
    return {'receipt_no': receipt, 'issuer': issuer, 'route': route,
            'source_url': 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=' + receipt,
            'document_sha256': sha256(raw.encode('utf-8')).hexdigest(), 'text': text,
            'api_failures': errors, 'order_registered': False, 'score_effect': 0}
