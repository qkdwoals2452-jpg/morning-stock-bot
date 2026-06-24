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


def get_company_match_score(stock, theme_words):
    if len(stock["code"]) != 6 or not stock["code"].isdigit():
        return {"score": 0, "memo": "비상장/코드오류 제외", "matched": {}}
        
    stock_name = stock["name"]
    sector = stock.get("sector", "")

    company_text = sector + " " + collect_company_text(stock_name)

    business_score, business_matched = count_matches(
        company_text,
        theme_words
    )

    customer_keywords = [
        "고객", "납품", "공급", "수주", "계약", "북미", "미국",
        "Microsoft", "Amazon", "Google", "Meta", "Nvidia", "Tesla",
        "SpaceX", "OpenAI"
    ]

    customer_score, customer_matched = count_matches(
        company_text,
        customer_keywords
    )

    supply_keywords = [
        "공급망", "부품", "소재", "장비", "협력사", "벤더",
        "변압기", "전선", "전력기기", "반도체", "기판", "냉각",
        "배터리", "동박", "방산", "우주항공"
    ]

    supply_score, supply_matched = count_matches(
        company_text,
        supply_keywords
    )

    capex_keywords = [
        "증설", "공장", "투자", "CAPEX", "생산능력", "신규라인",
        "북미공장", "미국공장"
    ]

    capex_score, capex_matched = count_matches(
        company_text,
        capex_keywords
    )

    investment_keywords = [
        "지분", "투자", "출자", "관계사", "자회사", "비상장",
        "IPO", "SpaceX", "OpenAI", "xAI", "Anthropic", "Starlink"
    ]

    investment_score, investment_matched = count_matches(
        company_text,
        investment_keywords
    )

    # 1차 수정: 오탐 제거
    # 고객/공급/투자/증설 단어는 네이버 검색 결과에 너무 쉽게 섞이므로
    # 아직 점수에 반영하지 않는다.
    total_score = business_score
    

    if total_score >= 60:
        memo = "사업내용 키워드 일치"
    elif total_score >= 35:
        memo = "사업내용 일부 일치"
    elif total_score > 0:
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
            "business": business_matched[:5],
            "customer": customer_matched[:5],
            "supply": supply_matched[:5],
            "capex": capex_matched[:5],
            "investment": investment_matched[:5],
        }
    }
