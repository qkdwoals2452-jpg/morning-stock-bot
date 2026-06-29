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
        # 1) 기본정보: 등락률
        basic_url = f"https://m.stock.naver.com/api/stock/{code}/basic"

        basic_res = requests.get(
            basic_url,
            headers=HEADERS,
            timeout=5
        )

        basic = basic_res.json()

        change_rate = to_float(
            basic.get("fluctuationsRatio")
        )

        # 2) 차트 API: 거래량
        chart_url = f"https://api.stock.naver.com/chart/domestic/item/{code}/day?periodType=dayCandle"

        chart_res = requests.get(
            chart_url,
            headers=HEADERS,
            timeout=5
        )

        chart_data = chart_res.json()

        volume = None
        close_price = None

        if isinstance(chart_data, list) and len(chart_data) > 0:
            latest = chart_data[0]

            volume = to_int(
                latest.get("accumulatedTradingVolume")
            )

            close_price = to_float(
                latest.get("closePrice")
            )

        trading_value = None

        if volume is not None and close_price is not None:
            trading_value = int(volume * close_price)

        print(
            "MARKET VALUE:",
            code,
            "change:",
            change_rate,
            "volume:",
            volume,
            "trading_value:",
            trading_value
        )

        return {
            "change_rate": change_rate,
            "volume": volume,
            "trading_value": trading_value
        }

    except Exception as e:
        print("MARKET ERROR:", code, e)

        return {
            "change_rate": None,
            "volume": None,
            "trading_value": None
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
