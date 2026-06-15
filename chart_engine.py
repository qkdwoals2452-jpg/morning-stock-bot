import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://m.stock.naver.com/"
}


def to_float(value):
    try:
        return float(str(value).replace(",", "").replace("%", ""))
    except:
        return None


def get_price_history(code):
    """
    네이버 모바일 차트 API에서 최근 일봉 데이터를 가져온다.
    실패하면 빈 리스트 반환.
    """

    urls = [
        f"https://m.stock.naver.com/api/stock/{code}/chart/day?periodType=dayCandle",
        f"https://api.stock.naver.com/chart/domestic/item/{code}/day?periodType=dayCandle"
    ]

    for url in urls:
        try:
            res = requests.get(
                url,
                headers=HEADERS,
                timeout=7
            )

            data = res.json()

            if isinstance(data, dict):
                raw = data.get("priceInfos") or data.get("data") or []
            else:
                raw = data

            prices = []

            for row in raw:
                close = (
                    row.get("closePrice")
                    or row.get("close")
                    or row.get("endPrice")
                )

                high = (
                    row.get("highPrice")
                    or row.get("high")
                )

                low = (
                    row.get("lowPrice")
                    or row.get("low")
                )

                volume = (
                    row.get("accumulatedTradingVolume")
                    or row.get("volume")
                )

                close = to_float(close)
                high = to_float(high)
                low = to_float(low)
                volume = to_float(volume)

                if close is not None:
                    prices.append({
                        "close": close,
                        "high": high,
                        "low": low,
                        "volume": volume
                    })

            if prices:
                return prices[-260:]

        except:
            pass

    return []


def moving_average(values, days):
    if len(values) < days:
        return None

    return sum(values[-days:]) / days


def get_chart_score(stock):
    code = stock["code"]

    history = get_price_history(code)

    if len(history) < 60:
        return {
            "score": 0,
            "memo": "차트 데이터 부족",
            "details": {}
        }

    closes = [x["close"] for x in history if x["close"] is not None]
    highs = [x["high"] for x in history if x["high"] is not None]

    if not closes:
        return {
            "score": 0,
            "memo": "차트 확인불가",
            "details": {}
        }

    current = closes[-1]

    ma20 = moving_average(closes, 20)
    ma60 = moving_average(closes, 60)
    ma120 = moving_average(closes, 120)

    high_52w = max(highs) if highs else None

    score = 0
    memo = []

    # 20일선 돌파/상회
    if ma20:
        if current > ma20:
            score += 5
            memo.append("20일선 위")
        else:
            score -= 3
            memo.append("20일선 아래")

    # 60일선 상회
    if ma60:
        if current > ma60:
            score += 7
            memo.append("60일선 위")
        else:
            score -= 5
            memo.append("60일선 아래")

    # 120일선 상회
    if ma120:
        if current > ma120:
            score += 5
            memo.append("120일선 위")
        else:
            score -= 3
            memo.append("120일선 아래")

    # 52주 고점 대비 낙폭
    high_gap = None

    if high_52w and high_52w > 0:
        high_gap = round((current - high_52w) / high_52w * 100, 2)

        if -25 <= high_gap <= -8:
            score += 10
            memo.append("고점 대비 적당한 조정")
        elif high_gap > -5:
            score -= 5
            memo.append("고점 근처 추격주의")
        elif high_gap < -40:
            score -= 5
            memo.append("장기 약세 주의")

    # 최근 20일 고점 돌파
    if len(closes) >= 21:
        recent_high = max(closes[-21:-1])

        if current > recent_high:
            score += 10
            memo.append("20일 신고가 돌파")

    if not memo:
        memo.append("차트 중립")

    return {
        "score": score,
        "memo": ", ".join(memo),
        "details": {
            "current": current,
            "ma20": round(ma20, 2) if ma20 else None,
            "ma60": round(ma60, 2) if ma60 else None,
            "ma120": round(ma120, 2) if ma120 else None,
            "high_52w_gap": high_gap
        }
    }
