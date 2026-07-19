def score_news_quality(article):
    title = article.get("title", "").lower()
    market = article.get("market", "")
    text = title

    score = 0
    reason = []

    # 진짜 돈이 움직이는 뉴스
    strong_words = [
        "to invest", "will invest", "invests", "investment of", "investment", "spend", "spending", "capex",
        "build", "expand", "expansion", "contract", 
        "supply", "order", "factory", "plant", "production",
        "revenue", "guidance", "beat", "raise",
        "acquisition", "merger", "partnership",
        "투자", "증설", "수주", "계약", "공급", "공장",
        "양산", "생산", "실적", "매출", "영업이익", "인수", "합병"
    ]

    # 약한 뉴스 / 노이즈
    weak_words = [
        "should investors care", "top stocks", "stocks to buy",
        "why shares", "could", "may", "opinion", "column",
        "forum", "conference", "seminar",
        "포럼", "세미나", "간담회", "출범", "기념식",
        "토론회", "컨퍼런스", "전망", "분석", "칼럼"
    ]

    for w in strong_words:
        if w in text:
            score += 20
            reason.append(f"강한뉴스:{w}")

    for w in weak_words:
        if w in text:
            score -= 30
            reason.append(f"약한뉴스:{w}")

    # 미국뉴스 가산
    if market == "US":
        score += 10
        reason.append("미국뉴스")

    if score < 0:
        score = 0

    if score > 100:
        score = 100

    return {
        "score": score,
        "reason": reason,
        "is_core": score >= 20
    }


def filter_core_news(news):
    scored = []

    for article in news:
        q = score_news_quality(article)
        article["quality_score"] = q["score"]
        article["quality_reason"] = q["reason"]
        article["is_core_news"] = q["is_core"]

        if q["is_core"]:
            scored.append(article)

    scored = sorted(
        scored,
        key=lambda x: x.get("quality_score", 0),
        reverse=True
    )

    return scored
