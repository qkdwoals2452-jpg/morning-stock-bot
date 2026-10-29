"""Live RSS event alerts. Durable outbox reservations precede Telegram requests.

The dedicated state branch is serialized by the workflow. A crash during an API
request leaves an uncertain delivery for operator review, never an automatic resend.
"""
import hashlib
import html
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from event_engine import build_events
from event_identity_engine import canonical_link, same_event
from news_engine import get_us_news, get_korea_news
from telegram_bot import send_message
from breaking_event_gate import headline_action

UTC = timezone.utc
KST = ZoneInfo('Asia/Seoul')
TYPES = {'CAPEX', 'CONTRACT', 'M&A', 'EARNINGS', 'PRODUCTION', 'POLICY', 'FOMC'}
BOOTSTRAP_MINUTES = 30
RETENTION_DAYS = 7


def timestamp(value):
    try:
        stamp = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        # Unknown zones must not turn an old Korean article into a breaking story.
        return stamp.astimezone(UTC) if stamp.tzinfo else None
    except (ValueError, TypeError):
        return None


def article_time(article):
    return timestamp(article.get('published_at'))


def qualified(event):
    return (event.get('event_score', 0) >= 70 and event.get('event_type') in TYPES
            and headline_action(event)
            and event.get('evidence_strength') in {'STRONG', 'MEDIUM'}
            and (event.get('event_type') != 'EARNINGS'
                 or event.get('evidence_strength') == 'STRONG'))


def equivalent(left, right):
    if left.get('event_type') != right.get('event_type'):
        return False
    if left.get('event_key') and left['event_key'] == right.get('event_key'):
        return True
    # Require pairwise agreement so a vague article cannot bridge different deals.
    a, b = left.get('articles', []), right.get('articles', [])
    return bool(a and b and all(same_event(x, y) for x in a for y in b))


def escaped(value, limit=500):
    return html.escape(html.unescape(str(value or ''))[:limit])


def notice(event, now):
    article = max(event['articles'], key=article_time)
    published = article_time(article)
    label = '새 뉴스 감지' if now - published <= timedelta(minutes=30) else '지연 발견 뉴스'
    return (f'🚨 ORION {label} · 1차\n\n'
            f"{escaped(event['event_title'])}\n\n"
            f"유형: {escaped(event['event_type'])} / 사건 점수 {event['event_score']}\n"
            f"기사 근거: {escaped(event['evidence_strength'])}\n"
            f"발행: {published.astimezone(KST):%m/%d %H:%M} KST\n"
            f"감지: {now.astimezone(KST):%m/%d %H:%M} KST\n"
            f"출처: {escaped(article.get('source'))}\n"
            f'<a href="{html.escape(canonical_link(article["link"]), quote=True)}">원문 보기</a>\n\n'
            '기사 기반 알림입니다. 국내 종목 연결과 재무·가격 조건을 추가 검증합니다.')


