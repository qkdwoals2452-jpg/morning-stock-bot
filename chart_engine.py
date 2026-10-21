import requests
import math
from datetime import datetime, date, timedelta, time
from zoneinfo import ZoneInfo

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def to_float(value):
    try:
        return float(str(value).replace(",", "").replace("%", ""))
    except:
        return None


def _positive_price(value):
    number = to_float(value)
    if isinstance(value, bool) or number is None or not math.isfinite(number) or number <= 0:
        raise ValueError("유효하지 않은 가격")
    return number


def _normalize_price_history(data, start, cutoff, source, max_rows=260, allow_missing_close=False):
    """완료된 거래일을 정렬하고 날짜/가격이 모호한 응답은 사용하지 않는다."""
    raw = (data.get("priceInfos") or data.get("data") or []) if isinstance(data, dict) else data
    if not isinstance(raw, list):
        raise ValueError("일별 차트 응답 형식 오류")
    grouped = {}
    for row in raw:
        if not isinstance(row, dict):
            raise ValueError("일별 차트 행 형식 오류")
        stamp = row.get("localDate")
        if not isinstance(stamp, str) or len(stamp) != 8 or not stamp.isdigit():
            raise ValueError("거래일 확인불가")
        day = datetime.strptime(stamp, "%Y%m%d").date()
        if not start <= day <= cutoff:
            continue
        grouped.setdefault(day, []).append(row)
    by_date = {}
    # 계산에서 사용하지 않는 오래된 행의 결측으로 최신 260일을 버리지 않는다.
    days = sorted(grouped)
    if max_rows is not None:
        days = days[-max_rows:]
    selected = [(day, row) for day in days for row in grouped[day]]
    for day, row in selected:
        try:
            close = _positive_price(row.get("closePrice", row.get("close", row.get("endPrice"))))
        except ValueError:
            if not allow_missing_close:
                raise
            close = None
        high_value = row.get("highPrice", row.get("high"))
        low_value = row.get("lowPrice", row.get("low"))
        def optional_price(value):
            try:
                return _positive_price(value)
            except ValueError:
                return None
        high = optional_price(high_value)
        low = optional_price(low_value)
        # 종가는 이동평균에 사용하되 모순된 고가로 52주 낙폭을 만들지 않는다.
        if high is not None and close is not None and high < close:
            high = None
        if low is not None and close is not None and low > close:
            low = None
        volume_value = row.get("accumulatedTradingVolume", row.get("volume"))
        volume = to_float(volume_value)
        if volume_value is not None and (isinstance(volume_value, bool) or volume is None
                                         or not math.isfinite(volume) or volume < 0):
            volume = None
        item = {"date": day.isoformat(), "close": close, "high": high,
                "low": low, "volume": volume, "source": source}
        if day in by_date and by_date[day] != item:
            raise ValueError("동일 거래일 차트 값 충돌")
        by_date[day] = item
    return [by_date[day] for day in sorted(by_date)]


def _regular_session_rows(payload, symbol):
    """시간외 가격이 포함될 수 있는 기본 시세 대신 정규장 일봉만 사용한다."""
    data = payload["chart"]["result"][0]
    meta = data["meta"]
    if (meta.get("symbol") != symbol or meta.get("currency") != "KRW"
            or meta.get("exchangeTimezoneName") != "Asia/Seoul"
            or meta.get("dataGranularity") != "1d"):
        raise ValueError("정규장 일봉 종목/통화/시간대 확인불가")
    stamps = data["timestamp"]
    quote = data["indicators"]["quote"][0]
    fields = ("close", "high", "low", "volume")
    if not isinstance(stamps, list) or any(
        not isinstance(quote.get(field), list) or len(quote[field]) != len(stamps)
        for field in fields
    ):
        raise ValueError("일봉 날짜와 가격 개수 불일치")
    rows = []
    for index, stamp in enumerate(stamps):
        if isinstance(stamp, bool) or not isinstance(stamp, (int, float)) or not math.isfinite(stamp):
            raise ValueError("일봉 timestamp 확인불가")
        day = datetime.fromtimestamp(stamp, ZoneInfo("Asia/Seoul")).strftime("%Y%m%d")
        rows.append({"localDate": day, **{field: quote[field][index] for field in fields}})
    return rows


