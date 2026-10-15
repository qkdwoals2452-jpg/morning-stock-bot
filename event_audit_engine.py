"""Bounded decision logs; no files, HTTP requests or scoring changes."""
from collections import defaultdict
import json
import re


def safe_text(value, limit=240):
    text = re.sub(r'https?://\S+', '[URL]', str(value or ''), flags=re.I)
    text = re.sub(r'\b(?:api[_-]?key|token|authorization|password)\s*[:=]\s*\S+',
                  '[REDACTED]', text, flags=re.I)
    return re.sub(r'\s+', ' ', text).strip()[:limit]


def print_event_audit(decisions, event_count, sample_limit=24, per_reason_limit=2):
    """Count every decision; sample exclusions fairly across market/role/reason.

    Samples are headlines only and cannot replay full article bodies. Counts are
    article decisions, whereas event_count is the number of merged events.
    """
    accepted = sum(bool(row['accepted']) for row in decisions)
    print('사건 판정 집계:', json.dumps({
        'input_articles': len(decisions), 'accepted_articles': accepted,
        'rejected_articles': len(decisions) - accepted,
        'merged_events': event_count,
    }, ensure_ascii=False))
    buckets = defaultdict(list)
    for row in decisions:
        if not row['accepted']:
            key = (safe_text(row['market'], 16), safe_text(row['role'], 48),
                   safe_text(row['reason']))
            buckets[key].append(row)
    for (market, role, reason), rows in sorted(buckets.items()):
        print('사건 제외 사유:', json.dumps({
            'market': market, 'role': role, 'reason': reason, 'count': len(rows),
        }, ensure_ascii=False))
    # Round-robin prevents one common reason from consuming the sample budget.
    selected = []
    for index in range(max(0, per_reason_limit)):
        for key in sorted(buckets):
            rows = buckets[key]
            if index < len(rows) and len(selected) < max(0, sample_limit):
                selected.append(rows[index])
    for row in selected:
        print('사건 제외 표본:', json.dumps({
            key: safe_text(row[key]) if key != 'score' else row[key]
            for key in ('market', 'source', 'role', 'score', 'reason', 'title')
        }, ensure_ascii=False))
    print('사건 제외 표본 범위:', json.dumps({
        'shown': len(selected), 'omitted': len(decisions) - accepted - len(selected),
        'basis': 'headline_only_not_full_article_replay',
    }, ensure_ascii=False))
