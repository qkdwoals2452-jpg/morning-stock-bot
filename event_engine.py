from collections import defaultdict


IMPORTANT_KEYWORDS = [
    "investment", "invest", "capex", "spending",
    "contract", "supply", "deal", "order",
    "data center", "datacenter", "gpu", "hbm",
    "semiconductor", "memory", "micron", "nvidia",
    "tsmc", "broadcom", "microsoft", "meta",
    "amazon", "google", "oracle", "openai",
    "fed", "cpi", "ppi", "tariff", "export ban",

    "투자", "증설", "계약", "공급", "수주",
    "데이터센터", "반도체", "메모리", "장기 공급",
    "차량용", "LPDRAM", "NOR", "UFS", "SDV",
    "금리", "연준", "관세", "수출규제"
]

BLOCK_KEYWORDS = [
    # 투자 권유·목록형 기사
    "should investors care",
    "stocks to buy",
    "top stocks",
    "best stocks",
    "watchlist",
    "stock picks",

    # 비교·해설·의견 기사
    " vs. ",
    " vs ",
    "versus",
    "comparison",
    "what revenue growth",
    "what investors need to know",
    "for investors",
    "opinion",
    "column",
    "preview",
    "why shares",
    "billionaire",
    "analyst says",

    # 한국 저품질 기사
    "포럼",
    "세미나",
    "간담회",
    "출범",
    "기념식",
    "토론회",
    "칼럼",
    "루머",
    "추천주",
    "주목할 종목",
    # 미국 해설/분석 기사
    "what it means",
    "what you need to know",
    "should investors worry",
    "investors should be watching",
    "outlook",

    "analysis",

    "commentary",

    "insight",

    "review",

    "summary",

    # 한국 해설/분석 기사

    

    "평가",

    

    

    "분석",

    "의견",

    "진단",

    "해설",

    "브리핑",

    "시황",
    "three reasons",

    "stands to win",

    "week in review",

    "what's moving markets",

    "what is moving markets",

    "stock investors",

    "세가지 이유",

    "세 가지 이유",

    "주가상승 기대",

    "투자 포인트",

    "낙폭 과대주",

    "당분간 관망",

    "[종목+]",
    
    
]

STRONG_EVENT_RULES = {
    # 실제 계약·수주
    "long-term supply agreement": 50,
    "long-term contract": 50,
    "supply agreement": 40,
    "supply contract": 40,
    "wins contract": 40,

    # 실제 투자·증설
    "to invest": 40,
    "will invest": 40,
    "investment of": 35,
    "capital spending": 35,
    "capex": 35,
    "new factory": 35,
    "new plant": 35,
    "expand production": 35,

        
    # 양산

    "mass production": 40,

    "commercial production": 40,

    "volume production": 40,

    # 승인

    

    "FDA approval": 45,

    # 인수

    "acquisition": 45,

    "acquires": 45,

    "acquired": 45,

    "merger": 45,

    # 데이터센터

    

    # AI 투자

    "AI infrastructure": 40,

    "AI investment": 40,

    # 신규 고객

    "new customer": 35,

    "major customer": 35,

    # 한국어
    "장기 공급 계약": 50,
    "장기 공급계약": 50,
    "공급 계약": 40,
    "공급계약": 40,
    "대규모 수주": 40,
    "투자 확대": 35,
    "공장 투자": 35,
    "공장 증설": 35,
    "생산 확대": 35,
    "양산 시작": 35,
    "양산": 40,

    "상업 생산": 40,

    "FDA 승인": 45,

    "인수": 45,

    "합병": 45,

    "데이터센터": 35,

    "AI 인프라": 40,

    "신규 고객": 35,
}

def normalize_title(title):
    title = title.lower()

    remove_words = [
        "reuters", "bloomberg", "cnbc",
        "breaking", "exclusive", "update",
        "속보", "단독"
    ]

    for word in remove_words:
        title = title.replace(word, "")

    return title.strip()


def is_block_news(article):
    title = article.get("title", "").lower()

    for word in BLOCK_KEYWORDS:
        if word.lower() in title:
            return True, word

    return False, ""

