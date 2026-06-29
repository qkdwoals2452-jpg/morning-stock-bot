import requests

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
        url = f"https://m.stock.naver.com/api/stock/{code}/basic"

        res = requests.get(
            url,
            headers=HEADERS,
            timeout=5
        )

        data = res.json()
        print("MARKET DATA:", code, data)
        return {
            "change_rate": to_float(data.get("fluctuationsRatio")),
            "volume": to_int(data.get("accumulatedTradingVolume")),
            "trading_value": to_int(data.get("accumulatedTradingValue")),
        }

    except:
        return {
            "change_rate": None,
            "volume": None,
            "trading_value": None,
        }


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
        "trading_value": value
    }
