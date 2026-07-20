import re


# 기사 자체를 핵심 뉴스에서 제외할 표현
BLOCK_KEYWORDS = [
    # 영어 리뷰·추천·분석형 기사
    "week in review",
    "weekly review",
    "market review",
    "stocks to buy",
    "top stocks",
    "stock picks",
    "should investors care",
    "what it means",
    "three reasons",
    "stands to win",
    "what's moving markets",
    "what is moving markets",
    "stock investors",
    "opinion",
    "commentary",

    # 한국어 추천·분석형 기사
    "투자 전략",
    "투자 포인트",
    "투자계획 세워보니",
    "낙폭 과대주",
    "주의해야 할",
    "전망은",
    "분석",
    "칼럼",
    "시황",
    "브리핑",
    "해설",
    "의견",
    "진단",
    "세 가지 이유",
    "세가지 이유",
    "[종목+]",
]


# 실제 자금 이동이나 기업 변화를 나타내는 표현
STRONG_WORDS = [
    # 투자·설비
    "to invest",
    "will invest",
    "invests",
    "investment of",
    "capital expenditure",
    "capex",
    "spending plan",
    "to spend",
    "will spend",

    # 공장·생산·증설
    "build",
    "to build",
    "will build",
    "expand",
    "expansion",
    "factory",
    "new plant",
    "production",
    "mass production",
    "commercial production",

    # 계약·수주·공급
    "contract",
    "supply agreement",
    "supply contract",
    "purchase order",
    "new order",
    "orders worth",
    "partnership",

    # 실적·가이던스
    "revenue",
    "operating profit",
    "guidance",
    "raises guidance",
    "raised guidance",
    "beats estimates",
    "beat estimates",
    "earnings beat",

    # 인수합병
    "acquisition",
    "acquires",
    "acquired",
    "merger",

    # 한국어
    "투자",
    "증설",
    "수주",
    "계약",
    "공급계약",
    "장기공급",
    "공장",
    "공장 건설",
    "공장 투자",
    "양산",
    "생산 확대",
    "매출",
    "영업이익",
    "가이던스",
    "인수",
    "합병",
]


# 완전 차단까지는 아니지만 신뢰도를 떨어뜨리는 표현
WEAK_WORDS = [
    "could",
    "may",
    "might",
    "why shares",
    "why stock",
    "forum",
    "conference",
    "seminar",

    "포럼",
    "세미나",
    "간담회",
    "출범",
    "기념식",
    "토론회",
    "컨퍼런스",
    "가능성",
    "기대감",
]


def contains_keyword(text, keyword):
    """
    영어 키워드는 단어 경계를 검사한다.

    예:
    'beat'가 'marketbeat' 안에서 잘못 감지되는 문제 방지.
    한국어 또는 띄어쓰기 문구는 일반 포함 검사.
    """
    text = str(text or "").lower()
    keyword = str(keyword or "").lower().strip()

    if not keyword:
        return False

    # 영어 단일 단어
    if re.fullmatch(r"[a-z0-9]+", keyword):
        pattern = rf"\b{re.escape(keyword)}\b"
        return re.search(pattern, text) is not None

    # 영어 문구 또는 한국어 문구
    return keyword in text


def score_news_quality(article):
    title = str(article.get("title", "") or "")
    lower_title = title.lower()
    market = article.get("market", "")

    score = 0
    reason = []

    # 1. 추천·주간 리뷰·시황 기사는 먼저 차단
    for keyword in BLOCK_KEYWORDS:
        if contains_keyword(lower_title, keyword):
            return {
                "score": 0,
                "reason": [f"차단뉴스:{keyword}"],
                "is_core": False,
            }

    # 2. 실제 돈의 흐름과 기업 변화를 나타내는 표현
    matched_strong = set()

    for keyword in STRONG_WORDS:
        if contains_keyword(lower_title, keyword):
            matched_strong.add(keyword)

    for keyword in matched_strong:
        score += 20
        reason.append(f"강한뉴스:{keyword}")

    # 3. 추측·행사·기대감 표현 감점
    matched_weak = set()

    for keyword in WEAK_WORDS:
        if contains_keyword(lower_title, keyword):
            matched_weak.add(keyword)

    for keyword in matched_weak:
        score -= 30
        reason.append(f"약한뉴스:{keyword}")

    # 4. 미국 뉴스는 실제 강한 키워드가 있을 때만 가산점
    # 미국 기사라는 이유만으로 핵심 뉴스가 되지 않도록 제한
    if market == "US" and matched_strong:
        score += 10
        reason.append("미국뉴스")

    score = max(0, min(score, 100))

    return {
        "score": score,
        "reason": reason,
        "is_core": score >= 20,
    }


def filter_core_news(news):
    scored = []

    for article in news:
        quality = score_news_quality(article)

        article["quality_score"] = quality["score"]
        article["quality_reason"] = quality["reason"]
        article["is_core_news"] = quality["is_core"]

        if quality["is_core"]:
            scored.append(article)

    return sorted(
        scored,
        key=lambda article: article.get("quality_score", 0),
        reverse=True,
    )
