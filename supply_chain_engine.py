"""공식 원자료에서 검토한 관계를 사건에 연결하는 관찰 계층. 추천/점수에는 사용하지 않는다."""
from collections import Counter
from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from event_identity_engine import canonical_link
from event_understanding_engine import understand_event
from pre_news_activity_engine import parse_timestamp

SEOUL = ZoneInfo('Asia/Seoul')
ALLOWED_HOSTS = {'REGULATORY_FILING': {'kind.krx.co.kr', 'dart.fss.or.kr'},
                 'CORPORATE_IR': {'investor.nvidia.com', 'investors.micron.com'}}
RELATIONSHIPS = {'REPORTED_CUSTOMER', 'MEMORY_TECH_AGREEMENT'}
MAX_SOURCE_AGE_DAYS = 366
NEGATIVE = re.compile(r'\b(?:not|never|denied|cancelled|canceled|could|might|rumou?r|reportedly)\b|미체결|부인|취소|검토|수주\s*기대', re.I)
SPENDING = re.compile(r'\b(?:capex|capital expenditures?|capital spending|invest(?:s|ed|ment|ments)?|supply contract|supply agreement|begins production|mass production)\b|설비투자|공급계약|양산', re.I)
NON_MANUFACTURING = re.compile(r'\bresearch labs?\b|\bresearch and development\b|\bR&D\b|\bbuybacks?\b|\bdividends?\b|연구소|자사주|배당', re.I)


def load_supply_chain_evidence():
    try:
        data = json.loads(Path(__file__).with_name('supply_chain_evidence.json').read_text(encoding='utf-8'))
        return data if data.get('schema_version') == 1 else None
    except (OSError, ValueError, AttributeError):
        return None


def _has_term(text, term):
    pattern = re.escape(term)
    if re.search(r'[a-zA-Z]', term):
        pattern = r'(?<![a-zA-Z0-9])' + pattern + r'(?![a-zA-Z0-9])'
    return bool(re.search(pattern, text, re.I))


def _edge_reason(edge, entities, as_of):
    if (not isinstance(edge, dict) or not isinstance(edge.get('buyer'), str)
            or not isinstance(edge.get('supplier'), str) or edge['buyer'] not in entities or edge['supplier'] not in entities):
        return 'invalid_edge'
    if edge['buyer'] == edge['supplier'] or not isinstance(edge.get('relationship'), str) or edge['relationship'] not in RELATIONSHIPS:
        return 'invalid_relationship'
    if not isinstance(edge.get('id'), str) or not edge['id']:
        return 'invalid_edge'
    try:
        url = urlsplit(edge.get('source_url', ''))
        if (url.scheme != 'https' or url.username or url.password or url.port not in (None, 443)
                or url.hostname not in ALLOWED_HOSTS.get(edge.get('source_kind'), set())):
            return 'unapproved_source'
        published = date.fromisoformat(edge['published_on'])
        relationship_day = date.fromisoformat(edge['relationship_as_of'])
        reviewed, assumed = parse_timestamp(edge['reviewed_at'])
    except (KeyError, TypeError, ValueError):
        return 'missing_evidence_dates'
    if not reviewed or assumed or reviewed > as_of:
        return 'unavailable_at_assessment'
    # 공개일만 있을 때 그 날짜의 시작에 이미 알았다고 가정하지 않는다.
    if datetime.combine(published, time.max, SEOUL) > as_of or relationship_day > published or reviewed.date() < published:
        return 'invalid_evidence_timeline'
    if (as_of.date() - published).days > MAX_SOURCE_AGE_DAYS:
        return 'stale_source'
    if edge.get('review_method') != 'manual_primary_source' or any(not isinstance(edge.get(k), str) or not edge[k] for k in ('evidence_summary', 'section')):
        return 'missing_reviewed_evidence'
    terms = edge.get('context_terms')
    if not isinstance(terms, list) or not terms or any(not isinstance(t, str) or not t for t in terms):
        return 'missing_product_context'
    return None


