import requests
import pandas as pd
import time
from theme_engine import expand_theme_words

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}




def search_naver_related(theme_name, stocks):
    found = {}

    queries = [
        f"{theme_name} 관련주",
        f"{theme_name} 수혜주",
        f"{theme_name} 대장주",
        f"{theme_name} 테마주",
    ]
    def load_korean_stocks():
    url = "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download"

    try:
        df = pd.read_html(url, header=0)[0]
        df["종목코드"] = df["종목코드"].astype(str).str.zfill(6)

        stocks = []

        for _, row in df.iterrows():
            stocks.append({
                "name": str(row["회사명"]).strip(),
                "code": str(row["종목코드"]).strip(),
                "sector": str(row.get("업종", "")).strip()
            })

        return stocks

    except Exception as e:
        print("KRX 전체 종목 불러오기 실패:", e)
        return []

    for query in queries:
        try:
            res = requests.get(
                "https://search.naver.com/search.naver",
                params={"query": query},
                headers=HEADERS,
                timeout=7
            )

            text = res.text

            for stock in stocks:
                name = stock["name"]

                if name in text:
                    found.setdefault(name, 0)
                    found[name] += 5

            time.sleep(0.2)

        except Exception:
            pass

    return found


def find_direct_mentions(theme, stocks, news):
    found = {}

    articles = theme.get("articles", [])
    text = " ".join([a.get("title", "") for a in articles])

    for stock in stocks:
        name = stock["name"]

        if name in text:
            found.setdefault(name, 0)
            found[name] += 12

    return found


def find_sector_match(theme_name, stocks):
    found = {}
    words = expand_theme_words(theme_name)

    for stock in stocks:
        name = stock["name"]
        sector = stock.get("sector", "")

        score = 0

        for word in words:
            if not word:
                continue

            if word in name:
                score += 5

            if word in sector:
                score += 5

        lower_words = [w.lower() for w in words]

        if any(w in lower_words for w in ["ai", "gpu", "hbm", "semiconductor"]):
            if any(x in sector for x in ["반도체", "전자", "전기", "기계"]):
                score += 2

        if any(w in lower_words for w in ["data center", "datacenter", "power demand", "electricity demand", "grid", "transformer"]):
            if any(x in sector for x in ["전기", "전자", "기계", "건설", "전력"]):
                score += 2

        if any(w in lower_words for w in ["nuclear", "smr"]):
            if any(x in sector for x in ["전기", "기계", "건설", "엔지니어링"]):
                score += 2

        if score > 0:
            found[name] = score

    return found


def merge_scores(stocks, score_maps):
    stock_map = {s["name"]: s for s in stocks}
    merged = {}

    for score_map in score_maps:
        for name, score in score_map.items():
            if name not in stock_map:
                continue

            merged.setdefault(name, 0)
            merged[name] += score

    result = []

    for name, score in merged.items():
        stock = stock_map[name].copy()
        stock["relation_score"] = score
        result.append(stock)

    result = sorted(result, key=lambda x: x["relation_score"], reverse=True)

    return result[:30]


def find_related_stocks(theme, stocks, news):
    theme_name = theme["name"]

    direct = find_direct_mentions(theme, stocks, news)
    naver = search_naver_related(theme_name, stocks)
    sector = find_sector_match(theme_name, stocks)

    candidates = merge_scores(stocks, [direct, naver, sector])

    return candidates
