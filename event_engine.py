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
    "should investors care", "top stocks", "stocks to buy",
    "watchlist", "preview", "opinion", "column",
    "billionaire", "why shares",

    "포럼", "세미나", "간담회", "출범",
    "기념식", "토론회", "칼럼", "루머"
]


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

    block, block_word = is_block_news(article)

    if block:
        return 0, [f"제외:{block_word}"]

    for word in IMPORTANT_KEYWORDS:
        if word.lower() in title:
            score += 15
            reasons.append(word)

    if market == "US":
        score += 10
        reasons.append("US")

    if score > 100:
        score = 100

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