def _actor(entity, article):
    # 같은 문장의 기업 주체·금액 행동만 사용. 단순 고객명 언급은 출발 기업으로 삼지 않는다.
    aliases = '|'.join(re.escape(a) for a in sorted(entity['aliases'], key=len, reverse=True))
    pattern = re.compile(r'^\s*(?:' + aliases + r')(?=\s|[,，:]|은\s|는\s|이\s|가\s)', re.I)
    if not pattern.search(str(article.get('title', '') or '')):
        return None
    action_start = re.compile(r'^\s*[,，:]?\s*(?:은|는|이|가)?\s*'
        r'(?:(?:Technology|Inc\.?|Corporation|Corp\.?)\s*[,，]?\s*)*'
        r'(?:(?:will|plans?\s+to|has|had|to|today|is)\s+)*'
        r'(?:invest(?:s|ed)?|announc(?:es|ed)|sign(?:s|ed)?|report(?:s|ed)?|begins?|began|starts?|expands?|raises?|boosts?|투자|계약|양산)', re.I)
    for field in ('title', 'summary'):
        value = str(article.get(field, '') or '')
        sentences = [value] if field == 'title' else re.split(r'(?<=[!?。])\s+|\n|;|(?<=\.)\s+(?=[A-Z가-힣])', value)
        for sentence in sentences:
            match = pattern.search(sentence)
            if not match or NEGATIVE.search(sentence):
                continue
            tail = sentence[match.end():]
            if not action_start.search(tail):
                continue
            if re.search(r'\b(?:says?|said|analysts?)\b|따르면|경쟁사|주가|shares?', tail, re.I):
                continue
            # 실적의 CAPEX는 같은 기업 공식 IR의 실제 지출 문단만 허용한다.
            earnings_spending = (field == 'title' and understand_event(article).get('event_type') == 'EARNINGS'
                and urlsplit(article.get('link', '')).hostname in entity.get('official_hosts', [])
                and re.search(r'(?im)^\s*(?:Investments in capital expenditures|Capital expenditures)'
                              r'[^\n]{0,150}\bwere\b[^\n]{0,60}\$\s*[0-9]', str(article.get('summary', ''))))
            if SPENDING.search(sentence) or earnings_spending:
                return sentence.strip()
    return None


