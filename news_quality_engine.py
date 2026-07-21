import re


def contains_keyword(text, keyword):
    """
    영어 한 단어 키워드는 단어 단위로만 검사한다.

    예:
    - "beat estimates" 안의 "beat"는 감지
    - "MarketBeat" 안의 "beat"는 감지하지 않음
    """
    text = str(text or "").lower()
    keyword = str(keyword or "").lower().strip()

    if not keyword:
        return False

    # 영어 한 단어만 단어 경계 검사
    if re.fullmatch(r"[a-z0-9]+", keyword):
        pattern = rf"\b{re.escape(keyword)}\b"
        return re.search(pattern, text) is not None

    # 영어 문장 또는 한국어 키워드는 기존 방식 그대로 검사
    return keyword in text


def score_news_quality(article):
    title = article.get("title", "").lower()
    market = article.get("market", "")
    text = title

    score = 0
    reason = []

    # 수정 1: 주간 리뷰형 기사 차단
    if "week in review" in text:
        return {
            "score": 0,
            "reason": ["차단뉴스:week in review"],
            "is_core": False
        }

    # 진짜 돈이 움직이는 뉴스
    strong_words = [
        "to invest", "will invest", "invests", "investment of", "investment", "spend", "spending", "capex",
        "build", "expand", "expansion", "contract",
        "supply", "order", "factory", "plant", "production",
        "revenue", "guidance", "beat", "raise",
        "acquisition", "merger", "partnership",
        "투자", "증설", "수주", "계약", "공급", "공장",
        "양산", "생산", "실적", "매출", "영업이익", "인수", "합병"
         

        "to invest",

        "will invest",

        "invests",

        "investment",

        "investment of",

        "capital expenditure",

        "capex",

        "spend",

        "spending",

        "spending plan",

        "to spend",

        "will spend",

        # 공장 / 생산

        "build",

        "to build",

        "will build",

        "expand",

        "expansion",

        "factory",

        "plant",

        "new plant",

        "production",

        "mass production",

        "commercial production",

        "volume production",

        # 계약 / 공급 / 수주

        "contract",

        "long-term contract",

        "supply",

        "supply agreement",

        "supply contract",

        "purchase order",

        "new order",

        "orders worth",

        "partnership",

        # 실적

        "revenue",

        "operating profit",

        "guidance",

        "raise",

        "raises guidance",

        "raised guidance",

        "beat",

        "beats estimates",

        "beat estimates",

        "earnings beat",

        # 인수합병

        "acquisition",

        "acquires",

        "acquired",

        "merger",

        # 승인 (일반 approval은 제외)

        "fda approval",

        # AI / 데이터센터

        "data center",

        "datacenter",

        "gpu",

        "ai infrastructure",

        # 한국어

        "투자",

        "투자 확대",

        "증설",

        "생산",

        "생산 확대",

        "양산",

        "상업 생산",

        "공장",

        "공장 건설",

        "공장 투자",

        "수주",

        "계약",

        "장기공급",

        "공급",

        "공급계약",

        "매출",

        "실적",

        "영업이익",

        "가이던스",

        "인수",

        "합병",

        # FDA 승인만 유지

        "FDA 승인",

        # AI / 데이터센터

        "데이터센터",

        "AI 인프라",
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
        # 수정 2: MarketBeat 안의 beat 오탐 방지
        if contains_keyword(text, w):
            score += 20
            reason.append(f"강한뉴스:{w}")

    for w in weak_words:
        if contains_keyword(text, w):
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
