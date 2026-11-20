"""Read public originals on explicitly supported hosts, never chat assertions."""
import json
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit

import requests

ORIGINAL_HOSTS = {
    'www.reuters.com': 'Reuters_Original',
    'nvidianews.nvidia.com': 'NVIDIA_Original',
    'ir.coherent.com': 'Coherent_Original',
    'investor.nvidia.com': 'NVIDIA_IR_Original',
    'investors.micron.com': 'Micron_Original',
    'newsroom.intel.com': 'Intel_Original',
    'www.anthropic.com': 'Anthropic_Original',
    'www.lumentum.com': 'Lumentum_Original',
}
MAX_BYTES = 2 * 1024 * 1024
MAX_FETCHES = 2


def supported_url(url):
    try:
        p = urlsplit(url)
        return (p.scheme == 'https' and p.hostname in ORIGINAL_HOSTS
                and not p.username and not p.password and p.port in (None, 443))
    except (TypeError, ValueError):
        return False


class StructuredArticle(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.buffer = []
        self.nodes = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.active = dict(attrs).get('type', '').lower() == 'application/ld+json'
            self.buffer = []

    def handle_data(self, value):
        if self.active:
            self.buffer.append(value)

    def handle_endtag(self, tag):
        if tag == 'script' and self.active:
            try:
                self.nodes.append(json.loads(''.join(self.buffer)))
            except (ValueError, TypeError):
                pass
            self.active = False


def _articles(node):
    if isinstance(node, list):
        for child in node:
            yield from _articles(child)
    elif isinstance(node, dict):
        types = node.get('@type', [])
        types = [types] if isinstance(types, str) else types
        if isinstance(types, list) and any(t in ('NewsArticle', 'Article', 'ReportageNewsArticle') for t in types):
            yield node
        if '@graph' in node:
            yield from _articles(node['@graph'])


def parse_original(html, url, now):
    if not supported_url(url) or now.tzinfo is None:
        return None
    from event_identity_engine import canonical_link
    parser = StructuredArticle()
    parser.feed(html)
    candidates = []
    for node in _articles(parser.nodes):
        identity = node.get('url') or node.get('mainEntityOfPage')
        if isinstance(identity, dict):
            identity = identity.get('@id') or identity.get('url')
        try:
            if not supported_url(identity) or canonical_link(identity) != canonical_link(url):
                continue
            stamp = datetime.fromisoformat(str(node.get('datePublished', '')).replace('Z', '+00:00'))
            if stamp.tzinfo is None or not now - timedelta(hours=36) <= stamp <= now:
                continue
        except (TypeError, ValueError):
            continue
        title, body = node.get('headline'), node.get('articleBody')
        # A description, search snippet, dateModified or chat text cannot replace the original.
        if not isinstance(title, str) or not isinstance(body, str) or len(body.strip()) < 80:
            continue
        candidates.append({'title': title.strip(), 'summary': body.strip(),
            'published_at': stamp.astimezone(timezone.utc).isoformat(),
            'link': canonical_link(url), 'source': ORIGINAL_HOSTS[urlsplit(url).hostname],
            'market': 'US', 'publication_verified_by': 'Publisher_Article_JSONLD',
            'content_kind': 'publisher_article'})
    if len({(a['title'], a['summary'], a['published_at']) for a in candidates}) != 1:
        return None
    return candidates[0]


def fetch_original(url, now, session=None):
    if not supported_url(url):
        return None
    session = session or requests
    response = None
    try:
        response = session.get(url, timeout=(3, 8), allow_redirects=False, stream=True,
                               headers={'User-Agent': 'ORION public-source research'})
        if response.status_code != 200 or 'text/html' not in response.headers.get('Content-Type', ''):
            return None
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > MAX_BYTES:
                return None
            chunks.append(chunk)
        return parse_original(b''.join(chunks).decode('utf-8', errors='replace'), url, now)
    except (requests.RequestException, ValueError, TypeError):
        return None
    finally:
        if response is not None:
            response.close()
