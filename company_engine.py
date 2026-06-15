import requests
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def search_company_business(stock_name):
    queries = [
        f"{stock_name} 사업내용",
        f"{stock_name} 주요사업",
        f"{stock_name} 투자",
        f"{stock_name} 수주"
    ]

    text = ""

    for q in queries:
        try:
            res = requests.get(
                "https://search.naver.com/search.naver",
                params={"query": q},
                headers=HEADERS,
                timeout=7
            )
            text += " " + res.text
        except:
            pass

    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean)

    return clean


def get_company_match_score(stock, theme_words):
    stock_name = stock["name"]
    sector = stock.get("sector", "")

    text = sector + " " + search_company_business(stock_name)

    score = 0
    matched = []

    for word in theme_words:
        if not word:
            continue

        if word in text:
            score += 5
            matched.append(word)

    if score >= 20:
        memo = "사업내용 강한 일치"
    elif score >= 10:
        memo = "사업내용 일부 일치"
    elif score > 0:
        memo = "사업내용 약한 일치"
    else:
        memo = "사업내용 매칭 약함"

    return {
        "score": score,
        "memo": memo,
        "matched": list(set(matched))[:5]
    }