def build_supply_chain_watch(events, stocks, evidence=None, as_of=None):
    """공급망 경로를 관찰 목록에만 반환한다. 모든 경로는 신규 매출/이익 귀속 미확정이다."""
    now = as_of or datetime.now(SEOUL)
    now, assumed = parse_timestamp(now)
    report = {'status': 'ok', 'score_effect': 0, 'recommendation_eligible': False,
              'as_of': now.isoformat() if now else None, 'paths': [], 'excluded': {},
              'us_events_checked': 0, 'policy': 'reviewed_relationship_not_new_order'}
    book = evidence if evidence is not None else load_supply_chain_evidence()
    if not now or assumed or not isinstance(book, dict) or book.get('schema_version') != 1:
        report['status'] = 'evidence_unavailable'
        return report
    entities = book.get('entities', {})
    if not isinstance(entities, dict) or any(not isinstance(v, dict) or not isinstance(v.get('name'), str)
            or not v['name'] or v.get('country') not in ('US', 'KR') or not isinstance(v.get('aliases'), list)
            or not v['aliases'] or any(not isinstance(a, str) or not a for a in v['aliases'])
            or (v.get('country') == 'KR' and not re.fullmatch(r'[0-9A-Z]{6}', str(v.get('code', ''))))
            or not isinstance(v.get('official_hosts', []), list) for v in entities.values()):
        report['status'] = 'evidence_unavailable'
        return report
    excluded = Counter()
    graph = {}
    edges = book.get('edges', [])
    if not isinstance(edges, list):
        report['status'] = 'evidence_unavailable'
        return report
    for edge in edges:
        reason = _edge_reason(edge, entities, now)
        if reason:
            excluded[reason] += 1
        else:
            graph.setdefault(edge['buyer'], []).append(edge)
    listed = {str(s.get('code')): s for s in stocks if isinstance(s, dict)}
    seen = set()
    for event in events:
        if event.get('event_score', 0) < 70 or event.get('event_type') not in {'CAPEX', 'CONTRACT', 'PRODUCTION', 'EARNINGS'}:
            continue
        us_articles = [a for a in event.get('articles', []) if a.get('market') == 'US']
        if not us_articles:
            continue
        report['us_events_checked'] += 1
        for article in us_articles:
            stamp, _ = parse_timestamp(article.get('published_at'), article.get('source', ''))
            link = canonical_link(article.get('link'))
            if not stamp or stamp > now or not link:
                excluded['invalid_event_timestamp_or_link'] += 1
                continue
            if not understand_event(article).get('is_real_event'):
                excluded['not_real_event'] += 1
                continue
            text = ' '.join(str(article.get(k, '') or '') for k in ('title', 'summary'))
            if not SPENDING.search(text):
                excluded['no_spending_or_production_evidence'] += 1
                continue
            for start, entity in entities.items():
                if entity.get('country') != 'US':
                    continue
                actor_text = _actor(entity, article)
                if not actor_text:
                    continue
                if NON_MANUFACTURING.search(actor_text):
                    excluded['non_manufacturing_spending'] += 1
                    continue
                context = text if event.get('event_type') == 'EARNINGS' else actor_text
                def visit(node, path, nodes):
                    if len(path) >= 2:
                        return
                    for edge in graph.get(node, []):
                        target = edge['supplier']
                        if target in nodes:
                            continue
                        if not any(_has_term(context, t) for t in edge['context_terms']):
                            excluded['product_context_mismatch'] += 1
                            continue
                        # 최신 문서로 과거 사건 당시의 관계를 확인했다고 주장하지 않는다.
                        public_at = datetime.combine(date.fromisoformat(edge['published_on']), time.max, SEOUL)
                        if public_at > stamp:
                            excluded['source_published_after_event'] += 1
                            continue
                        route = path + [edge]
                        destination = entities[target]
                        code = destination.get('code')
                        stock = listed.get(code)
                        key = (event.get('event_key') or link, start, code, tuple(e['id'] for e in route))
                        if stock and stock.get('name') == destination.get('name') and key not in seen:
                            seen.add(key)
                            reviewed_before = all(parse_timestamp(e['reviewed_at'])[0] <= stamp for e in route)
                            report['paths'].append({
                                'event_key': event.get('event_key', ''), 'event_title': article.get('title', ''),
                                'event_link': link, 'event_published_at': stamp.isoformat(),
                                'actor_text': actor_text, 'company': stock['name'], 'code': code,
                                'path': [entities[n]['name'] for n in nodes + [target]],
                                'hops': len(route), 'evidence': deepcopy(route),
                                'status': 'DOCUMENTED_RELATION_EVENT_UNATTRIBUTED',
                                'knowledge_timing': 'known_before_event' if reviewed_before else 'retrospective_review',
                                'new_order_confirmed': False, 'revenue_attribution_confirmed': False,
                                'profit_effect_confirmed': False, 'score_effect': 0,
                                'spending_scope': 'companywide_not_supplier_allocation',
                                'event_spending_state': ('disclosed_companywide_capex' if event.get('event_type') == 'EARNINGS'
                                                         else 'announced_action_not_supplier_order'),
                                'recommendation_eligible': False,
                                'note': '원자료의 기존 관계만 확인. 신규 수주·매출·이익 귀속 및 현재 관계 지속은 별도 검증 필요.',
                            })
                        visit(target, route, nodes + [target])
                visit(start, [], [start])
    report['excluded'] = dict(excluded)
    return report