def detect_event_type(article):
    """
    기사에서 '실제로 발생한 사건'이 있는지 먼저 판정한다.
    단순 키워드 개수는 세지 않는다.
    """

    title = str(article.get("title", "") or "")
    summary = str(article.get("summary", "") or "")
    source = str(article.get("source", "") or "")
    market = article.get("market", "")

    text = f"{title} {summary}".lower()

    # -------------------------------------------------
    # 1. 공식기관 이벤트
    # -------------------------------------------------
    if source.startswith("FED_"):
        return {
            "is_event": True,
            "event_type": "FED",
            "importance": 90,
            "reason": "미 연준 공식 발표"
        }

    if source.startswith("BLS_"):
        return {
            "is_event": True,
            "event_type": "MACRO",
            "importance": 90,
            "reason": "미국 공식 경제지표"
        }

    # -------------------------------------------------
    # 2. 투자권유/가정/단순 전망형은 '사건'으로 인정하지 않음
    # -------------------------------------------------
    non_event_patterns = [
        "worth buying",
        "worth investing",
        "should you buy",
        "is it time to buy",
        "could be worth",
        "will be worth",
        "stock pick",
        "stocks to buy",
        "buy now",
        "price target",
        "what if you invested",
        "$10,000 investment",
        "what investors need to know",
        "to consider",
        "could rise",
        "could soar",
        "may rise",
        "might rise",
    ]

    if any(p in text for p in non_event_patterns):
        return {
            "is_event": False,
            "event_type": "NO_EVENT",
            "importance": 0,
            "reason": "실제 사건 없는 투자/전망형 콘텐츠"
        }

    # -------------------------------------------------
    # 3. 실제 사건 유형 판별
    #    '산업 단어'가 아니라 '행동/변화'를 찾는다.
    # -------------------------------------------------

    # 금리 / 통화정책
    if any(p in text for p in [
        "fomc",
        "interest rate decision",
        "raises rates",
        "cuts rates",
        "holds rates",
        "rate hike",
        "rate cut",
        "금리 인상",
        "금리 인하",
        "금리 동결"
    ]):
        return {
            "is_event": True,
            "event_type": "MONETARY_POLICY",
            "importance": 95,
            "reason": "금리·통화정책 변화"
        }

    # 관세 / 규제 / 정부정책
    if any(p in text for p in [
        "imposes tariff",
        "raises tariff",
        "cuts tariff",
        "export ban",
        "export restriction",
        "sanctions",
        "new regulation",
        "tariff announced",
        "관세 부과",
        "관세 인상",
        "수출 규제",
        "수출 금지",
        "제재 발표"
    ]):
        return {
            "is_event": True,
            "event_type": "POLICY",
            "importance": 90,
            "reason": "정부 정책·관세·규제 변화"
        }

    # 실적 발표
    earnings_action = any(p in text for p in [
        "reports revenue",
        "reported revenue",
        "reports earnings",
        "reported earnings",
        "earnings beat",
        "earnings miss",
        "raises guidance",
        "cuts guidance",
        "lowered guidance",
        "quarterly results",
        "실적 발표",
        "영업이익",
        "매출액"
    ])

    if earnings_action:
        return {
            "is_event": True,
            "event_type": "EARNINGS",
            "importance": 70,
            "reason": "기업 실적·가이던스 변화"
        }

    # 실제 투자 / CAPEX
    capex_action = any(p in text for p in [
        "will invest",
        "to invest",
        "plans to invest",
        "announced investment",
        "capital expenditure",
        "raises capex",
        "increases capex",
        "cuts capex",
        "spending plan",
        "투자 확대",
        "투자 계획",
        "설비투자",
        "투자 축소"
    ])

    if capex_action:
        return {
            "is_event": True,
            "event_type": "CAPEX",
            "importance": 80,
            "reason": "실제 투자·CAPEX 변화"
        }

    # 계약 / 수주 / 공급
    contract_action = any(p in text for p in [
        "wins contract",
        "signed contract",
        "signs contract",
        "supply agreement",
        "supply contract",
        "purchase order",
        "long-term agreement",
        "공급계약 체결",
        "장기 공급계약",
        "수주",
        "계약 체결"
    ])

    if contract_action:
        return {
            "is_event": True,
            "event_type": "CONTRACT",
            "importance": 75,
            "reason": "실제 계약·수주 발생"
        }

    # 공장 / 증설 / 양산
    production_action = any(p in text for p in [
        "new factory",
        "new plant",
        "expand production",
        "expands production",
        "mass production",
        "commercial production",
        "begins production",
        "공장 증설",
        "생산 확대",
        "양산 시작",
        "양산 본격화"
    ])

    if production_action:
        return {
            "is_event": True,
            "event_type": "PRODUCTION",
            "importance": 75,
            "reason": "생산능력 변화·양산"
        }

    # M&A
    ma_action = any(p in text for p in [
        "acquires",
        "acquired",
        "acquisition",
        "merger",
        "to acquire",
        "인수",
        "합병"
    ])

    if ma_action:
        return {
            "is_event": True,
            "event_type": "M&A",
            "importance": 75,
            "reason": "인수·합병"
        }

    # -------------------------------------------------
    # 실제 변화가 확인되지 않으면 사건으로 만들지 않음
    # -------------------------------------------------
    return {
        "is_event": False,
        "event_type": "NO_EVENT",
        "importance": 0,
        "reason": "실제 행동·변화 확인 안 됨"
    }


