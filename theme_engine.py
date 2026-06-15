import re
from collections import Counter

STOPWORDS = {
    "증시", "주가", "상승", "하락", "급등", "급락", "오늘", "국내", "미국",
    "한국", "시장", "투자", "기업", "관련", "기대", "우려", "전망", "기록",
    "속보", "단독", "종합", "마감", "개장", "특징주",
    "news", "stock", "stocks", "market", "shares", "company", "earnings",
    "the", "and", "for", "with", "from", "after", "before", "into", "over",
    "this", "that", "are", "was", "will", "has", "have", "says", "new"
}

CONCEPT_EXPANSION = {
    "ai": ["AI", "데이터센터", "전력", "반도체", "HBM", "냉각", "서버"],
    "artificial intelligence": ["AI", "데이터센터", "전력", "반도체", "HBM", "냉각"],
    "data center": ["데이터센터", "전력", "변압기", "전선", "냉각", "ESS", "원전"],
    "datacenter": ["데이터센터", "전력", "변압기", "전선", "냉각", "ESS", "원전"],
    "power demand": ["전력", "전력기기", "변압기", "전선", "원전", "ESS"],
    "electricity demand": ["전력", "전력기기", "변압기", "전선", "원전", "ESS"],
    "grid": ["전력망", "전력기기", "변압기", "송전", "배전"],
    "transformer": ["변압기", "전력기기", "전력망"],
    "nuclear": ["원전", "SMR", "전력", "발전"],
    "smr": ["SMR", "원전", "발전"],
    "gpu": ["GPU", "HBM", "반도체", "패키징", "기판"],
    "hbm": ["HBM", "반도체", "패키징", "검사장비"],
    "semiconductor": ["반도체", "HBM", "장비", "소재", "기판"],
    "robot": ["로봇", "감속기", "센서", "자동화"],
    "robotics": ["로봇", "감속기", "센서", "자동화"],
    "defense": ["방산", "미사일", "레이더", "항공우주"],
    "battery": ["2차전지", "양극재", "음극재", "전해액", "동박"],
    "copper": ["구리", "전선", "동박", "전력"],
    "rare earth": ["희토류", "자석", "전기차", "방산"],
    "autonomous": ["자율주행", "전장", "센서", "ADAS"],
    "self driving": ["자율주행", "전장", "센서", "ADAS"],
}


def make_reason(theme_name, articles):
    us_count = len([a for a in articles if a.get("market") == "US"])
    kr_count = len([a for a in articles if a.get("market") == "KR"])

    if us_count > 0 and kr_count > 0:
        return f"미국뉴스 {us_count}개와 국내뉴스 {kr_count}개가 동시에 감지됨"

    if us_count > 0:
        return f"미국뉴스 {us_count}개에서 먼저 감지된 테마"

    return f"국내뉴스 {kr_count}개에서 감지된 테마"


def extract_themes(news):
    counter = Counter()
    theme_articles = {}

    for article in news:
        title = article.get("title", "")
        lower = title.lower()

        # 1) 미국 핵심 키워드 → 한국 산업으로 확장
        for phrase, expanded_words in CONCEPT_EXPANSION.items():
            if phrase in lower:
                score = 6 if article.get("market") == "US" else 3

                counter[phrase] += score
                theme_articles.setdefault(phrase, []).append(article)

                for word in expanded_words:
                    counter[word] += score
                    theme_articles.setdefault(word, []).append(article)

        # 2) 뉴스 제목 단어에서 자동 테마 후보 추출
        clean = re.sub(r"[^가-힣A-Za-z0-9 ]", " ", title)
        words = clean.split()

        for word in words:
            w = word.strip()
            lw = w.lower()

            if len(w) < 2:
                continue

            if lw in STOPWORDS:
                continue

            score = 2 if article.get("market") == "US" else 1

            counter[w] += score
            theme_articles.setdefault(w, []).append(article)

    themes = []

    for name, score in counter.most_common(20):
        articles = theme_articles.get(name, [])

        themes.append({
            "name": name,
            "score": score,
            "reason": make_reason(name, articles),
            "articles": articles
        })

    return themes


def expand_theme_words(theme_name):
    words = set()
    words.add(theme_name)

    lower = theme_name.lower()

    if lower in CONCEPT_EXPANSION:
        for w in CONCEPT_EXPANSION[lower]:
            words.add(w)

    for key, values in CONCEPT_EXPANSION.items():
        if theme_name in values:
            words.add(key)
            for v in values:
                words.add(v)

    return list(words)
