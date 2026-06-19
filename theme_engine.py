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
    "data center": ["데이터센터", "전력", "전력기기", "변압기", "전선", "냉각", "냉각시스템", "ESS", "발전", "원전", "SMR", "배전", "송전"],
    "data center": ["데이터센터", "전력", "전력기기", "변압기", "전선", "냉각", "냉각시스템", "ESS", "발전", "원전", "SMR", "배전", "송전"],
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
    "robotaxi": ["자율주행", "전장", "센서", "ADAS", "로보택시"],
    "cybercab": ["자율주행", "전장", "센서", "ADAS", "로보택시"],
    "tesla": ["자율주행", "전장", "센서", "ADAS", "로보택시"],
    "spacex": ["우주항공", "위성", "위성통신", "발사체"],
    "starlink": ["우주항공", "위성통신", "통신장비"],
    "satellite": ["우주항공", "위성", "위성통신"],
    "rocket": ["우주항공", "발사체"],
}

THEME_ARTICLE_KEYWORDS = {
    "AI": ["ai", "artificial intelligence", "인공지능", "nvidia", "openai", "gpu", "ai chip", "machine learning"],
    "ai": ["ai", "artificial intelligence", "인공지능", "nvidia", "openai", "gpu", "ai chip", "machine learning"],

    "반도체": ["semiconductor", "chip", "memory", "hbm", "dram", "micron", "sk hynix", "삼성전자", "반도체"],
    "HBM": ["hbm", "memory", "dram", "micron", "sk hynix", "삼성전자", "하이닉스"],
    "GPU": ["gpu", "nvidia", "엔비디아", "ai chip"],

    "데이터센터": ["data center", "datacenter", "server", "cloud", "데이터센터", "서버", "전력", "냉각"],
    "전력": ["power", "electricity", "grid", "transformer", "전력", "변압기", "전선", "송전", "배전"],
    "전력기기": ["power", "grid", "transformer", "전력기기", "변압기"],
    "변압기": ["transformer", "grid", "변압기", "전력기기"],
    "전선": ["cable", "wire", "grid", "전선", "케이블"],

    "원전": ["nuclear", "smr", "원전", "원자력"],
    "SMR": ["smr", "nuclear", "소형모듈원전"],

    "로봇": ["robot", "robotics", "로봇", "휴머노이드"],
    "방산": ["defense", "missile", "radar", "방산", "미사일", "레이더"],
    "우주항공": ["spacex", "starlink", "satellite", "rocket", "space", "위성", "위성통신", "우주"],
    "스타링크": ["starlink", "satellite internet", "위성통신", "저궤도위성"],
    "위성통신": ["satellite", "starlink", "communication satellite", "위성통신"],
    "우주": ["space", "spacex", "rocket", "launch", "orbit", "우주", "위성"],
    "자율주행": ["robotaxi", "cybercab", "tesla", "autonomous", "self driving", "자율주행", "로보택시", "전장", "ADAS"],
    "2차전지": ["battery", "lithium", "배터리", "2차전지"],
}


def article_matches_theme(theme_name, article):
    title = article.get("title", "")
    lower = title.lower()
    if theme_name in ["AI", "ai"]:
        exclude_words = ["spacex", "space stock", "rocket", "starlink"]
        if any(word in lower for word in exclude_words):
            return False
    keywords = THEME_ARTICLE_KEYWORDS.get(theme_name, [])

    if not keywords:
        expanded = expand_theme_words(theme_name)
        keywords = [str(x).lower() for x in expanded]

    for kw in keywords:
        if not kw:
            continue

        if str(kw).lower() in lower:
            return True

    return False


def unique_articles_for_theme(theme_name, articles, limit=10):
    result = []
    seen = set()

    for article in articles:
        title = article.get("title", "").strip()
        link = article.get("link", "").strip()

        if not title:
            continue

        key = link or title

        if key in seen:
            continue

        if not article_matches_theme(theme_name, article):
            continue

        seen.add(key)
        result.append(article)

        if len(result) >= limit:
            break

    return result


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

        for phrase, expanded_words in CONCEPT_EXPANSION.items():
            if phrase in lower:
                score = 6 if article.get("market") == "US" else 3

                counter[phrase] += score
                theme_articles.setdefault(phrase, []).append(article)

                for word in expanded_words:
                    counter[word] += score
                    theme_articles.setdefault(word, []).append(article)

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
        raw_articles = theme_articles.get(name, [])
        articles = unique_articles_for_theme(name, raw_articles, limit=10)

        if not articles:
            continue

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
