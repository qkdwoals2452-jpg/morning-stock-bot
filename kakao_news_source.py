"""Read-only Kakao TXT intake. Posts are research leads, not verified news.

No scraping, external requests, Telegram sends, or source-file modifications.
The caller owns authenticated transport and persistent checkpoints.
"""
import hashlib
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

ROOM = '[정보방] 미국 주식 뉴스 공장'
KST = timezone(timedelta(hours=9))
DATE = re.compile(r'^-+ (\d{4})년 (\d{1,2})월 (\d{1,2})일 .+ -+$')
MESSAGE = re.compile(r'^\[(.+?)\] \[(오전|오후) (\d{1,2}):(\d{2})\] ?(.*)$')
URL = re.compile(r'https?://[^\s<>]+')
SYSTEM = re.compile(r'^.+님이 (?:들어왔습니다|나갔습니다|퇴장했습니다)\.$')
MEDIA = {'사진', '동영상', '이모티콘', '삭제된 메시지입니다.'}


def decode_export(raw):
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        return raw.decode('utf-16')
    for encoding in ('utf-8-sig', 'cp949'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise ValueError('unsupported_export_encoding')


def parse_export(raw, room=ROOM):
    """Preserve Korean posting time; never use export time as publication time."""
    text = decode_export(raw)
    lines = text.splitlines()
    if not lines or lines[0].strip() != room + ' 님과 카카오톡 대화':
        raise ValueError('wrong_room')
    posts, day, current = [], None, None

    def flush():
        if current:
            current['text'] = '\n'.join(current.pop('lines')).strip()
            posts.append(current.copy())

    for line in lines[1:]:
        date = DATE.fullmatch(line)
        if date:
            flush()
            current = None
            day = tuple(map(int, date.groups()))
            datetime(*day)  # reject invalid dates instead of guessing
            continue
        match = MESSAGE.fullmatch(line)
        if match:
            flush()
            sender, period, hour, minute, body = match.groups()
            hour, minute = int(hour), int(minute)
            if day is None or not 1 <= hour <= 12 or not 0 <= minute <= 59:
                raise ValueError('invalid_message_time')
            stamp = datetime(*day, hour % 12 + (12 if period == '오후' else 0), minute, tzinfo=KST)
            current = {'sender': sender, 'posted_at': stamp.isoformat(), 'lines': [body]}
        elif SYSTEM.fullmatch(line):
            flush()
            current = None
        elif current:
            current['lines'].append(line)
    flush()
    occurrences = Counter()
    for post in posts:
        value = '\0'.join((room, post['sender'], post['posted_at'], post['text']))
        occurrence = occurrences[value]
        occurrences[value] += 1
        post['message_id'] = hashlib.sha256((value + '\0' + str(occurrence)).encode()).hexdigest()
        post['room'] = room
        post['source_kind'] = 'kakao_research_lead'
        post['publication_verified'] = False
        post['urls'] = list(dict.fromkeys(
            url.rstrip(').,;]') for url in URL.findall(post['text'])
            if urlsplit(url).hostname
        ))
        post['media_only'] = post['text'] in MEDIA
    return posts


def select_new_posts(posts, known_ids, *, now, hours=36):
    """Bound historical backfills and deduplicate cumulative export snapshots.

    known_ids must be checkpointed by the caller AFTER durable intake succeeds.
    This function does not mark anything processed or send any alerts.
    """
    if now.tzinfo is None:
        raise ValueError('timezone_required')
    selected, seen = [], set(known_ids)
    for post in posts:
        stamp = datetime.fromisoformat(post['posted_at'])
        if stamp.tzinfo is None:
            raise ValueError('timezone_required')
        if (post['message_id'] in seen or post['media_only']
                or not now - timedelta(hours=hours) <= stamp <= now):
            continue
        seen.add(post['message_id'])
        selected.append(post)
    return selected
