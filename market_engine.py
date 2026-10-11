import requests
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def to_float(value):
    try:
        return float(str(value).replace(",", "").replace("%", ""))
    except:
        return None


def to_int(value):
    try:
        return int(str(value).replace(",", ""))
    except:
        return None


def get_naver_market(code):
    try:
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        today = now.strftime("%Y%m%d")
        url = f"https://api.stock.naver.com/chart/domestic/item/{code}/day"
        res = requests.get(url, headers=HEADERS, params={
            "startDateTime": (now - timedelta(days=70)).strftime("%Y%m%d"),
            "endDateTime": today,
        }, timeout=7)
        res.raise_for_status()
        rows = res.json()
        if not isinstance(rows, list):
            raise ValueError("일별 차트 응답 형식 오류")
        # 아침에는 완료된 거래일을 사용하고, 날짜순으로 최신 행을 선택한다.
        rows = sorted((row for row in rows
                       if row.get("localDate")
                       and (row["localDate"] < today
                            or (row["localDate"] == today and now.time() >= time(15, 30)))),
                      key=lambda row: row["localDate"])
        if not rows:
            raise ValueError("완료된 거래일 데이터 없음")
        latest = rows[-1]
        volume = to_int(latest.get("accumulatedTradingVolume"))
        close = to_float(latest.get("closePrice"))
        previous = to_float(rows[-2].get("closePrice")) if len(rows) >= 2 else None
        change_rate = round((close / previous - 1) * 100, 2) if close is not None and previous else None
        value = int(volume * close) if volume is not None and close is not None else None
        print("MARKET VALUE:", code, "date:", latest["localDate"], "estimated:", value)
        return {
            "change_rate": change_rate, "volume": volume, "trading_value": value,
            "trading_date": latest["localDate"], "trading_value_is_estimate": True,
        }
    except Exception as e:
        print("MARKET ERROR:", code, type(e).__name__)
        return {"change_rate": None, "volume": None, "trading_value": None,
                "trading_date": None, "trading_value_is_estimate": True}


def get_market_score(stock):
    code = stock["code"]

    market = get_naver_market(code)

    score = 0
    memo = []

    change = market["change_rate"]
    value = market["trading_value"]

    if change is not None:
        if change >= 7:
            score += 20
            memo.append("급등 강세")
        elif change >= 5:
            score += 15
            memo.append("강한 상승")
        elif change >= 3:
            score += 10
            memo.append("상승 반응")
        elif change >= 1:
            score += 5
            memo.append("초기 반응")
        elif change <= -7:
            score -= 10
            memo.append("급락 주의")
        elif change <= -3:
            score -= 5
            memo.append("약세")

    if value is not None:
        if value >= 3000_0000_0000:
            score += 25
            memo.append("거래대금 폭발")
        elif value >= 1500_0000_0000:
            score += 20
            memo.append("거래대금 강함")
        elif value >= 500_0000_0000:
            score += 10
            memo.append("거래대금 양호")
        elif value >= 100_0000_0000:
            score += 5
            memo.append("거래대금 발생")
        else:
            score -= 3
            memo.append("거래대금 약함")

    if not memo:
        memo.append("시장 데이터 확인불가")

    return {
        "score": score,
        "memo": ", ".join(memo),
        "change_rate": change,
        "volume": market["volume"],
        "trading_value": value,
        "trading_date": market.get("trading_date"),
        "trading_value_is_estimate": market.get("trading_value_is_estimate", True)
    }
