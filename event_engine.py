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
    ORION V2 사건 판별기

    핵심:
    1. 기사에서 가능한 사건을 전부 찾는다.
    2. 첫 키워드에 걸렸다고 바로 종료하지 않는다.
    3. 가장 구체적이고 실제 돈의 흐름과 가까운 사건을 주 사건으로 선택한다.
    """

    title = str(article.get("title", "") or "")
    summary = str(article.get("summary", "") or "")
    source = str(article.get("source", "") or "")

    text = f"{title} {summary}".lower()

    candidates = []

    def add_event(event_type, importance, reason):
        candidates.append({
            "event_type": event_type,
            "importance": importance,
            "reason": reason
        })

    # =================================================
    # 1. 공식기관 사건
    # =================================================

    if source.startswith("FED_"):

        if any(p in text for p in [
            "fomc statement",
            "federal open market committee",
            "target range for the federal funds rate",
            "interest rate decision",
            "maintain the target range",
            "rate cut",
            "rate hike"
        ]):
            add_event(
                "FOMC",
                95,
                "FOMC·미국 통화정책 결정"
            )

        if "powell" in text and any(p in text for p in [
            "monetary policy",
            "inflation",
            "interest rate",
            "labor market",
            "employment",
            "economic outlook"
        ]):
            add_event(
                "POWELL",
                90,
                "파월 핵심 통화정책·경제 발언"
            )

        if any(p in text for p in [
            "monetary policy",
            "interest rate",
            "inflation",
            "price stability",
            "labor market",
            "employment"
        ]):
            add_event(
                "FED_SPEECH",
                70,
                "Fed 위원 통화정책·경제 발언"
            )

        if any(p in text for p in [
            "bank regulation",
            "financial regulation",
            "capital requirements",
            "bank supervision",
            "financial stability"
        ]):
            add_event(
                "FED_REGULATION",
                55,
                "Fed 금융규제·금융시스템 정책"
            )

    if source.startswith("BLS_"):
        add_event(
            "MACRO",
            90,
            "미국 공식 경제지표"
        )

    # =================================================
    # 2. 정책 / 관세 / 규제
    # =================================================

    if any(p in text for p in [
        "imposes tariff",
        "raises tariff",
        "cuts tariff",
        "export ban",
        "export restriction",
        "sanctions",
        "tariff announced",
        "관세 부과",
        "관세 인상",
        "수출 규제",
        "수출 금지",
        "제재 발표"
    ]):
        add_event(
            "POLICY",
            90,
            "정부 정책·관세·규제 변화"
        )

    # =================================================
    # 3. M&A
    # =================================================

    if any(p in text for p in [
        "acquires",
        "acquired",
        "acquisition",
        "to acquire",
        "merger",
        "takeover bid",
        "인수",
        "합병"
    ]):
        add_event(
            "M&A",
            80,
            "인수·합병 발생"
        )

    # =================================================
    # 4. 계약 / 수주 / 수주잔고
    # =================================================

    if any(p in text for p in [
        "wins contract",
        "signed contract",
        "signs contract",
        "supply agreement",
        "supply contract",
        "purchase order",
        "long-term agreement",
        "orderbook",
        "backlog",
        "공급계약 체결",
        "장기 공급계약",
        "수주",
        "수주잔고",
        "계약 체결"
    ]):
        add_event(
            "CONTRACT",
            80,
            "계약·수주·수주잔고 변화"
        )

    # =================================================
    # 5. 투자 / CAPEX
    # =================================================

    if any(p in text for p in [
        "will invest",
        "to invest",
        "plans to invest",
        "announced investment",
        "capital expenditure",
        "capex",
        "spending plan",
        "spending plans",
        "투자 확대",
        "투자 계획",
        "설비투자",
        "투자 축소"
    ]):
        add_event(
            "CAPEX",
            80,
            "투자·CAPEX 변화"
        )

    # =================================================
    # 6. 생산 / 증설 / 양산
    # =================================================

    if any(p in text for p in [
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
    ]):
        add_event(
            "PRODUCTION",
            75,
            "생산능력·증설·양산 변화"
        )

    # =================================================
    # 7. 실적 / 가이던스
    #    다른 구체적 사건보다 뒤에서 판정
    # =================================================

    earnings_signals = [
        "reports revenue",
        "reported revenue",
        "record revenue",
        "revenue rose",
        "revenue grew",
        "revenue growth",
        "reports earnings",
        "reported earnings",
        "earnings beat",
        "earnings miss",
        "profit surge",
        "profit rose",
        "profit growth",
        "raises guidance",
        "raised guidance",
        "raised guide",
        "cuts guidance",
        "lowered guidance",
        "quarterly results",
        "실적 발표",
        "영업이익",
        "매출액",
        "매출 증가",
        "영업이익 증가"
    ]

    if any(p in text for p in earnings_signals):
        add_event(
            "EARNINGS",
            70,
            "기업 실적·가이던스 변화"
        )

    # =================================================
    # 8. 후보가 없으면 사건 아님
    # =================================================

    if not candidates:
        return {
            "is_event": False,
            "event_type": "NO_EVENT",
            "importance": 0,
            "reason": "실제 행동·변화 확인 안 됨"
        }

    # =================================================
    # 9. 가장 중요한 사건 선택
    # =================================================

    priority = {
        "FOMC": 100,
        "POLICY": 95,
        "POWELL": 90,
        "M&A": 85,
        "CONTRACT": 84,
        "CAPEX": 83,
        "PRODUCTION": 82,
        "MACRO": 80,
        "EARNINGS": 70,
        "FED_SPEECH": 60,
        "FED_REGULATION": 50
    }

    best = max(
        candidates,
        key=lambda x: (
            priority.get(x["event_type"], 0),
            x["importance"]
        )
    )

    return {
        "is_event": True,
        "event_type": best["event_type"],
        "importance": best["importance"],
        "reason": best["reason"],
        "detected_events": [
            x["event_type"]
            for x in candidates
        ]
    }
    
def classify_event_status(article):
    """
    사건의 '신분'을 분류한다.

    PRIMARY   : 공식기관/기업이 직접 발표한 1차 정보
    CONFIRMED : 실제 발생한 사건을 보도한 기사
    ANALYSIS  : 전망/해설/분석/투자아이디어
    RUMOR     : 루머/가능성/협상설 등 미확정 정보
    """

    title = str(article.get("title", "") or "")
    summary = str(article.get("summary", "") or "")
    source = str(article.get("source", "") or "")

    text = f"{title} {summary}".lower()

    # ---------------------------------------------
    # 1. RUMOR - 가장 먼저 검사
    # ---------------------------------------------
    rumor_patterns = [
        "rumor",
        "rumors",
        "reportedly",
        "may acquire",
        "might acquire",
        "could acquire",
        "possible merger",
        "considering acquisition",
        "in talks",
        "early talks",
        "exploring a deal",
        "인수설",
        "합병설",
        "매각설",
        "검토 중",
        "협상 중",
        "가능성"
    ]

    if any(p in text for p in rumor_patterns):
        return "RUMOR"

    # ---------------------------------------------
    # 2. 공식 1차 출처
    # ---------------------------------------------
    if source.startswith("FED_"):
        return "PRIMARY"

    if source.startswith("BLS_"):
        return "PRIMARY"

    # 향후 White House / SEC / 기업 IR 추가 시
    # 이곳에서 PRIMARY로 분류한다.

    # ---------------------------------------------
    # 3. 해설 / 전망 / 투자아이디어
    # ---------------------------------------------
    analysis_patterns = [
        "outlook",
        "analysis",
        "commentary",
        "opinion",
        "preview",
        "what it means",
        "what investors",
        "should investors",
        "worth buying",
        "stocks to buy",
        "stock pick",
        "price target",
        "could rise",
        "could soar",
        "stocks to watch",

        "stock to watch",

        "shares rise",

        "shares jump",

        "stock rises",

        "stock jumps",

        "benefit from",

        "beneficiary",
        "전망",
        "분석",
        "해설",
        "칼럼",
        "주간",
        "위클리",
        "투자 포인트",
        "주목할 종목"
        "주목",

        "수혜",

        "기대감",

        "추천",

        "추천 후",

        "주가 상승",

        "주가 상승세",

        "주식 초고수",

        "mk시그널",
    ]

    if any(p in text for p in analysis_patterns):
        return "ANALYSIS"

    # ---------------------------------------------
    # 4. 나머지 실제 사건 기사
    # ---------------------------------------------
    return "CONFIRMED"
def calc_event_score(article):

    event = detect_event_type(article)
    status = classify_event_status(article)

    if not event["is_event"]:
        return 0, [
            event["reason"]
        ]
    # 루머는 실제 사건으로 사용하지 않는다.
    if status == "RUMOR":
        return 0, ["사건신분:RUMOR", "미확정 정보"]

    # 해설/전망은 Money Flow 시작 사건으로 사용하지 않는다.
    if status == "ANALYSIS":
        return 0, ["사건신분:ANALYSIS", "해설·전망 기사"]

    score = event["importance"]

    reasons = [
        f"사건신분:{status}",
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