def calc_event_score(article):

    event = detect_event_type(article)

    if not event["is_event"]:
        return 0, [
            event["reason"]
        ]

    score = event["importance"]

    reasons = [
        f"사건유형:{event['event_type']}",
        event["reason"]
    ]

    market = article.get("market", "")
    source = article.get("source", "")

    # 미국 공식/원문이면 신뢰도 보강
    if market == "US":
        reasons.append("US")

    if source.startswith("FED_") or source.startswith("BLS_"):
        score = min(100, score + 5)
        reasons.append("공식출처")

    return min(score, 100), reasons


def make_event_grade(score):
    if score >= 90:
        return "S"
    elif score >= 70:
        return "A"
    elif score >= 50:
        return "B"
    elif score >= 30:
        return "C"
    else:
        return "D"


def make_event_key(article):
    title = normalize_title(article.get("title", ""))

    core_words = []

    for word in IMPORTANT_KEYWORDS:
        if word.lower() in title:
            core_words.append(word.lower())

    if core_words:
        return "_".join(sorted(core_words[:4]))

    return title[:60]


def merge_same_events(news):
    grouped = defaultdict(list)

    for article in news:
        score, reasons = calc_event_score(article)

        if score < 30:
            continue

        article["event_score_raw"] = score
        article["event_reasons"] = reasons

        key = make_event_key(article)
        grouped[key].append(article)

    events = []

    for key, articles in grouped.items():
        best = max(
            articles,
            key=lambda x: x.get("event_score_raw", 0)
        )

        source_count = len(
            set(
                a.get("source", "")
                for a in articles
            )
        )

        score = best.get("event_score_raw", 0)

        if source_count >= 2:
            score += 10

        if score > 100:
            score = 100

        events.append({
            "event_title": best.get("title", ""),
            "event_key": key,
            "event_score": score,
            "event_grade": make_event_grade(score),
            "articles": articles,
            "source_count": source_count,
            "market": best.get("market", ""),
            "reason": best.get("event_reasons", [])
        })

    events = sorted(
        events,
        key=lambda x: x["event_score"],
        reverse=True
    )

    return events


def extract_money_flow(event):
    title = event.get("event_title", "").lower()
    flows = []

    mapping = {
        "ai": ["AI"],
        "data center": ["데이터센터", "전력", "냉각"],
        "datacenter": ["데이터센터", "전력", "냉각"],
        "gpu": ["GPU", "HBM", "반도체"],
        "hbm": ["HBM", "반도체"],
        "memory": ["메모리", "반도체"],
        "micron": ["메모리", "반도체", "차량용 반도체"],
        "gm": ["차량용 반도체", "SDV"],
        "lpdram": ["차량용 메모리"],
        "nor": ["차량용 메모리"],
        "ufs": ["차량용 메모리"],
        "power": ["전력", "변압기"],
        "fed": ["금리", "환율", "은행"],
        "cpi": ["금리", "환율"],
        "ppi": ["금리", "환율"],
        "tariff": ["관세", "수출입"],
        "투자": ["투자", "CAPEX"],
        "증설": ["증설", "장비"],
        "계약": ["계약", "공급망"],
        "공급": ["공급망"],
        "차량용": ["차량용 반도체", "SDV"],
        "데이터센터": ["데이터센터", "전력", "냉각"],
        "반도체": ["반도체"],
        "메모리": ["메모리", "반도체"],
    }

    for key, values in mapping.items():
        if key in title:
            for v in values:
                if v not in flows:
                    flows.append(v)

    return flows


def build_events(news):
    events = merge_same_events(news)

    for event in events:
        event["money_flow"] = extract_money_flow(event)

    return events
