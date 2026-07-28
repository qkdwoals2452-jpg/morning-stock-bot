import re


GENERIC_WORDS = {
    "ai",
    "인공지능",
    "반도체",
    "공급",
    "투자",
    "계약",
    "장비",
    "부품",
    "소재",
    "사업",
    "고객",
    "수주",
    "생산",
    "공장",
    "서버",
    "데이터센터"
}


STRONG_WORDS = {
    "hbm",
    "hbm3",
    "hbm3e",
    "hbm4",
    "gpu",
    "cdu",
    "액침냉각",
    "수랭식",
    "liquid cooling",
    "cowos",
    "패키징",
    "유리기판",
    "실리콘포토닉스",
    "변압기",
    "전력기기",
    "ess",
    "낸드",
    "dram",
    "파운드리",
    "첨단패키징",
    "후공정",
    "테스트소켓",
    "프로브카드"
}


CUSTOMER_WORDS = {
    "nvidia",
    "엔비디아",
    "microsoft",
    "마이크로소프트",
    "amazon",
    "아마존",
    "google",
    "구글",
    "meta",
    "메타",
    "openai",
    "tesla",
    "테슬라",
    "tsmc",
    "micron",
    "마이크론",
    "broadcom",
    "브로드컴"
}


def normalize_text(text):
    text = str(text or "").lower()
    text = re.sub(r"\s+", " ", text)
    return text


def flatten_company_words(company):
    matched = company.get("matched", {})

    words = []

    for value in matched.values():
        if isinstance(value, list):
            words.extend(value)

    cleaned = []

    for word in words:
        word_low = normalize_text(word).strip()

        if not word_low:
            continue

        if word_low in GENERIC_WORDS:
            continue

        cleaned.append(word_low)

    return list(set(cleaned))


def get_news_impact_score(stock, theme, articles, company):
    stock_name = normalize_text(stock.get("name", ""))
    stock_code = normalize_text(stock.get("code", ""))

    article_text_parts = []

    for article in articles:
        article_text_parts.append(article.get("title", ""))
        article_text_parts.append(article.get("summary", ""))

    article_text = normalize_text(" ".join(article_text_parts))

    company_words = flatten_company_words(company)

    direct_matched = []
    strong_matched = []
    customer_matched = []

    for word in company_words:
        if word in article_text:
            direct_matched.append(word)

            if word in STRONG_WORDS:
                strong_matched.append(word)

            if word in CUSTOMER_WORDS:
                customer_matched.append(word)

    score = 0
    reasons = []

    # 1. 회사명이 기사에 직접 등장
    if stock_name and stock_name in article_text:
        score += 70
        reasons.append("기사에 회사명 직접 등장")

    # 2. 종목코드가 기사에 등장
    if stock_code and stock_code in article_text:
        score += 20
        reasons.append("기사에 종목코드 등장")

    # 3. 구체적인 제품·기술 키워드
    if strong_matched:
        strong_score = min(len(set(strong_matched)) * 15, 45)
        score += strong_score
        reasons.append(
            "구체 기술 일치: " + ", ".join(sorted(set(strong_matched))[:5])
        )

    # 4. 고객사·글로벌 기업 연결
    if customer_matched:
        customer_score = min(len(set(customer_matched)) * 10, 20)
        score += customer_score
        reasons.append(
            "고객사 연결: " + ", ".join(sorted(set(customer_matched))[:3])
        )

    # 5. 일반 직접 매칭은 낮은 점수만 부여
    other_matched = [
        word
        for word in direct_matched
        if word not in strong_matched
        and word not in customer_matched
    ]

    if other_matched:
        other_score = min(len(set(other_matched)) * 3, 15)
        score += other_score
        reasons.append(
            "사업 키워드 일부 일치: "
            + ", ".join(sorted(set(other_matched))[:5])
        )

    score = min(score, 100)

    if score >= 70:
        memo = "뉴스 직접 수혜 가능성 높음"
    elif score >= 40:
        memo = "뉴스 수혜 연결 가능성 있음"
    elif score >= 20:
        memo = "뉴스 간접 관련"
    else:
        memo = "뉴스와 직접 연결 약함"

    exclude = score < 20

    return {
        "score": score,
        "memo": memo,
        "matched": sorted(set(direct_matched))[:10],
        "strong_matched": sorted(set(strong_matched))[:10],
        "customer_matched": sorted(set(customer_matched))[:10],
        "reasons": reasons,
        "exclude": exclude,
        "exclude_reason": (
            "기사와 기업의 직접 연결 근거 부족"
            if exclude
            else ""
        )
    }
