EVENT_RULES = {
    "S": {
        "score": 90,
        "keywords": [
            "capex", "ai capex", "investment", "invest",
            "data center", "datacenter", "gpu", "hbm",
            "nvidia", "blackwell", "tsmc", "broadcom",
            "microsoft", "meta", "amazon", "google",
            "openai", "oracle", "power demand",
            "rate cut", "rate hike", "cpi", "ppi", "fed",
            "tariff", "export ban",

            "투자", "증설", "데이터센터", "AI 투자",
            "엔비디아", "블랙웰", "TSMC", "브로드컴",
            "금리", "CPI", "PPI", "연준", "관세",
            "수출규제"
        ],
    },
    "A": {
        "score": 70,
        "keywords": [
            "contract", "deal", "supply", "order",
            "earnings beat", "guidance raise",
            "factory", "plant", "production",
            "merger", "acquisition",

            "계약", "수주", "공급", "실적", "가이던스",
            "공장", "양산", "생산", "인수", "합병"
        ],
    },
    "B": {
        "score": 50,
        "keywords": [
            "policy", "regulation", "subsidy",
            "partnership", "launch",

            "정책", "규제", "보조금", "파트너십", "출시"
        ],
    },
    "BLOCK": {
        "score": 0,
        "keywords": [
            "should investors care", "top stocks", "stocks to buy",
            "why shares", "billionaire", "opinion", "column",
            "preview", "watchlist", "rumor",

            "포럼", "세미나", "간담회", "출범", "기념식",
            "토론회", "컨퍼런스", "칼럼", "전망", "루머"
        ],
    },
}


def classify_event_article(article):
    title = article.get("title", "").lower()
    text = title

    for word in EVENT_RULES["BLOCK"]["keywords"]:
        if word.lower() in text:
            return {
                "event_grade": "BLOCK",
                "event_score": 0,
                "event_reason": f"제외뉴스:{word}"
            }

    for grade in ["S", "A", "B"]:
        for word in EVENT_RULES[grade]["keywords"]:
            if word.lower() in text:
                return {
                    "event_grade": grade,
                    "event_score": EVENT_RULES[grade]["score"],
                    "event_reason": f"{grade}급 사건:{word}"
                }

    return {
        "event_grade": "C",
        "event_score": 20,
        "event_reason": "일반뉴스"
    }


def filter_event_news(news):
    result = []

    for article in news:
        event = classify_event_article(article)

        article["event_grade"] = event["event_grade"]
        article["event_score"] = event["event_score"]
        article["event_reason"] = event["event_reason"]

        if event["event_grade"] in ["S", "A", "B"]:
            result.append(article)

    result = sorted(
        result,
        key=lambda x: x.get("event_score", 0),
        reverse=True
    )

    return result
