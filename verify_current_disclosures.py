"""Read-only live disclosure verification; no Telegram or tracking writes."""
from build_corp_db import ensure_corp_db
ensure_corp_db()
from finance_engine import get_dart_finance
for code in ('006400', '009540', '950200'):
    result = get_dart_finance(code)
    assert result.get('report'), f'{code}: no verified current report'
    assert result['op_margin'] is not None and result['debt_ratio'] is not None, f'{code}: incomplete finance'
    assert result['report']['receipt_numbers'], f'{code}: missing receipt provenance'
    print('LIVE DISCLOSURE:', code, result, flush=True)
