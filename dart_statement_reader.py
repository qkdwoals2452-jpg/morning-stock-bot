"""Read one complete statement basis; never mix consolidated and separate rows."""
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from config import DART_API_KEY


def read_statement(corp_code, periods, as_of=None):
    as_of = as_of or datetime.now(ZoneInfo('Asia/Seoul')).date()
    attempts = []
    for year, report_code in periods:
        for basis in ('CFS', 'OFS'):
            attempt = {'year': year, 'report_code': report_code, 'fs_div': basis}
            attempts.append(attempt)
            try:
                response = requests.get(
                    'https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json',
                    params={'crtfc_key': DART_API_KEY, 'corp_code': corp_code,
                            'bsns_year': str(year), 'reprt_code': report_code,
                            'fs_div': basis}, timeout=10)
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:
                # Exception strings may contain the API key in a request URL.
                attempt['status'] = type(exc).__name__
                return None, {'status': 'transport_error', 'attempts': attempts}
            status = str(payload.get('status', 'missing_status'))
            attempt['status'] = status
            if status == '013':
                continue
            rows = payload.get('list')
            if status != '000' or not isinstance(rows, list) or not rows:
                return None, {'status': 'api_error' if status != '000' else 'empty_statement',
                              'attempts': attempts}
            receipts = {row.get('rcept_no', '') for row in rows} - {''}
            if any(r[:8] > as_of.strftime('%Y%m%d') for r in receipts):
                return None, {'status': 'not_available_as_of', 'attempts': attempts}
            return rows, {'status': 'ok', 'year': year, 'report_code': report_code,
                          'fs_div': basis,
                          'basis': 'annual' if report_code == '11011' else 'year_to_date',
                          'receipt_numbers': sorted(receipts), 'attempts': attempts}
    return None, {'status': 'no_statement', 'attempts': attempts}
