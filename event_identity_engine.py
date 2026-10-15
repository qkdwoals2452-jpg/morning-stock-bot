"""같은 회사·사건 유형과 같은 실제 거래를 구분하는 보수적 비교 규칙."""
from datetime import datetime
from decimal import Decimal
import hashlib
import html
import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def normalized_text(text):
    return re.sub(r"\s+", " ", html.unescape(str(text or "")).casefold()).strip()


def canonical_link(link):
    try:
        parts = urlsplit(str(link or ""))
        if parts.scheme not in ("http", "https") or not parts.hostname:
            return ""
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                 if not k.lower().startswith("utm_") and k.lower() not in ("fbclid", "gclid")]
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path,
                           urlencode(sorted(query)), ""))
    except ValueError:
        return ""


def published_day(article):
    try:
        return datetime.fromisoformat(str(article.get("published_at", "")).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def duplicate_article(left, right):
    # 같은 단어 수로 중복을 판정하지 않는다. 다른 URL의 같은 제목도 반복 거래일 수 있다.
    if normalized_text(left.get("title")) != normalized_text(right.get("title")):
        return False
    if normalized_text(left.get("summary")) != normalized_text(right.get("summary")):
        return False
    a, b = canonical_link(left.get("link")), canonical_link(right.get("link"))
    if a or b:
        return bool(a and a == b and published_day(left) == published_day(right))
    return (left.get("source") == right.get("source")
            and left.get("published_at") == right.get("published_at"))


PRODUCTS = {
    "inspection_equipment": ("검사장비", "검사 장비", "inspection equipment"),
    "cooling_equipment": ("냉각장비", "냉각 장비", "액침냉각", "liquid cooling"),
    "transformer": ("변압기", "transformer"),
    "actuator": ("구동기", "actuator"),
    "lng_carrier": ("lng 운반선", "lng운반선", "lng carrier"),
    "gpu": ("gpu",), "hbm": ("hbm",), "hbm3": ("hbm3",),
    "hbm3e": ("hbm3e",), "hbm4": ("hbm4",),
}
GENERIC_PARTIES = re.compile(r"업체|기업|고객|시설|공장|원전|데이터센터|customer|company|firm|facility", re.I)
COUNTRIES = {"미국", "중국", "한국", "일본", "대만", "해외", "국내", "글로벌"}
GENERIC_NAMES = {"검사", "공급", "투자", "증설", "시장", "장비", "부품", "매출", "계약", "생산", "공정", "정부", "경제"}


def event_facts(article):
    # 요약의 과거 실적/다른 거래 금액을 현재 계약의 금액으로 합치지 않는다.
    title = normalized_text(article.get("title"))
    amounts = set()
    scale = {"조": Decimal(10) ** 12, "억": Decimal(10) ** 8, "만": Decimal(10) ** 4}
    number = r"([0-9][0-9,]*(?:\.[0-9]+)?)"
    for m in re.finditer(number + r"\s*(조|억|만)(?:\s*" + number + r"\s*(억|만))?\s*(원|달러)?", title):
        value = Decimal(m[1].replace(",", "")) * scale[m[2]]
        if m[3]:
            value += Decimal(m[3].replace(",", "")) * scale[m[4]]
        currency = {"원": "KRW", "달러": "USD"}.get(m[5], "UNKNOWN")
        amounts.add(f"{currency}:{value.normalize():f}")
    for m in re.finditer(r"(us\$|\$|usd|€|eur|₩|krw)\s*" + number + r"(?:\s*(million|billion|trillion))?", title):
        currency = "USD" if m[1] in ("us$", "$", "usd") else "EUR" if m[1] in ("€", "eur") else "KRW"
        value = Decimal(m[2].replace(",", "")) * {None: 1, "million": 10 ** 6, "billion": 10 ** 9, "trillion": 10 ** 12}[m[3]]
        amounts.add(f"{currency}:{value.normalize():f}")
    parties = set()
    for m in re.finditer(r"([가-힣A-Za-z0-9&.]+)\s*(?:에게|으로부터|로부터|와|과|에)(?=\s)", title):
        party = m[1]
        if (not GENERIC_PARTIES.search(party) and party not in COUNTRIES | GENERIC_NAMES
                and not re.fullmatch(r"[a-z]사|모사|모기업", party)):
            parties.add(party)
    for m in re.finditer(r"\bwith\s+([a-z][a-z0-9&. ]{1,50})", title):
        party = re.split(r"\s+(?:for|to|on|in|worth|valued|supply|contract)\b", m[1])[0].strip()
        if party and not GENERIC_PARTIES.search(party):
            parties.add(party)
    products = set()
    for product, terms in PRODUCTS.items():
        for term in terms:
            pattern = re.escape(term)
            if re.search(r"[a-z]", term) and not re.search(r"[가-힣]", term):
                pattern = r"(?<![a-z0-9])" + pattern + r"(?![a-z0-9])"
            if re.search(pattern, title):
                products.add(product)
    dates = {f"{int(y):04}-{int(m):02}-{int(d):02}" for y, m, d in
             re.findall(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", title)}
    for y, m, d in re.findall(r"(?:(\d{4})년\s*)?(\d{1,2})월\s*(\d{1,2})일", title):
        dates.add((f"{int(y):04}-" if y else "") + f"{int(m):02}-{int(d):02}")
    periods = set(re.findall(r"(?<!\d)(\d{1,2})년(?:간|짜리|\s+(?:장기|공급|계약))", title))
    locations = {place for place in re.findall(r"[가-힣A-Za-z0-9]+(?:공장|원전|데이터센터)", title)
                 if place not in ("반도체공장", "데이터센터", "ai데이터센터")}
    return {"amounts": sorted(amounts), "counterparties": sorted(parties),
            "products": sorted(products), "event_dates": sorted(dates),
            "contract_years": sorted(periods), "locations": sorted(locations)}


def facts_conflict(a, b):
    for field in ("amounts", "contract_years", "counterparties"):
        if a[field] and b[field] and a[field] != b[field]:
            return True
    for field in ("products", "locations"):
        if a[field] and b[field] and not set(a[field]) & set(b[field]):
            return True
    if a["event_dates"] and b["event_dates"]:
        compatible = any(x == y or (len(x) != len(y) and x[-5:] == y[-5:])
                         for x in a["event_dates"] for y in b["event_dates"])
        if not compatible:
            return True
    return False


def strong_match(a, b):
    return bool(a["amounts"] and a["amounts"] == b["amounts"]
                and a["counterparties"] and a["counterparties"] == b["counterparties"])


def same_event(left, right):
    a, b = event_facts(left), event_facts(right)
    if facts_conflict(a, b):
        return False
    days = published_day(left), published_day(right)
    if all(days) and abs((days[0] - days[1]).days) > 3:
        return False
    url = canonical_link(left.get("link"))
    if url and url == canonical_link(right.get("link")):
        return True
    if duplicate_article(left, right):
        return True
    # 정보가 없는 기사를 중간 다리로 삼아 서로 다른 계약을 합치지 않는다.
    dated = all(days) or bool(a["event_dates"] and a["event_dates"] == b["event_dates"])
    return bool(dated and strong_match(a, b))


def instance_key(subject_key, articles):
    facts = [event_facts(article) for article in articles]
    combined = {k: sorted({v for f in facts for v in f[k]}) for k in facts[0]}
    dates = [str(published_day(a)) for a in articles if published_day(a)]
    fingerprint = {"subject": subject_key, "facts": combined, "observed_day": min(dates) if dates else ""}
    if not combined["amounts"] or not combined["counterparties"]:
        fingerprint["articles"] = sorted({(canonical_link(a.get("link")), normalized_text(a.get("title"))) for a in articles})
    digest = hashlib.sha1(json.dumps(fingerprint, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]
    return f"{subject_key}_{digest}"


def publisher(article):
    source = str(article.get("source", ""))
    base = None
    for prefix, name in (("한국경제", "hankyung"), ("매일경제", "mk"), ("이데일리", "edaily"),
                         ("Yahoo", "yahoo"), ("Nasdaq", "nasdaq"), ("Investing", "investing"),
                         ("Bloomberg_", "bloomberg"), ("WSJ_", "wsj"),
                         ("FT_", "ft"), ("BBC_", "bbc"),
                         ("SEC_", "sec"), ("FED_", "fed"), ("BLS_", "bls")):
        if source.startswith(prefix):
            base = name
            break
    # 원 배포사 귀속이 명시된 재전송은 배포 매체 수만큼 독립 가산하지 않는다.
    attribution = normalized_text(article.get('origin_publisher'))
    for name, aliases in {
        'reuters': ('reuters', 'thomson reuters'),
        'ap': ('associated press', 'ap'),
        'bloomberg': ('bloomberg', 'bloomberg news'),
    }.items():
        if attribution in aliases:
            return name, base is not None
    text = normalized_text(str(article.get('title', '')) + ' ' + str(article.get('summary', '')))
    for pattern, name in [(r'\breuters\s*\)|according to reuters|reuters (?:reported|reports)', 'reuters'),
                          (r'\bassociated press\b|\(ap\)', 'ap'),
                          (r'\(bloomberg\)|according to bloomberg|bloomberg (?:reported|reports)', 'bloomberg')]:
        if re.search(pattern, text):
            return name, base is not None
    if base is not None:
        return base, True
    host = urlsplit(canonical_link(article.get("link"))).hostname
    return (host or f"label:{source}"), False


def corroboration_bonus(articles):
    # 여러 피드 이름/똑같은 본문을 다른 취재 근거로 세지 않는다.
    candidates = [a for a in articles if publisher(a)[1] and normalized_text(a.get("summary"))]
    for i, a in enumerate(candidates):
        for b in candidates[i + 1:]:
            if (publisher(a)[0] != publisher(b)[0]
                    and normalized_text(a.get('title')) != normalized_text(b.get('title'))
                    and normalized_text(a.get("summary")) != normalized_text(b.get("summary"))
                    and strong_match(event_facts(a), event_facts(b))):
                return 10
    return 0