def followup(event, results, status, failed=False):
    message = f'🔎 ORION 후속 검증 · 2차\n\n{escaped(event["event_title"])}\n\n'
    if failed:
        return message + '외부 데이터 조회·분석이 3회 실패했습니다. 종목 검증 보류로 기록했으며 운영 확인이 필요합니다.'
    analysis = status['analysis_status']
    message += (f"분석 종목 {analysis['analyzed_count']}개 / "
                f"검증 통과 {analysis['selected_count']}개\n")
    connections = analysis.get('connections', [])
    for item in connections[:2]:
        role = '기사상 사건 주체' if item['role'] == 'EVENT_ACTOR' else '기사상 거래 상대방'
        message += escaped(f"연결 근거: {item['name']} ({item['code']}) · {role}", 180) + '\n'
        for proof in item.get('evidence', [])[:1]:
            amounts = proof.get('amount_text', [])
            if amounts:
                message += '기사 기재 금액: ' + escaped(', '.join(amounts[:2]), 80) + '\n'
            url = canonical_link(proof.get('link'))
            if url:
                message += '<a href="' + html.escape(url, quote=True) + '">사건 당사자 근거 원문</a>\n'
    if connections:
        message += '기사상 거래 연결이며 계약별 매출 인식·이익 효과는 별도 검증이 필요합니다.\n'
    seen = set()
    for block in results:
        for stock in block.get('ranked', []):
            if stock['code'] not in seen and len(seen) < 5:
                seen.add(stock['code'])
                message += escaped(f"• {stock['name']} ({stock['code']}): {stock['final_score']}점") + '\n'
    if not analysis['selected_count']:
        message += ('국내 직접 분석 후보가 연결되지 않았습니다.\n' if not analysis['analyzed_count']
                    else '최종 검증 조건을 통과한 종목이 없습니다.\n')
    for item in analysis.get('excluded', [])[:5]:
        message += escaped(f"• {item['name']} ({item['code']}): {item['reason']}", 220) + '\n'
    paths = status.get('supply_chain_watch', {}).get('paths', [])
    for path in paths[:3]:
        message += '\n공급망 관찰: ' + escaped(' → '.join(path['path']), 200) + '\n'
        message += '기존 거래 관계만 확인. 이번 사건의 신규 수주·매출·이익 귀속은 미확정입니다.\n'
        for edge in path.get('evidence', [])[:2]:
            url = canonical_link(edge.get('source_url'))
            if url:
                message += '<a href="' + html.escape(url, quote=True) + '">관계 근거 원자료</a>\n'
    message += '\n가격 조건은 최근 정규장 일봉 기준이며 실시간 체결가 검증은 아닙니다.'
    if len(message) > 3500:
        # Rebuild complete HTML fragments; never slice an anchor or escaped entity.
        message = ('🔎 ORION 후속 검증 · 2차\n\n' + escaped(event['event_title'])
                   + f"\n\n분석 종목 {analysis['analyzed_count']}개 / 검증 통과 {analysis['selected_count']}개\n")
        for block in results[:2]:
            for stock in block.get('ranked', [])[:2]:
                message += escaped(f"• {stock['name']} ({stock['code']}): {stock['final_score']}점", 160) + '\n'
        for item in analysis.get('excluded', [])[:3]:
            message += escaped(f"• {item['name']} ({item['code']}): {item['reason']}", 160) + '\n'
        message += '\n상세 거래 근거는 1차 알림의 원문을 확인하세요. 매출·이익 귀속은 별도 검증이 필요합니다.\n가격 조건은 최근 정규장 일봉 기준입니다.'
    return message


class GitState:
    """Persist to a separate branch; failed pushes prohibit external sends."""
    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = self.directory / 'data/breaking_state.json'

    def load(self):
        if not self.path.exists():
            return {'version': 1, 'records': [], 'activation': {'phase': 'ready'}}
        state = json.loads(self.path.read_text())
        if state.get('version') != 1 or not isinstance(state.get('records'), list):
            raise RuntimeError('속보 상태 파일 검증 실패: 자동 초기화 금지')
        return state

    def save(self, state):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
        temporary.replace(self.path)
        def git(*args):
            result = subprocess.run(['git', '-C', str(self.directory), *args],
                                    capture_output=True, check=False)
            if result.returncode:
                raise RuntimeError('속보 상태 Git 저장 실패: 전송 중단')
        git('add', '--', 'data/breaking_state.json')
        changed = subprocess.run(['git', '-C', str(self.directory), 'diff', '--cached', '--quiet'])
        if changed.returncode == 1:
            git('-c', 'user.name=github-actions[bot]', '-c',
                'user.email=41898282+github-actions[bot]@users.noreply.github.com',
                'commit', '-m', 'chore: checkpoint live news alerts [skip ci]')
        elif changed.returncode:
            raise RuntimeError('속보 상태 변경 검사 실패')
        # Also push an existing local commit after a previous transient push failure.
        git('push', 'origin', 'HEAD:refs/heads/orion-alert-state')


def deliver(slot, message, state, save, send):
    if slot.get('phase') != 'ready':
        return False
    slot['phase'] = 'sending'
    save(state)  # Durable reservation before issuing any Telegram request.
    try:
        send(message)
    except Exception:
        slot['phase'] = 'uncertain'
        save(state)
        raise RuntimeError('텔레그램 전송 결과 불확실: 자동 재전송 없이 운영 확인 필요') from None
    slot['phase'] = 'sent'
    save(state)
    return True


def scan(state, news, now):
    """Queue newly discovered qualifying events; never replay bootstrap history."""
    initialized = bool(state.get('initialized_at'))
    cutoff = now - timedelta(days=RETENTION_DAYS)
    # Keep unresolved records even past retention for explicit operator review.
    state['records'] = [r for r in state['records'] if timestamp(r['seen_at']) >= cutoff
                        or r['notice']['phase'] not in {'sent', 'baseline', 'suppressed'}
                        or (r['notice']['phase'] == 'sent' and r['analysis']['phase'] != 'sent')]
    dated = [a for a in news if article_time(a) and canonical_link(a.get('link'))
             and timedelta(0) <= now - article_time(a) <= timedelta(hours=36)]
    added = baseline = 0
    for event in build_events(dated):
        if not headline_action(event):
            print('BREAKING HEADLINE REJECT:', event.get('event_type'), event.get('event_title', '')[:200])
        if not qualified(event) or any(equivalent(event, r['event']) for r in state['records']):
            continue
        latest = max(article_time(a) for a in event['articles'])
        old = not initialized and now - latest > timedelta(minutes=BOOTSTRAP_MINUTES)
        record = {'id': hashlib.sha256(event['event_key'].encode()).hexdigest()[:16],
                  'seen_at': now.isoformat(), 'event': event,
                  'notice': {'phase': 'baseline' if old else 'ready'},
                  'analysis': {'phase': 'ready', 'attempts': 0}}
        state['records'].append(record)
        baseline += int(old)
        added += int(not old)
    state.setdefault('initialized_at', now.isoformat())
    return added, baseline


