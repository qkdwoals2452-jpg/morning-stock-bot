import re
from collections import Counter

from industry_map import INDUSTRY_MAP


STOPWORDS = {
    "증시", "주가", "상승", "하락", "급등", "급락", "오늘", "국내", "미국",
    "한국", "시장", "투자", "기업", "관련", "기대", "우려", "전망", "기록",
    "속보", "단독", "종합", "마감", "개장", "특징주",

    "계약", "공급", "공급계약", "수주", "인수", "합병",
    "양산", "생산", "공장", "증설",
    "매출", "실적", "영업이익", "분기",
    "지분",

    "news", "stock", "stocks", "market", "shares", "company", "earnings",
    "the", "and", "for", "with", "from", "after", "before", "into", "over",
    "this", "that", "are", "was", "will", "has", "have", "says", "new",

    # 아래에서는 소문자로 비교하므로 소문자로 저장
    "q1", "q2", "q3", "q4",
}


BIG_PLAYERS = {
    "meta": "데이터센터",
    "microsoft": "데이터센터",
    "amazon": "클라우드",
    "google": "AI",
    "alphabet": "AI",
    "nvidia": "반도체",
    "amd": "반도체",
    "tesla": "자율주행",
    "spacex": "우주항공",
    "starlink": "위성통신",
    "openai": "AI",
}


CONCEPT_EXPANSION = {
    "ai": [
        "AI", "데이터센터", "전력", "반도체",
        "HBM", "냉각", "서버",
    ],

    "artificial intelligence": [
        "AI", "데이터센터", "전력",
        "반도체", "HBM", "냉각",
    ],

    "data center": [
        "데이터센터", "전력", "전력기기", "변압기",
        "전선", "냉각", "냉각시스템", "ESS",
        "발전", "원전", "SMR", "배전", "송전",
    ],

    "power demand": [
        "전력", "전력기기", "변압기", "전선", "원전", "ESS",
    ],

    "electricity demand": [
        "전력", "전력기기", "변압기", "전선", "원전", "ESS",
    ],

    "grid": [
        "전력망", "전력기기", "변압기", "송전", "배전",
    ],

    "transformer": [
        "변압기", "전력기기", "전력망",
    ],

    "nuclear": [
        "원전", "SMR", "전력", "발전",
    ],

    "smr": [
        "SMR", "원전", "발전",
    ],

    "gpu": [
        "GPU", "HBM", "반도체", "패키징", "기판",
    ],

    "hbm": [
        "HBM", "반도체", "패키징", "검사장비",
    ],

    "semiconductor": [
        "반도체", "HBM", "장비", "소재", "기판",
    ],

    "robot": [
        "로봇", "감속기", "센서", "자동화",
    ],

    "robotics": [
        "로봇", "감속기", "센서", "자동화",
    ],

    "defense": [
        "방산", "미사일", "레이더", "항공우주",
    ],

    "battery": [
        "2차전지", "양극재", "음극재", "전해액", "동박",
    ],

    "copper": [
        "구리", "전선", "동박", "전력",
    ],

    "rare earth": [
        "희토류", "자석", "전기차", "방산",
    ],

    "autonomous": [
        "자율주행", "전장", "센서", "ADAS",
    ],

    "self driving": [
        "자율주행", "전장", "센서", "ADAS",
    ],

    "robotaxi": [
        "자율주행", "전장", "센서", "ADAS", "로보택시",
    ],

    "cybercab": [
        "자율주행", "전장", "센서", "ADAS", "로보택시",
    ],

    "tesla": [
        "자율주행", "전장", "센서", "ADAS", "로보택시",
    ],

    "spacex": [
        "우주항공", "위성", "위성통신", "발사체",
    ],

    "starlink": [
        "우주항공", "위성통신", "통신장비",
    ],

    "satellite": [
        "우주항공", "위성", "위성통신",
    ],

    "rocket": [
        "우주항공", "발사체",
    ],
}


