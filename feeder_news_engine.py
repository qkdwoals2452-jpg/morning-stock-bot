"""Feeder transport with original Nasdaq RSS or article metadata verification."""
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
                           published_at=dt.isoformat(), publication_verified_by=original.get('publication_verified_by','Nasdaq_Stocks_RSS')))
    counts['verified'] = len(result)
    return result, counts



def original_from_article(body, url):
    """Require an exact canonical article identity and explicit publication date."""
    import json
    import html
    from html.parser import HTMLParser
    class Metadata(HTMLParser):
        def __init__(self):
            super().__init__(); self.canonical=[]; self.scripts=[]; self.active=False
        def handle_starttag(self, tag, attrs):
            a=dict(attrs)
            if tag=='link' and a.get('rel')=='canonical': self.canonical.append(a.get('href',''))
            if tag=='script' and a.get('type')=='application/ld+json':
                self.active=True; self.scripts.append('')
        def handle_endtag(self, tag):
            if tag=='script': self.active=False
        def handle_data(self, data):
            if self.active: self.scripts[-1]+=data
    parser=Metadata(); parser.feed(body)
    key=canonical_link(url)
    if {canonical_link(x) for x in parser.canonical}!={key}: return None
    candidates=[]
    def walk(node):
        if isinstance(node,list):
            for child in node: walk(child)
        elif isinstance(node,dict):
            kind=node.get('@type',[])
            if isinstance(kind,str): kind=[kind]
            if any(x in ('NewsArticle','Article','ReportageNewsArticle') for x in kind):
                identity=node.get('url') or node.get('mainEntityOfPage')
                if isinstance(identity,dict): identity=identity.get('@id')
                try:
                    dt=datetime.fromisoformat(node.get('datePublished','').replace('Z','+00:00'))
                    if dt.tzinfo and canonical_link(identity or '')==key and node.get('headline'):
                        candidates.append(dict(link=key,title=html.unescape(node['headline']),
                            summary=html.unescape(node.get('description','')),market='US',
                            published_at=dt.astimezone(timezone.utc).isoformat(),
                            publication_verified_by='Nasdaq_Article_JSONLD'))
                except (ValueError,TypeError,AttributeError): pass
            if '@graph' in node: walk(node['@graph'])
    for script in parser.scripts:
        try: walk(json.loads(script))
        except (ValueError,TypeError): pass
    if len({x['published_at'] for x in candidates})!=1: return None
    return candidates[0]


def fetch_article_originals(items, originals, limit=12):
    """Bounded independent article checks; never follow redirects to other hosts."""
    import requests
    from concurrent.futures import ThreadPoolExecutor
    known={canonical_link(x.get('link','')) for x in originals}
    urls=[]
    for item in items:
        if not isinstance(item,dict): continue
        url=canonical_link(item.get('url',''))
        parts=urlsplit(url)
        if (parts.scheme=='https' and parts.hostname in ('nasdaq.com','www.nasdaq.com')
                and parts.path.startswith('/articles/') and url not in known):
            known.add(url); urls.append(url)
        if len(urls)>=limit: break
    def fetch(url):
        try:
            r=requests.get(url,timeout=(3,5),allow_redirects=False)
            if r.status_code==200 and len(r.content)<=3000000:
                return original_from_article(r.text,url)
        except (requests.RequestException,ValueError,TypeError): pass
        return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        articles=[x for x in pool.map(fetch,urls) if x]
    return articles,dict(article_attempted=len(urls),article_verified=len(articles),
                         article_unverified=len(urls)-len(articles))


def fetch_verified_feeder(url, originals, diagnostics=None, *, verify_articles=False):
    """Fetch an explicitly configured export without logging its address.

    RSS matches are preferred. Optional article checks require canonical URL and
    explicit timezone-aware original publication metadata; proxy dates never win.
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
        if verify_articles:
            additional, audit = fetch_article_originals(data['items'], originals)
            originals = list(originals) + additional
            report.update(audit)
        articles, counts = verified_feeder_articles(data['items'], originals)
        report.update(counts, status='ok' if articles else 'no_verified_articles')
    except (requests.RequestException, ValueError, TypeError):
        articles = []
        report['error'] = 'fetch_or_validation_failed'
    if diagnostics is not None:
        diagnostics['Nasdaq_Feeder_Verified'] = report
    return articles
