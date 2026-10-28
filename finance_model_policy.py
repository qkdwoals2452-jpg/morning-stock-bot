"""Reviewed industrial holding companies are not deposit-taking institutions.

This only selects the ordinary consolidated finance model; it never bypasses
missing data, leverage, profitability, business or price checks.
"""
import re

INDUSTRIAL_HOLDINGS = {
    '009540': {
        'name': 'HD한국조선해양',
        'source_url': 'https://kind.krx.co.kr/external/2026/03/20/001327/20260320004889/11011.htm',
        'section': '사업의 내용 / 주요 사업: 조선, 해양플랜트, 엔진기계',
        'reviewed_on': '2026-10-28',
    },
}


def financial_model_unsupported(stock):
    sector = str(stock.get('sector', ''))
    # Only the ambiguous holding-company classification can use this review.
    reviewed = INDUSTRIAL_HOLDINGS.get(str(stock.get('code', '')))
    if (sector.strip() == '기타 금융업' and reviewed
            and stock.get('name') == reviewed['name']):
        return False
    return bool(re.search(r'금융|은행|저축기관|보험|증권', sector))
