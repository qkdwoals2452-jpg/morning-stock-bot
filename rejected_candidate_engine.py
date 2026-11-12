"""Audit rejected candidates separately from recommendations and score learning."""
import json
import math
from pathlib import Path
from datetime import datetime, date
from zoneinfo import ZoneInfo
from chart_engine import get_price_history

FILE = Path('data/rejected_candidates.json')


def track_rejections(rejections, *, now=None, price_cache=None, historical=None):
    now = now or datetime.now(ZoneInfo('Asia/Seoul'))
    if now.tzinfo is None:
        raise ValueError('timezone required')
    now = now.astimezone(ZoneInfo('Asia/Seoul'))
    records = json.loads(FILE.read_text()) if FILE.exists() else []
    # Historical observations require an explicit dated source; never backdate live rows.
    for item in rejections:
        code = item.get('code', '')
        if not isinstance(code, str) or len(code) != 6 or not code.isdigit():
            continue
        decision_at = historical['decision_at'] if historical else now.isoformat()
        observed = datetime.fromisoformat(decision_at)
        if observed.tzinfo is None or observed > now:
            raise ValueError('invalid observation timestamp')
        key = (observed.astimezone(ZoneInfo('Asia/Seoul')).date().isoformat(), code,
               item.get('stage'), item.get('reason'))
        if any(tuple(r['key']) == key for r in records):
            continue
        records.append({'key': list(key), 'name': item.get('name'), 'code': code,
                        'decision_at': decision_at, 'recorded_at': now.isoformat(),
                        'decision': 'rejected_or_held', 'stage': item.get('stage'),
                        'reason': item.get('reason'), 'evidence': item.get('evidence', {}),
                        'provenance': historical or {'source': 'runtime_analysis'},
                        'evaluation': {}})
    for record in records:
        day = record['key'][0]
        # Historical returns are an exclusion audit, never a simulated buy signal.
        rows = get_price_history(record['code'], cache=price_cache, start_date=day)
        def valid(row):
            value = row.get('close')
            return (row.get('source') == 'YAHOO_REGULAR_CLOSE'
                    and isinstance(value, (int, float)) and not isinstance(value, bool)
                    and math.isfinite(value) and value > 0)
        rows = sorted({r['date']: r for r in rows if valid(r)}.values(), key=lambda r: r['date'])
        # Freeze the reference close to the actual decision date; no previous-day substitution.
        base = next((r for r in rows if r['date'] == day), None)
        future = [r for r in rows if day < r['date'] <= now.date().isoformat()]
        evaluation = {'status': 'missing_decision_close', 'reference': 'decision_day_close',
                      'interpretation': 'exclusion_audit_not_tradable_return', 'checkpoints': {}}
        if base:
            evaluation.update(status='tracking', base_date=day, base_close=base['close'],
                              price_source=base['source'])
            for horizon in (1, 3, 5):
                if len(future) >= horizon:
                    row = future[horizon - 1]
                    evaluation['checkpoints'][str(horizon)] = {
                        'date': row['date'], 'close': row['close'],
                        'return_pct': round((row['close'] / base['close'] - 1) * 100, 4)}
        record['evaluation'] = evaluation
    FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(FILE)
    print('제외·보류 관찰 기록:', len(records), '(추천·학습 가산점과 분리)')
    return records