def get_price_history(code, now=None, *, cache=None, start_date=None, as_of=None,
                      max_rows=260, allow_missing_close=False):
    if not isinstance(code, str) or len(code) != 6 or not code.isdigit() or code == "000000":
        print("CHART ERROR:", "유효하지 않은 종목코드")
        return []
    now = now or datetime.now(ZoneInfo("Asia/Seoul"))
    if now.tzinfo is None:
        raise ValueError("차트 기준시각에 시간대 필요")
    now = now.astimezone(ZoneInfo("Asia/Seoul"))
    end = now.date()
    start = end - timedelta(days=400)
    cutoff = end if now.time() >= time(15, 30) else end - timedelta(days=1)
    if as_of is not None:
        cutoff = min(cutoff, date.fromisoformat(as_of))
    if start_date is not None:
        start = date.fromisoformat(start_date) - timedelta(days=14)
    key = (code, start.isoformat(), cutoff.isoformat(), max_rows, allow_missing_close)
    if cache is not None and key in cache:
        return cache[key]
    params = {
        "period1": int(datetime.combine(start, time.min, ZoneInfo("Asia/Seoul")).timestamp()),
        "period2": int(datetime.combine(cutoff + timedelta(days=1), time.min,
                                        ZoneInfo("Asia/Seoul")).timestamp()),
        "interval": "1d", "includePrePost": "false",
    }
    source = "YAHOO_REGULAR_CLOSE"
    # 응답의 symbol을 확인하므로 KOSPI/KOSDAQ을 잘못 매핑하지 않는다.
    # 정규장 기준을 확인할 수 없는 NAVER 통합/시간외 가격으로 대체하지 않는다.
    for suffix in (".KS", ".KQ"):
        symbol = code + suffix
        try:
            res = requests.get(
                "https://query1.finance.yahoo.com/v8/finance/chart/" + symbol,
                params=params,
                headers=HEADERS,
                timeout=7
            )

            res.raise_for_status()
            raw = _regular_session_rows(res.json(), symbol)
            prices = _normalize_price_history(raw, start, cutoff, source,
                                              max_rows, allow_missing_close)
            print("CHART COUNT:", code, len(prices), "source:", source)

            if prices:
                print("CHART SNAPSHOT:", code, "date:", prices[-1]["date"],
                      "close:", prices[-1]["close"], "source:", source,
                      "symbol:", symbol, "cutoff:", cutoff.isoformat())
                if any(item["high"] is None for item in prices):
                    print("CHART QUALITY:", code, "고가 결측/불일치: 52주 고점 판정 보류")
                if cache is not None:
                    cache[key] = prices
                return prices

        except Exception as e:
            print("CHART ERROR:", code, source, type(e).__name__)

    if cache is not None:
        cache[key] = []
    return []

def moving_average(values, days):
    if len(values) < days:
        return None

    return sum(values[-days:]) / days


def pass_long_term_trend(chart):
    """120일선 데이터가 없거나 아래면 추천 제외. 등급/가산점으로 상쇄하지 않는다."""
    details = chart.get('details', {}) if isinstance(chart, dict) else {}
    if not isinstance(details, dict):
        return False, '120일선 추세 데이터 확인불가'
    values = []
    for key in ('current', 'ma120'):
        value = details.get(key)
        number = to_float(value)
        if isinstance(value, bool) or number is None or not math.isfinite(number) or number <= 0:
            return False, '120일선 추세 데이터 확인불가'
        values.append(number)
    if values[0] < values[1]:
        return False, '120일선 아래'
    return True, '120일선 이상'


def get_chart_score(stock, *, price_cache=None):
    code = stock["code"]
    name = stock.get("name", code)

    print("\n" + "=" * 50)

    print("차트 분석:", name, code)

    history = get_price_history(code, cache=price_cache)

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

    high_52w = max(highs) if highs and len(highs) == len(history) else None

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
    print("CHART RESULT:", name, code, score, memo)
    return {
        "score": score,
        "memo": ", ".join(memo),
        "details": {
            "current": current,
            "price_date": history[-1].get("date"),
            "price_source": history[-1].get("source"),
            "ma20": round(ma20, 2) if ma20 else None,
            "ma60": round(ma60, 2) if ma60 else None,
            "ma120": round(ma120, 2) if ma120 else None,
            "high_52w_gap": high_gap
        }
    }