def analyze(event):
    from main import run
    return run(news_override=event['articles'], notify=False, track_history=False)


def process(state, save, news, now=None, send=send_message, analyze_event=analyze):
    now = now or datetime.now(UTC)
    for record in state['records']:
        if record['notice']['phase'] == 'ready' and not qualified(record['event']):
            record['notice']['phase'] = 'suppressed'
            record['analysis']['phase'] = 'suppressed'
    added, baseline = scan(state, news, now)
    save(state)
    deliver(state['activation'],
            '🛰 ORION 속보 감시를 시작했습니다.\n\n'
            '미국·한국 RSS를 5분 간격으로 확인하도록 예약했습니다. '
            '신규 핵심 사건은 1차 뉴스 알림 → 2차 종목 검증 결과로 전송합니다.\n'
            '최초 실행에서는 30분보다 오래된 기사를 기준 기록으로만 남깁니다.\n'
            'RSS 반영과 GitHub 예약 실행 지연으로 실제 알림은 늦어질 수 있습니다.',
            state, save, send)
    notices = analyses = 0
    # All first notices precede expensive DART/chart work.
    for record in state['records']:
        if notices < 5 and record['notice']['phase'] == 'ready':
            notices += int(deliver(record['notice'], notice(record['event'], now), state, save, send))
    for record in state['records']:
        slot = record['analysis']
        if analyses >= 2 or record['notice']['phase'] != 'sent' or slot['phase'] != 'ready':
            continue
        analyses += 1
        if 'message' not in slot:
            try:
                results, status = analyze_event(record['event'])
                slot['message'] = followup(record['event'], results, status)
            except Exception as exc:
                slot['attempts'] += 1
                print('BREAKING ANALYSIS RETRY:', record['id'], slot['attempts'], type(exc).__name__)
                if slot['attempts'] >= 3:
                    slot['message'] = followup(record['event'], [], {}, failed=True)
                save(state)
                if 'message' not in slot:
                    continue
        deliver(slot, slot['message'], state, save, send)
    uncertain = sum(slot['phase'] in {'sending', 'uncertain'} for slot in
                    [state['activation']] + [r[p] for r in state['records'] for p in ('notice', 'analysis')])
    pending = sum(r['notice']['phase'] == 'ready' or
                  (r['notice']['phase'] == 'sent' and r['analysis']['phase'] == 'ready')
                  for r in state['records'])
    report = dict(collected=len(news), new=added, baseline=baseline,
                  notices=notices, analyses=analyses, pending=pending, uncertain=uncertain)
    print('BREAKING LIVE RESULT:', json.dumps(report, ensure_ascii=False))
    if uncertain:
        raise RuntimeError('미확정 전송이 남아 있습니다: 상태 브랜치에서 수신 여부 확인 필요')
    return report


def run():
    started = datetime.now(UTC)
    directory = os.environ.get('ORION_ALERT_STATE_DIR')
    if not directory:
        raise RuntimeError('영속 상태 경로 없이 실전 알림을 실행할 수 없습니다')
    store = GitState(directory)
    state = store.load()
    diagnostics = {}
    news = get_us_news(diagnostics=diagnostics, limit=None) + get_korea_news(diagnostics=diagnostics, limit=None)
    if not news:
        raise RuntimeError('수집 뉴스 0건: 감시 정상으로 기록하지 않습니다')
    report = process(state, store.save, news)
    previous = timestamp(state.get('last_poll', {}).get('started_at'))
    state['last_poll'] = {'started_at': started.isoformat(),
                          'previous_started_at': previous.isoformat() if previous else None,
                          'start_gap_seconds': round((started - previous).total_seconds(), 2) if previous else None,
                          'completed_at': datetime.now(UTC).isoformat(), **report}
    store.save(state)
    return report


if __name__ == '__main__':
    run()
