import requests
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def clean_html(text):
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def search_text(query):
    try:
        res = requests.get(
            "https://search.naver.com/search.naver",
            params={"query": query},
            headers=HEADERS,
            timeout=7
        )
        return clean_html(res.text)
    except:
        return ""


def collect_company_text(stock_name):
    queries = [
        f"{stock_name} 사업내용",
        f"{stock_name} 주요사업",
        
        
    ]

    text = ""

    for q in queries:
        text += " " + search_text(q)

    return text


def count_matches(text, words):
    score = 0
    matched = []

    for word in words:
        if not word:
            continue

        if word in text:
            score += 3
            matched.append(word)

    return score, list(set(matched))


def count_matches(text, words, point=3, limit=30):
    score = 0
    matched = []

    text_low = text.lower()

    for word in words:
        if not word:
            continue

        if word.lower() in text_low:
            score += point
            matched.append(word)

    return min(score, limit), list(set(matched))


def get_company_match_score(stock, theme_words):
    if len(stock["code"]) != 6 or not stock["code"].isdigit():
        return {
            "score": 0,
            "memo": "비상장/코드오류 제외",
            "business_score": 0,
            "customer_score": 0,
            "supply_score": 0,
            "capex_score": 0,
            "investment_score": 0,
            "matched": {}
        }

    stock_name = stock["name"]
    sector = stock.get("sector", "")

    company_text = sector + " " + collect_company_text(stock_name)

    core_keywords = list(set(theme_words + [
        "AI", "인공지능", "데이터센터", "HBM", "반도체",
        "GPU", "서버", "패키징", "메모리", "전력",
        "전력기기", "변압기", "냉각", "ESS"
    ]))

    business_score, business_matched = count_matches(
        company_text,
        core_keywords,
        point=6,
        limit=60
    )

    customer_keywords = [
        "고객", "납품", "공급", "수주", "계약",
        "Nvidia", "엔비디아", "Microsoft", "Amazon",
        "Google", "Meta", "Tesla", "OpenAI", "SpaceX"
    ]

    customer_score, customer_matched = count_matches(
        company_text,
        customer_keywords,
        point=4,
        limit=20
    )

    supply_keywords = [
        "공급망", "부품", "소재", "장비", "협력사", "벤더",
        "패키징", "기판", "냉각", "전력기기", "변압기",
        "반도체", "배터리"
    ]

    supply_score, supply_matched = count_matches(
        company_text,
        supply_keywords,
        point=3,
        limit=15
    )

    capex_keywords = [
        "증설", "공장", "투자", "CAPEX", "생산능력",
        "신규라인", "북미공장", "미국공장"
    ]

    capex_score, capex_matched = count_matches(
        company_text,
        capex_keywords,
        point=3,
        limit=10
    )

    investment_keywords = [
        "지분", "투자", "출자", "관계사", "자회사",
        "비상장", "IPO", "SpaceX", "OpenAI", "xAI",
        "Anthropic", "Starlink"
    ]

    investment_score, investment_matched = count_matches(
        company_text,
        investment_keywords,
        point=3,
        limit=10
    )

    total_score = (
        business_score
        + customer_score
        + supply_score
        + capex_score
        + investment_score
    )
    exclude = False

    exclude_reason = ""

    if total_score < 45:

        exclude = True

        exclude_reason = "사업내용 매칭 약함"
    if total_score >= 70:
        memo = "사업내용 강한 일치"
    elif total_score >= 45:
        memo = "사업내용 일부 일치"
    elif total_score >= 20:
        memo = "사업내용 약한 일치"
    else:
        memo = "기업카드 매칭 약함"

    return {
        "score": total_score,
        "memo": memo,
        "business_score": business_score,
        "customer_score": customer_score,
        "supply_score": supply_score,
        "capex_score": capex_score,
        "investment_score": investment_score,
        "matched": {
            "business": business_matched[:8],
            "customer": customer_matched[:5],
            "supply": supply_matched[:5],
            "capex": capex_matched[:5],
            "investment": investment_matched[:5]
        },
        "exclude": exclude,

        "exclude_reason": exclude_reason
    }
