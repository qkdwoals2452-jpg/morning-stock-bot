import requests
import pandas as pd
import time
import io
import re
from theme_engine import expand_theme_words
from impact_engine import assess_company_event_relation

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def load_korean_stocks():
    url = "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download"
    # timeout은 소켓 대기 제한이며 전체 실행의 강제 종료 시간은 아니다.
    last_error = "unknown"
    for attempt in range(1, 3):
        res = None
        try:
            res = requests.get(url, headers=HEADERS, timeout=(5, 10))
            res.raise_for_status()
            res.encoding = "euc-kr"
            tables = pd.read_html(io.StringIO(res.text), header=0, flavor="lxml",
                                  converters={"종목코드": str})
            df = next((frame for frame in tables if
                       {"회사명", "종목코드", "업종"}.issubset(frame.columns)), None)
            if df is None or df.empty:
                raise ValueError("invalid stock table")
            stocks = []
            codes = set()
            for _, row in df.iterrows():
                name = row["회사명"]
                code = str(row["종목코드"]).strip()
                if re.fullmatch(r"[0-9]{1,6}", code):
                    code = code.zfill(6)
                if (pd.isna(name) or not str(name).strip()
                        or not re.fullmatch(r"[0-9A-Z]{6}", code) or code in codes):
                    raise ValueError("invalid stock row")
                codes.add(code)
                sector = row["업종"]
                stocks.append({"name": str(name).strip(), "code": code,
                               "sector": "" if pd.isna(sector) else str(sector).strip()})
            print("KRX 종목 수:", len(stocks))
            return stocks
        except (requests.RequestException, ValueError, KeyError) as exc:
            # 요청 URL이나 응답 본문 대신 오류 종류만 기록한다.
            last_error = type(exc).__name__
            print(f"KRX 목록 조회 실패: 시도 {attempt}/2 | 사유={last_error}")
        finally:
            if res is not None:
                res.close()
        if attempt < 2:
            time.sleep(1)
    raise RuntimeError(f"KRX 종목 목록 확인불가 ({last_error}) → 추천 실행 중단") from None


def search_naver_related(theme_name, stocks):
    found = {}

    queries = [
        f"{theme_name} 관련주",
        f"{theme_name} 수혜주",
        f"{theme_name} 대장주",
        f"{theme_name} 테마주",
    ]

    for query in queries:
        try:
            res = requests.get(
                "https://search.naver.com/search.naver",
                params={"query": query},
                headers=HEADERS,
                timeout=5
            )

            text = res.text

            for stock in stocks:
                name = stock["name"]

                if name and name in text:
                    found.setdefault(name, 0)
                    found[name] += 5

            time.sleep(0.1)

        except Exception:
            pass

    return found



def _has_company_mention(name, text):
    # 하이브리드의 '하이브'처럼 다른 단어의 일부는 기업 언급이 아니다.
    # 한국어 조사는 허용하되 조사 뒤에도 단어 경계를 요구한다.
    pattern = (r"(?<![가-힣A-Za-z0-9])" + re.escape(name)
               + r"(?=(?:은|는|이|가|을|를|와|과|의|에|에게|에서|으로부터|로부터|으로|로|도|만)?"
                 r"(?:[^가-힣A-Za-z0-9]|$))")
    return bool(re.search(pattern, text))


def find_direct_mentions(theme, stocks, news):
    found = {}

    articles = theme.get("articles", [])

    text_parts = []

    for article in articles:
        text_parts.append(article.get("title", ""))
        text_parts.append(article.get("summary", ""))
        text_parts.append(article.get("description", ""))

    text = " ".join(text_parts)

    # =====================================================
    # ORION COMPANY ALIAS MAP
    # 언론에서 자주 사용하는 회사 약칭 → KRX 정식 회사명
    # =====================================================
    company_aliases = {
        "삼성重": "삼성중공업",
        "삼성중": "삼성중공업",
        "한화에어로": "한화에어로스페이스",
    }

    # 1. 약칭 직접 매칭
    for alias, official_name in company_aliases.items():
        if _has_company_mention(alias, text):
            found[official_name] = 100

    # =====================================================
    # 2. KRX 정식 회사명 매칭
    #
    # 긴 회사명을 먼저 찾는다.
    # 이미 더 긴 회사명 안에서 발견된 짧은 회사명은 제외한다.
    #
    # 예:
    # SK하이닉스 → SK 제외
    # SK하이닉스 → 이닉스 제외
    # =====================================================

    matched_names = []

    sorted_stocks = sorted(
        stocks,
        key=lambda x: len(x.get("name", "")),
        reverse=True
    )

    for stock in sorted_stocks:
        name = stock.get("name", "").strip()

        if not name:
            continue

        if not _has_company_mention(name, text):
            continue

        # 두 글자 이름도 확정 사건의 당사자 근거가 있으면 허용한다.
        # 원익을 원익IPS의 일부로 찾거나 SK를 SK하이닉스로 오인하지 않는다.
        if len(name) <= 2:
            if assess_company_event_relation(stock, articles)["pass"]:
                found[name] = 100
            continue

        # 이미 발견한 더 긴 회사명의 일부라면 제외
        is_substring = False

        for matched_name in matched_names:
            if name != matched_name and name in matched_name:
                is_substring = True
                break

        if is_substring:
            continue

        found[name] = 100
        matched_names.append(name)

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
           if any(x in sector for x in ["전기", "전자", "기계", "건설", "전력", "에너지"]):
               score += 15

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
        if not score_map:
            continue

        for name, score in score_map.items():
            if name not in stock_map:
                continue

            merged.setdefault(name, 0)
            merged[name] += score

    candidates = []

    for name, score in merged.items():
        stock = stock_map[name].copy()
        stock["relation_score"] = score
        candidates.append(stock)

    candidates = sorted(
        candidates,
        key=lambda x: x["relation_score"],
        reverse=True
    )

    return candidates[:50]
    
def find_related_stocks(theme, stocks, news):
    theme_name = theme["name"]

    # =====================================================
    # ORION DIRECT RELATION CANDIDATE GATE
    # 기사에 실제로 등장한 한국 상장사만 1차 후보 허용
    # =====================================================

    direct = find_direct_mentions(
        theme,
        stocks,
        news
    )

    candidates = merge_scores(
        stocks,
        [direct]
    )

    print(
        "직접 언급 후보 수:",
        theme_name,
        len(candidates)
    )

    if candidates:
        print(
            "직접 언급 후보:",
            [
                stock["name"]
                for stock in candidates[:20]
            ]
        )

    return candidates
