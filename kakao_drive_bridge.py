"""Private Drive intake; chat text never enters the investment engine.

Only an exact URL join to an issuer/publisher RSS record is eligible. The
original article owns title, body and publication date. Unknown links stay pending.
"""
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
import requests
from event_identity_engine import canonical_link
from kakao_news_source import parse_export, select_new_posts

FOLDER = '188Lv-7_iifjiYyiUyiJXNPrHFmSzbpd3'
BASELINE = '1eMOugPMULBShjb2Ya9d8KlLS1dRThgmt'
API = 'https://www.googleapis.com/drive/v3/files'
PRIMARY = {'NVIDIA_Newsroom': 'nvidianews.nvidia.com',
           'PRNewswire_Tech': 'www.prnewswire.com'}
MAX_BYTES = 10 * 1024 * 1024
UTC = timezone.utc


def timestamp(value):
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return dt.astimezone(UTC) if dt.tzinfo else None
    except (ValueError, TypeError):
        return None


class DriveReader:
    def __init__(self, token, session=None):
        self.session = session or requests.Session()
        self.headers = {'Authorization': 'Bearer ' + token}

    def get(self, url, **kwargs):
        r = self.session.get(url, headers=self.headers, timeout=(5, 20),
                             allow_redirects=False, **kwargs)
        if r.status_code != 200:
            raise ValueError('drive_read_failed')
        return r

    def metadata(self, file_id):
        return self.get(API + '/' + file_id,
                        params={'fields': 'id,name,mimeType,parents,size,modifiedTime'}).json()

    def read(self, metadata):
        if (FOLDER not in metadata.get('parents', [])
                or metadata.get('mimeType') != 'text/plain'
                or not metadata.get('name', '').endswith('.txt')
                or not 0 < int(metadata.get('size', 0)) <= MAX_BYTES):
            raise ValueError('invalid_drive_export')
        response = self.get(API + '/' + metadata['id'], params={'alt': 'media'}, stream=True)
        try:
            chunks, total = [], 0
            for chunk in response.iter_content(65536):
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError('export_too_large')
                chunks.append(chunk)
            return b''.join(chunks)
        finally:
            response.close()

    def latest(self):
        # Pagination is necessary even when a provider page has no usable TXT.
        files, token = [], None
        for _ in range(100):
            params = {'q': "'%s' in parents and trashed = false and mimeType = 'text/plain'" % FOLDER,
                      'fields': 'nextPageToken,files(id,name,mimeType,parents,size,modifiedTime)',
                      'orderBy': 'modifiedTime desc', 'pageSize': 100}
            if token:
                params['pageToken'] = token
            data = self.get(API, params=params).json()
            files.extend(f for f in data.get('files', []) if f.get('name', '').endswith('.txt'))
            token = data.get('nextPageToken')
            if not token:
                break
        else:
            raise ValueError('folder_listing_incomplete')
        if not files:
            raise ValueError('no_txt_export')
        return max(files, key=lambda f: f['modifiedTime'])


def access_token(session=None):
    values = [os.environ.get(k, '') for k in
              ('ORION_DRIVE_CLIENT_ID', 'ORION_DRIVE_CLIENT_SECRET', 'ORION_DRIVE_REFRESH_TOKEN')]
    if not all(values):
        return None
    session = session or requests
    response = session.post('https://oauth2.googleapis.com/token',
                            data=dict(zip(('client_id', 'client_secret', 'refresh_token'), values),
                                      grant_type='refresh_token'), timeout=(5, 20),
                            allow_redirects=False)
    if response.status_code != 200:
        raise ValueError('drive_auth_failed')
    return response.json()['access_token']


def join_originals(posts, originals, now):
    index = {}
    for article in originals:
        key = canonical_link(article.get('link', ''))
        stamp = timestamp(article.get('published_at'))
        host = urlsplit(key).hostname
        if (article.get('publication_verified_by') != 'Publisher_RSS'
                or urlsplit(key).scheme != 'https'
                or host != PRIMARY.get(article.get('source'))
                or not stamp or not now - timedelta(hours=36) <= stamp <= now):
            continue
        index.setdefault(key, []).append(article)
    joined, pending, seen = [], [], set()
    for post in posts:
        matched = False
        for url in post.get('urls', []):
            key = canonical_link(url)
            candidates = index.get(key, [])
            if not candidates or len({timestamp(a['published_at']) for a in candidates}) != 1:
                continue
            matched = True
            if key not in seen:
                seen.add(key)
                joined.append(dict(candidates[0], kakao_posted_at=post['posted_at'],
                                   kakao_message_id=post['message_id']))
        if not matched:
            pending.append(post)
    return joined, pending


def intake(reader, originals, state, now):
    metadata = reader.latest()
    posts = parse_export(reader.read(metadata))
    # Bootstrap against the acknowledged baseline, never historical chat replay.
    known = set(state.get('known_ids', []))
    if not state.get('initialized'):
        baseline = posts if metadata['id'] == BASELINE else parse_export(reader.read(reader.metadata(BASELINE)))
        known.update(p['message_id'] for p in baseline)
    recent = select_new_posts(posts, known, now=now, hours=1 if not state.get('initialized') else 36)
    # Retry unresolved original links on every scan; no private chat text is stored.
    pending_index = {p['message_id']: p for p in state.get('pending', [])
                     if timestamp(p.get('posted_at')) and now - timedelta(hours=36) <= timestamp(p['posted_at']) <= now}
    for p in recent:
        pending_index[p['message_id']] = {
            'message_id': p['message_id'], 'posted_at': p['posted_at'],
            # Persist only supported public original URLs, never chat text,
            # sender identities, arbitrary attachments or private link tokens.
            'urls': list(dict.fromkeys(canonical_link(url) for url in p['urls']
                         if urlsplit(url).scheme == 'https'
                         and urlsplit(url).hostname in PRIMARY.values()))}

    joined, pending = join_originals(list(pending_index.values()), originals, now)
    modified = timestamp(metadata['modifiedTime'])
    report = {'status': 'ok', 'file_id': metadata['id'], 'modified_at': metadata['modifiedTime'],
              'last_posted_at': max((p['posted_at'] for p in posts), default=None),
              'new_leads': len(recent), 'verified_articles': len(joined),
              'pending_unverified': len(pending),
              'file_stale': bool(modified and now - modified > timedelta(minutes=30))}
    # Commit the checkpoint only after successful parsing and verification.
    state.update(initialized=True, known_ids=list(dict.fromkeys(p['message_id'] for p in posts)),
                 pending=pending, last_scan=report)
    return joined, report


def collect(originals, state=None, diagnostics=None, *, reader=None, now=None):
    state = state if state is not None else {}
    now = now or datetime.now(UTC)
    try:
        if reader is None:
            token = access_token()
            if not token:
                report = {'status': 'not_configured', 'verified_articles': 0}
                if diagnostics is not None:
                    diagnostics['Kakao_Drive'] = report
                print('카톡 Drive 연결: not_configured (읽기 인증 필요)')
                return []
            reader = DriveReader(token)
        articles, report = intake(reader, originals, state, now)
    except Exception as exc:
        # Never log tokens, private URLs, response bodies or chat text.
        articles, report = [], {'status': 'error', 'error_type': type(exc).__name__}
    if diagnostics is not None:
        diagnostics['Kakao_Drive'] = report
    print('카톡 Drive 연결:', report.get('status'), '| 신규:', report.get('new_leads', 0),
          '| 원문 확인:', report.get('verified_articles', 0),
          '| 미검증 보류:', report.get('pending_unverified', 0))
    return articles
