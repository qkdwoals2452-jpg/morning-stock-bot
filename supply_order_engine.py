"""검토된 개별 주문 문서만 대조한다. 사건 인과·매출 인식·추천 점수는 확정하지 않는다."""
from collections import Counter
from copy import deepcopy
from datetime import date, datetime, time
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from pre_news_activity_engine import parse_timestamp

SEOUL = ZoneInfo('Asia/Seoul')


def load_supply_order_evidence():
    try:
        return json.loads(Path(__file__).with_name('supply_order_evidence.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def _term(text, term):
    pattern = re.escape(term)
    if re.search('[a-zA-Z]', term):
        pattern = r'(?<![a-zA-Z0-9])' + pattern + r'(?![a-zA-Z0-9])'
    return bool(re.search(pattern, text, re.I))


def _party(value):
    value = re.sub(r'주식회사|\(주\)|㈜', '', value)
    value = re.sub(r'(?:,?\s*(?:incorporated|inc\.?|co\.?,?\s*ltd\.?|corporation|corp\.?))\s*$',
                   '', value, flags=re.I)
    return re.sub(r'[^a-z0-9가-힣]', '', value.lower())


def _reason(order, entities, now):
    if not isinstance(order, dict):
        return 'invalid_order'
    buyer, supplier = order.get('buyer'), order.get('supplier')
    if (not isinstance(buyer, str) or not isinstance(supplier, str)
            or buyer == supplier or buyer not in entities or supplier not in entities):
        return 'invalid_counterparties'
    if (order.get('review_method') != 'manual_primary_source'
            or order.get('state') not in ('disclosed_contract', 'amended_contract', 'cancelled_contract')
            or not isinstance(order.get('contract_id'), str) or not order['contract_id']):
        return 'unverified_or_inactive_order'
    try:
        url = urlsplit(order['source_url'])
        receipt = order['receipt_no']
        if (url.scheme != 'https' or url.hostname != 'dart.fss.or.kr' or url.username or url.password
                or url.port not in (None, 443) or url.path != '/dsaf001/main.do'
                or not isinstance(receipt, str) or not re.fullmatch(r'[0-9]{14}', receipt)
                or parse_qs(url.query).get('rcpNo') != [receipt]):
            return 'unapproved_order_source'
        published = date.fromisoformat(order['published_on'])
        ordered = date.fromisoformat(order['ordered_on'])
        ending = date.fromisoformat(order['delivery_end_on'])
        reviewed, assumed = parse_timestamp(order['reviewed_at'])
        if (not reviewed or assumed or reviewed > now or reviewed.date() < published
                or datetime.combine(published, time.max, SEOUL) > now):
            return 'order_unavailable_at_assessment'
        if ordered > published or ending < ordered:
            return 'invalid_order_timeline'
        fields = order['source_fields']
        if (not isinstance(fields, dict) or any(not isinstance(fields.get(k), str) or not fields[k]
                for k in ('supplier', 'buyer', 'product', 'amount', 'section'))):
            return 'missing_primary_order_fields'
        if not all(any(_party(fields[role]) == _party(alias) for alias in entities[order[role]]['aliases'])
                   for role in ('buyer', 'supplier')):
            return 'counterparty_evidence_mismatch'
        amount = order['amount']
        if (isinstance(amount, bool) or not isinstance(amount, int) or amount < 0
                or (amount == 0 and order['state'] != 'cancelled_contract')
                or order.get('currency') not in ('KRW', 'USD')
                or not re.fullmatch(r'[0-9,]+', fields['amount'])
                or int(fields['amount'].replace(',', '')) != amount):
            return 'invalid_order_amount'
        terms = order['product_terms']
        if (not isinstance(terms, list) or not terms or any(not isinstance(t, str) or not t
                or not _term(fields['product'], t) for t in terms)):
            return 'missing_product_evidence'
    except (KeyError, TypeError, ValueError):
        return 'invalid_order_evidence'
    return None


def review_supply_orders(buyer, supplier, context, event_at, entities, as_of, evidence=None):
    """최종 공급 경로의 실제 거래상대·제품을 대조. 문서 확인과 사건 귀속을 분리한다."""
    report = {'status': 'no_verified_order', 'documented_orders': [], 'excluded': {},
              'documented_order_confirmed': False, 'event_order_attribution_confirmed': False,
              'revenue_recognition_confirmed': False, 'profit_effect_confirmed': False,
              'score_effect': 0, 'recommendation_eligible': False,
              'note': '확인된 주문 문서가 없다는 것은 주문이 없다는 뜻이 아닙니다. 계약금액은 매출·이익 인식액이 아닙니다.'}
    book = evidence if evidence is not None else load_supply_order_evidence()
    now, assumed = parse_timestamp(as_of)
    stamp, stamp_assumed = parse_timestamp(event_at)
    if (not now or assumed or not stamp or stamp_assumed or stamp > now
            or not isinstance(book, dict) or book.get('schema_version') != 1
            or not isinstance(book.get('orders'), list)):
        report['status'] = 'order_evidence_unavailable'
        return report
    rejected = Counter()
    eligible = []
    for order in book['orders']:
        reason = _reason(order, entities, now)
        if reason:
            rejected[reason] += 1
        else:
            eligible.append(order)
    # 같은 공시의 충돌하는 추출값을 골라 쓰거나 합산하지 않는다.
    receipts = {}
    for order in eligible:
        receipts.setdefault(order['receipt_no'], []).append(order)
    contracts = {}
    for versions in receipts.values():
        if any(order != versions[0] for order in versions):
            rejected['conflicting_order_evidence'] += 1
            continue
        order = versions[0]
        contracts.setdefault((order['buyer'], order['supplier'], order['contract_id']), []).append(order)
    for versions in contracts.values():
        latest_day = max(order['published_on'] for order in versions)
        latest = [order for order in versions if order['published_on'] == latest_day]
        if len(latest) != 1:
            rejected['ambiguous_order_revision'] += 1
            continue
        order = latest[0]
        if order['state'] == 'cancelled_contract':
            rejected['cancelled_order'] += 1
            continue
        if (order['buyer'], order['supplier']) != (buyer, supplier):
            rejected['different_order_counterparty'] += 1
            continue
        if not any(_term(context, term) for term in order['product_terms']):
            rejected['different_order_product'] += 1
            continue
        public_at = datetime.combine(date.fromisoformat(order['published_on']), time.max, SEOUL)
        reviewed, _ = parse_timestamp(order['reviewed_at'])
        document = deepcopy({key: order[key] for key in (
            'contract_id', 'buyer', 'supplier', 'receipt_no', 'source_url', 'review_method',
            'state', 'published_on', 'ordered_on', 'delivery_end_on', 'reviewed_at',
            'amount', 'currency', 'product_terms', 'source_fields')})
        document['knowledge_timing'] = ('known_before_event' if public_at <= stamp and reviewed <= stamp
                                        else 'retrospective_review')
        document['order_timing'] = ('predates_event' if date.fromisoformat(order['ordered_on']) < stamp.date()
                                    else 'same_day_or_later_not_causal_proof')
        # 계약서상 예정 납기일은 실제 납품·검수·매출 인식의 증거가 아니다.
        # 미검색 정정/취소 이력까지 현재 유효성 확인으로 승격하지 않는다.
        document['delivery_period_state'] = (
            'scheduled_end_passed_completion_unverified'
            if date.fromisoformat(order['delivery_end_on']) < now.astimezone(SEOUL).date()
            else 'within_scheduled_period_completion_unverified')
        document['delivery_completion_confirmed'] = False
        document['revenue_recognition_confirmed'] = False
        document['profit_effect_confirmed'] = False
        document['revision_search_complete'] = False
        document['missing_evidence'] = [
            'current_amendment_and_cancellation_review',
            'specific_us_event_order_allocation',
            'actual_delivery_and_acceptance',
            'contract_specific_revenue_recognition',
            'contract_specific_profit_effect',
        ]
        # 원문에 사건별 배분 근거가 없는 계약을 전사 CAPEX/다른 고객 주문에 귀속하지 않는다.
        document['event_order_attribution_confirmed'] = False
        document['score_effect'] = 0
        document['recommendation_eligible'] = False
        report['documented_orders'].append(document)
    if report['documented_orders']:
        report['status'] = 'documented_order_event_unattributed'
        report['documented_order_confirmed'] = True
    report['excluded'] = dict(rejected)
    return report
