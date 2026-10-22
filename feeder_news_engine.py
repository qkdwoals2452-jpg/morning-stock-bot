"""Optional Feeder transport; only Nasdaq RSS-confirmed articles are eligible."""
from datetime import datetime, timezone
from urllib.parse import urlsplit
from event_identity_engine import canonical_link


def verified_feeder_articles(items, originals):
    """Join by canonical URL; never substitute Feeder ingestion time for publication."""
    index = {}
    for article in originals:
        key = canonical_link(article.get('link', ''))
        try:
            dt = datetime.fromisoformat(article.get('published_at', '').replace('Z', '+00:00'))
            if dt.tzinfo is None:
                continue
        except (ValueError, TypeError, AttributeError):
            continue
        if key:
            index.setdefault(key, []).append((article, dt.astimezone(timezone.utc)))
    result, seen = [], set()
    counts = dict(received=len(items), duplicates=0, unverified=0, date_conflicts=0)
    for item in items:
        if not isinstance(item, dict):
            counts['unverified'] += 1
            continue
        key = canonical_link(item.get('url', ''))
        host = urlsplit(key).hostname or ''
        if not key or host not in ('nasdaq.com', 'www.nasdaq.com'):
            counts['unverified'] += 1
            continue
        if key in seen:
            counts['duplicates'] += 1
            continue
        seen.add(key)
        candidates = index.get(key, [])
        if not candidates or len({dt for _, dt in candidates}) != 1:
            counts['unverified'] += 1
            continue
        original, dt = candidates[0]
        # Original title/summary and time win, including on conflicting Feeder dates.
        try:
            feeder_dt = datetime.fromisoformat(str(item.get('date_published', '')).replace('Z', '+00:00'))
            conflict = feeder_dt.tzinfo is None or feeder_dt.astimezone(timezone.utc) != dt
        except (ValueError, TypeError):
            conflict = True
        counts['date_conflicts'] += int(conflict)
        result.append(dict(original, source='Nasdaq_Feeder_Verified',
                           published_at=dt.isoformat(), publication_verified_by='Nasdaq_Stocks_RSS'))
    counts['verified'] = len(result)
    return result, counts


def fetch_verified_feeder(url, originals, diagnostics=None):
    """Fetch an explicitly configured export without logging its address.

    Caller must supply trusted original RSS articles. Empty/failed originals
    deliberately produce no usable articles, rather than trusting proxy dates.
    """
    import requests
    report = {'status': 'error', 'http_status': None}
    try:
        parts = urlsplit(url)
        if parts.scheme != 'https' or parts.hostname != 'feeder.co' or not parts.path.startswith('/out/f/'):
            raise ValueError('invalid_export_url')
        response = requests.get(url, timeout=(3, 5), allow_redirects=False)
        report['http_status'] = response.status_code
        if response.status_code != 200:
            raise ValueError('http_error')
        data = response.json()
        if (not isinstance(data, dict) or data.get('version') != 'https://jsonfeed.org/version/1.1'
                or not isinstance(data.get('items'), list)):
            raise ValueError('invalid_json_feed')
        articles, counts = verified_feeder_articles(data['items'], originals)
        report.update(counts, status='ok' if articles else 'no_verified_articles')
    except (requests.RequestException, ValueError, TypeError):
        articles = []
        report['error'] = 'fetch_or_validation_failed'
    if diagnostics is not None:
        diagnostics['Nasdaq_Feeder_Verified'] = report
    return articles
