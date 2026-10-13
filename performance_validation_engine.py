"""평가 기간·확인 시점이 있는 완료 성과만 집계한다. 파일은 수정하지 않는다."""
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
import math
import re
from statistics import mean
from zoneinfo import ZoneInfo

SEOUL = ZoneInfo('Asia/Seoul')


def aware_timestamp(value):
    try:
        value = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return value.astimezone(SEOUL) if value.tzinfo is not None else None
    except (TypeError, ValueError):
        return None


def finite_number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def completed_performance(records, as_of=None, horizon=5):
    assessed = aware_timestamp(as_of or datetime.now(timezone.utc))
    excluded = Counter()
    groups = defaultdict(list)
    if assessed is None or not isinstance(horizon, int) or horizon not in (1, 3, 5, 10, 20) or isinstance(horizon, bool) or not isinstance(records, list):
        return {'status': 'invalid_input', 'samples': [], 'count': 0,
                'accuracy': None, 'average': None, 'excluded': {}}
    field = f'result_{horizon}d'
    for record in records:
        if not isinstance(record, dict):
            excluded['invalid_record'] += 1
            continue
        code = str(record.get('code', ''))
        if not re.fullmatch(r'[0-9]{6}', code) or code == '000000':
            excluded['invalid_record'] += 1
            continue
        try:
            recommended = date.fromisoformat(record.get('date', ''))
            dates = record.get('checkpoint_dates') or {}
            completed = date.fromisoformat(dates.get(field, ''))
        except (TypeError, ValueError, AttributeError):
            excluded['pending_or_missing_date'] += 1
            continue
        observed = record.get('checkpoint_observed_at') or {}
        observed = aware_timestamp(observed.get(field)) if isinstance(observed, dict) else None
        if record.get('checkpoint_method') != 'trading_sessions_v1' or observed is None:
            excluded['unverified_provenance'] += 1
            continue
        if (recommended >= assessed.date() or completed >= assessed.date()
                or observed > assessed):
            excluded['not_available_at_as_of'] += 1
            continue
        value, start = record.get(field), record.get('start_price')
        if ((completed - recommended).days < horizon or observed.date() < completed
                or not finite_number(value) or value < -100
                or not finite_number(start) or start <= 0):
            excluded['invalid_record'] += 1
            continue
        groups[(recommended.isoformat(), code)].append({
            'code': code, 'name': record.get('name', ''), 'date': recommended.isoformat(),
            'completed_date': completed.isoformat(), 'observed_at': observed.isoformat(),
            'return': value, 'horizon': horizon})
    samples = []
    for key in sorted(groups):
        group = groups[key]
        if len({(row['completed_date'], row['return']) for row in group}) != 1:
            excluded['conflicting_duplicate_group'] += len(group)
            continue
        # 같은 종목·추천일이 여러 테마에 등장해도 성과는 한 번만 센다.
        samples.append(min(group, key=lambda row: row['observed_at']))
        excluded['duplicate_rows'] += len(group) - 1
    returns = [row['return'] for row in samples]
    count = len(returns)
    return {'status': 'available' if count else 'no_verified_outcomes',
            'as_of': assessed.isoformat(), 'horizon': horizon,
            'cutoff_policy': 'outcome_date_before_assessment_day',
            'return_basis': 'reference_price_only_before_costs',
            'samples': samples, 'count': count,
            'winners': sum(value > 0 for value in returns),
            'losers': sum(value < 0 for value in returns),
            'flat': sum(value == 0 for value in returns),
            'accuracy': round(sum(value > 0 for value in returns) / count * 100, 1) if count else None,
            'average': round(mean(returns), 2) if count else None,
            'excluded': dict(excluded)}
