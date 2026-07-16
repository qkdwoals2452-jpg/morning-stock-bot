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

def calc_event_score(article):
    title = article.get("title", "").lower()
    market = article.get("market", "")

    score = 0
    reasons = []

    # 1. 사건이 아닌 기사 먼저 제거
    block, block_word = is_block_news(article)

    if block:
        return 0, [f"제외:{block_word}"]

    # 2. 실제 계약·투자·증설 사건에 강한 점수
    for phrase, bonus in STRONG_EVENT_RULES.items():
        if phrase.lower() in title:
            score += bonus
            reasons.append(f"강한사건:{phrase}")

    # 3. 일반 중요 키워드 점수
    matched_words = set()

    for word in IMPORTANT_KEYWORDS:
        word_lower = word.lower()

        if word_lower in title and word_lower not in matched_words:
            score += 10
            reasons.append(word)
            matched_words.add(word_lower)

    # 4. 미국 원문 사건 가산점
    if market == "US":
        score += 10
        reasons.append("US")

    score = min(score, 100)

    return score, reasons



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