THEME_ARTICLE_KEYWORDS = {
    "AI": [
        "ai", "artificial intelligence", "인공지능",
        "nvidia", "openai", "gpu", "ai chip",
        "machine learning",
    ],

    "반도체": [
        "semiconductor", "chip", "memory", "hbm",
        "dram", "micron", "sk hynix", "삼성전자", "반도체",
    ],

    "HBM": [
        "hbm", "memory", "dram", "micron",
        "sk hynix", "삼성전자", "하이닉스",
    ],

    "GPU": [
        "gpu", "nvidia", "엔비디아", "ai chip",
    ],

    "데이터센터": [
        "data center", "datacenter", "server", "cloud",
        "데이터센터", "서버", "전력", "냉각",
    ],

    "전력": [
        "power", "electricity", "grid", "transformer",
        "전력", "변압기", "전선", "송전", "배전",
    ],

    "전력기기": [
        "power", "grid", "transformer", "전력기기", "변압기",
    ],

    "변압기": [
        "transformer", "grid", "변압기", "전력기기",
    ],

    "전선": [
        "cable", "wire", "grid", "전선", "케이블",
    ],

    "원전": [
        "nuclear", "smr", "원전", "원자력",
    ],

    "SMR": [
        "smr", "nuclear", "소형모듈원전",
    ],

    "로봇": [
        "robot", "robotics", "로봇", "휴머노이드",
    ],

    "방산": [
        "defense", "missile", "radar",
        "방산", "미사일", "레이더",
    ],

    "우주항공": [
        "spacex", "starlink", "satellite", "rocket",
        "space", "위성", "위성통신", "우주",
    ],

    "스타링크": [
        "starlink", "satellite internet",
        "위성통신", "저궤도위성",
    ],

    "위성통신": [
        "satellite", "starlink",
        "communication satellite", "위성통신",
    ],

    "우주": [
        "space", "spacex", "rocket",
        "launch", "orbit", "우주", "위성",
    ],

    "자율주행": [
        "robotaxi", "cybercab", "tesla",
        "autonomous", "self driving",
        "자율주행", "로보택시", "전장", "adas",
    ],

    "2차전지": [
        "battery", "lithium", "배터리", "2차전지",
    ],
}


def article_matches_theme(theme_name, article):
    title = article.get("title", "")
    lower = title.lower()

    if theme_name == "AI":
        exclude_words = [
            "spacex",
            "space stock",
            "rocket",
            "starlink",
        ]

        if any(word in lower for word in exclude_words):
            return False

    keywords = THEME_ARTICLE_KEYWORDS.get(theme_name, [])

    if not keywords:
        expanded = expand_theme_words(theme_name)
        keywords = [str(item).lower() for item in expanded]

    for keyword in keywords:
        keyword = str(keyword).strip().lower()

        if not keyword:
            continue

        if keyword in lower:
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
    us_count = len([
        article
        for article in articles
        if article.get("market") == "US"
    ])

    kr_count = len([
        article
        for article in articles
        if article.get("market") == "KR"
    ])

    if us_count > 0 and kr_count > 0:
        return (
            f"미국뉴스 {us_count}개와 "
            f"국내뉴스 {kr_count}개가 동시에 감지됨"
        )

    if us_count > 0:
        return f"미국뉴스 {us_count}개에서 먼저 감지된 테마"

    return f"국내뉴스 {kr_count}개에서 감지된 테마"


def extract_themes(news):
    counter = Counter()
    theme_articles = {}

    for article in news:
        title = article.get("title", "")
        lower = title.lower()
        market = article.get("market")

        # 대형 기업명 기반 테마 감지
        for company, theme in BIG_PLAYERS.items():
            if company in lower:
                score = 10 if market == "US" else 5

                counter[theme] += score
                theme_articles.setdefault(theme, []).append(article)

        # 개념 키워드 기반 테마 확장
        for phrase, expanded_words in CONCEPT_EXPANSION.items():
            if phrase in lower:
                score = 10 if market == "US" else 5

                # phrase는 감지용 키워드이므로
                # ai, copper 등을 별도 테마로 저장하지 않는다.
                for word in expanded_words:
                    counter[word] += score
                    theme_articles.setdefault(word, []).append(article)

        # 제목 안의 일반 단어 추출
        clean = re.sub(
            r"[^가-힣A-Za-z0-9 ]",
            " ",
            title,
        )

        words = clean.split()

        for word in words:
            word = word.strip()
            lower_word = word.lower()

            if len(word) < 2:
                continue

            # 07, 2026 등 숫자만 있는 단어 제외
            if word.isdigit():
                continue

            if lower_word in STOPWORDS:
                continue

            # AI, ai, Ai를 모두 AI로 통일
            theme_name = "AI" if lower_word == "ai" else word

            score = 2 if market == "US" else 1

            counter[theme_name] += score
            theme_articles.setdefault(
                theme_name,
                [],
            ).append(article)

    themes = []

    for name, score in counter.most_common(20):
        raw_articles = theme_articles.get(name, [])

        articles = unique_articles_for_theme(
            name,
            raw_articles,
            limit=10,
        )

        if not articles:
            continue

        themes.append({
            "name": name,
            "score": score,
            "reason": make_reason(name, articles),
            "articles": articles,
        })

    return themes


def expand_theme_words(theme_name):
    words = {theme_name}

    for word in expand_with_industry_map(theme_name):
        words.add(word)

    lower_theme = theme_name.lower()

    if lower_theme in CONCEPT_EXPANSION:
        for word in CONCEPT_EXPANSION[lower_theme]:
            words.add(word)

    for key, values in CONCEPT_EXPANSION.items():
        if theme_name in values:
            words.add(key)

            for value in values:
                words.add(value)

    return list(words)


def expand_with_industry_map(theme_name):
    words = {theme_name}

    if theme_name in INDUSTRY_MAP:
        for item in INDUSTRY_MAP[theme_name]:
            words.add(item)

    for key, values in INDUSTRY_MAP.items():
        if theme_name in values:
            words.add(key)

            for item in values:
                words.add(item)

    return list(words)
