import requests
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


THEME_VERIFY_WORDS = {
    "데이터센터": ["데이터센터", "전력", "변압기", "전력기기", "냉각", "비상발전기", "서버", "ESS"],
    "전력": ["전력", "전력기기", "변압기", "송전", "배전", "초고압", "전선"],
    "반도체": ["반도체", "메모리", "HBM", "패키징", "검사장비", "장비", "소재"],
    "HBM": ["HBM", "메모리", "패키징", "검사장비", "본딩", "테스트"],
    "AI": ["AI", "인공지능", "GPU", "HBM", "데이터센터", "서버", "반도체"],
    "냉각": ["냉각", "액침냉각", "열관리", "공조", "칠러", "데이터센터"],
    "우주항공": ["우주", "위성", "위성통신", "발사체", "항공우주"],
    "자율주행": ["자율주행", "ADAS", "전장", "센서", "카메라", "라이다"],
    "방산": ["방산", "미사일", "레이더", "유도무기", "항공"],
    "원전": ["원전", "원자력", "SMR", "발전", "터빈"]
}


def clean_html(text):
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def search_company_text(stock_name):
    queries = [
        f"{stock_name} 사업내용",
        f"{stock_name} 주요사업",
        f"{stock_name} 주요제품",
        f"{stock_name} 수주",
        f"{stock_name} 공급",
        f"{stock_name} 투자"
    ]

    text = ""

    for q in queries:
        try:
            res = requests.get(
                "https://search.naver.com/search.naver",
                params={"query": q},
                headers=HEADERS,
                timeout=5
            )
            text += " " + clean_html(res.text)
        except:
            pass

    return text


def verify_company_theme(stock, theme_name):
    stock_name = stock.get("name", "")
    sector = stock.get("sector", "")

    words = THEME_VERIFY_WORDS.get(theme_name, [])

    if not words:
        return {
            "pass": False,
            "score": 0,
            "memo": "검증 키워드 없음",
            "matched": []
        }

    text = sector + " " + search_company_text(stock_name)

    score = 0
    matched = []

    for word in words:
        if word in text:
            score += 15
            matched.append(word)

    matched = list(set(matched))

    if score >= 70:
        passed = True
        memo = "사업내용 검증 통과"
    elif score >= 40:
        passed = False
        memo = "사업내용 일부 관련, 추천 제외"
    else:
        passed = False
        memo = "사업내용 불일치, 추천 제외"

    return {
        "pass": passed,
        "score": score,
        "memo": memo,
        "matched": matched[:5]
    }
